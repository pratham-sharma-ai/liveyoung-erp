import streamlit as st
from app.db import _get_all_rows


def render():
    st.markdown("#### Assumptions & Open Items")
    st.caption("These assumptions drive all calculations. Correct anything that's wrong — the numbers update instantly.")

    products = _get_all_rows('products')
    rm = _get_all_rows('raw_materials')
    packaging = _get_all_rows('packaging_configs')

    # ------------------------------------------------------------------
    # Section 1: Processing Costs
    # ------------------------------------------------------------------
    st.markdown("##### 1. Processing Costs (Karsy)")
    st.markdown("*Blended cost per unit at Karsy facility. Currently indicative — needs Karsy confirmation.*")

    proc_data = {}
    for p in products:
        form = p['delivery_form']
        cost = p['processing_cost_per_unit']
        if form not in proc_data:
            proc_data[form] = cost

    if proc_data:
        cols = st.columns(len(proc_data))
        for i, (form, cost) in enumerate(sorted(proc_data.items())):
            cols[i].metric(form, f"Rs {cost:.2f}/unit")
    else:
        st.info("No products configured yet.")

    with st.expander("What this means"):
        st.markdown("""
        - TAB/CAP/POW: Rs 1.50 per tablet/capsule/sachet
        - GEL: Rs 2.50 per gel sachet
        - This is what Karsy charges to manufacture each unit
        - **Action needed**: Confirm these rates with Karsy operations team
        """)

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 2: Packaging Rates
    # ------------------------------------------------------------------
    st.markdown("##### 2. Packaging Rates")
    st.markdown("*All packaging costs are vendor estimates. Need final quotes before first production order.*")

    if packaging:
        rows = []
        for p in packaging:
            rows.append({
                'Component': p['component_name'],
                'Delivery Form': p['delivery_form'],
                'Cost/Pack': f"Rs {p['cost_per_pack']:.2f}",
                'Status': 'Estimate'
            })

        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("What this means"):
        st.markdown("""
        - Sachet film: Rs 4.50/sachet (updated from Rs 2.70)
        - Secondary boxes: Rs 50-85 per pack depending on type
        - Bottle (PET 100cc): Rs 9 per pack
        - **Action needed**: Get final quotes from all 3 packaging vendors
        """)

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 3: Buffer & Margin Assumptions
    # ------------------------------------------------------------------
    st.markdown("##### 3. Buffer % & Target Margins")
    st.markdown("*Buffer covers manufacturing wastage. Margins are target GM% used to calculate selling price.*")

    if products:
        import pandas as pd
        rows = []
        for p in sorted(products, key=lambda x: x['base_code']):
            rows.append({
                'Product': p['base_code'],
                'Format': p['delivery_form'],
                'Buffer %': f"{p['buffer_percent'] * 100:.0f}%",
                'Target GM %': f"{p['margin_percent'] * 100:.0f}%",
                'Status': 'Active' if any(s['product_id'] == p['id'] for s in _get_all_rows('skus')) else 'Pipeline'
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("Pricing formula"):
        st.markdown("""
        ```
        Total Cost = RM Cost + PM Cost + Processing Cost
        Net Total  = Total Cost × (1 + Buffer%)
        Selling Price = Net Total / (1 - GM%)
        ```
        Example: If Net Total = Rs 500 and GM = 70%, then SP = 500 / (1 - 0.70) = Rs 1,667
        """)

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 4: Batch Manufacturing Constraints
    # ------------------------------------------------------------------
    st.markdown("##### 4. Batch Manufacturing Constraints")
    st.markdown("*Minimum batch weights at Karsy. SKUs below minimum can't be manufactured standalone.*")

    batch_data = {
        'TAB': {'min_kg': 7, 'std_kg': 50, 'min_units': 50000},
        'CAP': {'min_kg': 5, 'std_kg': 25, 'min_units': 50000},
        'POW': {'min_kg': 5, 'std_kg': 100, 'min_units': 10000},
        'GEL': {'min_kg': 5, 'std_kg': 50, 'min_units': 5000},
    }

    import pandas as pd
    rows = []
    for form, d in batch_data.items():
        rows.append({
            'Format': form,
            'Min Batch Weight': f"{d['min_kg']} kg",
            'Standard Batch': f"{d['std_kg']} kg",
            'Min Commercial Units': f"{d['min_units']:,}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.warning("GUT-CAP and PCOS-TAB are currently below minimum batch weight. Options: increase pack count, combine production runs, or defer launch.")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 5: Vendor Lead Times
    # ------------------------------------------------------------------
    st.markdown("##### 5. Vendor Lead Times")
    st.markdown("*Default assumptions. Active ingredients = 28 days, Excipients/Others = 14 days.*")

    lead_time_summary = {'28 days (Active)': 0, '14 days (Others)': 0, 'Unknown': 0}
    for r in rm:
        remarks = str(r.get('remarks', ''))
        if '28' in remarks:
            lead_time_summary['28 days (Active)'] += 1
        elif '14' in remarks:
            lead_time_summary['14 days (Others)'] += 1
        else:
            lead_time_summary['Unknown'] += 1

    cols = st.columns(3)
    for i, (label, count) in enumerate(lead_time_summary.items()):
        cols[i].metric(label, f"{count} materials")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 6: SKU Reclassifications
    # ------------------------------------------------------------------
    st.markdown("##### 6. Key Changes from V6 to V11")
    st.markdown("""
    | Change | Detail |
    |---|---|
    | WM-TAB / WM-POW | Reclassified from "Women's Health" to **"Weight Management"** |
    | Pumpkin Extract | Renamed to **Pumpkin Powder** |
    | 3 new RMs added | L-Citrulline (RM69), Betaine (RM70), L-Taurine (RM71) |
    | Sachet film rate | Updated from Rs 2.70 to **Rs 4.50** |
    | 3 vendor rate changes | RM72: 1000→1800, RM73: 800→1000, RM74: 1000→600 |
    | PM Components | Added lead time, currency, active vendor flag |
    | Pipeline SKUs | DYS-TAB, DYS-POW, DIAB-TAB, DIAB-POW, LIVER-POW (inactive, preserved) |
    """)

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 7: What the client needs to confirm
    # ------------------------------------------------------------------
    st.markdown("##### Things to Confirm Before Production")
    st.error("**CRITICAL** — Must resolve before first production order")
    st.markdown("""
    1. Final packaging rates from all 3 vendors
    2. Karsy min batch weights and standard batch sizes
    3. Karsy processing cost per unit (currently indicative)
    4. RM lead times from each active vendor
    """)

    st.warning("**HIGH** — Should resolve before board presentation")
    st.markdown("""
    5. Finalize ENERGY-POW formulation (Mannitol = 0g currently)
    6. Decision on GUT-CAP & PCOS-TAB (below min batch weight)
    7. Activate pipeline SKU formulations when ready
    8. Confirm vendor names and quote references for packaging
    """)
