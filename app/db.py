"""
Database layer — Google Sheets as backend via gspread.
Each table = one worksheet tab. Row 1 = headers. Column A = id.
"""

import gspread
import os
import json
import time
import streamlit as st

SHEET_ID = "1HAYm6Jm1_Inakqv04krAruHUQbryZoTff7OQckMAZsA"
CREDS_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')

# Table schemas: table_name -> list of column names (id is always first)
SCHEMAS = {
    'raw_materials': [
        'id', 'name', 'moq_kg', 'rate_per_kg', 'category', 'source',
        'negotiator', 'vendor1', 'vendor2', 'vendor3', 'remarks'
    ],
    'products': [
        'id', 'base_code', 'category', 'delivery_form', 'daily_consumption',
        'units_per_pack', 'processing_cost_per_unit', 'packaging_cost_per_pack',
        'clinical_trial_required', 'clinical_duration_months', 'clinical_participants',
        'clinical_packs_per_month', 'margin_percent', 'buffer_percent'
    ],
    'formulations': [
        'id', 'product_id', 'raw_material_id', 'grams_per_unit'
    ],
    'skus': [
        'id', 'product_id', 'flavour_code', 'flavour_name', 'sku_code',
        'pack_count', 'phase'
    ],
    'packaging_configs': [
        'id', 'delivery_form', 'component_name', 'cost_per_pack'
    ],
    'inventory': [
        'id', 'raw_material_id', 'qty_grams', 'location'
    ],
    'launch_phases': [
        'id', 'phase_number', 'start_date', 'gap_days'
    ],
}

# Numeric columns (will be cast to float on read)
NUMERIC_COLS = {
    'id', 'moq_kg', 'rate_per_kg', 'daily_consumption', 'units_per_pack',
    'processing_cost_per_unit', 'packaging_cost_per_pack', 'clinical_trial_required',
    'clinical_duration_months', 'clinical_participants', 'clinical_packs_per_month',
    'margin_percent', 'buffer_percent', 'product_id', 'raw_material_id',
    'grams_per_unit', 'pack_count', 'phase', 'cost_per_pack', 'qty_grams',
    'phase_number', 'gap_days',
}


_cache = {}


def _get_client():
    """Get authenticated gspread client."""
    if 'gs_client' not in _cache:
        if os.path.exists(CREDS_FILE):
            _cache['gs_client'] = gspread.service_account(filename=CREDS_FILE)
        else:
            # For Streamlit Cloud: credentials stored in secrets (TOML format)
            creds_dict = dict(st.secrets["gcp_service_account"])
            _cache['gs_client'] = gspread.service_account_from_dict(creds_dict)
    return _cache['gs_client']


def _get_spreadsheet():
    """Get the spreadsheet."""
    if 'gs_spreadsheet' not in _cache:
        client = _get_client()
        _cache['gs_spreadsheet'] = client.open_by_key(SHEET_ID)
    return _cache['gs_spreadsheet']


def _get_worksheet(table_name):
    """Get or create a worksheet for a table."""
    ss = _get_spreadsheet()
    try:
        ws = ss.worksheet(table_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=table_name, rows=1000, cols=len(SCHEMAS[table_name]))
        ws.update('A1', [SCHEMAS[table_name]])
        ws.format('A1:Z1', {'textFormat': {'bold': True}})
    return ws


def _parse_row(headers, row_values):
    """Convert a sheet row into a dict with proper types."""
    d = {}
    for i, h in enumerate(headers):
        val = row_values[i] if i < len(row_values) else ''
        if h in NUMERIC_COLS:
            try:
                val = float(val) if val != '' else 0
            except (ValueError, TypeError):
                val = 0
        d[h] = val
    return d


# Cache for reducing API calls — cleared on writes
def _invalidate_cache(table_name=None):
    """Clear cached data."""
    if table_name:
        key = f'cache_{table_name}'
        _cache.pop(key, None)
    else:
        keys_to_del = [k for k in _cache if k.startswith('cache_')]
        for k in keys_to_del:
            del _cache[k]


def _get_all_rows(table_name):
    """Get all rows from a table, with caching."""
    key = f'cache_{table_name}'
    if key not in _cache:
        ws = _get_worksheet(table_name)
        data = ws.get_all_values()
        if len(data) <= 1:
            _cache[key] = []
        else:
            headers = data[0]
            _cache[key] = [_parse_row(headers, row) for row in data[1:] if any(v.strip() for v in row)]
    return _cache[key]


# =============================================
# Public API — same interface as the old SQLite db.py
# =============================================

