import streamlit as st
import pandas as pd
from app.engine import get_product_costing, get_all_product_costings
from app.db import fetch_all, execute


def _fmt_rs(value):
    """Format as Rs X,XX,XXX."""
    if value is None or value == 0:
        return "Rs 0"
    return f"Rs {value:,.0f}"


def render():
    st.markdown("#### \U0001f4b0 Costing & Pricing")

    tab1, tab2 = st.tabs(["\U0001f4cb  All Products", "\U0001f50d  Product Detail"])

    # ==================================================================
    # TAB 1 — All Products comparison table
    # ==================================================================
    with tab1:
        with st.spinner("Loading costing data..."):
            costings = get_all_product_costings()
        active = [c for c in costings if c is not None]

        if not active:
            st.info("No products found. Create products with SKUs first.")
            return

        # Build dataframe
        rows = []
        for c in active:
            margin_pct = c['margin_percent'] * 100
            rows.append({
                'Product': c['product']['base_code'],
                'Form': c['product']['delivery_form'],
                'Units/Pack': c['units_per_pack'],
                'RM Cost': c['pack_rm_cost'],
                'PM Cost': c['pack_pm_cost'],
                'Processing': c['processing_cost'],
                'Total Cost': c['total_cost'],
                'Buffer': c['buffer'],
                'Net Total': c['net_total'],
                'Margin %': margin_pct,
                'Gross Margin': c['gross_margin'],
                'Selling Price': c['selling_price'],
                'Multiplier': c['multiplier'],
            })
        df = pd.DataFrame(rows)

        # Styled dataframe with conditional formatting
        def _style_table(styler):
            # Highlight margins: green >= 70, yellow 50-69, red < 50
            styler.map(
                lambda v: 'background-color: #D4EDDA; color: #155724;' if v >= 70
                else ('background-color: #FFF3CD; color: #856404;' if v >= 50
                      else 'background-color: #F8D7DA; color: #721C24;'),
                subset=['Margin %'],
            )
            # Format currency columns
            currency_cols = ['RM Cost', 'PM Cost', 'Processing', 'Total Cost',
                             'Buffer', 'Net Total', 'Gross Margin', 'Selling Price']
            styler.format({col: 'Rs {:,.0f}' for col in currency_cols})
            styler.format({'Margin %': '{:.0f}%', 'Multiplier': '{:.1f}x'})
            return styler

        styled = df.style.pipe(_style_table)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Summary metrics
        st.markdown("---")
        st.markdown("##### Price Range Summary")
        avg_sp = sum(c['selling_price'] for c in active) / len(active)
        min_c = min(active, key=lambda x: x['selling_price'])
        max_c = max(active, key=lambda x: x['selling_price'])
        avg_margin = sum(c['margin_percent'] for c in active) / len(active) * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Selling Price", _fmt_rs(avg_sp))
        c2.metric("Lowest SP", _fmt_rs(min_c['selling_price']),
                   delta=min_c['product']['base_code'], delta_color="off")
        c3.metric("Highest SP", _fmt_rs(max_c['selling_price']),
                   delta=max_c['product']['base_code'], delta_color="off")
        c4.metric("Avg Margin", f"{avg_margin:.0f}%")

    # ==================================================================
    # TAB 2 — Product Detail with waterfall + margin simulator
    # ==================================================================
    with tab2:
        products = fetch_all("SELECT id, base_code FROM products ORDER BY base_code")
        if not products:
            st.info("No products found.")
            return

        selected = st.selectbox(
            "Select Product",
            [""] + [p['base_code'] for p in products],
            key="costing_product_select",
        )

        if not selected:
            st.info("Select a product above to view detailed costing.")
            return

        prod_id = next((p['id'] for p in products if p['base_code'] == selected), None)
        if not prod_id:
            st.warning("Product not found.")
            return

        with st.spinner(f"Loading costing for {selected}..."):
            costing = get_product_costing(prod_id)

        if not costing:
            st.warning(f"No costing data available for {selected}. Check formulations and SKUs.")
            return

        # ------------------------------------------------------------------
        # Waterfall-style cost build-up chart
        # ------------------------------------------------------------------
        st.markdown(f"##### Cost Build-up: {selected}")

        import plotly.graph_objects as go

        buf_pct = costing['product']['buffer_percent'] * 100
        labels = ['Raw Material', 'Packaging', 'Processing', f'Buffer ({buf_pct:.0f}%)', 'Total Cost', 'Gross Margin', 'Selling Price']
        values = [
            costing['pack_rm_cost'],
            costing['pack_pm_cost'],
            costing['processing_cost'],
            costing['buffer'],
            costing['net_total'],
            costing['gross_margin'],
            costing['selling_price'],
        ]
        # Waterfall: components are relative, totals are absolute
        measures = ['relative', 'relative', 'relative', 'relative', 'total', 'relative', 'total']
        colors = ['#0D6EFD', '#6C757D', '#198754', '#FFC107', '#0D6EFD', '#20C997', '#0D47A1']

        fig = go.Figure(go.Waterfall(
            orientation='v',
            measure=measures,
            x=labels,
            y=values,
            text=[f"Rs {v:,.0f}" for v in values],
            textposition='outside',
            connector=dict(line=dict(color='#ccc', width=1)),
            increasing=dict(marker=dict(color='#0D6EFD')),
            decreasing=dict(marker=dict(color='#DC3545')),
            totals=dict(marker=dict(color='#0D47A1')),
        ))
        fig.update_layout(
            height=350,
            margin=dict(l=0, r=0, t=10, b=30),
            yaxis_title='Rs per Pack',
            font=dict(size=12),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # ------------------------------------------------------------------
        # Cost breakdown metrics
        # ------------------------------------------------------------------
        st.markdown("##### Per-Pack Cost Breakdown")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Raw Material", _fmt_rs(costing['pack_rm_cost']))
        c2.metric("Packaging", _fmt_rs(costing['pack_pm_cost']))
        c3.metric("Processing", _fmt_rs(costing['processing_cost']))
        c4.metric("Net Total", _fmt_rs(costing['net_total']))

        c1, c2, c3 = st.columns(3)
        c1.metric("Selling Price", _fmt_rs(costing['selling_price']))
        c2.metric("Gross Margin", _fmt_rs(costing['gross_margin']))
        c3.metric("Multiplier", f"{costing['multiplier']:.1f}x")

        st.markdown("---")

        # ------------------------------------------------------------------
        # MARGIN SIMULATOR — prominent
        # ------------------------------------------------------------------
        st.markdown("##### \U0001f3af Margin Simulator")

        sim_col1, sim_col2 = st.columns([1, 2])

        with sim_col1:
            new_margin = st.slider(
                "Target Margin %",
                min_value=10,
                max_value=95,
                value=int(costing['margin_percent'] * 100),
                step=1,
                key="margin_slider",
            )

        net = costing['net_total']
        new_sp = net / (1 - new_margin / 100) if new_margin < 100 else 0
        new_gm = new_sp - net
        delta_sp = new_sp - costing['selling_price']

        with sim_col2:
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Net Total", _fmt_rs(net))
            sc2.metric(
                f"Gross Margin ({new_margin}%)",
                _fmt_rs(new_gm),
            )
            sc3.metric(
                "New Selling Price",
                _fmt_rs(new_sp),
                delta=f"{'+' if delta_sp >= 0 else ''}{_fmt_rs(delta_sp)}"
                if new_margin != int(costing['margin_percent'] * 100) else None,
            )

        if new_margin != int(costing['margin_percent'] * 100):
            if st.button("\U00002705  Save this margin", type="primary"):
                execute("UPDATE products SET margin_percent=? WHERE id=?",
                        (new_margin / 100, prod_id))
                st.success(f"Margin updated to {new_margin}%")
                st.rerun()

        st.markdown("---")

        # ------------------------------------------------------------------
        # RM breakdown table
        # ------------------------------------------------------------------
        st.markdown("##### Raw Material Cost Breakdown (per unit)")

        rm_details = fetch_all("""
            SELECT rm.name, f.grams_per_unit, rm.rate_per_kg,
                   f.grams_per_unit * rm.rate_per_kg / 1000 as cost_per_unit
            FROM formulations f
            JOIN raw_materials rm ON rm.id = f.raw_material_id
            WHERE f.product_id = ? AND f.grams_per_unit > 0
            ORDER BY cost_per_unit DESC
        """, (prod_id,))

        if rm_details:
            rows = []
            for r in rm_details:
                pct = (r['cost_per_unit'] / costing['unit_rm_cost'] * 100) if costing['unit_rm_cost'] > 0 else 0
                rows.append({
                    'Ingredient': r['name'],
                    'Grams/Unit': f"{r['grams_per_unit']:.4f}",
                    'Rate/KG': _fmt_rs(r['rate_per_kg']),
                    'Cost/Unit': f"Rs {r['cost_per_unit']:.4f}",
                    '% of RM Cost': f"{pct:.1f}%",
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("---")

        # ------------------------------------------------------------------
        # Pack summary
        # ------------------------------------------------------------------
        st.markdown("##### Pack Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Packs", f"{costing['total_packs']:,}")
        c2.metric("Trial Packs", f"{costing['trial_packs']:,}")
        c3.metric("Sales Packs", f"{costing['sales_packs']:,}")
