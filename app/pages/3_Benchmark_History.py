"""Benchmark History — platform summary, trends, and full run browser."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from database.migrations import get_session_factory
from database.repository import BenchmarkRepository

st.set_page_config(page_title="History · Nebius Endpoint Lab", page_icon="📋", layout="wide")


@st.cache_resource
def _factory():
    return get_session_factory()


def _repo() -> BenchmarkRepository:
    return BenchmarkRepository(_factory()())


def _fmt(val: float | None, unit: str = "", decimals: int = 0) -> str:
    if val is None:
        return "—"
    return f"{val:.{decimals}f}{unit}"


st.title("📋 Benchmark History")
st.caption("Platform summary, trends, and full run browser")
st.divider()

# ── Platform Summary ──────────────────────────────────────────────────────────
try:
    repo    = _repo()
    summary = repo.get_platform_summary()
    trends  = repo.get_trend_data(limit=30)
except Exception as exc:
    st.error(f"Database error: {exc}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Runs",     summary["total_runs"])
c2.metric("Models Tested",  summary["models_tested"])
c3.metric("Avg TTFT",       _fmt(summary["avg_ttft_ms"], "ms"))
c4.metric("Avg Throughput", _fmt(summary["avg_rps"], " rps", 2))

# ── Trends ────────────────────────────────────────────────────────────────────
if trends:
    st.divider()
    ch1, ch2 = st.columns(2)

    ts_labels  = [r["timestamp"].strftime("%m/%d %H:%M") if r["timestamp"] else "" for r in trends]
    model_lbls = [r["model"] for r in trends]

    with ch1:
        fig = go.Figure(go.Scatter(
            x=ts_labels, y=[r["ttft_ms"] for r in trends],
            mode="lines+markers", hovertext=model_lbls, marker_color="#636EFA",
        ))
        fig.update_layout(
            title="TTFT Over Time (ms)", yaxis_title="ms", height=260,
            margin={"t": 40, "b": 30},
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        fig2 = go.Figure(go.Scatter(
            x=ts_labels, y=[r["rps"] for r in trends],
            mode="lines+markers", hovertext=model_lbls, marker_color="#00CC96",
        ))
        fig2.update_layout(
            title="Throughput Over Time (rps)", yaxis_title="rps", height=260,
            margin={"t": 40, "b": 30},
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
try:
    models_available = _repo().get_distinct_models()
except Exception:
    models_available = []

f1, f2, f3 = st.columns([2, 2, 1])

with f1:
    model_filter = st.selectbox("Filter by Model", ["All"] + models_available)
    model_filter = None if model_filter == "All" else model_filter

with f2:
    date_options = ["Last 7 days", "Last 30 days", "Last 90 days", "All time"]
    date_range   = st.selectbox("Date Range", date_options, index=1)
    now = datetime.utcnow()
    start_date = {
        "Last 7 days":  now - timedelta(days=7),
        "Last 30 days": now - timedelta(days=30),
        "Last 90 days": now - timedelta(days=90),
        "All time":     None,
    }[date_range]

with f3:
    st.write("")
    st.button("🔄 Refresh", use_container_width=True)

# ── Load ──────────────────────────────────────────────────────────────────────
try:
    runs = _repo().list_runs(model_filter=model_filter, start_date=start_date, limit=500)
except Exception as exc:
    st.error(f"DB error: {exc}"); st.stop()

if not runs:
    st.info("No runs match the current filters.")
    st.stop()

# ── Filtered summary ──────────────────────────────────────────────────────────
col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Matching Runs", len(runs))
ttfts = [r["ttft_ms"] for r in runs if r["ttft_ms"]]
rpss  = [r["rps"]     for r in runs if r["rps"]]
col_b.metric("Avg TTFT",       f"{sum(ttfts)/len(ttfts):.0f}ms" if ttfts else "—")
col_c.metric("Avg Throughput", f"{sum(rpss)/len(rpss):.2f} rps" if rpss else "—")
col_d.metric("Models",         len({r["model_id"] for r in runs}))

st.divider()

# ── Table ─────────────────────────────────────────────────────────────────────
df = pd.DataFrame(runs)

display = {
    "run_id":       "Run ID",
    "timestamp":    "Date",
    "model":        "Model",
    "platform":     "Platform",
    "ttft_ms":      "TTFT (ms)",
    "lat_p50_ms":   "p50 (ms)",
    "lat_p90_ms":   "p90 (ms)",
    "lat_p99_ms":   "p99 (ms)",
    "rps":          "RPS",
    "tok_per_s":    "Tok/s",
    "success_rate": "Success",
    "ttr_s":        "Time→Ready (s)",
}
df_show = df[[c for c in display if c in df.columns]].rename(columns=display)

if "Date" in df_show.columns:
    df_show["Date"] = df_show["Date"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M") if x else "—")
for col in ["TTFT (ms)", "p50 (ms)", "p90 (ms)", "p99 (ms)", "Time→Ready (s)"]:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(lambda x: f"{x:.0f}" if x is not None else "—")
if "RPS" in df_show.columns:
    df_show["RPS"] = df_show["RPS"].apply(lambda x: f"{x:.2f}" if x is not None else "—")
if "Tok/s" in df_show.columns:
    df_show["Tok/s"] = df_show["Tok/s"].apply(lambda x: f"{x:.1f}" if x is not None else "—")
if "Success" in df_show.columns:
    df_show["Success"] = df_show["Success"].apply(lambda x: f"{x*100:.1f}%" if x is not None else "—")

st.dataframe(df_show, use_container_width=True, hide_index=True, height=460)

# ── Export ────────────────────────────────────────────────────────────────────
st.divider()
st.download_button(
    "📥 Export CSV",
    data=df_show.to_csv(index=False),
    file_name=f"nebius_bench_history_{datetime.utcnow().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)

# ── Delete ────────────────────────────────────────────────────────────────────
with st.expander("🗑️ Delete a run"):
    run_ids = [r["run_id"] for r in runs]
    to_delete = st.selectbox("Select Run ID to delete", run_ids)
    if st.button("Delete selected run", type="secondary"):
        try:
            _repo().delete_run(to_delete)
            st.success(f"Run {to_delete} deleted.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
