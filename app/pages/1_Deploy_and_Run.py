"""
Deploy & Run — full endpoint lifecycle and benchmark workflow.

idle → creating → polling → ready → benchmarking → results → (deleting) → done
Results are automatically saved to the SQLite database when the benchmark finishes.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import streamlit as st
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from benchmark.benchmark_runner import BenchmarkResults, run_benchmark
from benchmark.concurrency import run_concurrency_sweep, CONCURRENCY_LEVELS
from database.migrations import get_session_factory
from database.repository import (
    BenchmarkRepository, RunRecord, DeploymentRecord,
    PerformanceRecord, ConcurrencyRecord,
)
from orchestrator.create_endpoint import create_endpoint
from orchestrator.delete_endpoint import delete_endpoint
from orchestrator.get_status import EndpointState, EndpointStatus, check_serve_ready, get_endpoint_status
from orchestrator.nebius_client import NebiusClientError
from reports.html_report import generate_html_report
from reports.json_report import generate_json_report
from reports.markdown_report import generate_markdown_report

st.set_page_config(
    page_title="Deploy & Run · Nebius Endpoint Lab",
    page_icon="🚀",
    layout="wide",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REFRESH_INTERVAL = 2
POLL_INTERVAL    = 5

GPU_PLATFORMS: list[dict[str, Any]] = [
    {"id": "gpu-h200-sxm", "name": "NVIDIA® H200 NVLink",  "vram_gb": 141, "label": "NVIDIA H200"},
    {"id": "gpu-b200-sxm", "name": "NVIDIA® B200 NVLink",  "vram_gb": 180, "label": "NVIDIA B200"},
    {"id": "gpu-rtx6000",  "name": "NVIDIA® RTX PRO 6000", "vram_gb": 96,  "label": "NVIDIA RTX PRO 6000"},
]
_PLATFORM_BY_ID = {p["id"]: p for p in GPU_PLATFORMS}

# Nebius on-demand GPU pricing (USD per GPU per hour, as of June 2026)
# Source: https://nebius.com/prices
GPU_PRICE_PER_HOUR: dict[str, float] = {
    "gpu-h200-sxm": 2.45,
    "gpu-b200-sxm": 3.95,
    "gpu-rtx6000":  0.95,
}
# Typical end-to-end benchmark session duration in hours
# (create ~1 min + model load ~8 min + benchmark ~3 min + delete ~1 min)
_ESTIMATED_SESSION_HOURS = 13 / 60


# ── DB helpers ─────────────────────────────────────────────────────────────────

@st.cache_resource
def _session_factory():
    return get_session_factory()


def _save_run(results: BenchmarkResults) -> str | None:
    """Save a completed benchmark run to the DB.  Returns run_id or None on error."""
    try:
        cfg = st.session_state.get("model_config") or {}
        run_id = st.session_state.get("current_run_id", "unknown")
        conc_job = st.session_state.get("conc_job") or {}
        conc_results: list[ConcurrencyRecord] = []
        for lvl in (conc_job.get("result") or {}).get("levels", []):
            conc_results.append(ConcurrencyRecord(
                concurrency_level=lvl.concurrency,
                requests_per_second=lvl.requests_per_second,
                latency_p95_ms=lvl.latency_p95_ms,
                latency_mean_ms=lvl.latency_mean_ms,
                success_rate=lvl.success_rate,
                total_tokens=lvl.total_tokens,
                duration_s=lvl.duration_s,
            ))
        record = RunRecord(
            run_id=run_id,
            model_id=cfg.get("model_id", cfg.get("id", "unknown")),
            model_display_name=cfg.get("display_name", ""),
            endpoint_id=st.session_state.get("endpoint_id"),
            platform=st.session_state.get("selected_platform") or cfg.get("platform"),
            preset=cfg.get("preset"),
            deployment=DeploymentRecord(
                endpoint_creation_time_s=st.session_state.get("creation_duration"),
                time_to_ready_s=st.session_state.get("time_to_ready"),
                deletion_time_s=(st.session_state.get("deletion_result") or None)
                    and st.session_state["deletion_result"].deletion_duration_seconds,
            ),
            performance=PerformanceRecord(
                ttft_ms=results.ttft.ttft_ms if results.ttft.success else None,
                itl_mean_ms=results.itl.mean_itl_ms if results.itl.success else None,
                itl_p50_ms=results.itl.p50_itl_ms if results.itl.success else None,
                itl_p90_ms=results.itl.p90_itl_ms if results.itl.success else None,
                itl_p99_ms=results.itl.p99_itl_ms if results.itl.success else None,
                itl_tokens_per_second=results.itl.tokens_per_second if results.itl.success else None,
                latency_ms=results.latency.latency_ms if results.latency.success else None,
                latency_tokens_per_second=results.latency.tokens_per_second if results.latency.success else None,
                lat_p50_ms=results.percentiles.p50_ms if results.percentiles.success else None,
                lat_p90_ms=results.percentiles.p90_ms if results.percentiles.success else None,
                lat_p99_ms=results.percentiles.p99_ms if results.percentiles.success else None,
                lat_mean_ms=results.percentiles.mean_ms if results.percentiles.success else None,
                lat_std_ms=results.percentiles.std_ms if results.percentiles.success else None,
                requests_per_second=results.throughput.requests_per_second,
                throughput_tokens_per_second=results.throughput.tokens_per_second,
                total_output_tokens=results.throughput.total_output_tokens,
                success_rate=results.throughput.success_rate,
                total_requests=results.throughput.total_requests,
                failed_requests=results.throughput.failed_requests,
            ),
            concurrency=conc_results,
        )
        factory = _session_factory()
        with factory() as sess:
            BenchmarkRepository(sess).save_run(record)
        return run_id
    except Exception as exc:
        logger.error("Failed to save run: %s", exc)
        return None


def _patch_deletion_time(deletion_s: float) -> None:
    run_id = st.session_state.get("current_run_id")
    if not run_id:
        return
    try:
        factory = _session_factory()
        with factory() as sess:
            BenchmarkRepository(sess).update_deletion_time(run_id, deletion_s)
    except Exception as exc:
        logger.warning("Could not patch deletion time: %s", exc)


# ── helpers ────────────────────────────────────────────────────────────────────

def _parse_disk_gi(disk_size: str) -> int:
    s = disk_size.strip()
    if s.endswith("Ti"):
        return int(float(s[:-2]) * 1024)
    if s.endswith("Gi"):
        return int(s[:-2])
    return 120


def _load_models() -> list[dict[str, Any]]:
    with open(ROOT / "config" / "models.yaml") as fh:
        return yaml.safe_load(fh)["models"]


def _state_badge(state_str: str | None) -> str:
    icons = {
        "RUNNING": "🟢 RUNNING", "FAILED": "🔴 FAILED",
        "CREATING": "🟡 CREATING", "PROVISIONING": "🟡 PROVISIONING",
        "STARTING": "🟡 STARTING", "STOPPING": "🟠 STOPPING",
        "STOPPED": "⚫ STOPPED",
    }
    return icons.get(state_str or "", f"⚪ {state_str or '—'}")


def _elapsed(start: float | None) -> str:
    return "—" if start is None else f"{time.time() - start:.0f}s"


def _init_session() -> None:
    defaults: dict[str, Any] = {
        "workflow": "idle", "model_config": None,
        "endpoint_id": None, "endpoint_url": None, "auth_token": None,
        "op_start": None, "creation_duration": None, "time_to_ready": None,
        "deletion_result": None, "error_message": None, "selected_platform": None,
        "selected_engine": "vllm",
        "current_run_id": None, "run_saved": False,
        "create_job": None, "poll_job": None, "warmup_job": None,
        "bench_job": None, "delete_job": None, "conc_job": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── background workers ──────────────────────────────────────────────────────────

def _spawn_create(
    cfg: dict[str, Any],
    hf_token: str | None = None,
    platform_override: str | None = None,
    engine: str = "vllm",
    gpu_count_override: int | None = None,
    disk_size_override: str | None = None,
    image_tag: str = "latest",
    quantization: str | None = None,
    dtype: str = "auto",
    gpu_memory_utilization: float = 0.90,
    enable_prefix_caching: bool = False,
    max_num_seqs: int | None = None,
    mem_fraction_static: float = 0.88,
    disable_radix_cache: bool = False,
    max_running_requests: int | None = None,
    attention_backend: str = "flashinfer",
) -> None:
    job: dict[str, Any] = {"done": False, "result": None, "error": None}
    st.session_state.create_job        = job
    st.session_state.op_start          = time.time()
    st.session_state.selected_platform = platform_override or cfg["platform"]
    st.session_state.selected_engine   = engine
    effective_platform  = platform_override or cfg["platform"]
    effective_gpu_count = gpu_count_override if gpu_count_override is not None else cfg.get("gpu_count", 1)
    effective_disk_size = disk_size_override or cfg.get("disk_size", "250Gi")

    def _run() -> None:
        try:
            result = create_endpoint(
                model_id=cfg["model_id"], image=cfg["image"],
                platform=effective_platform,
                gpu_count=effective_gpu_count,
                served_model_name=cfg["served_model_name"],
                max_model_len=cfg.get("max_model_len", 4096),
                disk_size=effective_disk_size,
                hf_token=hf_token or None,
                engine=engine,
                image_tag=image_tag,
                quantization=quantization if quantization != "none" else None,
                dtype=dtype,
                gpu_memory_utilization=gpu_memory_utilization,
                enable_prefix_caching=enable_prefix_caching,
                max_num_seqs=max_num_seqs if max_num_seqs and max_num_seqs > 0 else None,
                mem_fraction_static=mem_fraction_static,
                disable_radix_cache=disable_radix_cache,
                max_running_requests=max_running_requests if max_running_requests and max_running_requests > 0 else None,
                attention_backend=attention_backend,
            )
            job["result"] = result
        except Exception as exc:
            job["error"] = str(exc)
        finally:
            job["done"] = True
    threading.Thread(target=_run, daemon=True).start()


def _spawn_poll(endpoint_id: str) -> None:
    job: dict[str, Any] = {"done": False, "status": None, "url": None, "auth_token": None, "error": None}
    st.session_state.poll_job  = job
    st.session_state.op_start  = time.time()
    st.session_state.workflow  = "polling"

    def _run() -> None:
        consecutive = 0
        while not job["done"]:
            try:
                status = get_endpoint_status(endpoint_id)
                consecutive = 0
                job["status"] = status
                job["url"]    = status.url
                job["auth_token"] = status.auth_token
                if status.state.is_terminal_ok:
                    job["done"] = True
                elif status.state.is_terminal_fail:
                    job["error"] = status.error or "Endpoint FAILED"
                    job["done"]  = True
            except NebiusClientError as exc:
                consecutive += 1
                if consecutive >= 10:
                    job["error"] = str(exc); job["done"] = True
            if not job["done"]:
                time.sleep(POLL_INTERVAL)
    threading.Thread(target=_run, daemon=True).start()


def _spawn_benchmark(endpoint_url: str, auth_token: str | None, cfg: dict[str, Any]) -> None:
    import uuid
    run_id = str(uuid.uuid4())[:8]
    job: dict[str, Any] = {"done": False, "result": None, "error": None, "phase": "Starting…"}
    st.session_state.bench_job       = job
    st.session_state.op_start        = time.time()
    st.session_state.workflow        = "benchmarking"
    st.session_state.current_run_id  = run_id
    st.session_state.run_saved       = False

    def _run() -> None:
        try:
            result = run_benchmark(
                endpoint_url=endpoint_url, model=cfg["served_model_name"],
                max_tokens=cfg.get("max_tokens", 512), auth_token=auth_token,
                on_progress=lambda msg: job.update({"phase": msg}),
            )
            job["result"] = result
        except Exception as exc:
            job["error"] = str(exc)
        finally:
            job["done"] = True
    threading.Thread(target=_run, daemon=True).start()


def _spawn_concurrency(endpoint_url: str, auth_token: str | None, cfg: dict[str, Any]) -> None:
    job: dict[str, Any] = {"done": False, "result": None, "error": None, "phase": "Starting…"}
    st.session_state.conc_job = job

    api_key  = auth_token or os.getenv("NEBIUS_API_KEY") or "dummy"
    base_url = endpoint_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=120.0)
    model  = cfg["served_model_name"]

    def _run() -> None:
        try:
            result = run_concurrency_sweep(
                client=client, model=model, max_tokens=64,
                on_progress=lambda msg: job.update({"phase": msg}),
            )
            job["result"] = result
        except Exception as exc:
            job["error"] = str(exc)
        finally:
            job["done"] = True
    threading.Thread(target=_run, daemon=True).start()


def _spawn_delete(endpoint_id: str) -> None:
    job: dict[str, Any] = {"done": False, "result": None, "error": None}
    st.session_state.delete_job = job
    st.session_state.op_start   = time.time()
    st.session_state.workflow   = "deleting"

    def _run() -> None:
        try:
            result = delete_endpoint(endpoint_id)
            job["result"] = result
        except Exception as exc:
            job["error"] = str(exc)
        finally:
            job["done"] = True
    threading.Thread(target=_run, daemon=True).start()


# ── UI components ──────────────────────────────────────────────────────────────

def _status_card() -> None:
    cfg   = st.session_state.model_config or {}
    poll  = st.session_state.poll_job or {}
    status: EndpointStatus | None = poll.get("status")
    eid   = st.session_state.endpoint_id or "—"
    short = eid[-14:] if len(eid) > 14 else eid
    state_str = status.state.value if status else (
        "CREATING" if st.session_state.workflow == "creating" else "—"
    )
    platform_id = st.session_state.selected_platform or cfg.get("platform", "—")
    pi = _PLATFORM_BY_ID.get(platform_id, {})
    platform_display = f"{pi.get('name', platform_id)} ({pi.get('vram_gb', '?')} GB)" if pi else platform_id
    engine = st.session_state.get("selected_engine", "vllm")
    engine_display = {"vllm": "vLLM", "sglang": "SGLang"}.get(engine, engine)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Endpoint ID",  short, help=eid)
    c2.metric("Model",        cfg.get("display_name", "—"))
    c3.metric("Engine",       engine_display)
    c4.metric("GPU Platform", platform_display)
    c5.metric("Status",       _state_badge(state_str))
    c6.metric("Elapsed",      _elapsed(st.session_state.op_start))


def _results_dashboard(results: BenchmarkResults) -> None:
    import plotly.graph_objects as go

    st.markdown("**Lifecycle**")
    lc1, lc2 = st.columns(2)
    lc1.metric("Endpoint Creation", f"{st.session_state.creation_duration or 0:.0f}s")
    lc2.metric("Time → Ready",      f"{st.session_state.time_to_ready or 0:.0f}s")
    st.divider()

    st.markdown("**Responsiveness**")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("TTFT",             f"{results.ttft.ttft_ms:.0f}ms" if results.ttft.success else "N/A",
              help="Time to first token (streaming)")
    r2.metric("ITL Mean",         f"{results.itl.mean_itl_ms:.1f}ms" if results.itl.success else "N/A")
    r3.metric("ITL p90",          f"{results.itl.p90_itl_ms:.1f}ms" if results.itl.success else "N/A")
    r4.metric("Token Gen Speed",  f"{results.itl.tokens_per_second:.1f} tok/s" if results.itl.success else "N/A")
    st.divider()

    st.markdown("**Latency Distribution**  *(20-sample E2E)*")
    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("p50",  f"{results.percentiles.p50_ms:.0f}ms")
    p2.metric("p90",  f"{results.percentiles.p90_ms:.0f}ms")
    p3.metric("p99",  f"{results.percentiles.p99_ms:.0f}ms")
    p4.metric("Mean", f"{results.percentiles.mean_ms:.0f}ms")
    p5.metric("Std",  f"{results.percentiles.std_ms:.0f}ms")
    st.divider()

    st.markdown("**Throughput**  *(10 concurrent requests)*")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Requests/sec",     f"{results.throughput.requests_per_second:.2f} rps")
    t2.metric("Token Throughput", f"{results.throughput.tokens_per_second:.1f} tok/s")
    t3.metric("Success Rate",     f"{results.throughput.success_rate * 100:.0f}%",
              delta=f"{results.throughput.failed_requests} failed" if results.throughput.failed_requests else None,
              delta_color="inverse")
    t4.metric("Output Tokens",    str(results.throughput.total_output_tokens))
    st.divider()

    ch1, ch2 = st.columns(2)
    with ch1:
        pct = results.percentiles
        fig = go.Figure(go.Bar(
            x=["p50", "p90", "p99", "Mean"],
            y=[pct.p50_ms, pct.p90_ms, pct.p99_ms, pct.mean_ms],
            marker_color=["#636EFA", "#EF553B", "#FF6692", "#AB63FA"],
            text=[f"{v:.0f}ms" for v in [pct.p50_ms, pct.p90_ms, pct.p99_ms, pct.mean_ms]],
            textposition="outside",
        ))
        fig.update_layout(title="Latency Percentiles", yaxis_title="ms", height=300,
                          margin={"t":50,"b":20}, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        if results.itl.raw_gaps_ms:
            fig2 = go.Figure(go.Histogram(x=results.itl.raw_gaps_ms, nbinsx=20, marker_color="#00CC96"))
            fig2.add_vline(x=results.itl.mean_itl_ms, line_dash="dash", line_color="#EF553B",
                           annotation_text="mean")
            fig2.update_layout(title="ITL Distribution", xaxis_title="ms", yaxis_title="count",
                               height=300, margin={"t":50,"b":20},
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)


def _download_buttons(results: BenchmarkResults, conc_data: list | None = None) -> None:
    cfg = st.session_state.model_config or {}
    dr = st.session_state.deletion_result
    deletion_s = dr.deletion_duration_seconds if dr else None
    ts = int(time.time())
    model_id = cfg.get("id", "unknown")

    json_str = generate_json_report(model_id, results,
        st.session_state.creation_duration or 0, st.session_state.time_to_ready or 0, deletion_s)
    md_str   = generate_markdown_report(model_id, results,
        st.session_state.creation_duration or 0, st.session_state.time_to_ready or 0, deletion_s)
    html_str = generate_html_report(model_id, results,
        st.session_state.creation_duration or 0, st.session_state.time_to_ready or 0, deletion_s,
        concurrency_data=conc_data)

    d1, d2, d3 = st.columns(3)
    d1.download_button("📥 JSON",     json_str, f"bench_{model_id}_{ts}.json", "application/json", use_container_width=True)
    d2.download_button("📥 Markdown", md_str,   f"bench_{model_id}_{ts}.md",   "text/markdown",    use_container_width=True)
    d3.download_button("📥 HTML",     html_str, f"bench_{model_id}_{ts}.html", "text/html",        use_container_width=True)


# ── section renderers ──────────────────────────────────────────────────────────

def _hf_size_to_disk(size_bytes: int | None) -> str:
    """Estimate disk size from safetensors total bytes, with 30% headroom."""
    if not size_bytes:
        return "250Gi"
    gb = size_bytes / 1_073_741_824  # bytes → GiB
    padded = gb * 1.3
    if padded <= 120:
        return "120Gi"
    if padded <= 200:
        return f"{int(padded // 10 * 10 + 10)}Gi"
    if padded <= 500:
        return f"{int(padded // 50 * 50 + 50)}Gi"
    if padded <= 1024:
        return "1Ti"
    return "2Ti"


def _hf_model_to_cfg(model: Any) -> dict[str, Any]:
    """Convert a HuggingFace ModelInfo object into a model config dict."""
    model_id: str = model.id
    name = model_id.split("/")[-1]
    size_bytes: int | None = None
    if hasattr(model, "safetensors") and model.safetensors:
        st_info = model.safetensors
        if hasattr(st_info, "total"):
            # total is parameter count; BF16 = 2 bytes/param
            size_bytes = st_info.total * 2

    disk_size = _hf_size_to_disk(size_bytes)
    size_gi = _parse_disk_gi(disk_size)
    gpu_count = 8 if size_gi >= 280 else 1

    params_b = (size_bytes / 2 / 1e9) if size_bytes else None
    if params_b:
        if params_b < 10:
            category = "Tiny / Fast"
        elif params_b < 50:
            category = "Balanced"
        elif params_b < 100:
            category = "Large"
        else:
            category = "Frontier"
    else:
        category = "Balanced"

    is_gated = bool(model.gated) if hasattr(model, "gated") and model.gated else False

    downloads = getattr(model, "downloads", 0) or 0
    likes     = getattr(model, "likes", 0) or 0

    return {
        "id": model_id.lower().replace("/", "-").replace(".", "-"),
        "display_name": name,
        "category": category,
        "description": (
            f"HuggingFace · {model_id}"
            + (f" · {params_b:.1f}B params" if params_b else "")
            + f" · {downloads:,} downloads · {likes:,} likes"
        ),
        "image": "vllm/vllm-openai:latest",
        "model_id": model_id,
        "served_model_name": name,
        "platform": "gpu-h200-sxm",
        "gpu_count": gpu_count,
        "max_model_len": 4096,
        "max_tokens": 512,
        "disk_size": disk_size,
        "gated": is_gated,
    }


@st.cache_data(ttl=120, show_spinner=False)
def _search_hf_models(query: str, limit: int = 30) -> list[dict[str, Any]]:
    """Search HuggingFace for text-generation models; returns list of config dicts."""
    from huggingface_hub import list_models
    results = list(list_models(
        search=query,
        pipeline_tag="text-generation",
        sort="downloads",
        limit=limit,
        expand=["safetensors", "downloads", "likes", "gated"],
    ))
    return [_hf_model_to_cfg(m) for m in results]


def _pick_from_catalogue(models: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_name = {m["display_name"]: m for m in models}
    categories: dict[str, list[str]] = {}
    for m in models:
        categories.setdefault(m.get("category", "Other"), []).append(m["display_name"])

    cat_labels = {
        "Tiny / Fast": "── Tiny / Fast  (1 × GPU) ──",
        "Balanced":    "── Balanced  (1 × GPU, ≤64 GB VRAM) ──",
        "Large":       "── Large  (8 × GPU required) ──",
        "Frontier":    "── Frontier  (8 × GPU required) ──",
    }
    options: list[str] = []
    separators: set[str] = set()
    for cat, names in categories.items():
        sep = cat_labels.get(cat, f"── {cat} ──")
        options.append(sep); separators.add(sep); options.extend(names)

    selected = st.selectbox(
        "Select Model",
        options,
        help=(
            "Choose a model from the curated catalogue.\n\n"
            "**Tiny / Fast** — 1–8B params, 1× GPU, fastest cold-start and lowest cost.\n\n"
            "**Balanced** — 10–50B params, 1× GPU on H200/B200 (≥141 GB VRAM).\n\n"
            "**Large** — 65–75B params, requires 8× GPU (weights exceed single-GPU headroom).\n\n"
            "**Frontier** — MoE or 100B+ models, requires 8× GPU.\n\n"
            "🔒 Models marked gated require a HuggingFace token and license acceptance. "
            "See the **Models** page in the sidebar for step-by-step instructions.\n\n"
            "Selecting a model pre-fills GPU preset, disk size, and platform with recommended defaults — "
            "you can override all of them below."
        ),
    )
    if selected in separators:
        selected = next(n for n in options if n not in separators)
    cfg = by_name.get(selected)
    if cfg:
        st.caption(f"{cfg.get('description','')}  |  default {cfg.get('gpu_count',1)}× GPU · disk: {cfg.get('disk_size','—')}")
    return cfg


def _pick_from_hf() -> dict[str, Any] | None:
    c1, c2 = st.columns([4, 1])
    query = c1.text_input(
        "Search HuggingFace",
        placeholder="e.g. llama, qwen, mistral, deepseek…",
        label_visibility="collapsed",
        key="hf_query_input",
        help=(
            "Search the HuggingFace Hub for text-generation models.\n\n"
            "Returns the top 30 results sorted by all-time downloads.\n\n"
            "Filters automatically to `pipeline_tag=text-generation` so only LLMs appear.\n\n"
            "Results include model size (from safetensors), download count, and gated status — "
            "used to auto-fill disk size, GPU preset, and the token requirement below."
        ),
    )
    search_clicked = c2.button("Search", type="primary", use_container_width=True)

    if "hf_search_results" not in st.session_state:
        st.session_state.hf_search_results = []
    if "hf_search_query_last" not in st.session_state:
        st.session_state.hf_search_query_last = ""

    if search_clicked and query.strip():
        with st.spinner(f'Searching HuggingFace for "{query}"…'):
            st.session_state.hf_search_results = _search_hf_models(query.strip())
            st.session_state.hf_search_query_last = query.strip()

    results: list[dict[str, Any]] = st.session_state.hf_search_results
    if not results:
        st.caption("Returns top-30 text-generation models sorted by downloads.")
        return None

    st.caption(f'{len(results)} models for "{st.session_state.hf_search_query_last}" · sorted by downloads')
    idx = st.selectbox(
        "HF Model",
        range(len(results)),
        format_func=lambda i: results[i]["model_id"],
        label_visibility="collapsed",
        help=(
            "Select a model from the search results.\n\n"
            "Selecting a model automatically sets:\n"
            "- **Disk size** — estimated from safetensors byte count + 30% headroom\n"
            "- **GPU preset** — 1 GPU for models under ~200 GiB, 8 GPUs for larger\n"
            "- **Gated** — whether a HuggingFace token is required\n\n"
            "You can override disk size and GPU preset in the sections below."
        ),
    )
    cfg = results[idx]
    st.caption(cfg.get("description", ""))
    if cfg.get("gated"):
        st.info("🔒 Gated model — HuggingFace token with license acceptance required.")
    return cfg


def _section_idle(models: list[dict[str, Any]]) -> None:
    source = st.radio(
        "Model source",
        ["📋 Catalogue", "🤗 HuggingFace Search"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.divider()

    if source == "📋 Catalogue":
        cfg = _pick_from_catalogue(models)
    else:
        cfg = _pick_from_hf()
        if cfg is None:
            return  # no search done yet — don't render the rest

    if cfg is None:
        return

    # ── HuggingFace token (gated models only) ─────────────────────────────────
    is_gated = bool(cfg.get("gated", False))
    hf = os.getenv("HUGGING_FACE_HUB_TOKEN", "")
    if is_gated:
        st.divider()
        hf = st.text_input(
            "🔑 HuggingFace Token",
            value=os.getenv("HUGGING_FACE_HUB_TOKEN", ""),
            type="password",
            placeholder="hf_xxxx…",
            help=(
                "Required for this gated model.\n\n"
                "Your HuggingFace access token (starts with `hf_`).\n\n"
                "You must also have accepted the model's license on HuggingFace before deploying. "
                "Go to the model page on HuggingFace → click **Agree and access repository**.\n\n"
                "**How to get a token:** huggingface.co/settings/tokens → New token → Read role.\n\n"
                "**Persistent setup:** add `HUGGING_FACE_HUB_TOKEN=hf_xxx` to your `.env` file "
                "and this field pre-fills automatically.\n\n"
                "See the **Models** page for full step-by-step instructions."
            ),
        )
        if not hf.strip():
            st.warning(
                "🔒 This model requires a HuggingFace token and license acceptance. "
                "The **Create Endpoint** button will remain disabled until a token is provided. "
                "See the [Models page](pages/0_Models.py) for setup instructions.",
            )

    st.divider()
    col_platform, col_preset, col_disk = st.columns(3)

    with col_platform:
        default_idx = next((i for i, p in enumerate(GPU_PLATFORMS) if p["id"] == (cfg or {}).get("platform", "gpu-h200-sxm")), 0)
        platform_labels = [p["label"] for p in GPU_PLATFORMS]
        choice = st.radio(
            "GPU Platform",
            platform_labels,
            index=default_idx,
            help=(
                "The GPU hardware your endpoint runs on.\n\n"
                "**NVIDIA H200 · 141 GB VRAM · $2.45/GPU/hr** *(recommended)*\n"
                "Best price/performance ratio. Supports all model sizes in the catalogue. "
                "H200 SXM uses NVLink for fast multi-GPU communication.\n\n"
                "**NVIDIA B200 · 180 GB VRAM · $3.95/GPU/hr** *(highest memory)*\n"
                "Newest Blackwell architecture. Extra headroom for very large models or "
                "workloads needing maximum KV cache. Higher cost than H200.\n\n"
                "**NVIDIA RTX PRO 6000 · 96 GB VRAM · $0.95/GPU/hr** *(budget)*\n"
                "Most affordable option. Suitable for small models (≤30B params). "
                "⚠️ SGLang's kernels target H100/A100 — use vLLM on this platform.\n\n"
                "Changing the platform updates the VRAM warning and cost estimate below."
            ),
        )
        sel_platform = GPU_PLATFORMS[platform_labels.index(choice)]

    with col_preset:
        default_gpu_count = (cfg or {}).get("gpu_count", 1)
        gpu_preset_labels = ["1 GPU", "8 GPUs"]
        gpu_preset_values = [1, 8]
        default_preset_idx = 1 if default_gpu_count == 8 else 0
        preset_choice = st.radio(
            "GPU Preset",
            gpu_preset_labels,
            index=default_preset_idx,
            help=(
                "Number of GPUs allocated to the endpoint.\n\n"
                "**1 GPU** — sufficient for models up to ~64 GB in BF16 (≤32B params on H200). "
                "Faster cold-start, lower cost.\n\n"
                "**8 GPUs** — required for 70B+ models whose weights exceed single-GPU VRAM. "
                "Nebius only offers 1 or 8 GPU presets — there are no 2- or 4-GPU options.\n\n"
                "The model's recommended preset is pre-selected automatically. "
                "A VRAM warning appears below if your choice is insufficient for the selected model.\n\n"
                "Cost scales linearly: 8 GPUs = 8× the hourly rate."
            ),
        )
        selected_gpu_count = gpu_preset_values[gpu_preset_labels.index(preset_choice)]

    from orchestrator.create_endpoint import resolve_preset
    total_vram = sel_platform["vram_gb"] * selected_gpu_count
    vram_needs = {"Tiny / Fast": 16, "Balanced": 64, "Large": 144, "Frontier": 300}.get(
        (cfg or {}).get("category", ""), 0
    )
    if cfg and vram_needs > total_vram:
        st.warning(
            f"⚠️ **{sel_platform['name']}** × {selected_gpu_count} = {total_vram} GB total VRAM, "
            f"but **{cfg['display_name']}** needs ~{vram_needs} GB. "
            f"Consider more GPUs or H200 / B200."
        )
    price_per_gpu = GPU_PRICE_PER_HOUR.get(sel_platform["id"], 0.0)
    hourly_total  = price_per_gpu * selected_gpu_count
    session_cost  = hourly_total * _ESTIMATED_SESSION_HOURS
    try:
        preset_preview = resolve_preset(selected_gpu_count, sel_platform["id"])
        st.caption(f"Preset: `{preset_preview}` — {selected_gpu_count} × {sel_platform['name']} · {total_vram} GB VRAM")
        st.caption(f"💰 ${hourly_total:.2f} / hr · ~${session_cost:.2f} / session · [nebius.com/prices](https://nebius.com/prices)")
    except ValueError as exc:
        st.error(str(exc))

    with col_disk:
        default_disk_gi = max(120, _parse_disk_gi((cfg or {}).get("disk_size", "120Gi")))
        disk_gi = st.number_input(
            "Disk Size (Gi)",
            min_value=120,
            value=default_disk_gi,
            step=10,
            help=(
                "Persistent disk attached to the endpoint VM. Holds the model weights downloaded from HuggingFace.\n\n"
                "**Minimum: 120 Gi** (Nebius platform floor).\n\n"
                "**Rough guide by model size:**\n"
                "- ≤10B params → 120 Gi\n"
                "- 10–30B params → 150–200 Gi\n"
                "- 30–75B params → 200–300 Gi\n"
                "- 70B+ / large MoE → 300–500 Gi\n"
                "- Frontier MoE (235B, 671B) → 1 Ti\n\n"
                "The model's recommended size is pre-filled. "
                "If you pick a smaller disk than needed, the endpoint will fail during model download. "
                "Slightly oversizing is safe and cheap."
            ),
        )
        disk_size_str = f"{int(disk_gi)}Gi"
        st.caption(f"Disk: `{disk_size_str}`")

    st.divider()
    ENGINE_OPTIONS = {
        "vllm":   ("vLLM",   "vllm/vllm-openai:latest",   "Battle-tested, widest model support"),
        "sglang": ("SGLang", "lmsysorg/sglang:latest",     "High-throughput RadixAttention engine"),
    }
    engine_labels = [v[0] for v in ENGINE_OPTIONS.values()]
    engine_keys   = list(ENGINE_OPTIONS.keys())
    engine_choice = st.radio(
        "Inference Engine",
        engine_labels,
        horizontal=True,
        help=(
            "The inference server running inside the endpoint container.\n\n"
            "**vLLM** — battle-tested, widest model compatibility, strong community support. "
            "Best default choice. Uses PagedAttention for efficient KV cache management.\n\n"
            "**SGLang** — optimised for high-throughput workloads via RadixAttention (prefix caching on by default). "
            "Can outperform vLLM on workloads with shared system prompts. "
            "⚠️ Unreliable on RTX 6000 — kernels target H100/A100 architecture.\n\n"
            "Both expose an OpenAI-compatible `/v1/chat/completions` and `/v1/completions` API, "
            "so benchmarks work identically regardless of which engine you pick."
        ),
    )
    selected_engine = engine_keys[engine_labels.index(engine_choice)]
    eng_image, eng_desc = ENGINE_OPTIONS[selected_engine][1], ENGINE_OPTIONS[selected_engine][2]
    st.caption(f"`{eng_image}` — {eng_desc}")
    if selected_engine == "sglang" and sel_platform["id"] == "gpu-rtx6000":
        st.warning(
            "⚠️ **SGLang + RTX 6000 is unreliable.** SGLang's kernels target H100/A100 — "
            "JIT compilation consistently fails on RTX 6000 Ada. Use **vLLM** on this platform, "
            "or switch to H200/B200 if you need SGLang."
        )

    st.divider()
    with st.expander("⚙️ Advanced Options"):
        st.caption(
            "Wrong combinations can cause the endpoint to fail after a ~10 min wait — read the warnings carefully."
        )

        # ── Shared: quantization · dtype · image tag ───────────────────────────
        sh1, sh2, sh3 = st.columns(3)
        quantization = sh1.selectbox(
            "Quantization",
            ["none", "fp8", "awq", "gptq"],
            index=0,
            help=(
                "**none** — full precision (safest).\n\n"
                "**fp8** — 8-bit float, ~50% less VRAM. Requires an FP8 checkpoint on HuggingFace.\n\n"
                "**awq** — 4-bit AWQ. Requires a pre-quantized AWQ checkpoint.\n\n"
                "**gptq** — 4-bit GPTQ. Requires a pre-quantized GPTQ checkpoint."
            ),
        )
        dtype = sh2.selectbox(
            "dtype",
            ["auto", "bfloat16", "float16"],
            index=0,
            help=(
                "**auto** — engine picks best dtype (recommended).\n\n"
                "**bfloat16** — better numerical range, preferred on H200/B200.\n\n"
                "**float16** — slightly faster on older GPUs, can overflow on large models."
            ),
        )
        image_tag = sh3.text_input(
            "Image Tag",
            value="latest",
            help=(
                "Docker image tag. Use `latest` or pin to a release like `v0.8.5`.\n\n"
                "⚠️ Must exist on Docker Hub — an invalid tag fails at pull time."
            ),
        )

        st.divider()

        # ── Engine-specific ────────────────────────────────────────────────────
        if selected_engine == "vllm":
            st.caption("**vLLM options**")
            v1, v2, v3 = st.columns(3)
            gpu_memory_utilization = v1.slider(
                "GPU Memory Utilization",
                min_value=0.50, max_value=1.00, value=0.90, step=0.01,
                help=(
                    "Fraction of VRAM for model + KV cache (default 0.90).\n\n"
                    "Higher → more KV cache → better throughput.\n\n"
                    "Lower → safer if model is close to VRAM limit.\n\n"
                    "⚠️ Above 0.95: high OOM risk. Below 0.60: very limited KV cache."
                ),
            )
            enable_prefix_caching = v2.toggle(
                "Prefix Caching",
                value=False,
                help=(
                    "Caches KV states of shared prompt prefixes across requests.\n\n"
                    "Only useful when many requests share the same system prompt. "
                    "No benefit for diverse/random prompts."
                ),
            )
            max_num_seqs = v3.number_input(
                "Max Sequences  (0 = vLLM default 256)",
                min_value=0, max_value=1024, value=0, step=8,
                help=(
                    "Max sequences the engine batches simultaneously.\n\n"
                    "Higher → better GPU utilisation under load, more memory pressure.\n\n"
                    "Lower → more predictable latency under light load."
                ),
            )
            # SGLang defaults (unused)
            mem_fraction_static  = 0.88
            disable_radix_cache  = False
            max_running_requests = 0
            attention_backend    = "flashinfer"

        else:  # sglang
            st.caption("**SGLang options**")
            s1, s2, s3, s4 = st.columns(4)
            mem_fraction_static = s1.slider(
                "Memory Fraction Static",
                min_value=0.50, max_value=1.00, value=0.88, step=0.01,
                help=(
                    "Fraction of VRAM reserved for the KV cache pool (SGLang default 0.88).\n\n"
                    "Equivalent to vLLM's gpu-memory-utilization.\n\n"
                    "⚠️ Above 0.95: OOM risk. Below 0.60: very limited KV cache."
                ),
            )
            radix_on = s2.toggle(
                "RadixAttention  (Prefix Cache)",
                value=True,
                help=(
                    "SGLang's RadixAttention reuses KV cache for shared prompt prefixes. "
                    "Enabled by default — gives big TTFT wins for repeated system prompts.\n\n"
                    "Turn off only if you're debugging or using a workload with no shared prefixes."
                ),
            )
            disable_radix_cache = not radix_on
            max_running_requests = s3.number_input(
                "Max Running Requests  (0 = default)",
                min_value=0, max_value=1024, value=0, step=8,
                help=(
                    "Max concurrent requests SGLang processes simultaneously.\n\n"
                    "Leave at 0 to use SGLang's default (based on available memory)."
                ),
            )
            _attn_options = ["flashinfer", "triton", "torch_native"]
            _attn_default = 1 if sel_platform["id"] == "gpu-rtx6000" else 0
            attention_backend = s4.selectbox(
                "Attention Backend",
                _attn_options,
                index=_attn_default,
                help=(
                    "**flashinfer** — fastest, recommended for H200/B200.\n\n"
                    "**triton** — architecture-agnostic, recommended for RTX 6000.\n\n"
                    "**torch_native** — slowest, most compatible."
                ),
            )
            # vLLM defaults (unused)
            gpu_memory_utilization = 0.90
            enable_prefix_caching  = False
            max_num_seqs           = 0

        # ── Guardrails ─────────────────────────────────────────────────────────
        if quantization in ("awq", "gptq"):
            st.warning(
                f"⚠️ **{quantization.upper()} requires a pre-quantized checkpoint.** "
                f"The model on HuggingFace must already be in {quantization.upper()} format. "
                f"Applying this to a standard FP16 checkpoint will fail."
            )
        if quantization == "fp8":
            st.warning(
                "⚠️ **FP8 requires an FP8-quantized checkpoint.** "
                "Check HuggingFace for an `-FP8` variant of your model before deploying."
            )
        mem_util = mem_fraction_static if selected_engine == "sglang" else gpu_memory_utilization
        mem_label = "mem-fraction-static" if selected_engine == "sglang" else "gpu-memory-utilization"
        if mem_util > 0.95:
            st.warning(f"⚠️ **{mem_label} {mem_util:.2f} is very high** — high OOM risk during model loading.")
        if mem_util < 0.60:
            st.warning(f"⚠️ **{mem_label} {mem_util:.2f} is very low** — KV cache will be severely limited.")
        if selected_engine == "sglang" and attention_backend == "flashinfer" and sel_platform["id"] == "gpu-rtx6000":
            st.warning(
                "⚠️ **flashinfer may not be supported on RTX 6000 Ada.** "
                "The `lmsysorg/sglang:latest` image's flashinfer build targets H100/H200. "
                "Switch to **triton** or **torch_native** to avoid a StartFailed error."
            )
        if image_tag.strip() not in ("latest", "") and not image_tag.strip().startswith("v"):
            st.info(f"ℹ️ Image tag `{image_tag.strip()}` — make sure it exists on Docker Hub.")

    disabled = is_gated and not hf.strip()
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        if st.button("🚀 Create Endpoint", type="primary", use_container_width=True, disabled=disabled):
            if cfg:
                st.session_state.model_config = cfg
                _spawn_create(
                    cfg, hf_token=hf.strip() or None,
                    platform_override=sel_platform["id"],
                    engine=selected_engine,
                    gpu_count_override=selected_gpu_count,
                    disk_size_override=disk_size_str,
                    image_tag=image_tag.strip() or "latest",
                    quantization=quantization,
                    dtype=dtype,
                    gpu_memory_utilization=gpu_memory_utilization,
                    enable_prefix_caching=enable_prefix_caching,
                    max_num_seqs=int(max_num_seqs) if max_num_seqs else 0,
                    mem_fraction_static=mem_fraction_static,
                    disable_radix_cache=disable_radix_cache,
                    max_running_requests=int(max_running_requests) if max_running_requests else 0,
                    attention_backend=attention_backend,
                )
                st.switch_page("pages/2_Endpoint_Management.py")


def _section_creating() -> None:
    job = st.session_state.create_job or {}
    _status_card()
    st.info("⏳ Submitting endpoint creation request…")
    if job.get("done"):
        if job.get("error"):
            st.session_state.workflow = "error"
            st.session_state.error_message = job["error"]
            st.rerun()
        else:
            r = job["result"]
            st.session_state.endpoint_id       = r.endpoint_id
            st.session_state.creation_duration = r.creation_duration_seconds
            st.session_state.workflow          = "submitted"
            st.rerun()
    else:
        time.sleep(REFRESH_INTERVAL); st.rerun()
    if st.button("↩ Deploy another endpoint"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


def _section_polling() -> None:
    job = st.session_state.poll_job or {}
    _status_card()
    status: EndpointStatus | None = job.get("status")
    if status and status.state.is_transient:
        st.info(f"⏳ Waiting for RUNNING state… ({_elapsed(st.session_state.op_start)})")
    else:
        st.info("⏳ First status check in progress…")
    if job.get("done"):
        if job.get("error"):
            st.session_state.workflow = "error"; st.session_state.error_message = job["error"]
        else:
            st.session_state.endpoint_url  = job["url"]
            st.session_state.auth_token    = job["auth_token"]
            st.session_state.workflow      = "warming"
            st.session_state.op_start      = time.time()
        st.rerun()
    else:
        time.sleep(REFRESH_INTERVAL); st.rerun()


def _spawn_warmup(endpoint_url: str, auth_token: str | None) -> None:
    job: dict[str, Any] = {"done": False, "ready": False, "error": None}
    st.session_state.warmup_job = job

    def _run() -> None:
        while not job["done"]:
            if check_serve_ready(endpoint_url, auth_token)[0]:
                job["ready"] = True
                job["done"]  = True
            else:
                time.sleep(POLL_INTERVAL)
    threading.Thread(target=_run, daemon=True).start()


def _section_warming() -> None:
    job = st.session_state.get("warmup_job") or {}
    _status_card()

    if not job:
        _spawn_warmup(st.session_state.endpoint_url, st.session_state.auth_token)
        st.rerun()

    elapsed = _elapsed(st.session_state.op_start)
    st.info(f"🟡 **Container up** — vLLM is loading the model into GPU memory… ({elapsed})")
    st.caption("The endpoint will be ready to serve once `/v1/models` responds. This usually takes 2–4 minutes after the VM starts.")

    if job.get("done"):
        if job.get("ready"):
            st.session_state.time_to_ready = (
                (st.session_state.get("creation_duration") or 0) +
                (time.time() - (st.session_state.op_start or time.time()))
            )
            st.session_state.workflow = "ready"
        else:
            st.session_state.workflow = "error"
            st.session_state.error_message = job.get("error") or "Warmup failed"
        st.rerun()
    else:
        time.sleep(REFRESH_INTERVAL); st.rerun()


def _section_ready() -> None:
    _status_card()
    st.success("✅ Endpoint is RUNNING")
    url = st.session_state.endpoint_url
    if url:
        st.caption(f"URL: `{url}`")
    else:
        st.warning("No public URL detected. Enter manually:")
        manual = st.text_input("Endpoint URL")
        if manual: st.session_state.endpoint_url = manual.rstrip("/")
    st.divider()
    st.subheader("2. Benchmark")
    if st.button("▶ Run Benchmark", type="primary", disabled=not st.session_state.endpoint_url):
        _spawn_benchmark(st.session_state.endpoint_url, st.session_state.auth_token, st.session_state.model_config)
        st.rerun()


def _section_benchmarking() -> None:
    job = st.session_state.bench_job or {}
    _status_card()
    st.divider(); st.subheader("2. Benchmark")
    st.info(f"⏳ **{job.get('phase','Starting…')}**  ({_elapsed(st.session_state.op_start)})")
    st.progress(0, text="TTFT → ITL → Latency → Percentiles → Throughput")
    if job.get("done"):
        if job.get("error"):
            st.session_state.workflow = "error"; st.session_state.error_message = job["error"]
        else:
            # auto-save to DB
            if not st.session_state.run_saved:
                _save_run(job["result"])
                st.session_state.run_saved = True
            st.session_state.workflow = "results"
        st.rerun()
    else:
        time.sleep(REFRESH_INTERVAL); st.rerun()


def _section_results() -> None:
    job     = st.session_state.bench_job or {}
    results: BenchmarkResults | None = job.get("result")
    conc_job = st.session_state.conc_job or {}
    conc_done = conc_job.get("done", False)
    conc_result = conc_job.get("result")

    _status_card()
    st.divider(); st.subheader("2. Benchmark Results")

    run_id = st.session_state.get("current_run_id")
    if run_id:
        st.caption(f"Run ID: `{run_id}`")

    if results:
        _results_dashboard(results)

        # Concurrency section
        st.divider(); st.subheader("3. Concurrency Analysis  *(optional)*")
        if conc_done and conc_result:
            import pandas as pd, plotly.graph_objects as go
            levels = conc_result.levels
            df_c = pd.DataFrame([{
                "Concurrency": l.concurrency,
                "RPS": f"{l.requests_per_second:.2f}",
                "p95 Latency (ms)": f"{l.latency_p95_ms:.0f}",
                "Success Rate": f"{l.success_rate*100:.0f}%",
            } for l in levels])
            st.dataframe(df_c, use_container_width=True, hide_index=True)
            c_left, c_right = st.columns(2)
            with c_left:
                fig = go.Figure(go.Scatter(
                    x=[l.concurrency for l in levels],
                    y=[l.requests_per_second for l in levels],
                    mode="lines+markers+text",
                    text=[f"{l.requests_per_second:.1f}" for l in levels],
                    textposition="top center", marker_color="#636EFA",
                ))
                fig.update_layout(title="Throughput vs Concurrency", xaxis_title="Concurrency",
                                  yaxis_title="rps", height=300,
                                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            with c_right:
                fig2 = go.Figure(go.Scatter(
                    x=[l.concurrency for l in levels],
                    y=[l.latency_p95_ms for l in levels],
                    mode="lines+markers+text",
                    text=[f"{l.latency_p95_ms:.0f}" for l in levels],
                    textposition="top center", marker_color="#EF553B",
                ))
                fig2.update_layout(title="p95 Latency vs Concurrency", xaxis_title="Concurrency",
                                   yaxis_title="ms", height=300,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)
            st.caption(f"Concurrency levels: {[l.concurrency for l in levels]}")

        elif conc_job.get("phase") and not conc_done:
            st.info(f"⏳ {conc_job['phase']} ({_elapsed(None)})")
            time.sleep(REFRESH_INTERVAL); st.rerun()
        else:
            if st.button("📈 Run Concurrency Sweep", help=f"Tests at levels {CONCURRENCY_LEVELS}"):
                _spawn_concurrency(st.session_state.endpoint_url, st.session_state.auth_token, st.session_state.model_config)
                st.rerun()

        st.divider()
        conc_data = [{"concurrency": l.concurrency, "rps": l.requests_per_second, "p95_ms": l.latency_p95_ms}
                     for l in (conc_result.levels if conc_result else [])]
        _download_buttons(results, conc_data=conc_data or None)

    st.divider(); st.subheader("4. Cleanup")
    dr = st.session_state.deletion_result
    if dr:
        st.success(f"✅ Endpoint deleted in {dr.deletion_duration_seconds:.1f}s")
    elif st.session_state.endpoint_id:
        if st.button("🗑️ Delete Endpoint", type="secondary"):
            st.session_state.workflow = "deleting"; st.rerun()


def _section_deleting() -> None:
    job = st.session_state.delete_job or {}
    results: BenchmarkResults | None = (st.session_state.bench_job or {}).get("result")
    _status_card()
    if results:
        st.divider(); st.subheader("2. Benchmark Results")
        _results_dashboard(results)
    st.divider(); st.subheader("4. Cleanup")
    st.info(f"⏳ Deleting endpoint… ({_elapsed(st.session_state.op_start)})")
    if job.get("done"):
        if job.get("error"):
            st.session_state.workflow = "error"; st.session_state.error_message = job["error"]
        else:
            st.session_state.deletion_result = job["result"]
            _patch_deletion_time(job["result"].deletion_duration_seconds)
            st.session_state.workflow = "results"
        st.rerun()
    else:
        time.sleep(REFRESH_INTERVAL); st.rerun()


def _section_error(models: list[dict[str, Any]]) -> None:
    st.error(f"**Error:** {st.session_state.error_message or 'Unknown error'}")
    if st.button("↩ Start Over"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ── main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    _init_session()
    try:
        models = _load_models()
    except Exception as exc:
        st.error(f"Cannot load config/models.yaml: {exc}"); st.stop()

    st.title("🚀 Deploy & Run")
    st.caption("Create a Nebius AI endpoint, run the full benchmark suite, and download reports")
    st.divider()

    w = st.session_state.workflow

    st.header("1. Endpoint Deployment")
    if w == "idle":          _section_idle(models)
    elif w == "creating":    _section_creating()
    elif w == "submitted":   st.switch_page("pages/2_Endpoint_Management.py")
    elif w == "polling":     _section_polling()
    elif w == "warming":     _section_warming()
    elif w == "ready":       _section_ready()
    elif w == "benchmarking": _section_benchmarking()
    elif w == "results":   _section_results()
    elif w == "deleting":  _section_deleting()
    elif w == "error":     _section_error(models)


main()
