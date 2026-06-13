import streamlit as st
import pandas as pd
from app.db import fetch_all, fetch_one, execute, execute_returning


def _fmt_rs(value):
    if value is None or value == 0:
        return "-"
    return f"Rs {value:,.0f}"


def render():
    st.markdown("#### \U0001f9ec Products & Formulations")

    tab1, tab2, tab3 = st.tabs(["\U0001f4cb  Products", "\U0001f9ea  Edit Formulation", "\U00002795  Add Product"])

    # ==================================================================
    # TAB 1 — Products overview
    # ==================================================================
    with tab1:
        with st.spinner("Loading products..."):
            products = fetch_all("""
                SELECT p.*,
                       (SELECT COUNT(*) FROM formulations f WHERE f.product_id = p.id AND f.grams_per_unit > 0) as ingredient_count,
                       (SELECT COUNT(*) FROM skus s WHERE s.product_id = p.id) as sku_count,
                       (SELECT COALESCE(SUM(s.pack_count), 0) FROM skus s WHERE s.product_id = p.id) as total_packs
                FROM products p ORDER BY p.base_code
            """)

        if products:
            # Summary
            active = [p for p in products if p['total_packs'] > 0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Products", len(products))
            c2.metric("Active (with SKUs)", len(active))
            c3.metric("Total Packs", f"{sum(p['total_packs'] for p in products):,}")

            st.markdown("---")

            rows = []
            for p in products:
                rows.append({
                    'Base Code': p['base_code'],
                    'Category': p['category'],
                    'Form': p['delivery_form'],
                    'Units/Pack': int(p['units_per_pack']),
                    'Daily Use': int(p['daily_consumption']),
                    'Ingredients': int(p['ingredient_count']),
                    'SKUs': int(p['sku_count']),
                    'Total Packs': f"{int(p['total_packs']):,}",
                    'Clinical Trial': 'Yes' if p['clinical_trial_required'] else 'No',
                    'Margin': f"{p['margin_percent'] * 100:.0f}%",
                    'Pkg Cost': _fmt_rs(p['packaging_cost_per_pack']),
                    'Process/Unit': _fmt_rs(p['processing_cost_per_unit']),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)

            # Edit product details
            st.markdown("---")
            st.markdown("##### Edit Product Settings")
            prod_names = {p['base_code']: p['id'] for p in products}
            selected = st.selectbox("Select product", [""] + list(prod_names.keys()), key="edit_prod")

            if selected:
                p = next(pr for pr in products if pr['base_code'] == selected)
                with st.form(f"edit_prod_{p['id']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    units = c1.number_input("Units per Pack", value=int(p['units_per_pack']), min_value=1)
                    daily = c2.number_input("Daily Consumption", value=int(p['daily_consumption']), min_value=1)
                    proc = c3.number_input("Processing Cost/Unit (Rs)", value=float(p['processing_cost_per_unit']), step=0.5)
                    pkg = c4.number_input("Packaging Cost/Pack (Rs)", value=float(p['packaging_cost_per_pack']), step=1.0)

                    c1, c2, c3 = st.columns(3)
                    margin = c1.number_input("Margin %", value=float(p['margin_percent'] * 100),
                                             min_value=0.0, max_value=99.0, step=1.0)
                    buffer = c2.number_input("Buffer %", value=float(p['buffer_percent'] * 100),
                                             min_value=0.0, max_value=50.0, step=1.0)
                    clinical = c3.checkbox("Clinical Trial Required", value=bool(p['clinical_trial_required']))

                    if clinical:
                        c1, c2, c3 = st.columns(3)
                        duration = c1.number_input("Duration (months)", value=int(p['clinical_duration_months']), min_value=0)
                        participants = c2.number_input("Participants", value=int(p['clinical_participants']), min_value=0)
                        packs_mo = c3.number_input("Packs/month/person", value=int(p['clinical_packs_per_month']), min_value=0)
                    else:
                        duration = participants = packs_mo = 0

                    if st.form_submit_button("Update Product", type="primary"):
                        execute("""
                            UPDATE products SET
                                units_per_pack=?, daily_consumption=?, processing_cost_per_unit=?,
                                packaging_cost_per_pack=?, margin_percent=?, buffer_percent=?,
                                clinical_trial_required=?, clinical_duration_months=?,
                                clinical_participants=?, clinical_packs_per_month=?
                            WHERE id=?
                        """, (units, daily, proc, pkg, margin / 100, buffer / 100,
                              1 if clinical else 0, duration, participants, packs_mo, p['id']))
                        st.success(f"Updated {selected}")
                        st.rerun()
        else:
            st.info("No products found. Create your first product below.")

    # ==================================================================
    # TAB 2 — Edit Formulation
    # ==================================================================
    with tab2:
        products = fetch_all("SELECT id, base_code FROM products ORDER BY base_code")
        all_rm = fetch_all("SELECT id, name, category FROM raw_materials ORDER BY name")

        if products:
            selected_prod = st.selectbox("Select Product", [""] + [p['base_code'] for p in products],
                                         key="form_prod")
            if selected_prod:
                prod_id = next(p['id'] for p in products if p['base_code'] == selected_prod)

                with st.spinner(f"Loading formulation for {selected_prod}..."):
                    formulation = fetch_all("""
                        SELECT f.id, f.grams_per_unit, rm.name as rm_name, rm.id as rm_id,
                               rm.rate_per_kg, rm.category as rm_category
                        FROM formulations f
                        JOIN raw_materials rm ON rm.id = f.raw_material_id
                        WHERE f.product_id = ? AND f.grams_per_unit > 0
                        ORDER BY f.grams_per_unit DESC
                    """, (prod_id,))

                if formulation:
                    st.markdown(f"##### Formulation: {selected_prod}")
                    total_grammage = sum(f['grams_per_unit'] for f in formulation)

                    c1, c2 = st.columns(2)
                    c1.metric("Total Grammage/Unit", f"{total_grammage:.4f} g")
                    c2.metric("Ingredients", len(formulation))

                    rows = []
                    for f in formulation:
                        cost_per_unit = f['grams_per_unit'] * f['rate_per_kg'] / 1000
                        rows.append({
                            'Raw Material': f['rm_name'],
                            'Category': f['rm_category'],
                            'Grams/Unit': f"{f['grams_per_unit']:.4f}",
                            'Rate/KG': _fmt_rs(f['rate_per_kg']),
                            'Cost/Unit': f"Rs {cost_per_unit:.4f}",
                            '% of Grammage': f"{f['grams_per_unit'] / total_grammage * 100:.1f}%",
                        })
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No ingredients set for {selected_prod} yet. Use the form below to add.")

                # Edit formulation entries
                st.markdown("---")
                st.markdown("##### Update Ingredient")
                rm_options = {rm['name']: rm['id'] for rm in all_rm}

                with st.form("update_formulation"):
                    c1, c2 = st.columns([3, 1])
                    rm_name = c1.selectbox("Raw Material", list(rm_options.keys()))
                    grams = c2.number_input("Grams per Unit", min_value=0.0, step=0.001, format="%.4f")

                    submitted = st.form_submit_button("Set Ingredient Amount", type="primary")
                    if submitted:
                        rm_id = rm_options[rm_name]
                        if grams > 0:
                            execute("""
                                INSERT INTO formulations (product_id, raw_material_id, grams_per_unit)
                                VALUES (?, ?, ?)
                                ON CONFLICT(product_id, raw_material_id) DO UPDATE SET grams_per_unit=?
                            """, (prod_id, rm_id, grams, grams))
                            st.success(f"Set {rm_name} = {grams}g for {selected_prod}")
                        else:
                            execute("""
                                DELETE FROM formulations
                                WHERE product_id = ? AND raw_material_id = ?
                            """, (prod_id, rm_id))
                            st.success(f"Removed {rm_name} from {selected_prod}")
                        st.rerun()
        else:
            st.info("No products found. Create products first.")

    # ==================================================================
    # TAB 3 — Add Product
    # ==================================================================
    with tab3:
        with st.form("add_product"):
            st.markdown("##### Add New Product")
            c1, c2, c3 = st.columns(3)
            category = c1.text_input("Category (e.g., PCOS, ENERGY, WM)")
            delivery = c2.selectbox("Delivery Form", ["TAB", "POW", "CAP", "GEL"])
            base_code = c3.text_input("Base Code (auto-generated)", value="", disabled=True,
                                       help="Will be Category-Form, e.g. PCOS-TAB")

            c1, c2, c3, c4 = st.columns(4)
            units = c1.number_input("Units per Pack", value=30, min_value=1)
            daily = c2.number_input("Daily Consumption", value=1, min_value=1)
            proc = c3.number_input("Processing Cost/Unit (Rs)", value=2.0, step=0.5)
            pkg = c4.number_input("Packaging Cost/Pack (Rs)", value=105.0, step=1.0)

            c1, c2 = st.columns(2)
            margin = c1.slider("Target Margin %", 0, 95, 70)
            buffer = c2.slider("Buffer %", 0, 30, 10)

            if st.form_submit_button("Create Product", type="primary"):
                if category:
                    code = f"{category}-{delivery}"
                    try:
                        execute_returning("""
                            INSERT INTO products (base_code, category, delivery_form, units_per_pack,
                                daily_consumption, processing_cost_per_unit, packaging_cost_per_pack,
                                margin_percent, buffer_percent)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (code, category, delivery, units, daily, proc, pkg,
                              margin / 100, buffer / 100))
                        st.success(f"Created product: {code}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Category is required")
