#!/usr/bin/env python3
"""Legacy Streamlit launcher — use the web UI instead (`python scripts/run_web.py`)."""
import streamlit as st

st.set_page_config(page_title="Utility Coordinator", page_icon="⚡")
st.title("Utility Coordinator AI")
st.success("The primary interface is now the web application.")
st.code("python scripts/run_web.py", language="bash")
st.markdown("Open **[http://localhost:8080](http://localhost:8080)** after starting the server.")
