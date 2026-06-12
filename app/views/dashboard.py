import streamlit as st
import pandas as pd
from app.engine import get_dashboard_summary


def _fmt_rs(value):
    """Format a number as Rs X,XX,XXX (Indian comma style via {:,.0f})."""
    if value is None or value == 0:
        return "Rs 0"
    return f"Rs {value:,.0f}"


def render():
    st.markdown("#### \U0001f4ca Executive Dashboard")
    st.caption("Real-time overview of products, costs, and procurement")

    with st.spinner("Loading dashboard data..."):
        summary = get_dashboard_summary()

    # ------------------------------------------------------------------
    # Row 1 — Four key metrics
    # ------------------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Active Products",
        summary['active_products'],
        delta=f"of {summary['total_products']} total",
        delta_color="off",
    )
    c2.metric("Total SKUs", summary['total_skus'])
    c3.metric(
        "Working Capital Needed",
        _fmt_rs(summary['total_rm_cost_with_gst']),
        delta=f"RM {_fmt_rs(summary['total_rm_cost'])} + 18% GST",
        delta_color="off",
    )
    c4.metric(
        "MOQ Excess Cost",
        _fmt_rs(summary['total_surplus_cost']),
        delta=f"{summary['rms_to_buy_count']} items to procure",
        delta_color="off",
    )

    st.markdown("---")

    # ------------------------------------------------------------------
    # Row 2 — Cost breakdown chart (horizontal bar per product)
    # ------------------------------------------------------------------
    st.markdown("##### Cost Breakdown by Product (per pack)")

    if summary['costings']:
        import plotly.graph_objects as go

        products = [c['product']['base_code'] for c in summary['costings']]
        rm_costs = [c['pack_rm_cost'] for c in summary['costings']]
        pm_costs = [c['pack_pm_cost'] for c in summary['costings']]
        proc_costs = [c['processing_cost'] for c in summary['costings']]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=products, x=rm_costs, name='Raw Materials',
            orientation='h', marker_color='#0D6EFD',
            text=[f"Rs {v:,.0f}" for v in rm_costs], textposition='inside',
        ))
        fig.add_trace(go.Bar(
            y=products, x=pm_costs, name='Packaging',
            orientation='h', marker_color='#6C757D',
            text=[f"Rs {v:,.0f}" for v in pm_costs], textposition='inside',
        ))
        fig.add_trace(go.Bar(
            y=products, x=proc_costs, name='Processing',
            orientation='h', marker_color='#198754',
            text=[f"Rs {v:,.0f}" for v in proc_costs], textposition='inside',
        ))
        fig.update_layout(
            barmode='stack',
            height=max(250, len(products) * 55 + 80),
            margin=dict(l=0, r=20, t=10, b=30),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            xaxis_title='Cost per Pack (Rs)',
            yaxis=dict(autorange='reversed'),
            font=dict(size=12),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No active products with SKUs yet.")

    # ------------------------------------------------------------------
    # Row 3 — Top 5 most expensive raw materials
    # ------------------------------------------------------------------
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("##### Top 5 Costliest Raw Materials")

        rm_cost_map = {}
        for r in summary['rm_orders']:
            if r['total_grams_needed'] > 0:
                rm_cost_map[r['raw_material']] = r['actual_cost']

        if rm_cost_map:
            top5 = sorted(rm_cost_map.items(), key=lambda x: x[1], reverse=True)[:5]
            rows = []
            for rank, (name, cost) in enumerate(top5, 1):
                rows.append({
                    '#': rank,
                    'Raw Material': name,
                    'Procurement Cost': _fmt_rs(cost),
                    'Share': f"{cost / summary['total_rm_cost'] * 100:.1f}%" if summary['total_rm_cost'] > 0 else "-",
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No procurement data yet.")

    # ------------------------------------------------------------------
    # Row 3 (right) — MOQ analysis summary
    # ------------------------------------------------------------------
    with col_right:
        st.markdown("##### MOQ Surplus Analysis")

        surplus_items = [r for r in summary['rm_orders']
                         if r['surplus_kg'] > 0 and r['total_grams_needed'] > 0]
        total_surplus = summary['total_surplus_cost']

        c1, c2 = st.columns(2)
        c1.metric("Materials with Surplus", len(surplus_items))
        c2.metric("Total Surplus Value", _fmt_rs(total_surplus))

        if surplus_items:
            top_surplus = sorted(surplus_items, key=lambda x: x['surplus_cost'], reverse=True)[:5]
            rows = []
            for r in top_surplus:
                rows.append({
                    'Raw Material': r['raw_material'],
                    'Surplus (kg)': f"{r['surplus_kg']:.2f}",
                    'Surplus Cost': _fmt_rs(r['surplus_cost']),
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No MOQ surplus across all materials.")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Row 4 — Launch phases
    # ------------------------------------------------------------------
    if summary['phase_counts']:
        st.markdown("##### Launch Phases")
        phase_cols = st.columns(len(summary['phase_counts']))
        for i, (phase, count) in enumerate(sorted(summary['phase_counts'].items())):
            phase_cols[i].metric(f"Phase {phase}", f"{count} SKUs")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Row 5 — Product costing table
    # ------------------------------------------------------------------
    st.markdown("##### Product Costing Overview")
    if summary['costings']:
        rows = []
        for c in summary['costings']:
            margin_val = c['margin_percent'] * 100
            rows.append({
                'Product': c['product']['base_code'],
                'Category': c['product']['category'],
                'Form': c['product']['delivery_form'],
                'Packs': f"{c['total_packs']:,}",
                'RM/Pack': _fmt_rs(c['pack_rm_cost']),
                'PM/Pack': _fmt_rs(c['pack_pm_cost']),
                'Net Total': _fmt_rs(c['net_total']),
                'Margin': f"{margin_val:.0f}%",
                'Selling Price': _fmt_rs(c['selling_price']),
                'Multiplier': f"{c['multiplier']:.1f}x",
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No product costings available. Add products and SKUs first.")
