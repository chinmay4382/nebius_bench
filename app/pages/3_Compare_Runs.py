"""Compare Runs — side-by-side comparison of up to 4 benchmark runs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from database.migrations import get_session_factory
from database.repository import BenchmarkRepository

st.set_page_config(page_title="Compare · Nebius Endpoint Lab", page_icon="🔍", layout="wide")


@st.cache_resource
def _factory():
    return get_session_factory()


def _repo():
    return BenchmarkRepository(_factory()())


# ── page ────────────────────────────────────────────────────────────────────────

st.title("🔍 Compare Runs")
st.caption("Select up to 4 benchmark runs for side-by-side comparison")
st.divider()

try:
    runs = _repo().list_runs(limit=200)
except Exception as exc:
    st.error(f"DB error: {exc}"); st.stop()

if len(runs) < 2:
    st.info("Need at least 2 benchmark runs to compare.  Head to **Deploy & Run** to create some.")
    st.stop()

run_options = {f"{r['run_id']}  ·  {r['model']}  ·  {r['timestamp'].strftime('%m/%d %H:%M') if r['timestamp'] else ''}": r["run_id"]
               for r in runs}

selected_labels = st.multiselect(
    "Select runs to compare (2–4)",
    list(run_options.keys()),
    max_selections=4,
)

if len(selected_labels) < 2:
    st.info("Select at least 2 runs above.")
    st.stop()

selected_ids  = [run_options[lb] for lb in selected_labels]
selected_runs = [next(r for r in runs if r["run_id"] == rid) for rid in selected_ids]
labels        = [f"{r['run_id']} / {r['model']}" for r in selected_runs]

# ── Comparison table ─────────────────────────────────────────────────────────────

def _v(r: dict, key: str, fmt: str = ".0f", unit: str = "") -> str:
    val = r.get(key)
    if val is None:
        return "—"
    try:
        return f"{val:{fmt}}{unit}"
    except Exception:
        return str(val)

METRIC_ROWS = [
    ("Time → Ready",  "ttr_s",      ".0f", "s"),
    ("TTFT",          "ttft_ms",    ".0f", "ms"),
    ("ITL Mean",      "itl_mean_ms",".1f", "ms"),
    ("ITL p90",       "itl_p90_ms", ".1f", "ms"),
    ("E2E Latency",   "latency_ms", ".0f", "ms"),
    ("p50 Latency",   "lat_p50_ms", ".0f", "ms"),
    ("p90 Latency",   "lat_p90_ms", ".0f", "ms"),
    ("p99 Latency",   "lat_p99_ms", ".0f", "ms"),
    ("Throughput",    "rps",        ".2f", " rps"),
    ("Token Tput",    "tput_tok_s", ".1f", " tok/s"),
    ("Success Rate",  "success_rate",".1%",""),
]

table_data: dict = {"Metric": [m[0] for m in METRIC_ROWS]}
for r, lb in zip(selected_runs, labels):
    table_data[lb] = [_v(r, m[1], m[2], m[3]) for m in METRIC_ROWS]

st.subheader("Comparison Table")
st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

st.divider()

# ── Bar charts ─────────────────────────────────────────────────────────────────

def _bar(title: str, metric_key: str, unit: str, color: str) -> None:
    vals = [r.get(metric_key) for r in selected_runs]
    if all(v is None for v in vals):
        return
    fig = go.Figure(go.Bar(
        x=labels,
        y=[v if v is not None else 0 for v in vals],
        marker_color=color,
        text=[f"{v:.1f}{unit}" if v is not None else "N/A" for v in vals],
        textposition="outside",
    ))
    fig.update_layout(
        title=title, yaxis_title=unit.strip(), height=300,
        margin={"t": 50, "b": 20}, xaxis_tickangle=-20,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Visual Comparison")
ch1, ch2 = st.columns(2)
with ch1:
    _bar("TTFT (ms)",        "ttft_ms",    "ms",   "#636EFA")
    _bar("p90 Latency (ms)", "lat_p90_ms", "ms",   "#EF553B")
with ch2:
    _bar("Throughput (rps)", "rps",        " rps", "#00CC96")
    _bar("Success Rate",     "success_rate"," %",  "#AB63FA")
