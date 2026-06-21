"""Home — benchmark-first landing page for Nebius Endpoint Lab."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = Path(__file__).parent.parent / "assets"

st.set_page_config(
    page_title="Nebius Endpoint Lab",
    page_icon="🔬",
    layout="wide",
)

# ── Hero ───────────────────────────────────────────────────────────────────────

logo_col, hero_col = st.columns([1, 6])
with logo_col:
    st.image(str(ASSETS / "nebius-logo-white.png"), use_container_width=True)

with hero_col:
    st.html("""
    <div style="padding: 0.5rem 0 1.5rem 0;">
        <p style="
            color: #6e7681;
            font-size: 0.75rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            font-weight: 600;
            margin: 0 0 0.75rem 0;
        ">Nebius AI · Serverless Endpoints</p>
        <h1 style="
            font-size: 3rem;
            font-weight: 900;
            line-height: 1.1;
            margin: 0 0 1.25rem 0;
            letter-spacing: -0.02em;
        ">Stop guessing.<br>Start measuring.</h1>
        <p style="
            font-size: 1.1rem;
            color: #c9d1d9;
            max-width: 660px;
            line-height: 1.7;
            margin: 0;
        ">Know your LLM's real TTFT, throughput, and cost before you build on it.
        Deploy any open-source model on Nebius H200, B200, or RTX 6000 GPUs —
        full benchmark suite runs automatically, report downloads in one click.</p>
    </div>
    """)

cta1, cta2, _ = st.columns([2, 2, 4])
with cta1:
    st.page_link("pages/1_Deploy_and_Run.py",    label="🚀 Run your first benchmark", use_container_width=True)
with cta2:
    st.page_link("pages/3_Benchmark_History.py", label="📋 View benchmark history",   use_container_width=True)

st.divider()


# ── Why benchmark? ─────────────────────────────────────────────────────────────

st.html("""
<h2 style="font-size: 1.6rem; font-weight: 700; margin: 0 0 0.4rem 0;">Why benchmark?</h2>
<p style="color: #8b949e; margin: 0 0 1.5rem 0; font-size: 0.95rem;">
  Spec sheets tell you clock speed and VRAM. They don't tell you whether your app
  will hit 100 ms TTFT at 10 concurrent users. These three problems show up every time you skip measurement.
</p>
<div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.25rem; margin-bottom: 0.5rem;">
  <div style="padding: 1.5rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;">
    <div style="font-size: 1.75rem; margin-bottom: 0.75rem;">📊</div>
    <h3 style="font-size: 1rem; font-weight: 700; margin: 0 0 0.5rem 0;">Spec sheets don't transfer</h3>
    <p style="color: #8b949e; line-height: 1.65; font-size: 0.88rem; margin: 0;">
      An H200 and B200 look similar on paper. On a 70B MoE they diverge 2–3× in throughput.
      The only way to know is to measure on your actual model at your batch size.
    </p>
  </div>
  <div style="padding: 1.5rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;">
    <div style="font-size: 1.75rem; margin-bottom: 0.75rem;">⚙️</div>
    <h3 style="font-size: 1rem; font-weight: 700; margin: 0 0 0.5rem 0;">Engines differ more than you expect</h3>
    <p style="color: #8b949e; line-height: 1.65; font-size: 0.88rem; margin: 0;">
      vLLM and SGLang expose the same API but produce meaningfully different TTFT
      and RPS on the same GPU. One benchmark run tells you which engine to ship.
    </p>
  </div>
  <div style="padding: 1.5rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;">
    <div style="font-size: 1.75rem; margin-bottom: 0.75rem;">📐</div>
    <h3 style="font-size: 1rem; font-weight: 700; margin: 0 0 0.5rem 0;">SLAs need data, not guesses</h3>
    <p style="color: #8b949e; line-height: 1.65; font-size: 0.88rem; margin: 0;">
      Latency p50 looks fine. Latency p99 reveals what users actually experience.
      Without a concurrency sweep you're guessing your rate limiter size.
    </p>
  </div>
</div>
""")

st.divider()


# ── What you measure ───────────────────────────────────────────────────────────

st.html("""
<h2 style="font-size: 1.6rem; font-weight: 700; margin: 0 0 0.4rem 0;">What you measure</h2>
<p style="color: #8b949e; margin: 0 0 1.5rem 0; font-size: 0.95rem;">
  Every benchmark run produces six metrics and a full downloadable report — JSON, Markdown, and self-contained HTML.
