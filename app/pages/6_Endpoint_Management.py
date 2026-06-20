"""Endpoint Management — view, refresh, benchmark, and delete Nebius AI endpoints."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.delete_endpoint import delete_endpoint
from orchestrator.get_status import EndpointState, check_serve_ready
from orchestrator.list_endpoints import EndpointInfo, list_endpoints
from orchestrator.nebius_client import NebiusClientError

st.set_page_config(
    page_title="Endpoints · Nebius Endpoint Lab",
    page_icon="📡",
    layout="wide",
)

_STATE_BADGE = {
    EndpointState.RUNNING:      ("🟢", "RUNNING",      "#1a4731"),
    EndpointState.CREATING:     ("🟡", "CREATING",     "#3d3206"),
    EndpointState.PROVISIONING: ("🟡", "PROVISIONING", "#3d3206"),
    EndpointState.STARTING:     ("🟡", "STARTING",     "#3d3206"),
    EndpointState.STOPPING:     ("🟠", "STOPPING",     "#3d1f06"),
    EndpointState.STOPPED:      ("⚫", "STOPPED",      "#1a1a1a"),
    EndpointState.FAILED:       ("🔴", "FAILED",       "#4a1212"),
    EndpointState.ERROR:        ("🔴", "ERROR",        "#4a1212"),
    EndpointState.UNKNOWN:      ("⚪", "UNKNOWN",      "#2a2a2a"),
}

_SERVE_CHECK_TTL = 30  # seconds between health-check refreshes per endpoint


def _serve_badge(ep: EndpointInfo) -> tuple[str, str, str, str]:
    """Return (icon, label, bg, detail) for a RUNNING endpoint.

    Result is cached for _SERVE_CHECK_TTL seconds.
    """
    cache_key  = f"serve_ready_{ep.endpoint_id}"
    detail_key = f"serve_detail_{ep.endpoint_id}"
    ts_key     = f"serve_ready_ts_{ep.endpoint_id}"

    cached_at = st.session_state.get(ts_key, 0)
    if cache_key not in st.session_state or time.time() - cached_at > _SERVE_CHECK_TTL:
        ready, detail = check_serve_ready(ep.url or "", ep.auth_token, timeout=3)
        st.session_state[cache_key]  = ready
        st.session_state[detail_key] = detail
        st.session_state[ts_key]     = time.time()

    ready  = st.session_state[cache_key]
    detail = st.session_state.get(detail_key, "")

    if ready:
        return ("🟢", "READY TO SERVE", "#1a4731", "")
    return ("🟡", "CONTAINER UP", "#2a3d06", detail)


def _fmt_ts(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        return ts[:16].replace("T", " ") + " UTC"
    except Exception:
        return ts


def _handoff(ep: EndpointInfo) -> None:
    """Pre-fill Deploy & Run session state and navigate there."""
    model_display = ep.model or ep.name or ep.endpoint_id
    st.session_state["model_config"] = {
        "id": ep.endpoint_id, "display_name": model_display,
        "model_id": ep.model or "", "served_model_name": ep.model or "",
        "image": ep.image or "", "platform": ep.platform or "",
        "gpu_count": 1, "max_tokens": 512,
    }
    st.session_state["workflow"]           = "ready"
    st.session_state["endpoint_id"]        = ep.endpoint_id
    st.session_state["endpoint_url"]       = ep.url
    st.session_state["auth_token"]         = ep.auth_token
    st.session_state["creation_duration"]  = 0.0
    st.session_state["time_to_ready"]      = 0.0
    st.session_state["op_start"]           = time.time()
    st.session_state["selected_platform"]  = ep.platform
    for k in ("create_job", "poll_job", "warmup_job", "bench_job", "delete_job",
              "deletion_result", "current_run_id", "run_saved", "conc_job"):
        st.session_state[k] = None
    st.switch_page("pages/1_Deploy_and_Run.py")


def _spawn_delete(endpoint_id: str) -> dict:
    """Start deletion in a background thread; return the shared job dict."""
    job: dict = {"done": False, "success": False, "error": None, "duration_s": None}
    deleting_key = f"deleting_{endpoint_id}"
    st.session_state[deleting_key] = job

    def _run() -> None:
        try:
            result = delete_endpoint(endpoint_id)
            job["success"]    = True
            job["duration_s"] = result.deletion_duration_seconds
        except Exception as exc:
            job["error"] = str(exc)
        finally:
            job["done"] = True

    threading.Thread(target=_run, daemon=True).start()
    return job


def _render_test_panel(ep: EndpointInfo, ready: bool = True) -> None:
    """Inline API test panel for a running endpoint."""
    from openai import OpenAI

    eid = ep.endpoint_id
    with st.expander("🧪 Test API", expanded=False):
        if not ready:
            st.info("⏳ Model server is still loading — test will be enabled once the endpoint is ready to serve.")

        # ── Controls ────────────────────────────────────────────────────────
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            model_name = st.text_input(
                "Model name", value=ep.model or "",
                key=f"t_model_{eid}",
                help="The served_model_name the endpoint was started with.",
            )
        with c2:
            temperature = st.slider(
                "Temperature", 0.0, 2.0, 0.7, 0.05, key=f"t_temp_{eid}",
            )
        with c3:
            max_tokens = st.number_input(
                "Max tokens", min_value=1, max_value=4096, value=256, step=64,
                key=f"t_maxtok_{eid}",
            )

        with st.expander("System prompt (optional)", expanded=False):
            system_prompt = st.text_area(
                "System prompt", value="", key=f"t_sys_{eid}",
                placeholder="You are a helpful assistant.",
                label_visibility="collapsed",
            )

        prompt = st.text_area(
            "User prompt", value="Hello! Briefly describe what you can do.",
            key=f"t_prompt_{eid}", height=80,
        )

        ctl1, ctl2, ctl3 = st.columns([2, 2, 2])
        with ctl1:
            streaming = st.checkbox("Streaming", value=True, key=f"t_stream_{eid}")
        with ctl2:
            show_raw = st.checkbox("Show raw JSON", value=False, key=f"t_raw_{eid}")
        with ctl3:
            send = st.button(
                "▶ Send", key=f"t_send_{eid}",
                type="primary", use_container_width=True,
                disabled=not ready or not model_name.strip(),
            )

        if not send:
            return

        # ── Build client ─────────────────────────────────────────────────────
        api_key  = ep.auth_token or os.getenv("NEBIUS_API_KEY") or "dummy"
        base_url = (ep.url or "").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"

        if not base_url or base_url == "/v1":
            st.error("Endpoint has no public URL — cannot send request.")
            return

        client = OpenAI(base_url=base_url, api_key=api_key, timeout=120.0)
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": prompt})

        st.divider()

        # ── Streaming ────────────────────────────────────────────────────────
        if streaming:
            response_placeholder = st.empty()
            metrics_placeholder  = st.empty()
            collected            = []
            ttft_ms: float | None = None
            t0 = time.perf_counter()

            try:
                with st.spinner("Waiting for first token…"):
                    stream = client.chat.completions.create(
                        model=model_name.strip(),
                        messages=messages,
                        max_tokens=int(max_tokens),
                        temperature=temperature,
                        stream=True,
                    )

                for chunk in stream:
                    delta = (chunk.choices or [{}])[0]
                    content = getattr(getattr(delta, "delta", None), "content", None) or ""
                    if content:
                        if ttft_ms is None:
                            ttft_ms = (time.perf_counter() - t0) * 1000
                        collected.append(content)
                        response_placeholder.code("".join(collected), language=None)

                total_ms = (time.perf_counter() - t0) * 1000
                m1, m2 = metrics_placeholder.columns(2)
                m1.metric("TTFT", f"{ttft_ms:.0f} ms" if ttft_ms else "—")
                m2.metric("Total time", f"{total_ms:.0f} ms")

            except Exception as exc:
                st.error(f"Request failed: {exc}")

        # ── Non-streaming ─────────────────────────────────────────────────────
        else:
            t0 = time.perf_counter()
            try:
                with st.spinner("Waiting for response…"):
                    resp = client.chat.completions.create(
                        model=model_name.strip(),
                        messages=messages,
                        max_tokens=int(max_tokens),
                        temperature=temperature,
                        stream=False,
                    )
                total_ms = (time.perf_counter() - t0) * 1000
                content  = (resp.choices[0].message.content or "") if resp.choices else ""

                st.code(content, language=None)

                usage = resp.usage
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Total time",        f"{total_ms:.0f} ms")
                mc2.metric("Prompt tokens",     usage.prompt_tokens      if usage else "—")
                mc3.metric("Completion tokens", usage.completion_tokens  if usage else "—")
                mc4.metric("Total tokens",      usage.total_tokens       if usage else "—")

                if show_raw:
                    st.json(resp.model_dump())

            except Exception as exc:
                st.error(f"Request failed: {exc}")


def _render_card(ep: EndpointInfo) -> None:
    is_running   = ep.state == EndpointState.RUNNING
    is_transient = ep.state.is_transient
    is_error     = ep.state in (EndpointState.FAILED, EndpointState.UNKNOWN) or ep.state.value == "ERROR"

    if ep.state == EndpointState.RUNNING:
        icon, label, bg, serve_detail = _serve_badge(ep)
    else:
        icon, label, bg = _STATE_BADGE.get(ep.state, ("⚪", ep.state.value, "#2a2a2a"))
        serve_detail = ""

    is_serve_ready = label == "READY TO SERVE"

    confirm_key  = f"confirm_delete_{ep.endpoint_id}"
    deleting_key = f"deleting_{ep.endpoint_id}"
    deleted_key  = f"deleted_{ep.endpoint_id}"

    # Skip already-deleted endpoints
    if st.session_state.get(deleted_key):
        return

    with st.container(border=True):
        # ── Top row: name | badge | actions ────────────────────────────────
        col_name, col_badge, col_bench, col_del = st.columns([4, 2, 1, 1])

        with col_name:
            st.markdown(f"**{ep.name}**")
            short = ep.endpoint_id[-14:] if len(ep.endpoint_id) > 14 else ep.endpoint_id
            st.caption(f"`{short}`")

        with col_badge:
            st.markdown(
                f'<span style="background:{bg};border-radius:6px;padding:4px 10px;'
                f'font-size:.82rem;font-weight:600;display:inline-block;margin-top:6px">'
                f'{icon} {label}</span>',
                unsafe_allow_html=True,
            )
            if serve_detail:
                st.caption(serve_detail)

        with col_bench:
            if is_serve_ready:
                if st.button("▶ Benchmark", key=f"bench_{ep.endpoint_id}",
                             type="primary", use_container_width=True):
                    _handoff(ep)
            elif is_running:
                st.caption("Loading…")
            elif is_transient:
                st.caption("Starting…")

        with col_del:
            job = st.session_state.get(deleting_key)
            if job and not job["done"]:
                st.caption("Deleting…")
            elif job and job["done"] and job["success"]:
                st.session_state[deleted_key] = True
                st.rerun()
            elif job and job["done"] and job["error"]:
                st.error(f"Delete failed: {job['error']}", icon="🚨")
            elif st.session_state.get(confirm_key):
                pass  # confirm row rendered below
            else:
                if st.button("🗑️ Delete", key=f"del_{ep.endpoint_id}",
                             type="secondary", use_container_width=True):
                    st.session_state[confirm_key] = True
                    st.rerun()

        # ── Confirm row (shown when delete button was clicked) ─────────────
        if st.session_state.get(confirm_key):
            job = st.session_state.get(deleting_key)
            if job and not job["done"]:
                st.info(f"⏳ Deleting **{ep.name}**…")
            elif job and job["done"]:
                pass  # handled above via rerun
            else:
                cf1, cf2, cf3 = st.columns([4, 1, 1])
                with cf1:
                    st.warning(
                        f"⚠️ Delete **{ep.name}**? This stops the VM and removes the endpoint permanently.",
                        icon="⚠️",
                    )
                with cf2:
                    if st.button("✅ Yes, delete", key=f"confirm_yes_{ep.endpoint_id}",
                                 type="primary", use_container_width=True):
                        _spawn_delete(ep.endpoint_id)
                        st.rerun()
                with cf3:
                    if st.button("Cancel", key=f"confirm_no_{ep.endpoint_id}",
                                 use_container_width=True):
                        del st.session_state[confirm_key]
                        st.rerun()

        # ── Detail row ────────────────────────────────────────────────────
        d1, d2, d3, d4 = st.columns(4)
        d1.markdown("**Model**");           d1.caption(ep.model or "—")
        d2.markdown("**Platform / Preset**"); d2.caption(f"{ep.platform or '—'} · {ep.preset or '—'}")
        d3.markdown("**URL**");             d3.caption(f"`{ep.url}`" if ep.url else "—")
        d4.markdown("**Created**");         d4.caption(_fmt_ts(ep.created_at))

        if ep.image:
            with st.expander("Container image", expanded=False):
                st.code(ep.image, language="text")

        if is_running and ep.url:
            _render_test_panel(ep, ready=is_serve_ready)


# ── Also handle "ERROR" state in EndpointState ─────────────────────────────────
# The Nebius API returns "ERROR" which isn't in the enum — patch it here.
if not hasattr(EndpointState, "ERROR"):
    try:
        EndpointState._value2member_map_["ERROR"] = EndpointState.FAILED  # type: ignore[attr-defined]
    except Exception:
        pass


# ── Page ─────────────────────────────────────────────────────────────────────────

st.title("📡 Endpoint Management")
st.caption("All active Nebius AI endpoints for the current project")

tb_left, tb_right = st.columns([6, 1])
with tb_right:
    refresh = st.button("🔄 Refresh", use_container_width=True)

if "ep_list" not in st.session_state or refresh:
    # Clear deleted/confirm state on refresh so removed endpoints don't ghost
    for k in list(st.session_state.keys()):
        if k.startswith(("deleted_", "confirm_delete_", "deleting_")):
            del st.session_state[k]
    with st.spinner("Fetching from Nebius…"):
        try:
            st.session_state["ep_list"]         = list_endpoints()
            st.session_state["ep_list_fetched"] = time.time()
        except NebiusClientError as exc:
            st.error(f"Failed to list endpoints: {exc}")
            st.stop()

endpoints: list[EndpointInfo] = st.session_state.get("ep_list", [])
fetched = st.session_state.get("ep_list_fetched")

with tb_left:
    if fetched:
        st.caption(f"Last refreshed: {time.strftime('%H:%M:%S', time.localtime(fetched))}")

st.divider()

# Summary counts (exclude locally-deleted ones)
visible = [e for e in endpoints if not st.session_state.get(f"deleted_{e.endpoint_id}")]
total   = len(visible)
running = sum(1 for e in visible if e.state == EndpointState.RUNNING)
pending = sum(1 for e in visible if e.state.is_transient)
failed  = sum(1 for e in visible if e.state.value in ("FAILED", "ERROR"))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total",       total)
c2.metric("🟢 Running",  running)
c3.metric("🟡 Pending",  pending)
c4.metric("🔴 Failed",   failed)
st.divider()

if not visible:
    st.info("No endpoints found. Create one from **Deploy & Run**.")
    st.stop()


def _sort_key(ep: EndpointInfo) -> int:
    if ep.state == EndpointState.RUNNING:   return 0
    if ep.state.is_transient:              return 1
    if ep.state.value in ("FAILED","ERROR"): return 3
    return 2


# Auto-rerun while any deletion is in progress
any_deleting = any(
    not st.session_state.get(f"deleting_{e.endpoint_id}", {}).get("done", True)
    for e in endpoints
    if st.session_state.get(f"deleting_{e.endpoint_id}")
)

for ep in sorted(visible, key=_sort_key):
    _render_card(ep)

# Auto-refresh while any RUNNING endpoint isn't serve-ready yet
any_loading = any(
    e.state == EndpointState.RUNNING
    and not st.session_state.get(f"serve_ready_{e.endpoint_id}", False)
    for e in visible
)

if any_deleting:
    time.sleep(2)
    st.rerun()
elif any_loading:
    time.sleep(_SERVE_CHECK_TTL)
    st.rerun()