def init_db():
    """Create all worksheet tabs if they don't exist."""
    ss = _get_spreadsheet()
    existing = [ws.title for ws in ss.worksheets()]
    for table_name, columns in SCHEMAS.items():
        if table_name not in existing:
            ws = ss.add_worksheet(title=table_name, rows=1000, cols=len(columns))
            ws.update('A1', [columns])
            ws.format('A1:Z1', {'textFormat': {'bold': True}})
            time.sleep(0.5)  # Rate limit


def fetch_all(query, params=()):
    """
    Emulate SQL SELECT queries using in-memory filtering on sheet data.
    Supports basic patterns used in our app.
    """
    # Parse the query to determine what to do
    query_lower = query.strip().lower()

    # Route to the right handler
    if 'from raw_materials' in query_lower:
        return _query_raw_materials(query, params)
    elif 'from products' in query_lower:
        return _query_products(query, params)
    elif 'from formulations' in query_lower:
        return _query_formulations(query, params)
    elif 'from skus' in query_lower:
        return _query_skus(query, params)
    elif 'from packaging_configs' in query_lower:
        return _query_packaging(query, params)
    elif 'from inventory' in query_lower:
        return _query_inventory(query, params)
    elif 'from launch_phases' in query_lower:
        return _query_launch_phases(query, params)
    else:
        return []


def fetch_one(query, params=()):
    """Fetch first result from fetch_all."""
    results = fetch_all(query, params)
    return results[0] if results else None


def execute(query, params=()):
    """Execute INSERT, UPDATE, DELETE."""
    query_lower = query.strip().lower()
    if query_lower.startswith('insert'):
        return _execute_insert(query, params)
    elif query_lower.startswith('update'):
        return _execute_update(query, params)
    elif query_lower.startswith('delete'):
        return _execute_delete(query, params)


def execute_many(query, params_list):
    for params in params_list:
        execute(query, params)


def execute_returning(query, params=()):
    return _execute_insert(query, params)


# =============================================
# Query handlers — in-memory filtering
# =============================================

def _query_raw_materials(query, params):
    rows = _get_all_rows('raw_materials')
    q = query.lower()

    if 'left join inventory' in q:
        inv_rows = _get_all_rows('inventory')
        inv_map = {int(i['raw_material_id']): i for i in inv_rows}
        result = []
        for r in rows:
            r = dict(r)
            inv = inv_map.get(int(r['id']), {})
            r['stock_grams'] = inv.get('qty_grams', 0)
            result.append(r)
        return sorted(result, key=lambda x: str(x.get('name', '')))

    if 'where' in q and params:
        return _filter_by_id(rows, params)

    return sorted(rows, key=lambda x: str(x.get('name', '')))


def _query_products(query, params):
    rows = _get_all_rows('products')
    q = query.lower()

    if 'select p.*' in q or 'ingredient_count' in q or 'sku_count' in q:
        # Enriched product query
        form_rows = _get_all_rows('formulations')
        sku_rows = _get_all_rows('skus')
        result = []
        for p in rows:
            p = dict(p)
            pid = int(p['id'])
            p['ingredient_count'] = sum(1 for f in form_rows
                                        if int(f['product_id']) == pid and f['grams_per_unit'] > 0)
            p['sku_count'] = sum(1 for s in sku_rows if int(s['product_id']) == pid)
            p['total_packs'] = sum(int(s['pack_count']) for s in sku_rows if int(s['product_id']) == pid)
            result.append(p)
        return sorted(result, key=lambda x: str(x.get('base_code', '')))

    if 'where' in q and params:
        return _filter_by_id(rows, params)

    return sorted(rows, key=lambda x: str(x.get('base_code', '')))


def _query_formulations(query, params):
    rows = _get_all_rows('formulations')
    q = query.lower()

    if 'join raw_materials' in q and 'join products' in q:
        # Full join query for costing page
        rm_rows = _get_all_rows('raw_materials')
        rm_map = {int(r['id']): r for r in rm_rows}
        result = []
        for f in rows:
            if f['grams_per_unit'] <= 0:
                continue
            rm = rm_map.get(int(f['raw_material_id']))
            if not rm:
                continue
            pid_match = True
            if params:
                pid_match = int(f['product_id']) == int(params[0])
            if pid_match:
                r = dict(f)
                r['name'] = rm['name']
                r['rm_name'] = rm['name']
                r['rm_id'] = rm['id']
                r['rate_per_kg'] = rm['rate_per_kg']
                r['rm_category'] = rm['category']
                r['cost_per_unit'] = f['grams_per_unit'] * rm['rate_per_kg'] / 1000
                result.append(r)
        return sorted(result, key=lambda x: x.get('cost_per_unit', 0), reverse=True)

    if 'join raw_materials' in q:
        rm_rows = _get_all_rows('raw_materials')
        rm_map = {int(r['id']): r for r in rm_rows}
        result = []
        for f in rows:
            rm = rm_map.get(int(f['raw_material_id']))
            if not rm:
                continue
            pid_match = True
            if params:
                pid_match = int(f['product_id']) == int(params[0])
            if pid_match and f['grams_per_unit'] > 0:
                r = dict(f)
                r['rm_name'] = rm['name']
                r['rm_id'] = rm['id']
                r['rate_per_kg'] = rm['rate_per_kg']
                r['rm_category'] = rm['category']
                result.append(r)
        return sorted(result, key=lambda x: x.get('grams_per_unit', 0), reverse=True)

    if 'where' in q and params:
        if 'product_id' in q and 'raw_material_id' in q:
            return [f for f in rows
                    if int(f['product_id']) == int(params[0])
                    and int(f['raw_material_id']) == int(params[1])]
        elif 'product_id' in q:
            return [f for f in rows if int(f['product_id']) == int(params[0])]

    return rows


