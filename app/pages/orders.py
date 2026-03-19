import streamlit as st
import pandas as pd
from app.engine import get_rm_order_requirements


def render():
    st.title("Order Requirements")
    st.caption("Total raw material needed across all products, with MOQ and inventory analysis")

    orders = get_rm_order_requirements()

    # Filter to only materials that are actually needed
    needed = [r for r in orders if r['total_grams_needed'] > 0]

    if not needed:
        st.info("No order requirements. Add SKUs with pack counts first.")
        return

    # Summary metrics
    total_cost = sum(r['actual_cost'] for r in needed)
    total_surplus = sum(r['surplus_cost'] for r in needed)
    to_buy = [r for r in needed if r['shortfall_grams'] > 0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total RM Cost", f"Rs {total_cost:,.0f}")
    c2.metric("With GST (18%)", f"Rs {total_cost * 1.18:,.0f}")
    c3.metric("MOQ Surplus Cost", f"Rs {total_surplus:,.0f}")
    c4.metric("Materials to Buy", len(to_buy))

    st.markdown("---")

    # Filter options
    c1, c2 = st.columns(2)
    with c1:
        show_filter = st.radio("Show", ["All Needed", "To Buy Only", "MOQ Surplus Only"],
                               horizontal=True)
    with c2:
        sort_by = st.selectbox("Sort by", ["Cost (high to low)", "Name", "Shortfall (high to low)"])

    filtered = needed
    if show_filter == "To Buy Only":
        filtered = [r for r in filtered if r['shortfall_grams'] > 0]
    elif show_filter == "MOQ Surplus Only":
        filtered = [r for r in filtered if r['surplus_kg'] > 0]

    if sort_by == "Cost (high to low)":
        filtered.sort(key=lambda x: x['actual_cost'], reverse=True)
    elif sort_by == "Shortfall (high to low)":
        filtered.sort(key=lambda x: x['shortfall_grams'], reverse=True)
    else:
        filtered.sort(key=lambda x: x['raw_material'])

    # Main table
    rows = []
    for r in filtered:
        status = "Sufficient" if r['inventory_status'] == 'sufficient' else (
            "Partial" if r['inventory_status'] == 'partial' else "None")
        rows.append({
            'Raw Material': r['raw_material'],
            'Category': r['category'],
            'Needed (kg)': round(r['total_kg_needed'], 3),
            'MOQ (kg)': r['moq_kg'],
            'Order (kg)': round(r['order_kg'], 3),
            'Rate/KG': f"Rs {r['rate_per_kg']:,.0f}",
            'Total Cost': f"Rs {r['actual_cost']:,.0f}",
            'Surplus (kg)': round(r['surplus_kg'], 3) if r['surplus_kg'] > 0 else '-',
            'Surplus Cost': f"Rs {r['surplus_cost']:,.0f}" if r['surplus_cost'] > 0 else '-',
            'Stock (g)': r['inventory_grams'],
            'Shortfall (g)': round(r['shortfall_grams'], 0) if r['shortfall_grams'] > 0 else '-',
            'Status': status,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(filtered)} materials")

    # Product breakdown for selected material
    st.markdown("---")
    st.subheader("Product Breakdown")
    rm_options = {r['raw_material']: r for r in needed}
    selected = st.selectbox("Select raw material", [""] + list(rm_options.keys()))

    if selected:
        rm = rm_options[selected]
        if rm['product_breakdown']:
            rows = []
            for pb in sorted(rm['product_breakdown'], key=lambda x: x['grams_needed'], reverse=True):
                rows.append({
                    'Product': pb['product'],
                    'Grams/Unit': pb['grams_per_unit'],
                    'Total Units': f"{pb['total_units']:,}",
                    'Grams Needed': f"{pb['grams_needed']:,.1f}",
                    'KG Needed': f"{pb['grams_needed']/1000:.3f}",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.write(f"**Total needed**: {rm['total_kg_needed']:.3f} kg")
            st.write(f"**MOQ**: {rm['moq_kg']} kg")
            if rm['surplus_kg'] > 0:
                st.warning(f"MOQ surplus: {rm['surplus_kg']:.3f} kg (Rs {rm['surplus_cost']:,.0f} extra)")
