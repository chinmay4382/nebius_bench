"""Concurrency Analysis — throughput, latency, and reliability vs parallelism."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from database.migrations import get_session_factory
from database.repository import BenchmarkRepository

st.set_page_config(page_title="Concurrency · Nebius Endpoint Lab", page_icon="📈", layout="wide")


@st.cache_resource
def _factory():
    return get_session_factory()


def _repo():
    return BenchmarkRepository(_factory()())


# ── page ────────────────────────────────────────────────────────────────────────

st.title("📈 Concurrency Analysis")
st.caption("How throughput, latency, and reliability scale with concurrent request load")
st.divider()

try:
    runs = _repo().list_runs(limit=200)
except Exception as exc:
    st.error(f"DB error: {exc}"); st.stop()

runs_with_conc = [r for r in runs if r.get("has_concurrency")]

if not runs_with_conc:
    st.info(
        "No concurrency data yet.  "
        "Go to **Deploy & Run**, complete a benchmark, then click "
        "**📈 Run Concurrency Sweep** to collect data."
    )
    st.stop()

run_options = {
    f"{r['run_id']}  ·  {r['model']}  ·  {r['timestamp'].strftime('%m/%d %H:%M') if r['timestamp'] else ''}": r["run_id"]
    for r in runs_with_conc
}

selected_label = st.selectbox("Select benchmark run", list(run_options.keys()))
run_id = run_options[selected_label]

try:
    conc_data = _repo().get_concurrency_results(run_id)
except Exception as exc:
    st.error(f"DB error: {exc}"); st.stop()

if not conc_data:
    st.warning("No concurrency data for this run.")
    st.stop()

xs = [c["concurrency"] for c in conc_data]

# ── Summary metrics ───────────────────────────────────────────────────────────
max_rps  = max((c["rps"] or 0) for c in conc_data)
min_p95  = min((c["p95_ms"] or 9999) for c in conc_data)
max_sr   = max((c["success_rate"] or 0) for c in conc_data)
best_rps_level = conc_data[max(range(len(conc_data)), key=lambda i: conc_data[i]["rps"] or 0)]["concurrency"]

s1, s2, s3, s4 = st.columns(4)
s1.metric("Peak Throughput",       f"{max_rps:.2f} rps")
s2.metric("Best Concurrency Level",str(best_rps_level))
s3.metric("Best p95 Latency",      f"{min_p95:.0f}ms")
s4.metric("Max Success Rate",      f"{max_sr*100:.0f}%")

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────

ch1, ch2 = st.columns(2)

with ch1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=[c["rps"] for c in conc_data],
        mode="lines+markers+text",
        name="Throughput",
        text=[f"{c['rps']:.1f}" for c in conc_data],
        textposition="top center",
        marker=dict(color="#636EFA", size=10),
        line=dict(color="#636EFA", width=2),
    ))
    fig.update_layout(
        title="Throughput vs Concurrency", xaxis_title="Concurrent Requests",
        yaxis_title="Requests / sec", height=380,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

with ch2:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=xs, y=[c["p95_ms"] for c in conc_data],
        mode="lines+markers+text", name="p95 Latency",
        text=[f"{c['p95_ms']:.0f}ms" for c in conc_data],
        textposition="top center",
        marker=dict(color="#EF553B", size=10),
        line=dict(color="#EF553B", width=2),
    ))
    if any(c.get("mean_ms") for c in conc_data):
        fig2.add_trace(go.Scatter(
            x=xs, y=[c.get("mean_ms") for c in conc_data],
            mode="lines+markers", name="Mean Latency",
            marker=dict(color="#FF9F40", size=8),
            line=dict(color="#FF9F40", width=1, dash="dot"),
        ))
    fig2.update_layout(
        title="Latency vs Concurrency", xaxis_title="Concurrent Requests",
        yaxis_title="Latency (ms)", height=380,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig2, use_container_width=True)

ch3, ch4 = st.columns(2)

with ch3:
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=xs, y=[c["success_rate"] * 100 for c in conc_data],
        mode="lines+markers+text", name="Success Rate",
        text=[f"{c['success_rate']*100:.0f}%" for c in conc_data],
        textposition="top center",
        marker=dict(color="#00CC96", size=10),
        line=dict(color="#00CC96", width=2),
        fill="tozeroy", fillcolor="rgba(0,204,150,0.1)",
    ))
    fig3.update_layout(
        title="Reliability vs Concurrency", xaxis_title="Concurrent Requests",
        yaxis_title="Success Rate (%)", yaxis_range=[0, 105], height=380,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig3, use_container_width=True)

with ch4:
    fig4 = go.Figure(go.Bar(
        x=[str(c["concurrency"]) for c in conc_data],
        y=[(c.get("tokens") or 0) for c in conc_data],
        marker_color="#AB63FA",
        text=[(c.get("tokens") or 0) for c in conc_data],
        textposition="outside",
    ))
    fig4.update_layout(
        title="Total Output Tokens per Level", xaxis_title="Concurrency",
        yaxis_title="Tokens", height=380,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig4, use_container_width=True)

# ── Raw table ────────────────────────────────────────────────────────────────
import pandas as pd
st.divider()
st.subheader("Raw Data")
df = pd.DataFrame([{
    "Concurrency":    c["concurrency"],
    "Req/s":          f"{c['rps']:.2f}" if c["rps"] else "—",
    "p95 Lat (ms)":   f"{c['p95_ms']:.0f}" if c["p95_ms"] else "—",
    "Mean Lat (ms)":  f"{c.get('mean_ms', 0):.0f}" if c.get("mean_ms") else "—",
    "Success Rate":   f"{c['success_rate']*100:.1f}%" if c["success_rate"] is not None else "—",
    "Tokens":         c.get("tokens", 0),
    "Duration (s)":   f"{c['duration_s']:.1f}" if c.get("duration_s") else "—",
} for c in conc_data])
st.dataframe(df, use_container_width=True, hide_index=True)
