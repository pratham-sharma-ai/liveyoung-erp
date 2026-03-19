import streamlit as st
import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('LiveYoung')

# Ensure app module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

st.set_page_config(
    page_title="LiveYoung - Manufacturing ERP",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.db import init_db

# Initialize DB on first run
try:
    logger.info("Initializing database connection...")
    init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Database init failed: {e}")
    st.error(f"Failed to connect to database: {e}")

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
    from app.views.dashboard import render
    render()
elif page == "Raw Materials":
    from app.views.raw_materials import render
    render()
elif page == "Products & Formulations":
    from app.views.formulations import render
    render()
elif page == "SKUs & Launch Plan":
    from app.views.skus import render
    render()
elif page == "Costing & Pricing":
    from app.views.costing import render
    render()
elif page == "Order Requirements":
    from app.views.orders import render
    render()
elif page == "Inventory":
    from app.views.inventory import render
    render()
