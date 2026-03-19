"""
One-time seed: imports all data from the Excel workbook into Google Sheets.
Run this once to populate the sheets.
"""

import os
import sys
import time
import openpyxl
import gspread

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

EXCEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'MOQ and Costing V6-2 (1).xlsx')
CREDS_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
SHEET_ID = "1HAYm6Jm1_Inakqv04krAruHUQbryZoTff7OQckMAZsA"

# Product column mapping in the Excel (columns E-S in Formulation-SKU)
PRODUCT_COLUMNS = {
    'E': 'WM-TAB', 'F': 'WM-POW', 'G': 'PPCOS-Pro-TAB', 'H': 'PPCOS-Pro-POW',
    'I': 'ENERGY-POW', 'J': 'ENERGY-GEL', 'K': 'Dys-Tablet', 'L': 'Dys-Pow',
    'M': 'Diabetic-Tablet', 'N': 'Diabetic-powder', 'O': 'LIVER-TAB',
    'P': 'Liver-powder', 'Q': 'GUT-POW', 'R': 'GUT-CAP', 'S': 'PCOS-TAB',
}

PRODUCT_META = {
    'WM-TAB': ('WM', 'TAB'), 'WM-POW': ('WM', 'POW'),
    'PPCOS-Pro-TAB': ('PPCOS-Pro', 'TAB'), 'PPCOS-Pro-POW': ('PPCOS-Pro', 'POW'),
    'ENERGY-POW': ('ENERGY', 'POW'), 'ENERGY-GEL': ('ENERGY', 'GEL'),
    'Dys-Tablet': ('Dys', 'TAB'), 'Dys-Pow': ('Dys', 'POW'),
    'Diabetic-Tablet': ('Diabetic', 'TAB'), 'Diabetic-powder': ('Diabetic', 'POW'),
    'LIVER-TAB': ('LIVER', 'TAB'), 'Liver-powder': ('LIVER', 'POW'),
    'GUT-POW': ('GUT', 'POW'), 'GUT-CAP': ('GUT', 'CAP'),
    'PCOS-TAB': ('PCOS', 'TAB'),
}

UNIT_REQ_COL = {
    'WM-TAB': 4, 'WM-POW': 5, 'PPCOS-Pro-TAB': 6, 'PPCOS-Pro-POW': 7,
    'ENERGY-POW': 8, 'ENERGY-GEL': 9, 'Dys-Tablet': 10, 'Dys-Pow': 11,
    'Diabetic-Tablet': 12, 'Diabetic-powder': 13, 'LIVER-TAB': 14,
    'Liver-powder': 15, 'GUT-POW': 16, 'GUT-CAP': 17, 'PCOS-TAB': 18,
}

SCHEMAS = {
    'raw_materials': ['id', 'name', 'moq_kg', 'rate_per_kg', 'category', 'source',
                      'negotiator', 'vendor1', 'vendor2', 'vendor3', 'remarks'],
    'products': ['id', 'base_code', 'category', 'delivery_form', 'daily_consumption',
                 'units_per_pack', 'processing_cost_per_unit', 'packaging_cost_per_pack',
                 'clinical_trial_required', 'clinical_duration_months', 'clinical_participants',
                 'clinical_packs_per_month', 'margin_percent', 'buffer_percent'],
    'formulations': ['id', 'product_id', 'raw_material_id', 'grams_per_unit'],
    'skus': ['id', 'product_id', 'flavour_code', 'flavour_name', 'sku_code', 'pack_count', 'phase'],
    'packaging_configs': ['id', 'delivery_form', 'component_name', 'cost_per_pack'],
    'inventory': ['id', 'raw_material_id', 'qty_grams', 'location'],
    'launch_phases': ['id', 'phase_number', 'start_date', 'gap_days'],
}


def col_idx(letter):
    idx = 0
    for ch in letter:
        idx = idx * 26 + (ord(ch.upper()) - ord('A') + 1)
    return idx


def val(ws, row, col):
    v = ws.cell(row=row, column=col).value
    if v is None:
        return 0
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return v
    return v


def safe_str(v):
    if v is None:
        return ''
    return str(v)


def safe_float(v, default=0):
    if v is None or v == '':
        return default
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return default
    return float(v)