def _query_skus(query, params):
    rows = _get_all_rows('skus')
    q = query.lower()

    if 'join products' in q:
        prod_rows = _get_all_rows('products')
        prod_map = {int(p['id']): p for p in prod_rows}
        result = []
        for s in rows:
            p = prod_map.get(int(s['product_id']))
            if p:
                r = dict(s)
                r['base_code'] = p['base_code']
                r['category'] = p['category']
                r['delivery_form'] = p['delivery_form']
                r['units_per_pack'] = p['units_per_pack']
                result.append(r)
        return sorted(result, key=lambda x: (x.get('phase', 0), str(x.get('category', ''))))

    if 'where' in q and 'product_id' in q and params:
        return [s for s in rows if int(s['product_id']) == int(params[0])]

    return rows


def _query_packaging(query, params):
    rows = _get_all_rows('packaging_configs')
    if params:
        return [r for r in rows if str(r['delivery_form']) == str(params[0])]
    return rows


def _query_inventory(query, params):
    rows = _get_all_rows('inventory')
    if params:
        return [r for r in rows if int(r.get('raw_material_id', 0)) == int(params[0])]
    return rows


def _query_launch_phases(query, params):
    rows = _get_all_rows('launch_phases')
    return sorted(rows, key=lambda x: x.get('phase_number', 0))


def _filter_by_id(rows, params):
    """Filter rows where id matches first param."""
    try:
        target_id = int(params[0])
        return [r for r in rows if int(r['id']) == target_id]
    except (ValueError, IndexError):
        return rows


# =============================================
# Write handlers
# =============================================

def _next_id(table_name):
    """Get next auto-increment ID."""
    rows = _get_all_rows(table_name)
    if not rows:
        return 1
    return max(int(r.get('id', 0)) for r in rows) + 1


def _execute_insert(query, params):
    """Handle INSERT queries."""
    q = query.lower()

    # Determine table
    table_name = None
    for t in SCHEMAS:
        if t in q:
            table_name = t
            break
    if not table_name:
        return None

    schema = SCHEMAS[table_name]
    ws = _get_worksheet(table_name)

    # Handle ON CONFLICT (upsert)
    if 'on conflict' in q:
        return _execute_upsert(table_name, query, params)

    # Handle OR REPLACE / OR IGNORE
    if 'or replace' in q or 'or ignore' in q:
        return _execute_upsert(table_name, query, params)

    # Parse column names from query
    import re
    col_match = re.search(r'\(([^)]+)\)\s*values', q)
    if not col_match:
        return None
    col_names = [c.strip() for c in col_match.group(1).split(',')]

    # Build row
    new_id = _next_id(table_name)
    row_dict = {'id': new_id}
    for i, col in enumerate(col_names):
        if i < len(params):
            row_dict[col] = params[i]

    # Convert to row in schema order
    row_values = []
    for col in schema:
        val = row_dict.get(col, '')
        row_values.append(str(val) if val is not None else '')

    ws.append_row(row_values, value_input_option='RAW')
    _invalidate_cache(table_name)
    return new_id


