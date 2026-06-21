"""Nebius Endpoint Lab — navigation entrypoint."""

from pathlib import Path
import streamlit as st

ASSETS = Path(__file__).parent / "assets"

st.logo(
    str(ASSETS / "nebius-logo-white.png"),
    link="https://nebius.com",
    icon_image=str(ASSETS / "nebius-logo-white.png"),
)

pg = st.navigation(
    {
        "": [
            st.Page("pages/home_dashboard.py",  title="Home",                    icon="🏠", default=True),
            st.Page("pages/challenge.py",        title="Builders Challenge",      icon="🏆"),
            st.Page("pages/0_Models.py",         title="Models",                  icon="🤗"),
            st.Page("pages/1_Deploy_and_Run.py", title="Deploy & Run",        icon="🚀"),
            st.Page("pages/2_Endpoint_Management.py", title="Endpoint Management", icon="⚙️"),
        ],
        "Benchmark": [
            st.Page("pages/3_Benchmark_History.py",    title="Benchmark History",    icon="📋"),
            st.Page("pages/4_Compare_Runs.py",         title="Compare Runs",         icon="🔍"),
            st.Page("pages/5_Concurrency_Analysis.py", title="Concurrency Analysis", icon="📈"),
            st.Page("pages/6_Report_Center.py",        title="Report Center",        icon="📄"),
        ],
    }
)

pg.run()