</p>
<table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
  <thead>
    <tr style="border-bottom: 1px solid rgba(255,255,255,0.12);">
      <th style="text-align:left; padding: 0.6rem 1rem; color: #6e7681; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600;">Metric</th>
      <th style="text-align:left; padding: 0.6rem 1rem; color: #6e7681; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600;">What it measures</th>
      <th style="text-align:left; padding: 0.6rem 1rem; color: #6e7681; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600;">Why it matters</th>
    </tr>
  </thead>
  <tbody>
    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
      <td style="padding: 0.85rem 1rem; font-weight: 700; color: #58a6ff; white-space: nowrap;">TTFT</td>
      <td style="padding: 0.85rem 1rem; color: #e6edf3;">Time to first token</td>
      <td style="padding: 0.85rem 1rem; color: #8b949e;">The latency users feel before text starts appearing — critical for streaming chat UX</td>
    </tr>
    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
      <td style="padding: 0.85rem 1rem; font-weight: 700; color: #58a6ff; white-space: nowrap;">ITL</td>
      <td style="padding: 0.85rem 1rem; color: #e6edf3;">Inter-token latency — mean, p50, p90, p99</td>
      <td style="padding: 0.85rem 1rem; color: #8b949e;">How smooth the stream feels after the first token; high p99 ITL causes stuttering</td>
    </tr>
    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
      <td style="padding: 0.85rem 1rem; font-weight: 700; color: #58a6ff; white-space: nowrap;">Latency distribution</td>
      <td style="padding: 0.85rem 1rem; color: #e6edf3;">p50 / p90 / p99 across 20 end-to-end samples</td>
      <td style="padding: 0.85rem 1rem; color: #8b949e;">Reveals tail latency before it hits production — set SLAs with confidence</td>
    </tr>
    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
      <td style="padding: 0.85rem 1rem; font-weight: 700; color: #58a6ff; white-space: nowrap;">Throughput</td>
      <td style="padding: 0.85rem 1rem; color: #e6edf3;">Requests/sec and tokens/sec at 5 concurrent workers</td>
      <td style="padding: 0.85rem 1rem; color: #8b949e;">Your baseline capacity — how many parallel users the endpoint can sustain</td>
    </tr>
    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
      <td style="padding: 0.85rem 1rem; font-weight: 700; color: #58a6ff; white-space: nowrap;">Concurrency sweep</td>
      <td style="padding: 0.85rem 1rem; color: #e6edf3;">RPS and p95 latency at 1, 5, 10, 25, 50 users</td>
      <td style="padding: 0.85rem 1rem; color: #8b949e;">Find your saturation point and the exact concurrency where latency degrades</td>
    </tr>
    <tr>
      <td style="padding: 0.85rem 1rem; font-weight: 700; color: #58a6ff; white-space: nowrap;">Cost / session</td>
      <td style="padding: 0.85rem 1rem; color: #e6edf3;">GPU price × estimated session duration</td>
      <td style="padding: 0.85rem 1rem; color: #8b949e;">Know your per-experiment spend before you commit to a platform</td>
    </tr>
  </tbody>
</table>
""")

st.divider()


# ── How it works ───────────────────────────────────────────────────────────────

st.html("""
<h2 style="font-size: 1.6rem; font-weight: 700; margin: 0 0 0.4rem 0;">How it works</h2>
<p style="color: #8b949e; margin: 0 0 1.5rem 0; font-size: 0.95rem;">
  Four steps. The whole cycle — deploy, benchmark, report, teardown — takes about 15 minutes.
