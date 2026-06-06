"""
Nebius Endpoint Lab — Home Dashboard.

Shows aggregate stats from the benchmark history DB and provides
quick-action navigation to the other pages.
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from database.migrations import get_session_factory
from database.repository import BenchmarkRepository

st.set_page_config(
    page_title="Nebius Endpoint Lab",
    page_icon="🔬",
    layout="wide",
)


@st.cache_resource
def _session_factory():
    return get_session_factory()


def _repo() -> BenchmarkRepository:
    factory = _session_factory()
    return BenchmarkRepository(factory())


# ── helpers ────────────────────────────────────────────────────────────────────

def _fmt(val: float | None, unit: str = "", decimals: int = 0) -> str:
    if val is None:
        return "—"
    if decimals == 0:
        return f"{val:.0f}{unit}"
    return f"{val:.{decimals}f}{unit}"


# ── page ────────────────────────────────────────────────────────────────────────

st.title("🔬 Nebius Endpoint Lab")
st.caption("AI Infrastructure Benchmarking Platform for Nebius Serverless Endpoints")
st.divider()

try:
    repo   = _repo()
    summary = repo.get_platform_summary()
    recent  = repo.list_runs(limit=10)
    trends  = repo.get_trend_data(limit=30)
except Exception as exc:
    st.error(f"Database error: {exc}")
    st.stop()

# ── Platform Summary ────────────────────────────────────────────────────────────
st.subheader("Platform Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Runs",       summary["total_runs"])
c2.metric("Models Tested",    summary["models_tested"])
c3.metric("Avg TTFT",         _fmt(summary["avg_ttft_ms"], "ms"))
c4.metric("Avg Throughput",   _fmt(summary["avg_rps"], " rps", 2))

st.divider()

# ── Trend Charts ────────────────────────────────────────────────────────────────
if trends:
    st.subheader("Trends")
    ch1, ch2 = st.columns(2)

    ts_labels  = [r["timestamp"].strftime("%m/%d %H:%M") if r["timestamp"] else "" for r in trends]
    ttft_vals  = [r["ttft_ms"] for r in trends]
    rps_vals   = [r["rps"] for r in trends]
    model_lbls = [r["model"] for r in trends]

    with ch1:
        fig = go.Figure(go.Scatter(
            x=ts_labels, y=ttft_vals, mode="lines+markers",
            hovertext=model_lbls, marker_color="#636EFA",
        ))
        fig.update_layout(
            title="TTFT Over Time (ms)", yaxis_title="ms", height=260,
            margin={"t": 40, "b": 30}, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        fig2 = go.Figure(go.Scatter(
            x=ts_labels, y=rps_vals, mode="lines+markers",
            hovertext=model_lbls, marker_color="#00CC96",
        ))
        fig2.update_layout(
            title="Throughput Over Time (rps)", yaxis_title="rps", height=260,
            margin={"t": 40, "b": 30}, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

# ── Recent Benchmarks ────────────────────────────────────────────────────────────
st.subheader("Recent Benchmarks")

if not recent:
    st.info("No benchmark runs yet.  Head to **Deploy & Run** to create your first endpoint and benchmark.")
else:
    import pandas as pd

    df = pd.DataFrame(recent)
    display_cols = {
        "run_id":       "Run ID",
        "timestamp":    "Date",
        "model":        "Model",
        "ttft_ms":      "TTFT (ms)",
        "lat_p90_ms":   "p90 Lat (ms)",
        "rps":          "Throughput (rps)",
        "success_rate": "Success Rate",
    }
    df_display = df[[c for c in display_cols if c in df.columns]].rename(columns=display_cols)
    if "Date" in df_display.columns:
        df_display["Date"] = df_display["Date"].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M") if x else "—"
        )
    for col in ["TTFT (ms)", "p90 Lat (ms)"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(lambda x: f"{x:.0f}" if x else "—")
    if "Throughput (rps)" in df_display.columns:
        df_display["Throughput (rps)"] = df_display["Throughput (rps)"].apply(
            lambda x: f"{x:.2f}" if x else "—"
        )
    if "Success Rate" in df_display.columns:
        df_display["Success Rate"] = df_display["Success Rate"].apply(
            lambda x: f"{x*100:.1f}%" if x else "—"
        )
    st.dataframe(df_display, use_container_width=True, hide_index=True)

st.divider()

# ── Quick Actions ────────────────────────────────────────────────────────────────
st.subheader("Quick Actions")
qa1, qa2, qa3, qa4 = st.columns(4)
with qa1:
    st.page_link("pages/1_Deploy_and_Run.py",      label="🚀 Deploy & Run",          use_container_width=True)
with qa2:
    st.page_link("pages/2_Benchmark_History.py",   label="📋 Benchmark History",     use_container_width=True)
with qa3:
    st.page_link("pages/3_Compare_Runs.py",        label="🔍 Compare Runs",          use_container_width=True)
with qa4:
    st.page_link("pages/4_Concurrency_Analysis.py",label="📈 Concurrency Analysis",  use_container_width=True)
