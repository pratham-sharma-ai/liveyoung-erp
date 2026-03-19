import streamlit as st
import os
import sys

# Ensure app module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db import init_db

# Initialize DB on first run
init_db()

st.set_page_config(
    page_title="LiveYoung - Manufacturing ERP",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for cleaner look
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .stMetric { background: #f8f9fa; padding: 10px; border-radius: 8px; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 16px; }
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("LiveYoung ERP")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Raw Materials", "Products & Formulations",
     "SKUs & Launch Plan", "Costing & Pricing", "Order Requirements",
     "Inventory"],
    label_visibility="collapsed",
)

# Route to pages
if page == "Dashboard":
    from app.pages.dashboard import render
    render()
elif page == "Raw Materials":
    from app.pages.raw_materials import render
    render()
elif page == "Products & Formulations":
    from app.pages.formulations import render
    render()
elif page == "SKUs & Launch Plan":
    from app.pages.skus import render
    render()
elif page == "Costing & Pricing":
    from app.pages.costing import render
    render()
elif page == "Order Requirements":
    from app.pages.orders import render
    render()
elif page == "Inventory":
    from app.pages.inventory import render
    render()
