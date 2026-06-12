import streamlit as st
import pandas as pd
from app.db import fetch_all, execute


def _fmt_rs(value):
    if value is None or value == 0:
        return "-"
    return f"Rs {value:,.0f}"


def render():
    st.markdown("#### \U0001f4cb Inventory (Karsy Warehouse)")

    tab1, tab2 = st.tabs(["\U0001f4e6  Current Stock", "\U0000270f  Update Stock"])

    # ==================================================================
    # TAB 1 — Current Stock
    # ==================================================================
    with tab1:
        with st.spinner("Loading inventory..."):
            inventory = fetch_all("""
                SELECT rm.id, rm.name, rm.category, rm.moq_kg, rm.rate_per_kg,
                       COALESCE(inv.qty_grams, 0) as qty_grams,
                       COALESCE(inv.location, 'Karsy') as location
                FROM raw_materials rm
                LEFT JOIN inventory inv ON inv.raw_material_id = rm.id
                ORDER BY rm.name
            """)

        if inventory:
            # Summary metrics
            in_stock_count = sum(1 for i in inventory if i['qty_grams'] > 0)
            total_value = sum(
                i['qty_grams'] * i['rate_per_kg'] / 1000
                for i in inventory if i['qty_grams'] > 0
            )
            total_kg = sum(i['qty_grams'] / 1000 for i in inventory if i['qty_grams'] > 0)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Materials in Stock", f"{in_stock_count} of {len(inventory)}")
            c2.metric("Total Stock Value", _fmt_rs(total_value))
            c3.metric("Total Weight", f"{total_kg:,.1f} kg")
            c4.metric("Out of Stock", len(inventory) - in_stock_count)

            st.markdown("---")

            # Filters
            c1, c2 = st.columns(2)
            with c1:
                show = st.radio("Show", ["All", "In Stock Only", "Out of Stock"], horizontal=True)
            with c2:
                search = st.text_input("Search", key="inv_search", placeholder="Type to search...")

            filtered = inventory
            if show == "In Stock Only":
                filtered = [i for i in filtered if i['qty_grams'] > 0]
            elif show == "Out of Stock":
                filtered = [i for i in filtered if i['qty_grams'] == 0]
            if search:
                filtered = [i for i in filtered if search.lower() in i['name'].lower()]

            rows = []
            for i in filtered:
                stock_value = i['qty_grams'] * i['rate_per_kg'] / 1000 if i['qty_grams'] > 0 else 0
                rows.append({
                    'Raw Material': i['name'],
                    'Category': i['category'],
                    'Stock (g)': f"{i['qty_grams']:,.0f}" if i['qty_grams'] > 0 else '-',
                    'Stock (kg)': f"{i['qty_grams'] / 1000:.3f}" if i['qty_grams'] > 0 else '-',
                    'MOQ (kg)': i['moq_kg'],
                    'Value': _fmt_rs(stock_value),
                })

            df = pd.DataFrame(rows)

            # Color rows based on stock status
            def _color_stock(row):
                if row['Stock (g)'] == '-':
                    return ['background-color: #F8D7DA;'] * len(row)
                return [''] * len(row)

            styled = df.style.apply(_color_stock, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(filtered)} of {len(inventory)} materials")
        else:
            st.info("No materials found. Add raw materials first.")

    # ==================================================================
    # TAB 2 — Update Stock
    # ==================================================================
    with tab2:
        materials = fetch_all("SELECT id, name FROM raw_materials ORDER BY name")
        if materials:
            with st.form("update_inventory"):
                st.markdown("##### Update Stock Level")
                rm_options = {m['name']: m['id'] for m in materials}
                selected = st.selectbox("Raw Material", list(rm_options.keys()))
                qty = st.number_input("Quantity (grams)", min_value=0.0, step=100.0)

                if st.form_submit_button("Update Stock", type="primary"):
                    rm_id = rm_options[selected]
                    execute("""
                        INSERT INTO inventory (raw_material_id, qty_grams, location)
                        VALUES (?, ?, 'Karsy')
                        ON CONFLICT(raw_material_id) DO UPDATE SET qty_grams=?
                    """, (rm_id, qty, qty))
                    st.success(f"Updated {selected} stock to {qty:,.0f}g")
                    st.rerun()

            # Bulk update
            st.markdown("---")
            st.markdown("##### Bulk Update")
            st.caption("Paste raw material name and quantity (grams), one per line: name, qty")
            bulk_input = st.text_area("Bulk data (name, qty_grams)", height=150,
                                       placeholder="Ashwagandha, 5000\nVitamin C, 2000")
            if st.button("Apply Bulk Update", type="primary"):
                if bulk_input.strip():
                    count = 0
                    errors = 0
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
                                else:
                                    errors += 1
                            except ValueError:
                                errors += 1
                    msg = f"Updated {count} materials"
                    if errors:
                        msg += f" ({errors} skipped - name not found or invalid qty)"
                    st.success(msg)
                    st.rerun()
        else:
            st.info("No raw materials found. Add materials first.")
