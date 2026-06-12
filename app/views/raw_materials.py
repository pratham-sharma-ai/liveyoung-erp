import streamlit as st
import pandas as pd
from app.db import fetch_all, execute, execute_returning


def _fmt_rs(value):
    if value is None or value == 0:
        return "-"
    return f"Rs {value:,.0f}"


def render():
    st.markdown("#### \U0001f9ea Raw Materials")

    tab1, tab2 = st.tabs(["\U0001f4cb  View All", "\U00002795  Add New"])

    with tab1:
        with st.spinner("Loading raw materials..."):
            materials = fetch_all("""
                SELECT rm.*,
                       COALESCE(inv.qty_grams, 0) as stock_grams
                FROM raw_materials rm
                LEFT JOIN inventory inv ON inv.raw_material_id = rm.id
                ORDER BY rm.name
            """)

        if materials:
            # Summary metrics
            total = len(materials)
            in_stock = sum(1 for m in materials if m['stock_grams'] > 0)
            avg_rate = sum(m['rate_per_kg'] for m in materials if m['rate_per_kg']) / max(1, sum(1 for m in materials if m['rate_per_kg']))

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Materials", total)
            c2.metric("In Stock", f"{in_stock} of {total}")
            c3.metric("Avg Rate/KG", _fmt_rs(avg_rate))

            st.markdown("---")

            # Filters
            c1, c2 = st.columns(2)
            categories = sorted(set(m['category'] for m in materials if m['category']))
            with c1:
                cat_filter = st.multiselect("Filter by Category", categories)
            with c2:
                search = st.text_input("Search by name", placeholder="Type to search...")

            filtered = materials
            if cat_filter:
                filtered = [m for m in filtered if m['category'] in cat_filter]
            if search:
                filtered = [m for m in filtered if search.lower() in m['name'].lower()]

            rows = []
            for m in filtered:
                rows.append({
                    'Name': m['name'],
                    'MOQ (kg)': m['moq_kg'],
                    'Rate/KG': _fmt_rs(m['rate_per_kg']),
                    'Category': m['category'],
                    'Source': m['source'],
                    'Stock (g)': f"{m['stock_grams']:,.0f}" if m['stock_grams'] > 0 else '-',
                    'Negotiator': m['negotiator'],
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(filtered)} of {total} raw materials")

            # Edit section
            st.markdown("---")
            st.markdown("##### Edit Raw Material")
            rm_names = {m['name']: m['id'] for m in materials}
            selected = st.selectbox("Select material to edit", [""] + list(rm_names.keys()))

            if selected:
                rm = next(m for m in materials if m['name'] == selected)
                with st.form(f"edit_rm_{rm['id']}"):
                    c1, c2, c3 = st.columns(3)
                    name = c1.text_input("Name", rm['name'])
                    moq = c2.number_input("MOQ (kg)", value=float(rm['moq_kg']), min_value=0.0, step=0.5)
                    rate = c3.number_input("Rate/KG (Rs)", value=float(rm['rate_per_kg']), min_value=0.0, step=10.0)

                    c1, c2, c3 = st.columns(3)
                    category = c1.text_input("Category", rm['category'])
                    source = c2.text_input("Source", rm['source'])
                    negotiator = c3.text_input("Negotiator", rm['negotiator'])

                    c1, c2, c3 = st.columns(3)
                    v1 = c1.text_input("Vendor 1", rm['vendor1'])
                    v2 = c2.text_input("Vendor 2", rm['vendor2'])
                    v3 = c3.text_input("Vendor 3", rm['vendor3'])

                    remarks = st.text_input("Remarks", rm['remarks'])

                    if st.form_submit_button("Update", type="primary"):
                        execute("""
                            UPDATE raw_materials SET
                                name=?, moq_kg=?, rate_per_kg=?, category=?,
                                source=?, negotiator=?, vendor1=?, vendor2=?, vendor3=?, remarks=?
                            WHERE id=?
                        """, (name, moq, rate, category, source, negotiator,
                              v1, v2, v3, remarks, rm['id']))
                        st.success(f"Updated {name}")
                        st.rerun()
        else:
            st.info("No raw materials found. Add your first material below.")

    with tab2:
        with st.form("add_rm"):
            st.markdown("##### Add New Raw Material")
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name")
            moq = c2.number_input("MOQ (kg)", min_value=0.0, step=0.5)
            rate = c3.number_input("Rate/KG (Rs)", min_value=0.0, step=10.0)

            c1, c2, c3 = st.columns(3)
            category = c1.text_input("Category (Active/Filler/Sweetener/etc.)")
            source = c2.text_input("Source (Natural/Synthetic)")
            negotiator = c3.text_input("Negotiator")

            if st.form_submit_button("Add Raw Material", type="primary"):
                if name:
                    try:
                        execute_returning("""
                            INSERT INTO raw_materials (name, moq_kg, rate_per_kg, category, source, negotiator)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (name, moq, rate, category, source, negotiator))
                        st.success(f"Added {name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Name is required")
