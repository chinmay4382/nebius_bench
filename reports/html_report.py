"""HTML report with embedded Plotly charts."""

from __future__ import annotations

import time
from typing import Any

import plotly.graph_objects as go

from benchmark.benchmark_runner import BenchmarkResults


def _fig_to_div(fig: go.Figure) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False)


def generate_html_report(
    model: str,
    benchmark_results: BenchmarkResults,
    endpoint_creation_time_seconds: float,
    time_to_ready_seconds: float,
    deletion_time_seconds: float | None = None,
    concurrency_data: list[dict[str, Any]] | None = None,
) -> str:
    r = benchmark_results
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    # ── Charts ──────────────────────────────────────────────────────────────
    fig_pct = go.Figure(go.Bar(
        x=["p50", "p90", "p99", "Mean"],
        y=[r.percentiles.p50_ms, r.percentiles.p90_ms, r.percentiles.p99_ms, r.percentiles.mean_ms],
        marker_color=["#636EFA", "#EF553B", "#FF6692", "#AB63FA"],
        text=[f"{v:.0f}ms" for v in [r.percentiles.p50_ms, r.percentiles.p90_ms, r.percentiles.p99_ms, r.percentiles.mean_ms]],
        textposition="outside",
    ))
    fig_pct.update_layout(
        title="Latency Percentiles (ms)", yaxis_title="ms",
        height=350, template="plotly_dark",
    )

    fig_itl = None
    if r.itl.raw_gaps_ms:
        fig_itl = go.Figure(go.Histogram(x=r.itl.raw_gaps_ms, nbinsx=20, marker_color="#00CC96"))
        fig_itl.add_vline(x=r.itl.mean_itl_ms, line_dash="dash", line_color="#EF553B",
                          annotation_text=f"mean {r.itl.mean_itl_ms:.1f}ms")
        fig_itl.update_layout(
            title="Inter-Token Latency Distribution", xaxis_title="ms", yaxis_title="count",
            height=350, template="plotly_dark",
        )

    fig_conc_rps = fig_conc_lat = None
    if concurrency_data:
        xs = [c["concurrency"] for c in concurrency_data]
        fig_conc_rps = go.Figure(go.Scatter(
            x=xs, y=[c["rps"] for c in concurrency_data],
            mode="lines+markers+text",
            text=[f"{v:.1f}" for v in [c["rps"] for c in concurrency_data]],
            textposition="top center", marker_color="#636EFA",
        ))
        fig_conc_rps.update_layout(
            title="Throughput vs Concurrency", xaxis_title="Concurrent Requests",
            yaxis_title="Requests/sec", height=350, template="plotly_dark",
        )
        fig_conc_lat = go.Figure(go.Scatter(
            x=xs, y=[c["p95_ms"] for c in concurrency_data],
            mode="lines+markers+text",
            text=[f"{v:.0f}ms" for v in [c["p95_ms"] for c in concurrency_data]],
            textposition="top center", marker_color="#EF553B",
        ))
        fig_conc_lat.update_layout(
            title="p95 Latency vs Concurrency", xaxis_title="Concurrent Requests",
            yaxis_title="p95 Latency (ms)", height=350, template="plotly_dark",
        )

    def _safe_div(fig: go.Figure | None) -> str:
        return _fig_to_div(fig) if fig else "<p style='color:#888'>Not available</p>"

    # ── Summary table rows ───────────────────────────────────────────────────
    def _row(label: str, value: str) -> str:
        return f"<tr><td>{label}</td><td><strong>{value}</strong></td></tr>"

    metric_rows = "\n".join([
        _row("Model",                  model),
        _row("Timestamp",              ts),
        _row("Endpoint Creation",      f"{endpoint_creation_time_seconds:.1f}s"),
        _row("Time to Ready",          f"{time_to_ready_seconds:.1f}s"),
        _row("TTFT",                   f"{r.ttft.ttft_ms:.0f}ms" if r.ttft.success else "N/A"),
        _row("ITL Mean",               f"{r.itl.mean_itl_ms:.1f}ms" if r.itl.success else "N/A"),
        _row("ITL p90",                f"{r.itl.p90_itl_ms:.1f}ms" if r.itl.success else "N/A"),
        _row("Token Gen Speed",        f"{r.itl.tokens_per_second:.1f} tok/s" if r.itl.success else "N/A"),
        _row("E2E Latency",            f"{r.latency.latency_ms:.0f}ms" if r.latency.success else "N/A"),
        _row("p50 / p90 / p99",        f"{r.percentiles.p50_ms:.0f} / {r.percentiles.p90_ms:.0f} / {r.percentiles.p99_ms:.0f} ms"),
        _row("Throughput",             f"{r.throughput.requests_per_second:.2f} rps"),
        _row("Token Throughput",       f"{r.throughput.tokens_per_second:.1f} tok/s"),
        _row("Success Rate",           f"{r.throughput.success_rate * 100:.1f}%"),
    ])
    if deletion_time_seconds is not None:
        metric_rows += "\n" + _row("Deletion Time", f"{deletion_time_seconds:.1f}s")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Nebius Benchmark Report — {model}</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body  {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
             background: #0e1117; color: #e0e0e0; margin: 0; padding: 0; }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
    h1    {{ color: #636EFA; margin-bottom: 4px; }}
    .sub  {{ color: #888; margin-bottom: 32px; font-size: 0.9rem; }}
    h2    {{ color: #aaa; font-size: 1rem; text-transform: uppercase;
             letter-spacing: 0.08em; margin: 32px 0 12px; border-bottom: 1px solid #333; padding-bottom: 6px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 540px; margin-bottom: 16px; }}
    td    {{ padding: 8px 12px; border-bottom: 1px solid #333; font-size: 0.9rem; }}
    td:first-child {{ color: #888; width: 220px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
    .card {{ background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 8px; padding: 16px; }}
    @media (max-width: 700px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    footer{{ margin-top: 48px; color: #555; font-size: 0.8rem; text-align: center; }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>🔬 Nebius Endpoint Benchmark Report</h1>
  <div class="sub">Generated {ts} &nbsp;·&nbsp; Model: {model}</div>

  <h2>Summary</h2>
  <table>{metric_rows}</table>

  <h2>Latency Distribution</h2>
  <div class="card">{_safe_div(fig_pct)}</div>

  <h2>Inter-Token Latency</h2>
  <div class="card">{_safe_div(fig_itl)}</div>

  {'<h2>Concurrency Analysis</h2><div class="grid"><div class="card">' + _safe_div(fig_conc_rps) + '</div><div class="card">' + _safe_div(fig_conc_lat) + '</div></div>' if concurrency_data else ''}

  <footer>Generated by Nebius Endpoint Lab</footer>
</div>
</body>
</html>"""
