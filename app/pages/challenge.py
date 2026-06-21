"""Serverless AI Builders Challenge."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = Path(__file__).parent.parent / "assets"

st.set_page_config(
    page_title="Builders Challenge · Nebius Endpoint Lab",
    page_icon="🏆",
    layout="wide",
)

# ── Hero ──────────────────────────────────────────────────────────────────────

col_logo, col_hero = st.columns([1, 5])
with col_logo:
    st.image(str(ASSETS / "nebius-logo-white.png"), use_container_width=True)
with col_hero:
    st.caption("COMMUNITY COMPETITION")
    st.title("Serverless AI Builders Challenge")

st.markdown("""
Nebius Serverless AI makes GPU and CPU accelerated compute accessible without managing clusters
or long-running infrastructure. Run a job, serve a model, pay only for what you use.

**Build with Serverless AI. Share with the community. Win.**
""")

st.divider()

# ── About ─────────────────────────────────────────────────────────────────────

col_about, col_badge = st.columns([3, 1])

with col_about:
    st.markdown("""
The **Serverless AI Builders Challenge** is a community competition for ML engineers,
applied researchers, and data scientists. Build a reproducible AI or ML project using
**Nebius Serverless AI Jobs**, **Serverless AI Endpoints**, or both.
Publish your code, explain your approach in a technical blog post, and help other practitioners
learn from your work.

Whether you are running batch inference, building an evaluation pipeline, deploying an LLM endpoint,
creating a RAG application, or automating an agentic workflow — we want to see practical examples
that others can run, adapt, and learn from.
""")

with col_badge:
    st.markdown("""
<div style="
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 14px;
    padding: 24px 20px;
    background: linear-gradient(145deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
    text-align: center;
    height: 100%;
">
    <div style="font-size: 11px; letter-spacing: 2.5px; color: #888; margin-bottom: 16px; text-transform: uppercase;">In Partnership With</div>
    <div style="font-size: 36px; margin-bottom: 10px;">🎓</div>
    <div style="font-size: 17px; font-weight: 700; margin-bottom: 8px; color: #fff;">Nebius Academy</div>
    <div style="font-size: 12px; color: #999; line-height: 1.6;">The education &amp; research hub of Nebius — connecting real engineering with applied AI learning.</div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Why participate ───────────────────────────────────────────────────────────

st.header("Why Participate?")

w1, w2, w3, w4, w5 = st.columns(5)

with w1:
    with st.container(border=True):
        st.markdown("### 💰")
        st.markdown("**Win up to $2,000**")
        st.caption("In Nebius credits, plus badges, swag, and a featured spotlight on the Nebius blog and docs")

with w2:
    with st.container(border=True):
        st.markdown("### 🎁")
        st.markdown("**$100 Guaranteed**")
        st.caption("Every valid submission earns $100 in Nebius credits — no matter where you place")

with w3:
    with st.container(border=True):
        st.markdown("### 🛠️")
        st.markdown("**Hands-on Experience**")
        st.caption("Get real experience with Nebius Serverless AI infrastructure on production-grade GPUs")

with w4:
    with st.container(border=True):
        st.markdown("### ✍️")
        st.markdown("**Publish Your Work**")
        st.caption("Ship a technical blog post that showcases your skills to the broader ML community")

with w5:
    with st.container(border=True):
        st.markdown("### ⭐")
        st.markdown("**Awesome Projects**")
        st.caption("Earn a spot in the Nebius Awesome Serverless Projects library")

st.divider()

# ── What to build ─────────────────────────────────────────────────────────────

st.header("What to Build")

st.markdown("""
Anything that uses **Nebius Serverless AI Jobs** or **Nebius Serverless AI Endpoints** to solve a real problem.
Your project should be reproducible by another practitioner following your README.
We welcome projects across three domains:
""")

tab_ai, tab_health, tab_robotics = st.tabs([
    "🤖 AI & ML / MLOps",
    "🧬 Healthcare & Life Sciences",
    "🦾 Physical AI & Robotics",
])

with tab_ai:
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("#### AI & ML")
            st.markdown("""
- Fine-tuning pipelines
- Model serving endpoints
- Evaluation harnesses
- RAG pipelines
- Data processing jobs
- Agentic and multi-agent workflows
- Benchmarking setups
""")
    with col2:
        with st.container(border=True):
            st.markdown("#### MLOps")
            st.markdown("""
- Classical ML (CPU only)
- Experiment tracking pipelines
- Model evaluation and regression testing
- CI/CD for ML models
- Dataset processing and curation
""")

with tab_health:
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("#### Inference & Endpoints")
            st.markdown("""
- Protein structure prediction inference
- Medical image segmentation endpoints
- Clinical text classification jobs
- Drug-target interaction scoring
""")
    with col2:
        with st.container(border=True):
            st.markdown("#### Batch & Pipelines")
            st.markdown("""
- Genomic variant processing pipelines
- Bioinformatics batch workflows
- Clinical trial data processing
- Multi-omics data integration jobs
""")

with tab_robotics:
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("#### Simulation & Inference")
            st.markdown("""
- Robot simulation batch jobs
- Sensor fusion inference endpoints
- Object detection and tracking pipelines
- Trajectory prediction models
""")
    with col2:
        with st.container(border=True):
            st.markdown("#### Transfer & Processing")
            st.markdown("""
- Sim-to-real transfer pipelines
- Digital twin data processing
- Point cloud segmentation jobs
- Reinforcement learning rollout jobs
""")

st.divider()

# ── Submission requirements ───────────────────────────────────────────────────

st.header("Submission Requirements")

r1, r2, r3 = st.columns(3)

with r1:
    with st.container(border=True):
        st.markdown("#### 💻 Code")
        st.markdown("""
- Public GitHub repository
- Reproducible setup (`README`, dependencies, env vars)
- Uses Nebius Serverless AI Jobs and/or Endpoints
- Clean, well-structured code
""")

with r2:
    with st.container(border=True):
        st.markdown("#### ✍️ Blog Post")
        st.markdown("""
- Technical writeup explaining your approach
- What problem you solved and why
- Architecture decisions and tradeoffs
- Results and what you learned
""")

with r3:
    with st.container(border=True):
        st.markdown("#### ✅ Reproducibility")
        st.markdown("""
- Another practitioner can follow your README and run it
- Dependencies pinned or clearly specified
- Any required credentials/tokens documented
- Example outputs or screenshots included
""")

st.divider()

# ── CTA ───────────────────────────────────────────────────────────────────────

st.subheader("Ready to build?")
st.markdown("Start by deploying a model endpoint and running your first benchmark right here.")

cta1, cta2, cta3 = st.columns(3)
with cta1:
    st.page_link("pages/1_Deploy_and_Run.py", label="🚀 Deploy your first endpoint", use_container_width=True)
with cta2:
    st.page_link("pages/0_Models.py", label="🤗 Browse available models", use_container_width=True)
with cta3:
    st.link_button("🌐 Learn about Nebius Serverless AI", "https://nebius.com/", use_container_width=True)
