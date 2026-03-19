"""
Calculation engine — replaces all Excel formulas.
All monetary values in INR. Weights in grams unless noted.

Optimized: loads all data once from Google Sheets, computes everything in memory.
"""

from app.db import fetch_all, fetch_one, _get_all_rows


def _load_all_data():
    """Load all tables once. Returns a dict of all data needed for calculations."""
    products = _get_all_rows('products')
    formulations = _get_all_rows('formulations')
    raw_materials = _get_all_rows('raw_materials')
    skus = _get_all_rows('skus')
    inventory = _get_all_rows('inventory')
    packaging = _get_all_rows('packaging_configs')

    # Build lookup maps
    rm_map = {int(r['id']): r for r in raw_materials}
    inv_map = {int(i['raw_material_id']): i for i in inventory}
    pkg_map = {}
    for p in packaging:
        df = p['delivery_form']
        if df not in pkg_map:
            pkg_map[df] = 0
        pkg_map[df] += p['cost_per_pack']

    # Group formulations by product_id
    form_by_product = {}
    for f in formulations:
        pid = int(f['product_id'])
        if pid not in form_by_product:
            form_by_product[pid] = []
        form_by_product[pid].append(f)

    # Group SKUs by product_id
    sku_by_product = {}
    for s in skus:
        pid = int(s['product_id'])
        if pid not in sku_by_product:
            sku_by_product[pid] = []
        sku_by_product[pid].append(s)

    return {
        'products': products,
        'raw_materials': raw_materials,
        'rm_map': rm_map,
        'inv_map': inv_map,
        'pkg_map': pkg_map,
        'form_by_product': form_by_product,
        'sku_by_product': sku_by_product,
        'skus': skus,
        'formulations': formulations,
    }


def _calc_product_costing(product, data):
    """Calculate costing for a single product using pre-loaded data."""
    pid = int(product['id'])
    units = int(product['units_per_pack'])

    # Unit RM cost
    forms = data['form_by_product'].get(pid, [])
    unit_rm_cost = 0
    for f in forms:
        if f['grams_per_unit'] <= 0:
            continue
        rm = data['rm_map'].get(int(f['raw_material_id']))
        if rm:
            unit_rm_cost += f['grams_per_unit'] * rm['rate_per_kg'] / 1000

    pack_rm_cost = unit_rm_cost * units

    # Packaging cost
    pack_pm_cost = product['packaging_cost_per_pack']
    if not pack_pm_cost or pack_pm_cost <= 0:
        pack_pm_cost = data['pkg_map'].get(product['delivery_form'], 0)

    # Processing
    proc_per_unit = product['processing_cost_per_unit']
    processing_cost = proc_per_unit * units

    # Total (Excel includes proc_per_unit + proc_total)
    total_cost = pack_rm_cost + pack_pm_cost + proc_per_unit + processing_cost
    buffer = total_cost * product['buffer_percent']
    net_total = total_cost + buffer

    # Margin & SP (Excel formula)
    margin_pct = product['margin_percent']
    gross_margin = net_total / (1 - margin_pct) if margin_pct < 1 else 0
    selling_price = net_total + margin_pct + gross_margin
    multiplier = selling_price / net_total if net_total > 0 else 0

    # Packs
    product_skus = data['sku_by_product'].get(pid, [])
    total_packs = sum(int(s['pack_count']) for s in product_skus)

    trial_packs = 0
    if product['clinical_trial_required']:
        trial_packs = (int(product['clinical_duration_months']) *
                       int(product['clinical_participants']) *
                       int(product['clinical_packs_per_month']))

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


def get_product_costing(product_id):
    """Single product costing."""
    data = _load_all_data()
    for p in data['products']:
        if int(p['id']) == int(product_id):
            return _calc_product_costing(p, data)
    return None


def get_all_product_costings():
    """Costing for every product — single batch load."""
    data = _load_all_data()
    return [_calc_product_costing(p, data) for p in data['products']]


def get_product_total_packs(product_id):
    """Sum of all SKU pack counts for this product."""
    skus = _get_all_rows('skus')
    return sum(int(s['pack_count']) for s in skus if int(s['product_id']) == int(product_id))


def get_rm_order_requirements():
    """
    For each raw material, calculate total qty needed across all products,
    MOQ gap, actual cost, surplus cost, and inventory status.
    Single batch load — no per-item API calls.
    """
    data = _load_all_data()

    # Pre-calculate total units per product
    product_total_units = {}
    for p in data['products']:
        pid = int(p['id'])
        total_packs = sum(int(s['pack_count']) for s in data['sku_by_product'].get(pid, []))
        product_total_units[pid] = int(p['units_per_pack']) * total_packs

    # Build product map for name lookup
    product_map = {int(p['id']): p for p in data['products']}

    results = []
    for rm in data['raw_materials']:
        rm_id = int(rm['id'])
        total_grams = 0
        product_breakdown = []

        # Find all formulations using this RM
        for f in data['formulations']:
            if int(f['raw_material_id']) != rm_id or f['grams_per_unit'] <= 0:
                continue

            pid = int(f['product_id'])
            total_units = product_total_units.get(pid, 0)
            if total_units == 0:
                continue

            grams_needed = f['grams_per_unit'] * total_units
            total_grams += grams_needed

            prod = product_map.get(pid)
            product_breakdown.append({
                'product': prod['base_code'] if prod else f'Product {pid}',
                'grams_per_unit': f['grams_per_unit'],
                'total_units': total_units,
                'grams_needed': round(grams_needed, 2),
            })

        total_kg = total_grams / 1000
        moq_kg = rm['moq_kg'] or 0
        rate = rm['rate_per_kg'] or 0

        order_kg = max(total_kg, moq_kg) if total_kg > 0 else 0
        actual_cost = order_kg * rate
        surplus_kg = max(0, moq_kg - total_kg) if total_kg > 0 else 0
        surplus_cost = surplus_kg * rate

        inv = data['inv_map'].get(rm_id)
        inv_grams = inv['qty_grams'] if inv else 0
        inv_status = 'sufficient' if inv_grams >= total_grams else ('partial' if inv_grams > 0 else 'none')
        shortfall_grams = max(0, total_grams - inv_grams)

        results.append({
            'raw_material': rm['name'],
            'rm_id': rm_id,
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
    """High-level numbers for the dashboard. Single batch load."""
    data = _load_all_data()

    costings = [_calc_product_costing(p, data) for p in data['products']]
    rm_orders = get_rm_order_requirements()

    active_products = [c for c in costings if c and c['total_packs'] > 0]
    total_rm_cost = sum(r['actual_cost'] for r in rm_orders if r['total_grams_needed'] > 0)
    total_surplus_cost = sum(r['surplus_cost'] for r in rm_orders)
    total_packs = sum(c['total_packs'] for c in active_products)

    phase_counts = {}
    for s in data['skus']:
        ph = int(s['phase'])
        phase_counts[ph] = phase_counts.get(ph, 0) + 1

    rms_to_buy = [r for r in rm_orders if r['shortfall_grams'] > 0 and r['total_grams_needed'] > 0]

    return {
        'total_products': len(costings),
        'active_products': len(active_products),
        'total_skus': len(data['skus']),
        'total_packs': total_packs,
        'total_rm_cost': round(total_rm_cost, 2),
        'total_surplus_cost': round(total_surplus_cost, 2),
        'total_rm_cost_with_gst': round(total_rm_cost * 1.18, 2),
        'phase_counts': phase_counts,
        'rms_to_buy_count': len(rms_to_buy),
        'costings': active_products,
        'rm_orders': rm_orders,
    }