def batch_write(ws, rows, schema):
    """Write rows in batches to respect rate limits."""
    BATCH_SIZE = 50
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        # Convert each row dict to list in schema order
        values = []
        for row in batch:
            values.append([safe_str(row.get(col, '')) for col in schema])
        start_row = i + 2  # +1 for header, +1 for 1-indexed
        end_col = chr(ord('A') + len(schema) - 1)
        ws.update(f'A{start_row}:{end_col}{start_row + len(values) - 1}',
                  values, value_input_option='RAW')
        if i + BATCH_SIZE < len(rows):
            time.sleep(1)  # Rate limit


def seed():
    print("Connecting to Google Sheets...")
    gc = gspread.service_account(filename=CREDS_FILE)
    ss = gc.open_by_key(SHEET_ID)

    # Create/clear all worksheets
    existing = {ws.title: ws for ws in ss.worksheets()}
    for table_name, schema in SCHEMAS.items():
        if table_name in existing:
            ws = existing[table_name]
            ws.clear()
            ws.update('A1', [schema])
        else:
            ws = ss.add_worksheet(title=table_name, rows=1000, cols=len(schema))
            ws.update('A1', [schema])
        ws.format('A1:Z1', {'textFormat': {'bold': True}})
        time.sleep(0.5)

    # Remove default Sheet1 if it exists
    if 'Sheet1' in existing:
        try:
            ss.del_worksheet(existing['Sheet1'])
        except Exception:
            pass

    print(f"Loading Excel: {EXCEL_PATH}")
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)

    # =============================================
    # 1. RAW MATERIALS
    # =============================================
    print("Importing raw materials...")
    ws_rm = wb['RM Proqurement & MOQ']
    rm_rows = []
    rm_id = 0

    for row in range(3, ws_rm.max_row + 1):
        name = ws_rm.cell(row=row, column=3).value
        if not name or not isinstance(name, str) or name.strip() == '':
            continue
        name = name.strip()
        rm_id += 1

        moq = safe_float(val(ws_rm, row, 5))
        rate = safe_float(val(ws_rm, row, 6))
        category = val(ws_rm, row, 7)
        source = val(ws_rm, row, 8)
        negotiator = val(ws_rm, row, 4)
        vendor1 = val(ws_rm, row, 10)
        vendor2 = val(ws_rm, row, 11)
        vendor3 = val(ws_rm, row, 12)
        remarks = val(ws_rm, row, 13)

        rm_rows.append({
            'id': rm_id, 'name': name,
            'moq_kg': moq, 'rate_per_kg': rate,
            'category': safe_str(category) if not isinstance(category, (int, float)) else '',
            'source': safe_str(source) if not isinstance(source, (int, float)) else '',
            'negotiator': safe_str(negotiator) if not isinstance(negotiator, (int, float)) else '',
            'vendor1': safe_str(vendor1) if not isinstance(vendor1, (int, float)) else '',
            'vendor2': safe_str(vendor2) if not isinstance(vendor2, (int, float)) else '',
            'vendor3': safe_str(vendor3) if not isinstance(vendor3, (int, float)) else '',
            'remarks': safe_str(remarks) if not isinstance(remarks, (int, float)) else '',
        })

    ws = ss.worksheet('raw_materials')
    batch_write(ws, rm_rows, SCHEMAS['raw_materials'])
    print(f"  Imported {len(rm_rows)} raw materials")

    # Build name->id map
    rm_name_to_id = {r['name']: r['id'] for r in rm_rows}
    time.sleep(1)

    # =============================================
    # 2. PRODUCTS
    # =============================================
    print("Importing products...")
    ws_ur = wb['Unit Requirement']
    ws_uc = wb['Unit Cost']
    prod_rows = []
    prod_id = 0
    product_id_map = {}

    uc_col_map = {
        'WM-TAB': 5, 'WM-POW': 6, 'PPCOS-Pro-TAB': 7, 'PPCOS-Pro-POW': 8,
        'ENERGY-POW': 9, 'ENERGY-GEL': 10, 'Dys-Tablet': 11, 'Dys-Pow': 12,
        'Diabetic-Tablet': 13, 'Diabetic-powder': 14, 'LIVER-TAB': 15,
        'Liver-powder': 16, 'GUT-POW': 17, 'GUT-CAP': 18, 'PCOS-TAB': 19,
    }

    for base_code, (category, delivery_form) in PRODUCT_META.items():
        prod_id += 1
        col = UNIT_REQ_COL[base_code]
        uc_col = uc_col_map[base_code]

        clinical_req = str(val(ws_ur, 4, col)).strip()
        clinical = 1 if clinical_req.lower() == 'yes' else 0
        duration = safe_float(val(ws_ur, 5, col))
        participants = safe_float(val(ws_ur, 7, col))
        packs_month = safe_float(val(ws_ur, 8, col))
        units_per_pack = safe_float(val(ws_ur, 14, col), 30)
        daily_cons = safe_float(val(ws_uc, 4, uc_col), 1)
        processing = safe_float(val(ws_uc, 113, uc_col), 2)
        packaging = safe_float(val(ws_uc, 131, uc_col), 0)
        margin = safe_float(val(ws_uc, 118, uc_col), 0.70)

        prod_rows.append({
            'id': prod_id, 'base_code': base_code,
            'category': category, 'delivery_form': delivery_form,
            'daily_consumption': int(daily_cons),
            'units_per_pack': int(units_per_pack),
            'processing_cost_per_unit': processing,
            'packaging_cost_per_pack': packaging,
            'clinical_trial_required': clinical,
            'clinical_duration_months': int(duration),
            'clinical_participants': int(participants),
            'clinical_packs_per_month': int(packs_month) if packs_month else 1,
            'margin_percent': margin,
            'buffer_percent': 0.10,
        })
        product_id_map[base_code] = prod_id

    ws = ss.worksheet('products')
    batch_write(ws, prod_rows, SCHEMAS['products'])
    print(f"  Imported {len(prod_rows)} products")
    time.sleep(1)

    # =============================================
    # 3. FORMULATIONS
    # =============================================
    print("Importing formulations...")
    ws_form = wb['Formulation - SKU']
    form_rows = []
    form_id = 0

    for row in range(6, ws_form.max_row + 1):
        rm_name = ws_form.cell(row=row, column=3).value
        if not rm_name or not isinstance(rm_name, str) or rm_name.strip() == '':
            continue
        rm_name = rm_name.strip()
        rm_id_val = rm_name_to_id.get(rm_name)
        if not rm_id_val:
            continue

        for col_letter, base_code in PRODUCT_COLUMNS.items():
            ci = col_idx(col_letter)
            grams = ws_form.cell(row=row, column=ci).value
            if not grams or grams == 0:
                continue
            try:
                grams_val = float(grams)
            except (ValueError, TypeError):
                continue
            if grams_val <= 0:
                continue

            prod_id_val = product_id_map.get(base_code)
            if not prod_id_val:
                continue

            form_id += 1
            form_rows.append({
                'id': form_id,
                'product_id': prod_id_val,
                'raw_material_id': rm_id_val,
                'grams_per_unit': grams_val,
            })

    ws = ss.worksheet('formulations')
    batch_write(ws, form_rows, SCHEMAS['formulations'])
    print(f"  Imported {len(form_rows)} formulation entries")
    time.sleep(1)

    # =============================================
    # 4. SKUs
    # =============================================
    print("Importing SKUs...")
    ws_lp = wb['Launch Plan']
    sku_rows = []
    sku_id = 0

    for row in range(5, 22):
        category = ws_lp.cell(row=row, column=4).value
        delivery = ws_lp.cell(row=row, column=5).value
        flavour_code = ws_lp.cell(row=row, column=6).value
        flavour_name = ws_lp.cell(row=row, column=7).value
        sku_code = ws_lp.cell(row=row, column=8).value
        pack_count = ws_lp.cell(row=row, column=9).value

        if not category or not delivery:
            continue

        phase = 1
        for p, col in [(1, 10), (2, 11), (3, 12), (4, 13)]:
            v = ws_lp.cell(row=row, column=col).value
            if v and v == 1:
                phase = p
                break

        base_code = f"{category}-{delivery}"
        prod_id_val = product_id_map.get(base_code)
        if not prod_id_val:
            for bc, pid in product_id_map.items():
                if category in bc and delivery in bc:
                    prod_id_val = pid
                    break

        if not prod_id_val:
            print(f"  WARNING: No product match for {base_code}")
            continue

        if not sku_code or str(sku_code).startswith('='):
            sku_code = f"{str(category)[:2]}-{delivery}-{flavour_code}-{str(flavour_name or 'XX')[:2]}"

        sku_id += 1
        sku_rows.append({
            'id': sku_id,
            'product_id': prod_id_val,
            'flavour_code': safe_str(flavour_code),
            'flavour_name': safe_str(flavour_name),
            'sku_code': safe_str(sku_code),
            'pack_count': int(pack_count) if pack_count else 0,
            'phase': phase,
        })

    ws = ss.worksheet('skus')
    batch_write(ws, sku_rows, SCHEMAS['skus'])
    print(f"  Imported {len(sku_rows)} SKUs")
    time.sleep(1)

    # =============================================
    # 5. PACKAGING CONFIGS
    # =============================================
    print("Importing packaging configs...")
    pkg_data = [
        ('GEL', 'Primary Sachets - Gel', 35),
        ('POW', 'Primary Sachets - Powder (30-day)', 81),
        ('TAB', 'Primary PET bottle 100cc', 9),
        ('CAP', 'Primary PET bottle 100cc', 9),
        ('TAB', 'Secondary Box for PET bottle', 90),
        ('CAP', 'Secondary Box for PET bottle', 90),
        ('TAB', 'Clear label for PET bottle', 6),
        ('CAP', 'Clear label for PET bottle', 6),
        ('TAB', 'Stickers on secondary box', 0.25),
        ('CAP', 'Stickers on secondary box', 0.25),
        ('POW', 'Secondary box for 30-sachets', 90),
    ]
    pkg_rows = []
    for i, (df, comp, cost) in enumerate(pkg_data, 1):
        pkg_rows.append({'id': i, 'delivery_form': df, 'component_name': comp, 'cost_per_pack': cost})

    ws = ss.worksheet('packaging_configs')
    batch_write(ws, pkg_rows, SCHEMAS['packaging_configs'])
    print(f"  Imported {len(pkg_rows)} packaging configs")
    time.sleep(1)

    # =============================================
    # 6. INVENTORY
    # =============================================
    print("Importing inventory...")
    ws_inv = wb['material availability @ karsy']
    inv_rows = []
    inv_id = 0

    for row in range(3, ws_inv.max_row + 1):
        rm_name = ws_inv.cell(row=row, column=3).value
        qty_raw = ws_inv.cell(row=row, column=4).value

        if not rm_name or not isinstance(rm_name, str):
            continue
        rm_name = rm_name.strip()
        rm_id_val = rm_name_to_id.get(rm_name)
        if not rm_id_val:
            continue

        qty_grams = 0
        if qty_raw:
            qty_str = str(qty_raw).strip().lower()
            if qty_str == 'available':
                qty_grams = 999999
            elif qty_str.endswith('g'):
                try:
                    qty_grams = float(qty_str[:-1])
                except ValueError:
                    pass
            else:
                try:
                    qty_grams = float(qty_str)
                except ValueError:
                    pass

        if qty_grams > 0:
            inv_id += 1
            inv_rows.append({
                'id': inv_id,
                'raw_material_id': rm_id_val,
                'qty_grams': qty_grams,
                'location': 'Karsy',
            })

    ws = ss.worksheet('inventory')
    batch_write(ws, inv_rows, SCHEMAS['inventory'])
    print(f"  Imported {len(inv_rows)} inventory entries")
    time.sleep(1)

    # =============================================
    # 7. LAUNCH PHASES
    # =============================================
    print("Importing launch phases...")
    ws_lp2 = wb['Launch Plan']
    phase_rows = []
    for phase_num in range(1, 5):
        date_val = val(ws_lp2, 3, 9 + phase_num)
        if hasattr(date_val, 'strftime'):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val)
        gap = 0 if phase_num == 1 else 90
        phase_rows.append({
            'id': phase_num, 'phase_number': phase_num,
            'start_date': date_str, 'gap_days': gap,
        })

    ws = ss.worksheet('launch_phases')
    batch_write(ws, phase_rows, SCHEMAS['launch_phases'])
    print("  Imported 4 launch phases")

    wb.close()
    print("\nDone! Google Sheet seeded successfully.")
    print(f"View at: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == '__main__':
    seed()
