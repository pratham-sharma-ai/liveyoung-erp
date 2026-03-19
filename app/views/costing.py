import streamlit as st
import pandas as pd
from app.engine import get_product_costing, get_all_product_costings
from app.db import fetch_all, execute


def render():
    st.title("Costing & Pricing")

    tab1, tab2 = st.tabs(["All Products", "Product Detail"])

    with tab1:
        costings = get_all_product_costings()
        active = [c for c in costings if c is not None]

        if active:
            rows = []
            for c in active:
                rows.append({
                    'Product': c['product']['base_code'],
                    'Form': c['product']['delivery_form'],
                    'Units/Pack': c['units_per_pack'],
                    'RM Cost': round(c['pack_rm_cost'], 2),
                    'PM Cost': round(c['pack_pm_cost'], 2),
                    'Processing': round(c['processing_cost'], 2),
                    'Total Cost': round(c['total_cost'], 2),
                    'Buffer (10%)': round(c['buffer'], 2),
                    'Net Total': round(c['net_total'], 2),
                    'Margin': f"{c['margin_percent']*100:.0f}%",
                    'Gross Margin': round(c['gross_margin'], 2),
                    'Selling Price': round(c['selling_price'], 2),
                    'Multiplier': f"{c['multiplier']:.1f}x",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Summary
            st.markdown("---")
            avg_sp = sum(c['selling_price'] for c in active) / len(active)
            min_sp = min(c['selling_price'] for c in active)
            max_sp = max(c['selling_price'] for c in active)

            c1, c2, c3 = st.columns(3)
            c1.metric("Avg Selling Price", f"Rs {avg_sp:,.0f}")
            c2.metric("Min SP", f"Rs {min_sp:,.0f}")
            c3.metric("Max SP", f"Rs {max_sp:,.0f}")

    with tab2:
        products = fetch_all("SELECT id, base_code FROM products ORDER BY base_code")
        selected = st.selectbox("Select Product", [""] + [p['base_code'] for p in products])

        if selected:
            prod_id = next(p['id'] for p in products if p['base_code'] == selected)
            costing = get_product_costing(prod_id)

            if costing:
                # Cost breakdown
                st.subheader("Cost Breakdown per Pack")

                c1, c2, c3 = st.columns(3)
                c1.metric("Raw Material", f"Rs {costing['pack_rm_cost']:,.2f}")
                c2.metric("Packaging", f"Rs {costing['pack_pm_cost']:,.2f}")
                c3.metric("Processing", f"Rs {costing['processing_cost']:,.2f}")

                c1, c2, c3 = st.columns(3)
                c1.metric("Total Cost", f"Rs {costing['total_cost']:,.2f}")
                c2.metric("Net Total (with buffer)", f"Rs {costing['net_total']:,.2f}")
                c3.metric("Selling Price", f"Rs {costing['selling_price']:,.2f}")

                # Margin simulator
                st.markdown("---")
                st.subheader("Margin Simulator")
                st.caption("Adjust margin to see how selling price changes")

                new_margin = st.slider(
                    "Target Margin %",
                    min_value=10,
                    max_value=95,
                    value=int(costing['margin_percent'] * 100),
                    step=1,
                    key="margin_slider"
                )

                net = costing['net_total']
                new_gm = net / (1 - new_margin/100) if new_margin < 100 else 0
                new_sp = net + new_margin/100 + new_gm

                c1, c2, c3 = st.columns(3)
                c1.metric("Net Total", f"Rs {net:,.2f}")
                c2.metric(f"Gross Margin ({new_margin}%)", f"Rs {new_gm:,.2f}")
                c3.metric("New Selling Price", f"Rs {new_sp:,.2f}",
                          delta=f"Rs {new_sp - costing['selling_price']:,.2f}" if new_margin != int(costing['margin_percent']*100) else None)

                # Save new margin
                if new_margin != int(costing['margin_percent'] * 100):
                    if st.button("Save this margin"):
                        execute("UPDATE products SET margin_percent=? WHERE id=?",
                                (new_margin/100, prod_id))
                        st.success(f"Margin updated to {new_margin}%")
                        st.rerun()

                # RM breakdown
                st.markdown("---")
                st.subheader("Raw Material Cost Breakdown (per unit)")

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
                        rows.append({
                            'Ingredient': r['name'],
                            'Grams/Unit': r['grams_per_unit'],
                            'Rate/KG': f"Rs {r['rate_per_kg']:,.0f}",
                            'Cost/Unit': f"Rs {r['cost_per_unit']:.4f}",
                            '% of RM Cost': f"{r['cost_per_unit']/costing['unit_rm_cost']*100:.1f}%"
                        })
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)

                # Pack summary
                st.markdown("---")
                st.subheader("Pack Summary")
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Packs", f"{costing['total_packs']:,}")
                c2.metric("Trial Packs", f"{costing['trial_packs']:,}")
                c3.metric("Sales Packs", f"{costing['sales_packs']:,}")
