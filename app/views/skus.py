import streamlit as st
import pandas as pd
from app.db import fetch_all, fetch_one, execute, execute_returning


def render():
    st.markdown("#### \U0001f4e6 SKUs & Launch Plan")

    tab1, tab2 = st.tabs(["\U0001f4cb  Launch Plan", "\U00002795  Add SKU"])

    # ==================================================================
    # TAB 1 — Launch Plan
    # ==================================================================
    with tab1:
        with st.spinner("Loading launch plan..."):
            # Phase info
            phases = fetch_all("SELECT * FROM launch_phases ORDER BY phase_number")
            skus = fetch_all("""
                SELECT s.*, p.base_code, p.category, p.delivery_form, p.units_per_pack
                FROM skus s
                JOIN products p ON p.id = s.product_id
                ORDER BY s.phase, p.category, p.delivery_form
            """)

        # Phase timeline
        if phases:
            st.markdown("##### Phase Timeline")
            cols = st.columns(len(phases))
            for i, ph in enumerate(phases):
                phase_skus = [s for s in skus if int(s['phase']) == int(ph['phase_number'])]
                total_packs = sum(int(s['pack_count']) for s in phase_skus)
                cols[i].metric(
                    f"Phase {int(ph['phase_number'])}",
                    ph['start_date'],
                    delta=f"{len(phase_skus)} SKUs, {total_packs:,} packs",
                    delta_color="off",
                )
            st.markdown("---")

        if skus:
            # Summary
            total_skus = len(skus)
            total_packs = sum(int(s['pack_count']) for s in skus)
            total_units = sum(int(s['pack_count']) * int(s['units_per_pack']) for s in skus)

            c1, c2, c3 = st.columns(3)
            c1.metric("Total SKUs", total_skus)
            c2.metric("Total Packs", f"{total_packs:,}")
            c3.metric("Total Units", f"{total_units:,}")

            st.markdown("---")

            # Filter by phase
            all_phases = sorted(set(int(s['phase']) for s in skus))
            phase_filter = st.multiselect(
                "Filter by Phase",
                all_phases,
                default=[],
                format_func=lambda x: f"Phase {x}",
            )

            filtered = skus if not phase_filter else [s for s in skus if int(s['phase']) in phase_filter]

            rows = []
            for s in filtered:
                rows.append({
                    'SKU Code': s['sku_code'],
                    'Product': s['base_code'],
                    'Category': s['category'],
                    'Form': s['delivery_form'],
                    'Flavour': f"{s['flavour_name']} ({s['flavour_code']})",
                    'Pack Count': f"{int(s['pack_count']):,}",
                    'Units/Pack': int(s['units_per_pack']),
                    'Total Units': f"{int(s['pack_count']) * int(s['units_per_pack']):,}",
                    'Phase': int(s['phase']),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)

            # Phase summary
            st.markdown("---")
            st.markdown("##### Phase Summary")
            for phase_num in sorted(set(int(s['phase']) for s in skus)):
                phase_skus = [s for s in skus if int(s['phase']) == phase_num]
                total = sum(int(s['pack_count']) for s in phase_skus)
                products_in_phase = len(set(s['base_code'] for s in phase_skus))
                st.write(f"**Phase {phase_num}**: {len(phase_skus)} SKUs across {products_in_phase} products = {total:,} packs")

            # Edit SKU
            st.markdown("---")
            st.markdown("##### Edit SKU")
            sku_options = {s['sku_code']: s for s in skus}
            selected = st.selectbox("Select SKU to edit", [""] + list(sku_options.keys()))

            if selected:
                s = sku_options[selected]
                with st.form(f"edit_sku_{s['id']}"):
                    c1, c2, c3 = st.columns(3)
                    flavour_name = c1.text_input("Flavour Name", s['flavour_name'])
                    pack_count = c2.number_input("Pack Count", value=int(s['pack_count']), min_value=0)
                    phase = c3.number_input("Phase", value=int(s['phase']), min_value=1, max_value=4)

                    if st.form_submit_button("Update SKU", type="primary"):
                        execute("""
                            UPDATE skus SET flavour_name=?, pack_count=?, phase=?
                            WHERE id=?
                        """, (flavour_name, pack_count, phase, s['id']))
                        st.success(f"Updated {selected}")
                        st.rerun()

                # Delete option
                if st.button(f"Delete {selected}", type="secondary"):
                    execute("DELETE FROM skus WHERE id=?", (s['id'],))
                    st.success(f"Deleted {selected}")
                    st.rerun()
        else:
            st.info("No SKUs created yet. Use the Add SKU tab to get started.")

    # ==================================================================
    # TAB 2 — Add SKU
    # ==================================================================
    with tab2:
        products = fetch_all("SELECT id, base_code, category, delivery_form FROM products ORDER BY base_code")

        if products:
            with st.form("add_sku"):
                st.markdown("##### Create New SKU")

                c1, c2 = st.columns(2)
                prod_options = {p['base_code']: p['id'] for p in products}
                selected_prod = c1.selectbox("Product", list(prod_options.keys()))
                phase = c2.number_input("Launch Phase", value=1, min_value=1, max_value=4)

                c1, c2, c3 = st.columns(3)
                flavour_code = c1.text_input("Flavour Code (e.g., F1, T1, C1)")
                flavour_name = c2.text_input("Flavour Name (e.g., Orange, Mint)")
                pack_count = c3.number_input("Pack Count", value=100, min_value=0)

                # Auto-generate SKU code
                if selected_prod and flavour_code and flavour_name:
                    prod = next(p for p in products if p['base_code'] == selected_prod)
                    cat_prefix = prod['category'][:2].upper()
                    form = prod['delivery_form']
                    flav_prefix = flavour_name[:2]
                    sku_code = f"{cat_prefix}-{form}-{flavour_code}-{flav_prefix}"
                    st.info(f"Generated SKU Code: **{sku_code}**")
                else:
                    sku_code = ""

                if st.form_submit_button("Create SKU", type="primary"):
                    if flavour_code and flavour_name and sku_code:
                        prod_id = prod_options[selected_prod]
                        try:
                            execute_returning("""
                                INSERT INTO skus (product_id, flavour_code, flavour_name, sku_code, pack_count, phase)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (prod_id, flavour_code, flavour_name, sku_code, pack_count, phase))
                            st.success(f"Created SKU: {sku_code}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("All fields are required")
        else:
            st.warning("Create products first before adding SKUs.")
