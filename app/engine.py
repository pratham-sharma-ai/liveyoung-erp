"""
Calculation engine — replaces all Excel formulas.
All monetary values in INR. Weights in grams unless noted.
"""

from app.db import fetch_all, fetch_one


def get_product_unit_rm_cost(product_id):
    """
    For a product, sum(formulation_grams * rate_per_kg / 1000) across all raw materials.
    Returns cost per single unit (1 tablet / 1 sachet / 1 capsule).
    """
    rows = fetch_all("""
        SELECT f.grams_per_unit, rm.rate_per_kg
        FROM formulations f
        JOIN raw_materials rm ON rm.id = f.raw_material_id
        WHERE f.product_id = ? AND f.grams_per_unit > 0
    """, (product_id,))
    return sum(r['grams_per_unit'] * r['rate_per_kg'] / 1000 for r in rows)


def get_product_packaging_cost(product_id):
    """
    Packaging cost per pack — stored directly on the product.
    Falls back to delivery_form config if not set.
    """
    product = fetch_one("SELECT packaging_cost_per_pack, delivery_form FROM products WHERE id = ?", (product_id,))
    if not product:
        return 0
    if product['packaging_cost_per_pack'] and product['packaging_cost_per_pack'] > 0:
        return product['packaging_cost_per_pack']
    # Fallback to config table
    rows = fetch_all("""
        SELECT cost_per_pack FROM packaging_configs
        WHERE delivery_form = ?
    """, (product['delivery_form'],))
    return sum(r['cost_per_pack'] for r in rows)


def get_product_trial_packs(product_id):
    """
    If clinical trial required: duration * participants * packs_per_month.
    """
    p = fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if not p or not p['clinical_trial_required']:
        return 0
    return p['clinical_duration_months'] * p['clinical_participants'] * p['clinical_packs_per_month']


def get_product_total_packs(product_id):
    """
    Sum of all SKU pack counts for this product.
    """
    skus = fetch_all("""
        SELECT pack_count FROM skus WHERE product_id = ?
    """, (product_id,))
    return sum(int(s['pack_count']) for s in skus)


def get_product_sales_packs(product_id):
    """
    Total packs minus trial packs.
    """
    total = get_product_total_packs(product_id)
    trial = get_product_trial_packs(product_id)
    return max(0, total - trial)


def get_product_costing(product_id):
    """
    Full per-pack cost breakdown for a product.
    Returns dict with all cost components + selling price.
    """
    product = fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if not product:
        return None

    units = product['units_per_pack']
    unit_rm_cost = get_product_unit_rm_cost(product_id)
    pack_rm_cost = unit_rm_cost * units
    pack_pm_cost = get_product_packaging_cost(product_id)
    proc_per_unit = product['processing_cost_per_unit']
    processing_cost = proc_per_unit * units
    # Excel SUM(111:114) includes per-unit rate + total, matching client's pricing
    total_cost = pack_rm_cost + pack_pm_cost + proc_per_unit + processing_cost
    buffer = total_cost * product['buffer_percent']
    net_total = total_cost + buffer
    margin_pct = product['margin_percent']
    # Excel: GM = Net/(1-margin%), SP = Net + margin% + GM
    gross_margin = net_total / (1 - margin_pct) if margin_pct < 1 else 0
    selling_price = net_total + margin_pct + gross_margin
    multiplier = selling_price / net_total if net_total > 0 else 0

    total_packs = get_product_total_packs(product_id)
    trial_packs = get_product_trial_packs(product_id)
    sales_packs = max(0, total_packs - trial_packs)

    return {
        'product': dict(product),
        'units_per_pack': units,
        'unit_rm_cost': round(unit_rm_cost, 4),
        'pack_rm_cost': round(pack_rm_cost, 2),
        'pack_pm_cost': round(pack_pm_cost, 2),
        'processing_cost': round(processing_cost, 2),
        'total_cost': round(total_cost, 2),
        'buffer': round(buffer, 2),
        'net_total': round(net_total, 2),
        'margin_percent': margin_pct,
        'gross_margin': round(gross_margin, 2),
        'selling_price': round(selling_price, 2),
        'multiplier': round(multiplier, 2),
        'total_packs': total_packs,
        'trial_packs': trial_packs,
        'sales_packs': sales_packs,
    }


