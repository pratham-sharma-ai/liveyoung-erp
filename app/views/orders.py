import streamlit as st
import pandas as pd
from app.engine import get_rm_order_requirements


def _fmt_rs(value):
    """Format as Rs X,XX,XXX."""
    if value is None or value == 0:
        return "Rs 0"
    return f"Rs {value:,.0f}"


def render():
    st.markdown("#### \U0001f6d2 Order Requirements")
    st.caption("Total raw material needed across all products, with MOQ and inventory analysis")

    with st.spinner("Calculating order requirements..."):
        orders = get_rm_order_requirements()

    # Filter to only materials that are actually needed
    needed = [r for r in orders if r['total_grams_needed'] > 0]

    if not needed:
        st.info("No order requirements. Add SKUs with pack counts first.")
        return

    # ------------------------------------------------------------------
    # Summary banner
    # ------------------------------------------------------------------
    total_cost = sum(r['actual_cost'] for r in needed)
    total_surplus = sum(r['surplus_cost'] for r in needed)
    to_buy = [r for r in needed if r['shortfall_grams'] > 0]
    in_stock = [r for r in needed if r['inventory_status'] == 'sufficient']

    st.markdown("""
    <div style="background: linear-gradient(135deg, #0D6EFD 0%, #0D47A1 100%);
                border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 0.5rem;">
            <div style="text-align: center; color: white;">
                <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.85;">Total Procurement</div>
                <div style="font-size: 1.5rem; font-weight: 700;">""" + _fmt_rs(total_cost) + """</div>
            </div>
            <div style="text-align: center; color: white;">
                <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.85;">With GST (18%)</div>
                <div style="font-size: 1.5rem; font-weight: 700;">""" + _fmt_rs(total_cost * 1.18) + """</div>
            </div>
            <div style="text-align: center; color: white;">
                <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.85;">MOQ Surplus</div>
                <div style="font-size: 1.5rem; font-weight: 700;">""" + _fmt_rs(total_surplus) + """</div>
            </div>
            <div style="text-align: center; color: white;">
                <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.85;">Items to Buy</div>
                <div style="font-size: 1.5rem; font-weight: 700;">""" + str(len(to_buy)) + """ / """ + str(len(needed)) + """</div>
            </div>
            <div style="text-align: center; color: white;">
                <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.85;">In Stock</div>
                <div style="font-size: 1.5rem; font-weight: 700;">""" + str(len(in_stock)) + """</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Filter controls
    # ------------------------------------------------------------------
    c1, c2 = st.columns(2)
    with c1:
        show_filter = st.radio(
            "Show",
            ["All Needed", "To Buy Only", "MOQ Surplus Only", "In Stock Only"],
            horizontal=True,
        )
    with c2:
        sort_by = st.selectbox(
            "Sort by",
            ["Cost (high to low)", "Name", "Shortfall (high to low)"],
        )

    filtered = needed
    if show_filter == "To Buy Only":
        filtered = [r for r in filtered if r['shortfall_grams'] > 0]
    elif show_filter == "MOQ Surplus Only":
        filtered = [r for r in filtered if r['surplus_kg'] > 0]
    elif show_filter == "In Stock Only":
        filtered = [r for r in filtered if r['inventory_status'] == 'sufficient']

    if sort_by == "Cost (high to low)":
        filtered.sort(key=lambda x: x['actual_cost'], reverse=True)
    elif sort_by == "Shortfall (high to low)":
        filtered.sort(key=lambda x: x['shortfall_grams'], reverse=True)
    else:
        filtered.sort(key=lambda x: x['raw_material'])

    # ------------------------------------------------------------------
    # Color-coded main table
    # ------------------------------------------------------------------
    rows = []
    for r in filtered:
        if r['inventory_status'] == 'sufficient':
            status = "\U0001f7e2 In Stock"
        elif r['inventory_status'] == 'partial':
            status = "\U0001f7e1 Partial"
        else:
            status = "\U0001f534 Order"

        rows.append({
            'Status': status,
            'Raw Material': r['raw_material'],
            'Category': r['category'],
            'Needed (kg)': f"{r['total_kg_needed']:.2f}",
            'MOQ (kg)': f"{r['moq_kg']:.0f}",
            'Order (kg)': f"{r['order_kg']:.2f}",
            'Rate/KG': _fmt_rs(r['rate_per_kg']),
            'Total Cost': _fmt_rs(r['actual_cost']),
            'Surplus (kg)': f"{r['surplus_kg']:.2f}" if r['surplus_kg'] > 0 else '-',
            'Surplus Cost': _fmt_rs(r['surplus_cost']) if r['surplus_cost'] > 0 else '-',
            'Stock (g)': f"{r['inventory_grams']:,.0f}" if r['inventory_grams'] > 0 else '-',
            'Shortfall (g)': f"{r['shortfall_grams']:,.0f}" if r['shortfall_grams'] > 0 else '-',
        })

    df = pd.DataFrame(rows)

    # Apply row coloring via pandas Styler
    def _color_rows(row):
        if '\U0001f7e2' in str(row['Status']):
            return ['background-color: #D4EDDA;'] * len(row)
        elif '\U0001f7e1' in str(row['Status']):
            return ['background-color: #FFF3CD;'] * len(row)
        elif '\U0001f534' in str(row['Status']):
            return ['background-color: #F8D7DA;'] * len(row)
        return [''] * len(row)

    styled = df.style.apply(_color_rows, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=min(600, len(filtered) * 38 + 40))
    st.caption(f"Showing {len(filtered)} of {len(needed)} materials")

    # ------------------------------------------------------------------
    # Product breakdown for selected material
    # ------------------------------------------------------------------
    st.markdown("---")
    st.markdown("##### Product Breakdown by Material")
    rm_options = {r['raw_material']: r for r in needed}
    selected = st.selectbox("Select raw material", [""] + list(rm_options.keys()))

    if selected:
        rm = rm_options[selected]

        # Info banner for selected RM
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Needed", f"{rm['total_kg_needed']:.3f} kg")
        c2.metric("MOQ", f"{rm['moq_kg']} kg")
        c3.metric("Order Cost", _fmt_rs(rm['actual_cost']))
        c4.metric("Stock", f"{rm['inventory_grams']:,.0f} g")

        if rm['surplus_kg'] > 0:
            st.warning(f"MOQ surplus: {rm['surplus_kg']:.3f} kg ({_fmt_rs(rm['surplus_cost'])} extra)")

        if rm['product_breakdown']:
            rows = []
            for pb in sorted(rm['product_breakdown'], key=lambda x: x['grams_needed'], reverse=True):
                rows.append({
                    'Product': pb['product'],
                    'Grams/Unit': f"{pb['grams_per_unit']:.4f}",
                    'Total Units': f"{pb['total_units']:,}",
                    'Grams Needed': f"{pb['grams_needed']:,.1f}",
                    'KG Needed': f"{pb['grams_needed'] / 1000:.3f}",
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )
