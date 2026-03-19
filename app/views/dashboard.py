import streamlit as st
import pandas as pd
from app.engine import get_dashboard_summary


def render():
    st.title("Dashboard")

    with st.spinner("Loading dashboard..."):
        summary = get_dashboard_summary()

    # Top-level metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Products", summary['active_products'], f"of {summary['total_products']} total")
    c2.metric("Total SKUs", summary['total_skus'])
    c3.metric("Total Packs", f"{summary['total_packs']:,}")
    c4.metric("RM to Procure", summary['rms_to_buy_count'])

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total RM Cost", f"Rs {summary['total_rm_cost']:,.0f}")
        st.caption(f"With 18% GST: Rs {summary['total_rm_cost_with_gst']:,.0f}")
    with c2:
        st.metric("MOQ Surplus Cost", f"Rs {summary['total_surplus_cost']:,.0f}")
        st.caption("Extra cost from buying minimum order quantities")

    st.markdown("---")

    # Phase summary
    if summary['phase_counts']:
        st.subheader("Launch Phases")
        phase_cols = st.columns(len(summary['phase_counts']))
        for i, (phase, count) in enumerate(sorted(summary['phase_counts'].items())):
            phase_cols[i].metric(f"Phase {phase}", f"{count} SKUs")

    st.markdown("---")

    # Product costing overview
    st.subheader("Product Costing Overview")
    if summary['costings']:
        rows = []
        for c in summary['costings']:
            rows.append({
                'Product': c['product']['base_code'],
                'Category': c['product']['category'],
                'Form': c['product']['delivery_form'],
                'Packs': c['total_packs'],
                'RM Cost/Pack': c['pack_rm_cost'],
                'PM Cost/Pack': c['pack_pm_cost'],
                'Net Total': c['net_total'],
                'Margin %': f"{c['margin_percent']*100:.0f}%",
                'Selling Price': c['selling_price'],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # RM needing procurement
    st.subheader("Raw Materials Needing Procurement")
    rms_to_buy = [r for r in summary['rm_orders']
                  if r['shortfall_grams'] > 0 and r['total_grams_needed'] > 0]
    if rms_to_buy:
        rows = []
        for r in sorted(rms_to_buy, key=lambda x: x['actual_cost'], reverse=True):
            rows.append({
                'Raw Material': r['raw_material'],
                'Needed (kg)': round(r['total_kg_needed'], 2),
                'MOQ (kg)': r['moq_kg'],
                'Order (kg)': r['order_kg'],
                'Cost': f"Rs {r['actual_cost']:,.0f}",
                'Surplus Cost': f"Rs {r['surplus_cost']:,.0f}" if r['surplus_cost'] > 0 else '-',
                'In Stock (g)': r['inventory_grams'],
                'Shortfall (g)': r['shortfall_grams'],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.success("All raw materials sufficiently stocked!")
