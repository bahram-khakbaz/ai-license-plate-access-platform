from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

import storage

COLUMNS = [
    ('plate', 'Plate'),
    ('driver_name', 'Driver Name'),
    ('phone', 'Phone'),
    ('unit', 'Unit / Department'),
    ('vehicle_model', 'Vehicle Model'),
    ('vehicle_color', 'Vehicle Color'),
    ('status', 'Status'),
]

SAMPLE = ['12A34567', 'John Doe', '+0000000000', 'Security', 'Sedan', 'White', 'allowed']


def build_vehicle_template():
    wb = Workbook()
    ws = wb.active
    ws.title = 'vehicles'
    headers = [label for _, label in COLUMNS]
    ws.append(headers)
    ws.append(SAMPLE)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1F4E78')
        cell.alignment = Alignment(horizontal='center')
    widths = [18, 24, 18, 24, 20, 18, 16]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + idx)].width = width
    ws.freeze_panes = 'A2'
    notes = wb.create_sheet('README')
    notes.append(['Column', 'Description'])
    notes.append(['Plate', 'Required. Unique per site. Example: 12A34567'])
    notes.append(['Status', 'allowed, review, unknown'])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def read_vehicle_excel(file_storage):
    wb = load_workbook(file_storage, data_only=True)
    ws = wb.active
    header = [str(c.value or '').strip() for c in ws[1]]
    mapping = {}
    for idx, value in enumerate(header):
        normalized = value.lower().replace(' ', '_').replace('/', '_')
        for key, label in COLUMNS:
            if normalized in (key, label.lower().replace(' ', '_').replace('/', '_')):
                mapping[idx] = key
    rows = []
    for number, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        item = {'_row': number}
        for idx, value in enumerate(row):
            key = mapping.get(idx)
            if key:
                item[key] = str(value or '').strip()
        if item.get('plate'):
            rows.append(item)
    return rows


def import_vehicles_excel(file_storage, default_site_id=None):
    result = {'imported': 0, 'errors': []}
    if not file_storage:
        result['errors'].append({'row': '-', 'error': 'No file uploaded'})
        return result
    try:
        rows = read_vehicle_excel(file_storage)
    except Exception as exc:
        result['errors'].append({'row': '-', 'error': f'Could not read Excel file: {exc}'})
        return result
    for item in rows:
        row_num = item.pop('_row', '-')
        try:
            item['site_id'] = default_site_id
            storage.save_vehicle(item)
            result['imported'] += 1
        except Exception as exc:
            result['errors'].append({'row': row_num, 'error': str(exc)})
    return result