def _execute_upsert(table_name, query, params):
    """Handle INSERT ... ON CONFLICT ... DO UPDATE."""
    import re
    schema = SCHEMAS[table_name]
    ws = _get_worksheet(table_name)

    q = query.lower()
    col_match = re.search(r'\(([^)]+)\)\s*values', q)
    if not col_match:
        return None
    col_names = [c.strip() for c in col_match.group(1).split(',')]

    # Build the data dict from INSERT params
    data = {}
    for i, col in enumerate(col_names):
        if i < len(params):
            data[col] = params[i]

    # Determine conflict columns
    rows = _get_all_rows(table_name)

    # Find existing row based on unique keys
    existing = None
    existing_idx = None

    if table_name == 'formulations':
        for idx, r in enumerate(rows):
            if (int(r.get('product_id', 0)) == int(data.get('product_id', -1)) and
                int(r.get('raw_material_id', 0)) == int(data.get('raw_material_id', -1))):
                existing = r
                existing_idx = idx
                break
    elif table_name == 'inventory':
        for idx, r in enumerate(rows):
            if int(r.get('raw_material_id', 0)) == int(data.get('raw_material_id', -1)):
                existing = r
                existing_idx = idx
                break
    elif table_name == 'packaging_configs':
        for idx, r in enumerate(rows):
            if (str(r.get('delivery_form', '')) == str(data.get('delivery_form', '')) and
                str(r.get('component_name', '')) == str(data.get('component_name', ''))):
                existing = r
                existing_idx = idx
                break
    elif table_name == 'launch_phases':
        for idx, r in enumerate(rows):
            if int(r.get('phase_number', 0)) == int(data.get('phase_number', -1)):
                existing = r
                existing_idx = idx
                break
    elif table_name == 'skus':
        for idx, r in enumerate(rows):
            if str(r.get('sku_code', '')) == str(data.get('sku_code', '')):
                existing = r
                existing_idx = idx
                break
    elif table_name == 'raw_materials':
        for idx, r in enumerate(rows):
            if str(r.get('name', '')) == str(data.get('name', '')):
                existing = r
                existing_idx = idx
                break

    if existing:
        # Update: get the update columns from ON CONFLICT DO UPDATE SET
        # For simplicity, update all provided columns
        row_data = dict(existing)

        if 'do update set' in q:
            # Parse SET clause for specific columns
            set_match = re.search(r'do update set\s+(.+?)$', q)
            if set_match:
                set_clause = set_match.group(1)
                # Handle grams_per_unit=? or qty_grams=? patterns
                set_cols = re.findall(r'(\w+)\s*=\s*\?', set_clause)
                # The update params are at the end of the params tuple
                update_params = params[len(col_names):]
                for i, col in enumerate(set_cols):
                    if i < len(update_params):
                        row_data[col] = update_params[i]
        else:
            # OR REPLACE: update all columns
            for col in col_names:
                if col in data:
                    row_data[col] = data[col]

        row_values = [str(row_data.get(col, '')) for col in schema]
        ws.update(f'A{existing_idx + 2}', [row_values], value_input_option='RAW')
        _invalidate_cache(table_name)
        return int(existing['id'])
    else:
        # Insert new row
        if 'or ignore' in q:
            pass  # Still insert if no conflict found
        new_id = _next_id(table_name)
        data['id'] = new_id
        row_values = [str(data.get(col, '')) for col in schema]
        ws.append_row(row_values, value_input_option='RAW')
        _invalidate_cache(table_name)
        return new_id


def _execute_update(query, params):
    """Handle UPDATE queries."""
    import re
    q = query.lower()

    table_name = None
    for t in SCHEMAS:
        if t in q:
            table_name = t
            break
    if not table_name:
        return

    schema = SCHEMAS[table_name]
    ws = _get_worksheet(table_name)
    rows = _get_all_rows(table_name)

    # Parse SET clause
    set_match = re.search(r'set\s+(.+?)\s+where', q)
    if not set_match:
        return

    set_clause = set_match.group(1)
    set_cols = re.findall(r'(\w+)\s*=\s*\?', set_clause)

    # The last param is the WHERE id
    where_id = int(params[-1])
    set_values = params[:-1]

    for idx, r in enumerate(rows):
        if int(r['id']) == where_id:
            row_data = dict(r)
            for i, col in enumerate(set_cols):
                if i < len(set_values):
                    row_data[col] = set_values[i]

            row_values = [str(row_data.get(col, '')) for col in schema]
            ws.update(f'A{idx + 2}', [row_values], value_input_option='RAW')
            _invalidate_cache(table_name)
            return


def _execute_delete(query, params):
    """Handle DELETE queries."""
    q = query.lower()

    table_name = None
    for t in SCHEMAS:
        if t in q:
            table_name = t
            break
    if not table_name:
        return

    ws = _get_worksheet(table_name)
    rows = _get_all_rows(table_name)

    if not params:
        return

    # Find the row to delete
    if 'product_id' in q and 'raw_material_id' in q:
        for idx, r in enumerate(rows):
            if (int(r.get('product_id', 0)) == int(params[0]) and
                int(r.get('raw_material_id', 0)) == int(params[1])):
                ws.delete_rows(idx + 2)
                _invalidate_cache(table_name)
                return
    else:
        target_id = int(params[0])
        for idx, r in enumerate(rows):
            if int(r['id']) == target_id:
                ws.delete_rows(idx + 2)
                _invalidate_cache(table_name)
                return
