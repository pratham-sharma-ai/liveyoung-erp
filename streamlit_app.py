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
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="LiveYoung - Manufacturing ERP",
    page_icon="\U0001f3ed",
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

# ---------------------------------------------------------------------------
# Global CSS — professional, clean, finance-friendly
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Tighten top padding */
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }

    /* Metric cards */
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; color: #555; }
    div[data-testid="stMetricDelta"] { font-size: 0.8rem; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 20px; font-weight: 600; }

    /* Sidebar branding */
    section[data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem; }
    .sidebar-brand { text-align: center; padding: 1.2rem 0 0.5rem 0; }
    .sidebar-brand h1 { font-size: 1.5rem; font-weight: 800; color: #0D6EFD; margin: 0; letter-spacing: -0.02em; }
    .sidebar-brand p { font-size: 0.72rem; color: #888; margin: 0.15rem 0 0 0; text-transform: uppercase; letter-spacing: 0.12em; font-weight: 600; }
    .sidebar-divider { border: none; border-top: 1px solid #E0E0E0; margin: 0.6rem 0 0.4rem 0; }

    /* Navigation radio buttons — cleaner look */
    div[data-testid="stSidebar"] .stRadio > label { display: none; }
    div[data-testid="stSidebar"] .stRadio > div { gap: 2px; }
    div[data-testid="stSidebar"] .stRadio > div > label {
        padding: 0.55rem 1rem;
        border-radius: 6px;
        font-size: 0.88rem;
        font-weight: 500;
        transition: background 0.15s;
    }
    div[data-testid="stSidebar"] .stRadio > div > label:hover { background: rgba(13,110,253,0.06); }

    /* Footer */
    .app-footer {
        position: fixed; bottom: 0; left: 0; width: 100%;
        background: #F8F9FA; border-top: 1px solid #E0E0E0;
        padding: 6px 0; text-align: center; z-index: 999;
        font-size: 0.72rem; color: #999;
    }

    /* Dataframe tweaks */
    .stDataFrame { border-radius: 6px; }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <h1>\U0001f3ed LiveYoung</h1>
        <p>Manufacturing ERP</p>
    </div>
    <hr class="sidebar-divider">
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        [
            "\U0001f4ca  Dashboard",
            "\U0001f9ea  Raw Materials",
            "\U0001f9ec  Products & Formulations",
            "\U0001f4e6  SKUs & Launch Plan",
            "\U0001f4b0  Costing & Pricing",
            "\U0001f6d2  Order Requirements",
            "\U0001f4cb  Inventory",
            "⚙️  Assumptions",
        ],
        label_visibility="collapsed",
    )

    st.markdown("<hr class='sidebar-divider'>", unsafe_allow_html=True)
    st.caption("v2.0  |  Data: Google Sheets")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="app-footer">LiveYoung Nutraceuticals  &middot;  Manufacturing ERP  &middot;  Powered by Streamlit</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------
# Strip emoji prefix for matching
page_key = page.split("  ", 1)[-1].strip() if "  " in page else page

if page_key == "Dashboard":
    from app.views.dashboard import render
    render()
elif page_key == "Raw Materials":
    from app.views.raw_materials import render
    render()
elif page_key == "Products & Formulations":
    from app.views.formulations import render
    render()
elif page_key == "SKUs & Launch Plan":
    from app.views.skus import render
    render()
elif page_key == "Costing & Pricing":
    from app.views.costing import render
    render()
elif page_key == "Order Requirements":
    from app.views.orders import render
    render()
elif page_key == "Inventory":
    from app.views.inventory import render
    render()
elif page_key == "Assumptions":
    from app.views.assumptions import render
    render()
