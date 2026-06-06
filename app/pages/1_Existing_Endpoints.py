"""Redirects to the new Endpoint Management page."""
import streamlit as st
st.set_page_config(page_title="Moved", page_icon="📡")
st.info("This page has moved to **Endpoint Management** (page 6).")
st.page_link("pages/6_Endpoint_Management.py", label="Go to Endpoint Management →")
