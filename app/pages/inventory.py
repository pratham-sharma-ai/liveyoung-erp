import streamlit as st
import pandas as pd
from app.db import fetch_all, execute


def render():
    st.title("Inventory (Karsy)")

    tab1, tab2 = st.tabs(["Current Stock", "Update Stock"])

    with tab1:
        inventory = fetch_all("""
            SELECT rm.id, rm.name, rm.category, rm.moq_kg, rm.rate_per_kg,
                   COALESCE(inv.qty_grams, 0) as qty_grams,
                   COALESCE(inv.location, 'Karsy') as location
            FROM raw_materials rm
            LEFT JOIN inventory inv ON inv.raw_material_id = rm.id
            ORDER BY rm.name
        """)

        if inventory:
            c1, c2 = st.columns(2)
            with c1:
                show = st.radio("Show", ["All", "In Stock Only", "Out of Stock"], horizontal=True)
            with c2:
                search = st.text_input("Search", key="inv_search")

            filtered = inventory
            if show == "In Stock Only":
                filtered = [i for i in filtered if i['qty_grams'] > 0]
            elif show == "Out of Stock":
                filtered = [i for i in filtered if i['qty_grams'] == 0]
            if search:
                filtered = [i for i in filtered if search.lower() in i['name'].lower()]

            rows = []
            for i in filtered:
                rows.append({
                    'Raw Material': i['name'],
                    'Category': i['category'],
                    'Stock (g)': i['qty_grams'],
                    'Stock (kg)': round(i['qty_grams'] / 1000, 3) if i['qty_grams'] > 0 else 0,
                    'MOQ (kg)': i['moq_kg'],
                    'Value (Rs)': f"Rs {i['qty_grams'] * i['rate_per_kg'] / 1000:,.0f}" if i['qty_grams'] > 0 else '-',
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            in_stock = sum(1 for i in inventory if i['qty_grams'] > 0)
            total_value = sum(i['qty_grams'] * i['rate_per_kg'] / 1000 for i in inventory if i['qty_grams'] > 0)
            c1, c2 = st.columns(2)
            c1.metric("Materials in Stock", f"{in_stock} of {len(inventory)}")
            c2.metric("Estimated Stock Value", f"Rs {total_value:,.0f}")

    with tab2:
        materials = fetch_all("SELECT id, name FROM raw_materials ORDER BY name")
        if materials:
            with st.form("update_inventory"):
                st.subheader("Update Stock Level")
                rm_options = {m['name']: m['id'] for m in materials}
                selected = st.selectbox("Raw Material", list(rm_options.keys()))
                qty = st.number_input("Quantity (grams)", min_value=0.0, step=100.0)

                if st.form_submit_button("Update Stock"):
                    rm_id = rm_options[selected]
                    execute("""
                        INSERT INTO inventory (raw_material_id, qty_grams, location)
                        VALUES (?, ?, 'Karsy')
                        ON CONFLICT(raw_material_id) DO UPDATE SET qty_grams=?
                    """, (rm_id, qty, qty))
                    st.success(f"Updated {selected} stock to {qty}g")
                    st.rerun()

            # Bulk update
            st.markdown("---")
            st.subheader("Bulk Update")
            st.caption("Paste raw material name and quantity (grams), one per line: name, qty")
            bulk_input = st.text_area("Bulk data (name, qty_grams)", height=150)
            if st.button("Apply Bulk Update"):
                if bulk_input.strip():
                    count = 0
                    for line in bulk_input.strip().split('\n'):
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) == 2:
                            name, qty_str = parts
                            try:
                                qty = float(qty_str)
                                rm_id = rm_options.get(name)
                                if rm_id:
                                    execute("""
                                        INSERT INTO inventory (raw_material_id, qty_grams, location)
                                        VALUES (?, ?, 'Karsy')
                                        ON CONFLICT(raw_material_id) DO UPDATE SET qty_grams=?
                                    """, (rm_id, qty, qty))
                                    count += 1
                            except ValueError:
                                pass
                    st.success(f"Updated {count} materials")
                    st.rerun()