</p>
<div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 1.25rem; margin-bottom: 0.5rem;">
  <div style="padding: 1.5rem; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.07); border-radius: 10px;">
    <div style="
      display: inline-block;
      width: 2rem; height: 2rem; line-height: 2rem; text-align: center;
      background: rgba(88,166,255,0.12); border-radius: 50%;
      font-size: 0.85rem; font-weight: 800; color: #58a6ff;
      margin-bottom: 0.9rem;
    ">1</div>
    <h3 style="font-size: 0.95rem; font-weight: 700; margin: 0 0 0.5rem 0;">Pick any model</h3>
    <p style="color: #8b949e; line-height: 1.65; font-size: 0.87rem; margin: 0;">
      Search 1M+ HuggingFace models by name, or choose from the curated catalogue —
      Llama 4, Qwen 3, DeepSeek-R1, Gemma 3, and more.
      Disk size and GPU count auto-fill.
    </p>
  </div>
  <div style="padding: 1.5rem; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.07); border-radius: 10px;">
    <div style="
      display: inline-block;
      width: 2rem; height: 2rem; line-height: 2rem; text-align: center;
      background: rgba(88,166,255,0.12); border-radius: 50%;
      font-size: 0.85rem; font-weight: 800; color: #58a6ff;
      margin-bottom: 0.9rem;
    ">2</div>
    <h3 style="font-size: 0.95rem; font-weight: 700; margin: 0 0 0.5rem 0;">Configure and deploy</h3>
    <p style="color: #8b949e; line-height: 1.65; font-size: 0.87rem; margin: 0;">
      Choose GPU platform (H200 · B200 · RTX 6000) and inference engine (vLLM · SGLang).
      Click Create Endpoint — Nebius provisions the VM, pulls weights, starts the server.
    </p>
  </div>
  <div style="padding: 1.5rem; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.07); border-radius: 10px;">
    <div style="
      display: inline-block;
      width: 2rem; height: 2rem; line-height: 2rem; text-align: center;
      background: rgba(88,166,255,0.12); border-radius: 50%;
      font-size: 0.85rem; font-weight: 800; color: #58a6ff;
      margin-bottom: 0.9rem;
    ">3</div>
    <h3 style="font-size: 0.95rem; font-weight: 700; margin: 0 0 0.5rem 0;">Benchmark runs automatically</h3>
    <p style="color: #8b949e; line-height: 1.65; font-size: 0.87rem; margin: 0;">
      The full suite fires once the endpoint is ready: TTFT, ITL, latency distribution,
      throughput, and a concurrency sweep up to 50 users.
      Results save to a local SQLite database.
    </p>
  </div>
  <div style="padding: 1.5rem; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.07); border-radius: 10px;">
    <div style="
      display: inline-block;
      width: 2rem; height: 2rem; line-height: 2rem; text-align: center;
      background: rgba(88,166,255,0.12); border-radius: 50%;
      font-size: 0.85rem; font-weight: 800; color: #58a6ff;
      margin-bottom: 0.9rem;
    ">4</div>
    <h3 style="font-size: 0.95rem; font-weight: 700; margin: 0 0 0.5rem 0;">Download and delete</h3>
    <p style="color: #8b949e; line-height: 1.65; font-size: 0.87rem; margin: 0;">
      Export as HTML, JSON, or Markdown. Delete the endpoint in one click —
      billed only for the time the VM ran. No long-running infrastructure costs.
    </p>
  </div>