def get_all_product_costings():
    """
    Costing for every product.
    """
    products = fetch_all("SELECT id FROM products ORDER BY base_code")
    return [get_product_costing(p['id']) for p in products]


def get_rm_order_requirements():
    """
    For each raw material, calculate total qty needed across all products,
    MOQ gap, actual cost, surplus cost, and inventory status.
    """
    raw_materials = fetch_all("SELECT * FROM raw_materials ORDER BY name")
    products = fetch_all("SELECT * FROM products")

    results = []
    for rm in raw_materials:
        # Total grams needed across all products
        total_grams = 0
        product_breakdown = []

        for prod in products:
            form = fetch_one("""
                SELECT grams_per_unit FROM formulations
                WHERE product_id = ? AND raw_material_id = ?
            """, (prod['id'], rm['id']))

            if not form or form['grams_per_unit'] == 0:
                continue

            total_units = prod['units_per_pack'] * get_product_total_packs(prod['id'])
            grams_needed = form['grams_per_unit'] * total_units
            total_grams += grams_needed
            product_breakdown.append({
                'product': prod['base_code'],
                'grams_per_unit': form['grams_per_unit'],
                'total_units': total_units,
                'grams_needed': round(grams_needed, 2),
            })

        total_kg = total_grams / 1000
        moq_kg = rm['moq_kg'] or 0
        rate = rm['rate_per_kg'] or 0

        # MOQ logic: you pay for whichever is higher
        order_kg = max(total_kg, moq_kg) if total_kg > 0 else 0
        actual_cost = order_kg * rate
        surplus_kg = max(0, moq_kg - total_kg) if total_kg > 0 else 0
        surplus_cost = surplus_kg * rate

        # Inventory check
        inv = fetch_one("""
            SELECT qty_grams FROM inventory
            WHERE raw_material_id = ?
        """, (rm['id'],))
        inv_grams = inv['qty_grams'] if inv else 0
        inv_status = 'sufficient' if inv_grams >= total_grams else ('partial' if inv_grams > 0 else 'none')
        shortfall_grams = max(0, total_grams - inv_grams)

        results.append({
            'raw_material': rm['name'],
            'rm_id': rm['id'],
            'category': rm['category'],
            'moq_kg': moq_kg,
            'rate_per_kg': rate,
            'total_grams_needed': round(total_grams, 2),
            'total_kg_needed': round(total_kg, 4),
            'order_kg': round(order_kg, 4),
            'actual_cost': round(actual_cost, 2),
            'surplus_kg': round(surplus_kg, 4),
            'surplus_cost': round(surplus_cost, 2),
            'inventory_grams': inv_grams,
            'inventory_status': inv_status,
            'shortfall_grams': round(shortfall_grams, 2),
            'product_breakdown': product_breakdown,
        })

    return results


def get_dashboard_summary():
    """
    High-level numbers for the dashboard.
    """
    costings = get_all_product_costings()
    rm_orders = get_rm_order_requirements()

    active_products = [c for c in costings if c and c['total_packs'] > 0]
    total_rm_cost = sum(r['actual_cost'] for r in rm_orders if r['total_grams_needed'] > 0)
    total_surplus_cost = sum(r['surplus_cost'] for r in rm_orders)
    total_packs = sum(c['total_packs'] for c in active_products)

    # Count by phase
    skus = fetch_all("SELECT * FROM skus")
    phase_counts = {}
    for s in skus:
        ph = s['phase']
        phase_counts[ph] = phase_counts.get(ph, 0) + 1

    # RM needing procurement (shortfall > 0)
    rms_to_buy = [r for r in rm_orders if r['shortfall_grams'] > 0 and r['total_grams_needed'] > 0]

    return {
        'total_products': len(costings),
        'active_products': len(active_products),
        'total_skus': len(skus),
        'total_packs': total_packs,
        'total_rm_cost': round(total_rm_cost, 2),
        'total_surplus_cost': round(total_surplus_cost, 2),
        'total_rm_cost_with_gst': round(total_rm_cost * 1.18, 2),
        'phase_counts': phase_counts,
        'rms_to_buy_count': len(rms_to_buy),
        'costings': active_products,
        'rm_orders': rm_orders,
    }
