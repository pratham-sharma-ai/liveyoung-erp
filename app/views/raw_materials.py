import streamlit as st
import pandas as pd
from app.db import fetch_all, execute, execute_returning


def render():
    st.title("Raw Materials")

    tab1, tab2 = st.tabs(["View All", "Add New"])

    with tab1:
        materials = fetch_all("""
            SELECT rm.*,
                   COALESCE(inv.qty_grams, 0) as stock_grams
            FROM raw_materials rm
            LEFT JOIN inventory inv ON inv.raw_material_id = rm.id
            ORDER BY rm.name
        """)

        if materials:
            # Filters
            c1, c2 = st.columns(2)
            categories = sorted(set(m['category'] for m in materials if m['category']))
            with c1:
                cat_filter = st.multiselect("Filter by Category", categories)
            with c2:
                search = st.text_input("Search by name")

            filtered = materials
            if cat_filter:
                filtered = [m for m in filtered if m['category'] in cat_filter]
            if search:
                filtered = [m for m in filtered if search.lower() in m['name'].lower()]

            rows = []
            for m in filtered:
                rows.append({
                    'ID': m['id'],
                    'Name': m['name'],
                    'MOQ (kg)': m['moq_kg'],
                    'Rate/KG (Rs)': f"{m['rate_per_kg']:,.0f}" if m['rate_per_kg'] else '-',
                    'Category': m['category'],
                    'Source': m['source'],
                    'Stock (g)': m['stock_grams'],
                    'Negotiator': m['negotiator'],
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(filtered)} of {len(materials)} raw materials")

            # Edit section
            st.markdown("---")
            st.subheader("Edit Raw Material")
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

                    if st.form_submit_button("Update"):
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
            st.info("No raw materials found.")

    with tab2:
        with st.form("add_rm"):
            st.subheader("Add New Raw Material")
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name")
            moq = c2.number_input("MOQ (kg)", min_value=0.0, step=0.5)
            rate = c3.number_input("Rate/KG (Rs)", min_value=0.0, step=10.0)

            c1, c2, c3 = st.columns(3)
            category = c1.text_input("Category (Active/Filler/Sweetener/etc.)")
            source = c2.text_input("Source (Natural/Synthetic)")
            negotiator = c3.text_input("Negotiator")

            if st.form_submit_button("Add Raw Material"):
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