</div>
""")

st.divider()


# ── GPU platform cards ─────────────────────────────────────────────────────────

gpu_logo_col, gpu_text_col = st.columns([1, 8])
with gpu_logo_col:
    st.image(str(ASSETS / "nebius-logo-white.png"), use_container_width=True)
with gpu_text_col:
    st.html("""
    <h2 style="font-size: 1.6rem; font-weight: 700; margin: 0 0 0.3rem 0;">Nebius GPU Platforms</h2>
    <p style="color: #8b949e; margin: 0; font-size: 0.95rem;">
      All endpoints run on Nebius AI Cloud. Switch platforms between runs to compare price/performance directly.
    </p>
    """)

st.html("""
<div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.25rem; margin-top: 1.25rem; margin-bottom: 0.5rem;">

  <div style="padding: 1.75rem; background: rgba(63,185,80,0.06); border: 1px solid rgba(63,185,80,0.28); border-radius: 10px;">
    <div style="font-size: 0.72rem; font-weight: 700; color: #3fb950; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.6rem;">★ Recommended</div>
    <h3 style="font-size: 1.1rem; font-weight: 700; margin: 0 0 1.1rem 0;">NVIDIA® H200 SXM</h3>
    <div style="display: flex; gap: 2rem; margin-bottom: 1.1rem;">
      <div>
        <div style="font-size: 1.6rem; font-weight: 800; color: #3fb950; line-height: 1;">$2.45</div>
        <div style="font-size: 0.75rem; color: #8b949e; margin-top: 0.15rem;">per GPU / hr</div>
      </div>
      <div>
        <div style="font-size: 1.6rem; font-weight: 800; line-height: 1;">141 GB</div>
        <div style="font-size: 0.75rem; color: #8b949e; margin-top: 0.15rem;">NVLink VRAM</div>
      </div>
    </div>
    <p style="color: #8b949e; font-size: 0.87rem; line-height: 1.6; margin: 0;">
      Best price/performance ratio. Fits all single-GPU models up to 70B in BF16.
      NVLink fabric for fast multi-GPU on 8-GPU presets. Best starting point for any benchmark.
    </p>
    <div style="margin-top: 1rem; padding: 0.5rem 0.75rem; background: rgba(63,185,80,0.08); border-radius: 6px; font-size: 0.8rem; color: #3fb950;">
      Best for: 7B – 70B models
    </div>
  </div>

  <div style="padding: 1.75rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;">
    <div style="font-size: 0.72rem; font-weight: 700; color: #6e7681; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.6rem;">Highest Memory</div>
    <h3 style="font-size: 1.1rem; font-weight: 700; margin: 0 0 1.1rem 0;">NVIDIA® B200 SXM</h3>
    <div style="display: flex; gap: 2rem; margin-bottom: 1.1rem;">
      <div>
        <div style="font-size: 1.6rem; font-weight: 800; color: #e6edf3; line-height: 1;">$3.95</div>
        <div style="font-size: 0.75rem; color: #8b949e; margin-top: 0.15rem;">per GPU / hr</div>
      </div>
      <div>
        <div style="font-size: 1.6rem; font-weight: 800; line-height: 1;">180 GB</div>
        <div style="font-size: 0.75rem; color: #8b949e; margin-top: 0.15rem;">NVLink VRAM</div>
      </div>
    </div>
    <p style="color: #8b949e; font-size: 0.87rem; line-height: 1.6; margin: 0;">
      Extra 39 GB over H200 means more KV cache headroom for long contexts and fewer 8-GPU splits.
      Blackwell architecture outperforms H200 on FP8 workloads.
    </p>
    <div style="margin-top: 1rem; padding: 0.5rem 0.75rem; background: rgba(255,255,255,0.04); border-radius: 6px; font-size: 0.8rem; color: #8b949e;">
      Best for: 70B+ and large MoE models
    </div>
  </div>

  <div style="padding: 1.75rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;">
    <div style="font-size: 0.72rem; font-weight: 700; color: #6e7681; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.6rem;">Budget Option</div>
    <h3 style="font-size: 1.1rem; font-weight: 700; margin: 0 0 1.1rem 0;">NVIDIA® RTX PRO 6000</h3>
    <div style="display: flex; gap: 2rem; margin-bottom: 1.1rem;">
      <div>
        <div style="font-size: 1.6rem; font-weight: 800; color: #e6edf3; line-height: 1;">$0.95</div>
        <div style="font-size: 0.75rem; color: #8b949e; margin-top: 0.15rem;">per GPU / hr</div>
      </div>
      <div>
        <div style="font-size: 1.6rem; font-weight: 800; line-height: 1;">96 GB</div>
        <div style="font-size: 0.75rem; color: #8b949e; margin-top: 0.15rem;">VRAM</div>
      </div>
    </div>
    <p style="color: #8b949e; font-size: 0.87rem; line-height: 1.6; margin: 0;">
      Most affordable at $0.95/hr — ideal for small-model benchmarks and cost-sensitive experiments.
      ⚠️ Use vLLM only; SGLang's FlashInfer kernels target H100/H200 architecture.
    </p>
    <div style="margin-top: 1rem; padding: 0.5rem 0.75rem; background: rgba(255,255,255,0.04); border-radius: 6px; font-size: 0.8rem; color: #8b949e;">
      Best for: ≤ 30B models · vLLM only
    </div>
  </div>

</div>
""")

st.divider()


# ── Bottom CTA ─────────────────────────────────────────────────────────────────

cta_logo, cta_text = st.columns([1, 6])
with cta_logo:
    st.image(str(ASSETS / "nebius-logo-white.png"), use_container_width=True)
with cta_text:
    st.html("""
    <h2 style="font-size: 1.5rem; font-weight: 700; margin: 0 0 0.4rem 0;">Ready to benchmark?</h2>
    <p style="color: #8b949e; margin: 0; font-size: 0.95rem;">
      Deploy a model, run the suite, and have a report in under 15 minutes.
      No infrastructure to manage. No long-running costs. Just data.
    </p>
    """)

b1, b2, b3, _ = st.columns([2, 2, 2, 2])
with b1:
    st.page_link("pages/1_Deploy_and_Run.py", label="🚀 Deploy & benchmark",    use_container_width=True)
with b2:
    st.page_link("pages/0_Models.py",          label="🤗 Explore models",        use_container_width=True)
with b3:
    st.page_link("pages/challenge.py",         label="🏆 Builders Challenge",    use_container_width=True)
