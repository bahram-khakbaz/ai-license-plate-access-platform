import os
import re
import json
import base64
import threading
import queue
import time
import cv2
import numpy as np
from flask import session, redirect,  Flask, request, jsonify, render_template, send_from_directory, make_response, Response, stream_with_context
from PIL import Image
import db
import camera_manager as cm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))


app.secret_key = os.environ.get('SECRET_KEY') or 'change-me-dev-secret-key'
with open(os.path.join(BASE_DIR, 'plate_data.json'), encoding='utf-8') as f:
    PLATE_DATA = json.load(f)

FA_TO_EN = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')

# ── Models: lazy-loaded in background threads ──
det_model = None
ocr_model = None
models_ready = False
models_error = None
_load_lock = threading.Lock()

def _load_models():
    global det_model, ocr_model, models_ready, models_error
    try:
        from ultralytics import YOLO
        from hezar.models import Model
        print("Loading models | در حال بارگذاری مدل‌ها...")
        det_model = YOLO(os.path.join(BASE_DIR, 'best.pt'))
        ocr_model = Model.load("/root/.cache/hezar/models--hezarai--crnn-fa-license-plate-recognition-v2/snapshots/8f629aec2b5fb091e034317cb472dadd29640289")
        models_ready = True
        print("Models are ready | مدل‌ها آماده‌اند.")
    except Exception as e:
        models_error = str(e)
        print(f"Model load error | خطا در بارگذاری مدل‌ها: {e}")

def _after_models_loaded():
    """Inject models into camera_manager and start RTSP workers."""
    while not models_ready and not models_error:
        time.sleep(0.5)
    if models_ready:
        cm.det_model = det_model
        cm.ocr_model = ocr_model
        cm.start_all()

threading.Thread(target=_load_models, daemon=True).start()
threading.Thread(target=_after_models_loaded, daemon=True).start()


def lookup_plate(letter, suffix_fa):
    suffix = suffix_fa.translate(FA_TO_EN)
    vehicle_type = None
    for t in PLATE_DATA['carplate_types']:
        if letter in t['letters']:
            vehicle_type = t
            break
    matches = []
    for province, cities in PLATE_DATA['carplates'].items():
        for city, codes in cities.items():
            for code, letters in codes.items():
                if code == suffix and ((not letters) or (letter in letters)):
                    matches.append({'province': province, 'city': city})
    if not matches:
        for province, cities in PLATE_DATA['carplates'].items():
            for city, codes in cities.items():
                for code, letters in codes.items():
                    if code == suffix:
                        matches.append({'province': province, 'city': city})
    return {'vehicle_type': vehicle_type, 'locations': matches[:3]}


@app.route('/fonts/<path:filename>')
def serve_font(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'fonts'), filename)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)

@app.route('/')
def menu():
    resp = make_response(render_template('menu.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/scan')
def index():
    resp = make_response(render_template('index.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route('/status')
def status():
    return jsonify({'ready': models_ready, 'error': models_error})

@app.route('/detect', methods=['POST'])
def detect():
    if not models_ready:
        msg = models_error or 'Models are still loading | مدل‌ها هنوز در حال بارگذاری هستند'
        return jsonify({'error': msg, 'loading': not bool(models_error)}), 503

    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded | تصویری ارسال نشده'}), 400

    img_bytes = request.files['image'].read()
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return jsonify({'error': 'Unsupported image format | فرمت تصویر پشتیبانی نمی‌شود'}), 400

    results = det_model.predict(source=img, conf=0.4, verbose=False)
    annotated = results[0].plot()

    plates_found = len(results[0].boxes)
    best_conf = 0.0
    ocr_text = ''
    best_crop = None

    for box in results[0].boxes:
        conf = float(box.conf[0])
        if conf > best_conf:
            best_conf = conf

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        h, w = img.shape[:2]
        pad = 10
        x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad); y2 = min(h, y2 + pad)

        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        raw = ocr_model.predict(pil_img)

        if raw and len(raw) > 0:
            text = raw[0]['text']
            if text:
                ocr_text = text.strip()
                best_crop = crop

    plate_info = None
    if ocr_text:
        m = re.match(r'^([0-9۰-۹]{2})([؀-ۿ])([0-9۰-۹]{3})([0-9۰-۹]{2})$', ocr_text)
        if m:
            plate_info = lookup_plate(m.group(2), m.group(4))
            plate_info['prefix'] = m.group(1)
            plate_info['letter'] = m.group(2)
            plate_info['middle'] = m.group(3)
            plate_info['suffix'] = m.group(4)
            if plate_info['vehicle_type']:
                vt = plate_info['vehicle_type']
                plate_info['vehicle_type'] = {'type': vt['type'], 'id': vt['id'], 'bg': vt['bg'], 'color': vt['color']}

    save_images = True
    try:
        save_images = dx_get_setting('save_vehicle_images', '1') == '1'
    except Exception:
        save_images = True

    img_b64 = ''
    crop_b64 = ''
    image_path = ''
    crop_path = ''

    plate_for_file = ocr_text or 'unknown'

    if save_images:
        _, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])
        img_b64 = base64.b64encode(buf).decode('utf-8')
        image_path = dx_save_jpg_image(annotated, 'scan', plate_for_file)

        if best_crop is not None:
            _, cbuf = cv2.imencode('.jpg', best_crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
            crop_b64 = base64.b64encode(cbuf).decode('utf-8')
            crop_path = dx_save_jpg_image(best_crop, 'crop', plate_for_file)

    return jsonify({
        'image':        img_b64,
        'crop':         crop_b64,
        'image_path':   image_path,
        'crop_path':    crop_path,
        'images_enabled': save_images,
        'plates_found': plates_found,
        'best_conf':    best_conf,
        'ocr_text':     ocr_text,
        'plate_info':   plate_info,
    })


@app.route('/cameras')
def cameras_page():
    resp = make_response(render_template('cameras.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

# ── Camera CRUD ───────────────────────────────────────────────────────────────
@app.route('/api/cameras', methods=['GET'])
def api_cameras_list():
    cams = db.cameras_all()
    status = cm.worker_status()
    for c in cams:
        c['running'] = status.get(c['id'], False)
    return jsonify(cams)

@app.route('/api/cameras', methods=['POST'])
def api_camera_add():
    d = request.get_json(force=True)
    name = d.get('name', '').strip()
    url  = d.get('url', '').strip()
    role = d.get('role', 'entry')
    if not name or not url:
        return jsonify({'error': 'name and url are required | name و url الزامی هستند'}), 400
    cid = cm.add_camera(name, url, role)
    return jsonify({'id': cid})

@app.route('/api/cameras/<int:cid>', methods=['PUT'])
def api_camera_update(cid):
    d = request.get_json(force=True)
    db.camera_update(cid, d['name'], d['url'], d['role'], d.get('enabled', 1))
    # Restart worker with updated settings
    cm._stop_worker(cid)
    cam = db.camera_get(cid)
    if cam['enabled']:
        cm._start_worker(cam)
    return jsonify({'ok': True})

@app.route('/api/cameras/<int:cid>', methods=['DELETE'])
def api_camera_delete(cid):
    cm.remove_camera(cid)
    return jsonify({'ok': True})

@app.route('/api/cameras/<int:cid>/toggle', methods=['POST'])
def api_camera_toggle(cid):
    d = request.get_json(force=True)
    cm.set_enabled(cid, bool(d.get('enabled', True)))
    return jsonify({'ok': True})

@app.route('/api/cameras/<int:cid>/snapshot')
def api_camera_snapshot(cid):
    try:
        save_images = dx_get_setting('save_vehicle_images', '1') == '1'
    except Exception:
        save_images = True

    if not save_images:
        return jsonify({
            'image': '',
            'images_enabled': False,
            'message': 'Vehicle image output is disabled by system settings | نمایش تصویر خودرو در تنظیمات غیرفعال است'
        }), 200

    snap = cm.get_snapshot(cid)
    if snap is None:
        return jsonify({'error': 'No snapshot available | تصویری موجود نیست'}), 404

    snapshot_path = ''
    try:
        import base64
        import numpy as np
        import cv2

        raw = snap
        if isinstance(raw, str) and ',' in raw:
            raw = raw.split(',', 1)[1]

        arr = np.frombuffer(base64.b64decode(raw), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        snapshot_path = dx_save_jpg_image(img, f'camera_{cid}', 'snapshot')
    except Exception:
        snapshot_path = ''

    return jsonify({'image': snap, 'snapshot_path': snapshot_path, 'images_enabled': True})

# ── SSE event stream ──────────────────────────────────────────────────────────
@app.route('/api/events')
def api_events():
    q = cm.subscribe()
    def generate():
        try:
            # Send a heartbeat every 20s to keep connection alive
            while True:
                try:
                    evt = q.get(timeout=20)
                    yield f'data: {json.dumps(evt, ensure_ascii=False)}\n\n'
                except queue.Empty:
                    yield ': heartbeat\n\n'
        finally:
            cm.unsubscribe(q)
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

# ── Access Log ────────────────────────────────────────────────────────────────
@app.route('/api/log')
def api_log():
    limit = int(request.args.get('limit', 200))
    rows = db.log_recent(limit)

    for r in rows:
        try:
            r['image_url'] = dx_capture_url(r.get('image_path'))
            r['crop_url'] = dx_capture_url(r.get('crop_path'))
        except Exception:
            r['image_url'] = ''
            r['crop_url'] = ''

    return jsonify(rows)

@app.route('/api/log', methods=['DELETE'])
def api_log_clear():
    db.log_clear()
    return jsonify({'ok': True})



@app.route('/log-edit/<int:log_id>')
def log_edit_page(log_id):
    resp = make_response(render_template('log_edit.html', log_id=log_id))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@app.route('/api/log/<int:log_id>', methods=['GET'])
def api_log_get_one(log_id):
    r = db.log_get(log_id)
    if not r:
        return jsonify({'error': 'log not found | رکورد پیدا نشد'}), 404

    try:
        r['image_url'] = dx_capture_url(r.get('image_path'))
        r['crop_url'] = dx_capture_url(r.get('crop_path'))
    except Exception:
        r['image_url'] = ''
        r['crop_url'] = ''

    return jsonify(r)


@app.route('/api/log/<int:log_id>', methods=['PUT'])
def api_log_update_one(log_id):
    d = request.get_json(force=True)

    plate = (d.get('plate') or '').strip()
    role = (d.get('role') or 'entry').strip()
    operator = (d.get('operator') or '').strip()
    note = (d.get('note') or '').strip()

    if not plate:
        return jsonify({'error': 'plate is required | پلاک الزامی است'}), 400

    if role not in ['entry', 'exit']:
        return jsonify({'error': 'role must be entry or exit | نوع تردد باید ورود یا خروج باشد'}), 400

    ok = db.log_update(
        log_id=log_id,
        plate=plate,
        role=role,
        operator=operator,
        note=note
    )

    if not ok:
        return jsonify({'error': 'log not found | رکورد پیدا نشد'}), 404

    r = db.log_get(log_id)
    return jsonify({
        'ok': True,
        'log': r
    })


# ── Vehicles (Whitelist / Blacklist) ─────────────────────────────────────────
@app.route('/api/vehicles', methods=['GET'])
def api_vehicles_list():
    return jsonify(db.vehicles_all())

@app.route('/api/vehicles', methods=['POST'])
def api_vehicle_add():
    d = request.get_json(force=True)
    plate = d.get('plate', '').strip()
    if not plate:
        return jsonify({'error': 'plate is required | پلاک الزامی است'}), 400

    db.vehicle_upsert(
        plate=plate,
        label=d.get('label', '').strip(),
        list_type=d.get('list', 'white'),
        note=d.get('note', '').strip(),
        driver_name=d.get('driver_name', '').strip(),
        driver_phone=d.get('driver_phone', '').strip(),
        employee_code=d.get('employee_code', '').strip(),
        department=d.get('department', '').strip(),
        company=d.get('company', '').strip(),
        car_model=d.get('car_model', '').strip(),
        car_color=d.get('car_color', '').strip(),
        access_type=d.get('access_type', 'normal').strip()
    )
    return jsonify({'ok': True})

@app.route('/api/vehicles/<plate>', methods=['DELETE'])
def api_vehicle_delete(plate):
    db.vehicle_delete(plate)
    return jsonify({'ok': True})



@app.route('/vehicles')
def vehicles_page():
    resp = make_response(render_template('vehicles.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/logs')
def logs_page():
    resp = make_response(render_template('logs.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@app.route('/api/vehicles.csv')
def api_vehicles_csv():
    import csv, io
    rows = db.vehicles_all()
    out = io.StringIO()
    out.write('\ufeff')
    w = csv.writer(out)
    w.writerow([
        'plate','plate_norm','driver_name','driver_phone','employee_code',
        'department','company','car_model','car_color','list','access_type','label','note','added'
    ])
    for r in rows:
        w.writerow([
            r.get('plate',''), r.get('plate_norm',''), r.get('driver_name',''), r.get('driver_phone',''),
            r.get('employee_code',''), r.get('department',''), r.get('company',''), r.get('car_model',''),
            r.get('car_color',''), r.get('list',''), r.get('access_type',''), r.get('label',''),
            r.get('note',''), r.get('added','')
        ])
    resp = make_response(out.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename=digiexpress-vehicles.csv'
    return resp


@app.route('/api/log.csv')
def api_log_csv():
    import csv, io, sqlite3
    from datetime import datetime, timedelta

    if not current_user():
        return redirect('/login?next=/api/log.csv')

    dx_settings_init()

    default_days = dx_int_setting('csv_default_range_days', 30, 1, 3650)
    include_manual = dx_get_setting('csv_include_manual_entries', '1') == '1'
    include_unknown = dx_get_setting('csv_include_unknown_vehicles', '1') == '1'

    date_from = request.args.get('from') or request.args.get('date_from') or ''
    date_to = request.args.get('to') or request.args.get('date_to') or ''

    # اگر بازه زمانی انتخاب نشده بود، بازه پیش‌فرض از تنظیمات خوانده شود
    if not date_from and not date_to:
        dt_from = datetime.now() - timedelta(days=default_days)
        date_from = dt_from.strftime('%Y-%m-%d')

    con = sqlite3.connect(dx_db_path())
    con.row_factory = sqlite3.Row

    # تشخیص جدول لاگ موجود
    candidate_tables = ['access_logs', 'access_log', 'traffic_logs', 'traffic_log', 'plate_logs', 'plate_log', 'logs', 'detections']
    table = None
    for t in candidate_tables:
        r = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()
        if r:
            table = t
            break

    if not table:
        con.close()
        return jsonify({'error': 'log table not found'}), 500

    cols = [r['name'] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]

    date_col = next((c for c in ['created_at', 'created', 'ts', 'timestamp', 'time', 'logged_at'] if c in cols), None)
    if not date_col:
        date_col = cols[0]

    where = []
    params = []

    if date_from:
        where.append(f"datetime({date_col}) >= datetime(?)")
        params.append(date_from)

    if date_to:
        where.append(f"datetime({date_col}) <= datetime(?)")
        params.append(date_to + ' 23:59:59' if len(date_to) == 10 else date_to)

    if not include_manual and 'source' in cols:
        where.append("(source IS NULL OR lower(source) != 'manual')")

    # ناشناس‌ها را اگر تنظیم خاموش باشد حذف کن
    if not include_unknown:
        unknown_conditions = []

        if 'driver_name' in cols:
            unknown_conditions.append("(driver_name IS NOT NULL AND trim(driver_name) != '')")

        if 'list_status' in cols:
            unknown_conditions.append("(list_status IS NOT NULL AND trim(list_status) NOT IN ('', '-', 'none', 'unknown', 'ناشناس'))")
        elif 'status' in cols:
            unknown_conditions.append("(status IS NOT NULL AND trim(status) NOT IN ('', '-', 'none', 'unknown', 'ناشناس'))")

        # یعنی فقط ردیف‌هایی بمانند که یا راننده دارند یا status مشخص دارند
        if unknown_conditions:
            where.append("(" + " OR ".join(unknown_conditions) + ")")

    sql = f"SELECT * FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY datetime({date_col}) DESC"

    rows = con.execute(sql, params).fetchall()
    con.close()

    out = io.StringIO()
    w = csv.writer(out)

    # ترتیب ستون‌های مهم در ابتدا، بقیه بعدش
    preferred = [
        'id', date_col, 'plate', 'plate_norm', 'driver_name',
        'role', 'source', 'camera_name', 'confidence',
        'list_status', 'status', 'operator', 'note'
    ]

    headers = []
    for c in preferred:
        if c in cols and c not in headers:
            headers.append(c)

    for c in cols:
        if c not in headers:
            headers.append(c)

    w.writerow(headers)

    for r in rows:
        w.writerow([r[h] if h in r.keys() else '' for h in headers])

    resp = make_response(out.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename=digiexpress-access-log.csv'
    return resp





def dx_extract_ocr_text(raw):
    if not raw:
        return ''
    try:
        item = raw[0]
    except Exception:
        return ''
    try:
        if isinstance(item, dict):
            return str(item.get('text') or '').strip()
        try:
            return str(item['text'] or '').strip()
        except Exception:
            return str(getattr(item, 'text', '') or '').strip()
    except Exception:
        return ''


def dx_force_mobile_plate(text):
    import re
    fa = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    norm = str(text or '').strip()
    norm = norm.replace(' ', '').replace('-', '').replace('_', '')
    norm = norm.replace('ي', 'ی').replace('ك', 'ک')
    norm = norm.translate(fa)
    norm = re.sub(r'[^0-9؀-ۿ]', '', norm)

    m = re.search(r'([0-9]+)([؀-ۿ])([0-9]+)', norm)
    if not m:
        return norm

    left = m.group(1)
    letter = m.group(2)
    right = m.group(3)

    if len(left) < 2:
        return norm

    if len(right) >= 5:
        return left[-2:] + letter + right[:3] + right[3:5]

    if len(right) == 4:
        return left[-2:] + letter + right[:3] + right[3] + '0'

    return norm







def dx_detect_plate_color_from_crop(crop):
    """
    Approximate plate background color from plate crop.
    Returns: white, yellow, green, red, blue, unknown
    """
    import cv2
    import numpy as np

    if crop is None:
        return 'unknown'

    try:
        h, w = crop.shape[:2]
        if h < 10 or w < 30:
            return 'unknown'

        # مرکز پلاک را می‌گیریم تا نوار آبی سمت چپ اثر نگذارد
        x1 = int(w * 0.10)
        x2 = int(w * 0.92)
        y1 = int(h * 0.15)
        y2 = int(h * 0.85)
        roi = crop[y1:y2, x1:x2]
        if roi is None or roi.size == 0:
            roi = crop

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # ماسک‌های رنگ
        yellow = cv2.inRange(hsv, (12, 35, 70), (45, 255, 255))
        green  = cv2.inRange(hsv, (38, 30, 45), (95, 255, 255))
        blue   = cv2.inRange(hsv, (90, 35, 45), (140, 255, 255))

        red1 = cv2.inRange(hsv, (0, 45, 45), (13, 255, 255))
        red2 = cv2.inRange(hsv, (165, 45, 45), (180, 255, 255))
        red = cv2.bitwise_or(red1, red2)

        total = max(1, roi.shape[0] * roi.shape[1])

        ratios = {
            'yellow': float(np.count_nonzero(yellow)) / total,
            'green':  float(np.count_nonzero(green)) / total,
            'red':    float(np.count_nonzero(red)) / total,
            'blue':   float(np.count_nonzero(blue)) / total,
        }

        best = max(ratios, key=ratios.get)
        best_ratio = ratios[best]

        # برای پلاک زرد کمی threshold را پایین‌تر می‌گیریم چون عکس موبایل و نور محیط اثر می‌گذارد
        if best == 'yellow' and best_ratio >= 0.045:
            return 'yellow'
        if best == 'green' and best_ratio >= 0.07:
            return 'green'
        if best == 'red' and best_ratio >= 0.07:
            return 'red'
        if best == 'blue' and best_ratio >= 0.22:
            return 'blue'

        return 'white'
    except Exception:
        return 'unknown'



def dx_mobile_image_quality(img, crop=None, plate=''):
    import cv2
    import numpy as np

    warnings = []
    score = 100

    if img is None:
        return {
            'ok': False,
            'score': 0,
            'warnings': ['عکس معتبر نیست']
        }

    h, w = img.shape[:2]

    # Blur detection
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur_value = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        blur_value = 0.0

    if blur_value < 45:
        warnings.append('کیفیت عکس پایین است یا تصویر تار است؛ لطفاً نزدیک‌تر و واضح‌تر عکس بگیرید.')
        score -= 35
    elif blur_value < 75:
        warnings.append('تصویر کمی تار است؛ قبل از ثبت، پلاک را با دقت بررسی کنید.')
        score -= 15

    # Resolution check
    if w < 900 or h < 600:
        warnings.append('رزولوشن عکس پایین است؛ اگر ممکن است عکس را از نزدیک‌تر بگیرید.')
        score -= 15

    # Plate crop size check
    if crop is not None:
        ch, cw = crop.shape[:2]
        area_ratio = (cw * ch) / max(1, (w * h))

        if cw < 110 or ch < 35 or area_ratio < 0.002:
            warnings.append('پلاک در تصویر کوچک است؛ احتمال خطای OCR بیشتر می‌شود.')
            score -= 25
    else:
        if not plate:
            warnings.append('پلاک با اطمینان کافی پیدا نشد؛ بهتر است دوباره عکس بگیرید.')
            score -= 35

    if plate and len(str(plate).strip()) < 7:
        warnings.append('پلاک خوانده‌شده ناقص به نظر می‌رسد؛ قبل از ثبت اصلاح کنید.')
        score -= 25

    score = max(0, min(100, score))

    return {
        'ok': score >= 60,
        'score': score,
        'blur': round(blur_value, 2),
        'warnings': warnings
    }


def dx_mobile_ocr_image(img):
    import cv2
    from PIL import Image

    global det_model, ocr_model, models_ready, models_error

    if models_error:
        raise RuntimeError(str(models_error))
    if not models_ready:
        raise RuntimeError('models are not ready yet')

    best = {
        'plate': '',
        'confidence': 0.0,
        'crop': None
    }

    h, w = img.shape[:2]

    try:
        results = det_model.predict(source=img, conf=0.2, verbose=False)
        boxes = results[0].boxes
    except Exception:
        boxes = []

    for box in boxes:
        conf = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        pad = 35
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)

        crop = img[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            continue

        pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        raw = ocr_model.predict(pil)
        text = dx_extract_ocr_text(raw)
        plate = dx_force_mobile_plate(text)

        if plate and conf >= best['confidence']:
            best = {
                'plate': plate,
                'confidence': conf,
                'crop': crop
            }

    if not best['plate']:
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        raw = ocr_model.predict(pil)
        text = dx_extract_ocr_text(raw)
        plate = dx_force_mobile_plate(text)
        best = {
            'plate': plate,
            'confidence': 0.0,
            'crop': None
        }

    return best


@app.route('/api/mobile-entry/scan', methods=['POST'])
def api_mobile_entry_scan():
    import numpy as np
    import cv2

    if 'image' not in request.files:
        return jsonify({'error': 'image is required | عکس الزامی است'}), 400

    f = request.files['image']
    raw = f.read()

    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        return jsonify({'error': 'invalid image | عکس معتبر نیست'}), 400

    try:
        result = dx_mobile_ocr_image(img)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    plate = result.get('plate') or ''
    conf = float(result.get('confidence') or 0)

    plate_color = dx_detect_plate_color_from_crop(result.get('crop'))
    quality = dx_mobile_image_quality(img, result.get('crop'), plate)

    image_path = dx_save_jpg_image(img, 'mobile_frame', plate or 'unknown')
    crop_path = ''
    if result.get('crop') is not None:
        crop_path = dx_save_jpg_image(result.get('crop'), 'mobile_crop', plate or 'unknown')

    return jsonify({
        'ok': True,
        'plate': plate,
        'confidence': round(conf, 3),
        'image_path': image_path,
        'crop_path': crop_path,
        'quality': quality,
        'plate_color': plate_color
    })


@app.route('/api/mobile-entry/register', methods=['POST'])
def api_mobile_entry_register():
    d = request.get_json(force=True)

    plate = (d.get('plate') or '').strip()
    role = (d.get('role') or 'entry').strip()
    operator = (d.get('operator') or '').strip()
    note = (d.get('note') or '').strip()
    image_path = (d.get('image_path') or '').strip()
    crop_path = (d.get('crop_path') or '').strip()
    plate_color = (d.get('plate_color') or 'white').strip()

    if not plate:
        return jsonify({'error': 'plate is required | پلاک الزامی است'}), 400

    if role not in ['entry', 'exit']:
        return jsonify({'error': 'role must be entry or exit | نوع تردد باید ورود یا خروج باشد'}), 400

    u = current_user()
    if not operator and u:
        operator = u.get('full_name') or u.get('username') or ''

    db.log_add(
        plate=plate,
        camera_id=None,
        camera_name='ثبت موبایلی حراست',
        role=role,
        confidence=1.0,
        crop_b64='',
        source='mobile',
        operator=operator,
        note=note,
        image_path=image_path,
        crop_path=crop_path,
        plate_color=plate_color
    )

    vehicle = db.vehicle_get(plate)

    return jsonify({
        'ok': True,
        'plate': plate,
        'plate_norm': db.normalize_plate(plate),
        'vehicle': vehicle
    })


@app.route('/manual-entry')
def manual_entry_page():
    resp = make_response(render_template('manual_entry.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@app.route('/mobile-entry')
def mobile_entry_page():
    resp = make_response(render_template('mobile_entry.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/api/manual-entry', methods=['POST'])
def api_manual_entry():
    d = request.get_json(force=True)

    plate = (d.get('plate') or '').strip()
    role = (d.get('role') or 'entry').strip()
    operator = (d.get('operator') or '').strip()
    note = (d.get('note') or '').strip()

    if not plate:
        return jsonify({'error': 'plate is required | پلاک الزامی است'}), 400

    if role not in ['entry', 'exit']:
        return jsonify({'error': 'role must be entry or exit | نوع تردد باید ورود یا خروج باشد'}), 400

    db.log_add(
        plate=plate,
        camera_id=None,
        camera_name='ثبت دستی',
        role=role,
        confidence=1.0,
        crop_b64='',
        source='manual',
        operator=operator,
        note=note
    )

    vehicle = db.vehicle_get(plate)
    return jsonify({
        'ok': True,
        'plate': plate,
        'plate_norm': db.normalize_plate(plate),
        'role': role,
        'vehicle': vehicle
    })




def dx_capture_dir():
    from pathlib import Path
    from datetime import datetime
    d = Path(BASE_DIR) / 'data' / 'captures' / datetime.now().strftime('%Y-%m-%d')
    d.mkdir(parents=True, exist_ok=True)
    return d


def dx_safe_filename_part(value, default='unknown'):
    import re
    value = str(value or '').strip()
    value = re.sub(r'[^0-9A-Za-zآ-یء-ی_\-]+', '_', value)
    value = value.strip('_')
    return value or default


def dx_save_jpg_image(img, prefix='image', plate='unknown'):
    import cv2
    from datetime import datetime

    try:
        if dx_get_setting('save_vehicle_images', '1') != '1':
            return ''
    except Exception:
        pass

    if img is None:
        return ''

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_plate = dx_safe_filename_part(plate)
    filename = f'{prefix}_{ts}_{safe_plate}.jpg'
    path = dx_capture_dir() / filename

    ok = cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        return ''

    try:
        return str(path.relative_to(Path(BASE_DIR)))
    except Exception:
        return str(path)


def dx_alert_level_label(level):
    return {
        'low': 'کم',
        'medium': 'متوسط',
        'high': 'زیاد',
        'critical': 'بحرانی',
    }.get(level, 'متوسط')


def dx_enrich_dashboard_alerts(data):
    dx_settings_init()

    level = dx_get_setting('unknown_vehicle_alert_level', 'medium')
    if level not in ['low', 'medium', 'high', 'critical']:
        level = 'medium'

    alerts = data.get('alerts') or []
    enriched = []

    for a in alerts:
        d = dict(a) if not isinstance(a, dict) else dict(a)

        status = str(d.get('list_status') or d.get('status') or '').strip().lower()
        source = str(d.get('source') or '').strip().lower()
        driver = str(d.get('driver_name') or '').strip()
        plate = str(d.get('plate') or '').strip()

        is_black = status in ['black', 'blacklist', 'blocked', 'deny', 'denied', 'غیرمجاز']
        is_white = status in ['white', 'whitelist', 'allow', 'allowed', 'مجاز']
        is_unknown = (not driver and not is_white and not is_black) or status in ['', '-', 'none', 'unknown', 'ناشناس']
        is_manual_unknown = is_unknown and source == 'manual'

        alert_type = 'unknown'
        severity = 'medium'
        title = 'خودروی ناشناس'

        if is_black:
            alert_type = 'blacklist'
            severity = 'critical'
            title = 'خودروی غیرمجاز / blacklist'
        elif is_manual_unknown:
            alert_type = 'manual_unknown'
            severity = 'high'
            title = 'ثبت دستی خودروی ناشناس'
        elif is_unknown:
            alert_type = 'unknown'
            severity = level
            title = 'خودروی ناشناس'

        # فیلتر بر اساس سطح انتخاب‌شده
        if level == 'low':
            if alert_type != 'blacklist':
                continue

        elif level == 'medium':
            if alert_type not in ['blacklist', 'unknown']:
                continue

        elif level == 'high':
            if alert_type not in ['blacklist', 'unknown', 'manual_unknown']:
                continue

        elif level == 'critical':
            # در critical همه alertهای موجود نمایش داده می‌شوند
            pass

        d['alert_type'] = alert_type
        d['alert_severity'] = severity
        d['alert_title'] = title
        d['alert_level_setting'] = level
        d['alert_level_label'] = dx_alert_level_label(level)

        if not d.get('note'):
            d['note'] = title

        enriched.append(d)

    data['alerts'] = enriched
    data['alert_settings'] = {
        'unknown_vehicle_alert_level': level,
        'unknown_vehicle_alert_level_label': dx_alert_level_label(level),
        'alerts_count': len(enriched),
    }

    return data





def dx_capture_url(path):
    path = str(path or '').strip()
    if not path:
        return ''

    # مسیرهای ذخیره‌شده معمولاً data/captures/DATE/file.jpg هستند
    prefix = 'data/captures/'
    if path.startswith(prefix):
        return '/captures/' + path[len(prefix):]

    if path.startswith('/app/data/captures/'):
        return '/captures/' + path[len('/app/data/captures/'):]

    return ''


@app.route('/captures/<path:filename>')
def dx_capture_file(filename):
    u = current_user()
    if not u:
        return redirect('/login?next=/captures/' + quote(filename))

    # فقط کاربران لاگین‌شده ببینند
    base = os.path.join(BASE_DIR, 'data', 'captures')
    return send_from_directory(base, filename)


@app.route('/api/dashboard-stats')
def api_dashboard_stats():
    if not current_user():
        return jsonify({'error': 'auth required'}), 401

    data = db.dashboard_stats()
    data = dx_enrich_dashboard_alerts(data)

    for group in ['latest', 'alerts']:
        for r in data.get(group, []) or []:
            try:
                r['image_url'] = dx_capture_url(r.get('image_path'))
                r['crop_url'] = dx_capture_url(r.get('crop_path'))
            except Exception:
                r['image_url'] = ''
                r['crop_url'] = ''

    return jsonify(data)




@app.route('/vehicle')
def vehicle_root_redirect():
    return redirect('/vehicles')


@app.route('/vehicle/<path:plate_key>')
def vehicle_profile_page(plate_key):
    resp = make_response(render_template('vehicle_profile.html', plate_key=plate_key))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/api/vehicle-profile/<path:plate_key>')
def api_vehicle_profile(plate_key):
    data = db.vehicle_profile(plate_key)

    for r in data.get('logs', []):
        try:
            r['image_url'] = dx_capture_url(r.get('image_path'))
            r['crop_url'] = dx_capture_url(r.get('crop_path'))
        except Exception:
            r['image_url'] = ''
            r['crop_url'] = ''

    return jsonify(data)



# ===== LDAP / Role-based Access =====

ROLE_PERMISSIONS = {
    'admin': {
        'pages': ['/', '/scan', '/cameras', '/vehicles', '/logs', '/log-edit', '/manual-entry', '/mobile-entry', '/users', '/vehicle'],
        'apis_write': ['all'],
    },
    'security': {
        'pages': ['/', '/scan', '/cameras', '/vehicles', '/logs', '/log-edit', '/manual-entry', '/mobile-entry', '/vehicle'],
        'apis_write': ['/api/manual-entry', '/api/mobile-entry', '/api/log', '/api/vehicles', '/api/cameras'],
    },
    'viewer': {
        'pages': ['/', '/logs', '/vehicle'],
        'apis_write': [],
    },
}

def auth_mode():
    return os.environ.get('AUTH_MODE', 'local').strip().lower()

def current_user():
    username = session.get('username')
    if not username:
        return None
    return {
        'username': username,
        'role': session.get('role', 'viewer'),
        'full_name': session.get('full_name', '')
    }

def _role_from_ldap_groups(member_of):
    groups = set([str(x).lower() for x in (member_of or [])])

    admin_dn = os.environ.get('LDAP_ADMIN_GROUP_DN', '').lower()
    security_dn = os.environ.get('LDAP_SECURITY_GROUP_DN', '').lower()
    viewer_dn = os.environ.get('LDAP_VIEWER_GROUP_DN', '').lower()

    if admin_dn and admin_dn in groups:
        return 'admin'
    if security_dn and security_dn in groups:
        return 'security'
    if viewer_dn and viewer_dn in groups:
        return 'viewer'
    return None

def ldap_authenticate(username, password):
    if not username or not password:
        return None

    from ldap3 import Server, Connection, ALL, SUBTREE

    server_uri = os.environ.get('LDAP_SERVER_URI', '')
    use_ssl = os.environ.get('LDAP_USE_SSL', 'false').lower() == 'true'
    base_dn = os.environ.get('LDAP_BASE_DN', '')
    bind_dn = os.environ.get('LDAP_BIND_DN', '')
    bind_password = os.environ.get('LDAP_BIND_PASSWORD', '')
    user_filter_tpl = os.environ.get('LDAP_USER_FILTER', '(sAMAccountName={username})')

    if not server_uri or not base_dn or not bind_dn or not bind_password:
        raise RuntimeError('LDAP config is incomplete')

    server = Server(server_uri, use_ssl=use_ssl, get_info=ALL)

    # service bind
    svc = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)

    user_filter = user_filter_tpl.replace('{username}', username)
    svc.search(
        search_base=base_dn,
        search_filter=user_filter,
        search_scope=SUBTREE,
        attributes=['cn', 'displayName', 'mail', 'memberOf', 'sAMAccountName', 'uid']
    )

    if not svc.entries:
        return None

    entry = svc.entries[0]
    user_dn = entry.entry_dn

    member_of = []
    try:
        member_of = list(entry.memberOf.values)
    except Exception:
        member_of = []

    role = _role_from_ldap_groups(member_of)
    if not role:
        return None

    # user bind verifies password
    try:
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        user_conn.unbind()
    except Exception:
        return None

    full_name = ''
    try:
        full_name = str(entry.displayName.value or entry.cn.value or username)
    except Exception:
        full_name = username

    return {
        'username': username,
        'role': role,
        'full_name': full_name,
        'dn': user_dn
    }

def user_can_access_page(path, role):
    if role == 'admin':
        return True
    allowed = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS['viewer'])['pages']
    for prefix in allowed:
        if prefix == '/' and path == '/':
            return True
        if prefix != '/' and path.startswith(prefix):
            return True
    return False

def user_can_write_api(path, role):
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS['viewer'])['apis_write']
    if 'all' in perms:
        return True
    return any(path.startswith(prefix) for prefix in perms)

@app.before_request
def require_login_global():
    path = request.path or ''
    if path.startswith('/dx/'):
        return None

    if path.startswith('/static/'):
        return None

    if path in ['/login', '/status']:
        return None

    if not session.get('username'):
        if path.startswith('/api/'):
            return jsonify({'error': 'login required'}), 401
        return redirect('/login?next=' + path)

    role = session.get('role', 'viewer')

    if path.startswith('/api/'):
        if request.method in ['GET', 'HEAD']:
            return None
        if not user_can_write_api(path, role):
            return jsonify({'error': 'permission denied'}), 403
        return None

    if not user_can_access_page(path, role):
        return redirect('/')

    return None

@app.context_processor
def inject_auth_user():
    return {'auth_user': current_user(), 'auth_role': session.get('role', 'viewer')}


def dx_ldap_verify_email_password(email, password):
    if not email or not password:
        return None

    from ldap3 import Server, Connection, ALL, SUBTREE, NTLM

    email = (email or '').strip().lower()
    sam_name = email.split('@')[0] if '@' in email else email

    server_uri = os.environ.get('LDAP_SERVER_URI', '')
    use_ssl = os.environ.get('LDAP_USE_SSL', 'false').lower() == 'true'
    base_dn = os.environ.get('LDAP_BASE_DN', '')
    bind_dn = os.environ.get('LDAP_BIND_DN', '')
    bind_password = os.environ.get('LDAP_BIND_PASSWORD', '')
    user_filter_tpl = os.environ.get('LDAP_USER_FILTER', '(mail={username})')
    domain_netbios = os.environ.get('LDAP_DOMAIN_NETBIOS', 'DIGIKALA')

    if not server_uri or not base_dn or not bind_dn or not bind_password:
        raise RuntimeError('LDAP config is incomplete')

    server = Server(server_uri, use_ssl=use_ssl, get_info=ALL)
    svc = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)

    candidates = [
        user_filter_tpl.replace('{username}', email),
        user_filter_tpl.replace('{username}', sam_name),
        '(mail=%s)' % email,
        '(userPrincipalName=%s)' % email,
        '(sAMAccountName=%s)' % sam_name,
    ]

    entry = None
    used_filter = None

    for user_filter in dict.fromkeys(candidates):
        svc.search(
            search_base=base_dn,
            search_filter=user_filter,
            search_scope=SUBTREE,
            attributes=['cn', 'displayName', 'mail', 'userPrincipalName', 'sAMAccountName']
        )
        if svc.entries:
            entry = svc.entries[0]
            used_filter = user_filter
            break

    if not entry:
        return None

    user_dn = entry.entry_dn

    try:
        upn = str(entry.userPrincipalName.value or email)
    except Exception:
        upn = email

    try:
        sam = str(entry.sAMAccountName.value or sam_name)
    except Exception:
        sam = sam_name

    bind_tests = [
        ('simple_dn', user_dn, None),
        ('simple_upn', upn, None),
        ('simple_email', email, None),
        ('ntlm_domain_sam', domain_netbios + '\\\\' + sam, NTLM),
    ]

    ok = False
    used_bind = None

    for bind_name, bind_user, bind_auth in bind_tests:
        try:
            if bind_auth:
                user_conn = Connection(server, user=bind_user, password=password, authentication=bind_auth, auto_bind=True)
            else:
                user_conn = Connection(server, user=bind_user, password=password, auto_bind=True)
            user_conn.unbind()
            ok = True
            used_bind = bind_name
            break
        except Exception:
            pass

    if not ok:
        return None

    try:
        full_name = str(entry.displayName.value or entry.cn.value or email)
    except Exception:
        full_name = email

    return {
        'username': email,
        'full_name': full_name,
        'dn': user_dn,
        'used_filter': used_filter,
        'used_bind': used_bind
    }




def dx_ldap_password_verify(username, password):
    if not username or not password:
        return None

    from ldap3 import Server, Connection, ALL, SUBTREE

    username = (username or '').strip().lower()
    sam = username.split('@')[0] if '@' in username else username

    server_uri = os.environ.get('LDAP_SERVER_URI', '')
    use_ssl = os.environ.get('LDAP_USE_SSL', 'false').lower() == 'true'
    base_dn = os.environ.get('LDAP_BASE_DN', '')
    bind_dn = os.environ.get('LDAP_BIND_DN', '')
    bind_password = os.environ.get('LDAP_BIND_PASSWORD', '')
    user_filter_tpl = os.environ.get('LDAP_USER_FILTER', '(mail={username})')

    if not server_uri or not base_dn or not bind_dn or not bind_password:
        raise RuntimeError('LDAP config is incomplete')

    server = Server(server_uri, use_ssl=use_ssl, get_info=ALL)
    svc = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)

    filters = [
        user_filter_tpl.replace('{username}', username),
        user_filter_tpl.replace('{username}', sam),
        '(mail=%s)' % username,
        '(userPrincipalName=%s)' % username,
        '(sAMAccountName=%s)' % sam,
    ]

    entry = None
    for filt in dict.fromkeys(filters):
        svc.search(
            search_base=base_dn,
            search_filter=filt,
            search_scope=SUBTREE,
            attributes=['cn', 'displayName', 'mail', 'userPrincipalName', 'sAMAccountName']
        )
        if svc.entries:
            entry = svc.entries[0]
            break

    if not entry:
        return None

    user_dn = entry.entry_dn

    try:
        upn = str(entry.userPrincipalName.value or username)
    except Exception:
        upn = username

    bind_users = [user_dn, upn, username]

    ok = False
    for bind_user in bind_users:
        try:
            c = Connection(server, user=bind_user, password=password, auto_bind=True)
            c.unbind()
            ok = True
            break
        except Exception:
            pass

    if not ok:
        return None

    try:
        full_name = str(entry.displayName.value or entry.cn.value or username)
    except Exception:
        full_name = username

    return {
        'username': username,
        'full_name': full_name,
        'dn': user_dn
    }


def dx_local_role_login(username, password):
    username = (username or '').strip().lower()

    ldap_user = dx_ldap_password_verify(username, password)
    if not ldap_user:
        return None

    local_user = db.user_public(username)
    if not local_user:
        return None

    if not int(local_user.get('active') or 0):
        return None

    return {
        'username': local_user['username'],
        'role': local_user.get('role') or 'viewer',
        'full_name': local_user.get('full_name') or ldap_user.get('full_name') or username
    }


@app.route('/login', methods=['GET', 'POST', 'HEAD'])
def login_page():
    if request.method in ['GET', 'HEAD']:
        resp = make_response(render_template('login.html'))
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp

    d = request.get_json(silent=True) or request.form
    username = (d.get('username') or '').strip()
    password = d.get('password') or ''

    try:
        mode = auth_mode()
        if mode == 'ldap_local_roles':
            u = dx_local_role_login(username, password)
        elif mode == 'ldap':
            u = ldap_authenticate(username, password)
        else:
            u = db.user_authenticate(username, password)

        if not u:
            return jsonify({'error': 'نام کاربری، رمز عبور یا سطح دسترسی اشتباه است'}), 401

        if not isinstance(u, dict):
            return jsonify({'error': 'Auth returned invalid user object'}), 500

        if 'username' not in u:
            return jsonify({'error': 'Auth user object missing username', 'user': str(u)}), 500

        if 'role' not in u:
            return jsonify({'error': 'Auth user object missing role', 'user': str(u)}), 500

        session.clear()
        session['username'] = u['username']
        session['role'] = u.get('role') or 'viewer'
        session['full_name'] = u.get('full_name') or ''
        return jsonify({'ok': True, 'user': u})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'LDAP/Auth error: ' + repr(e)}), 500

@app.route('/logout')
def logout_page():
    session.clear()
    return redirect('/login')

@app.route('/api/me')
def api_me():
    return jsonify({'user': current_user()})



def dx_db_path():
    return os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'traffic.db'))


def dx_settings_init():
    import sqlite3
    con = sqlite3.connect(dx_db_path())
    con.execute(
        "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )

    defaults = {
        'session_timeout_hours': '12',

        'image_retention_days': '30',
        'log_retention_days': '180',
        'save_vehicle_images': '1',

        'login_message': '',

        'unknown_vehicle_alert_level': 'medium',

        'camera_reconnect_seconds': '10',
        'camera_snapshot_interval_seconds': '5',
        'camera_default_confidence': '0.65',

        'csv_default_range_days': '30',
        'csv_include_manual_entries': '1',
        'csv_include_unknown_vehicles': '1',
    }

    for key, value in defaults.items():
        con.execute(
            "INSERT OR IGNORE INTO app_settings(key,value) VALUES(?,?)",
            (key, value)
        )

    con.commit()
    con.close()


def dx_get_setting(key, default=''):
    import sqlite3
    dx_settings_init()
    con = sqlite3.connect(dx_db_path())
    row = con.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row[0] if row else default


def dx_set_setting(key, value):
    import sqlite3
    dx_settings_init()
    con = sqlite3.connect(dx_db_path())
    con.execute(
        "INSERT INTO app_settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value))
    )
    con.commit()
    con.close()




@app.context_processor
def dx_template_settings():
    try:
        dx_settings_init()
        return {
            'dx_login_message': dx_get_setting('login_message', '')
        }
    except Exception:
        return {
            'dx_login_message': ''
        }


@app.route('/users', methods=['GET', 'POST'])
def users_page():
    u = current_user()
    if not u:
        return redirect('/login?next=/users')
    if u.get('role') != 'admin':
        return jsonify({'error': 'admin access required'}), 403

    import sqlite3
    db_path = dx_db_path()
    msg = ''

    dx_settings_init()

    if request.method == 'POST':
        action = request.form.get('action') or 'save_user'


        if action == 'delete_user':
            username = (request.form.get('username') or '').strip().lower()

            if not username:
                msg = 'ایمیل کاربر معتبر نیست'
            elif username == (u.get('username') or '').strip().lower():
                msg = 'امکان حذف کاربر فعلی وجود ندارد'
            else:
                con = sqlite3.connect(db_path)
                con.execute("DELETE FROM users WHERE lower(username)=lower(?)", (username,))
                con.commit()
                con.close()
                msg = 'کاربر حذف شد'

        elif action == 'settings':
            try:
                timeout_hours = float(request.form.get('session_timeout_hours') or 12)
                if timeout_hours < 1:
                    timeout_hours = 1
                if timeout_hours > 168:
                    timeout_hours = 168

                image_retention_days = int(request.form.get('image_retention_days') or 30)
                if image_retention_days < 1:
                    image_retention_days = 1
                if image_retention_days > 3650:
                    image_retention_days = 3650

                log_retention_days = int(request.form.get('log_retention_days') or 180)
                if log_retention_days < 1:
                    log_retention_days = 1
                if log_retention_days > 3650:
                    log_retention_days = 3650

                image_cleanup_interval_days = int(request.form.get('image_cleanup_interval_days') or 7)
                if image_cleanup_interval_days < 1:
                    image_cleanup_interval_days = 1
                if image_cleanup_interval_days > 365:
                    image_cleanup_interval_days = 365

                camera_reconnect_seconds = int(request.form.get('camera_reconnect_seconds') or 10)
                if camera_reconnect_seconds < 1:
                    camera_reconnect_seconds = 1
                if camera_reconnect_seconds > 3600:
                    camera_reconnect_seconds = 3600

                camera_snapshot_interval_seconds = int(request.form.get('camera_snapshot_interval_seconds') or 5)
                if camera_snapshot_interval_seconds < 1:
                    camera_snapshot_interval_seconds = 1
                if camera_snapshot_interval_seconds > 3600:
                    camera_snapshot_interval_seconds = 3600

                camera_default_confidence = float(request.form.get('camera_default_confidence') or 0.65)
                if camera_default_confidence < 0.1:
                    camera_default_confidence = 0.1
                if camera_default_confidence > 0.99:
                    camera_default_confidence = 0.99

                csv_default_range_days = int(request.form.get('csv_default_range_days') or 30)
                if csv_default_range_days < 1:
                    csv_default_range_days = 1
                if csv_default_range_days > 3650:
                    csv_default_range_days = 3650

                alert_level = request.form.get('unknown_vehicle_alert_level') or 'medium'
                if alert_level not in ['low', 'medium', 'high', 'critical']:
                    alert_level = 'medium'

                dx_set_setting('session_timeout_hours', timeout_hours)
                dx_set_setting('image_retention_days', image_retention_days)
                dx_set_setting('log_retention_days', log_retention_days)
                dx_set_setting('save_vehicle_images', '1' if request.form.get('save_vehicle_images') == '1' else '0')
                dx_set_setting('login_message', (request.form.get('login_message') or '').strip())
                dx_set_setting('unknown_vehicle_alert_level', alert_level)

                dx_set_setting('camera_reconnect_seconds', camera_reconnect_seconds)
                dx_set_setting('camera_snapshot_interval_seconds', camera_snapshot_interval_seconds)
                dx_set_setting('camera_default_confidence', camera_default_confidence)

                dx_set_setting('csv_default_range_days', csv_default_range_days)
                dx_set_setting('csv_include_manual_entries', '1' if request.form.get('csv_include_manual_entries') == '1' else '0')
                dx_set_setting('csv_include_unknown_vehicles', '1' if request.form.get('csv_include_unknown_vehicles') == '1' else '0')

                msg = 'تنظیمات سامانه ذخیره شد'
            except Exception as e:
                msg = 'مقادیر تنظیمات معتبر نیست'

        else:
            username = (request.form.get('username') or '').strip().lower()
            full_name = (request.form.get('full_name') or '').strip()
            role = (request.form.get('role') or 'viewer').strip()
            active = int(request.form.get('active') or 1)

            if username and role in ['admin', 'security', 'viewer']:
                con = sqlite3.connect(db_path)
                con.execute(
                    "INSERT INTO users(username,password_hash,role,full_name,active) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(username) DO UPDATE SET role=excluded.role, full_name=excluded.full_name, active=excluded.active",
                    (username, 'LDAP_AUTH_ONLY', role, full_name, active)
                )
                con.commit()
                con.close()
                msg = 'کاربر ذخیره شد'
            else:
                msg = 'ایمیل یا نقش معتبر نیست'

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT id, username, role, full_name, active, created FROM users ORDER BY id DESC").fetchall()
    con.close()

    setting_keys = [
        'session_timeout_hours',

        'image_retention_days',
        'log_retention_days',
        'save_vehicle_images',

        'login_message',
        'unknown_vehicle_alert_level',

        'camera_reconnect_seconds',
        'camera_snapshot_interval_seconds',
        'camera_default_confidence',

        'csv_default_range_days',
        'csv_include_manual_entries',
        'csv_include_unknown_vehicles',
    ]

    settings = {k: dx_get_setting(k, '') for k in setting_keys}

    return render_template(
        'users.html',
        users=[dict(r) for r in rows],
        settings=settings,
        msg=msg
    )




def dx_role_can_access_path(role, path, method='GET'):
    role = role or 'viewer'
    path = path or '/'
    method = method or 'GET'

    # عمومی
    public_paths = ['/login', '/logout', '/status']
    if path in public_paths or path.startswith('/static/'):
        return True

    # admin همه چیز
    if role == 'admin':
        return True

    # viewer فقط مشاهده
    if role == 'viewer':
        allowed_exact = [
            '/',
            '/logs',
            '/api/me',
            '/api/dashboard-stats',
            '/api/log',
            '/api/log.csv',
            '/api/vehicles.csv',
        ]

        allowed_prefix = [
            '/vehicle/',
            '/api/vehicle-profile/',
        ]

        if path in allowed_exact:
            return True

        if any(path.startswith(x) for x in allowed_prefix):
            return True

        return False

    # security عملیات روزانه، نه تنظیمات و کاربران
    if role == 'security':
        blocked_exact = [
            '/users',
            '/api/settings/cleanup',
        ]

        blocked_prefix = [
            '/api/users',
            '/settings',
        ]

        if path in blocked_exact:
            return False

        if any(path.startswith(x) for x in blocked_prefix):
            return False

        # security به پنل عملیاتی دسترسی دارد
        allowed_prefix = [
            '/',
            '/scan',
            '/cameras',
            '/vehicles',
            '/manual-entry',
            '/mobile-entry',
            '/logs',
            '/log-edit',
            '/vehicle/',
            '/api/',
        ]

        return any(path == x or path.startswith(x) for x in allowed_prefix)

    return False


@app.before_request
def dx_role_access_guard():
    path = request.path or ''
    if path.startswith('/dx/'):
        return None

    if path.startswith('/static/') or path in ['/login', '/logout', '/status']:
        return None

    u = current_user()
    if not u:
        if path.startswith('/api/'):
            return jsonify({'error': 'auth required'}), 401
        return redirect('/login?next=' + quote(path))

    role = u.get('role') or 'viewer'

    if not dx_role_can_access_path(role, path, request.method):
        if path.startswith('/api/'):
            return jsonify({'error': 'access denied', 'role': role}), 403
        return jsonify({'error': 'access denied', 'role': role}), 403

    return None




# --- DigiExpress DX Public Routes Auth Bypass ---
try:
    from flask import request
    _dx_original_before_request_funcs = app.before_request_funcs.get(None, []).copy()
    app.before_request_funcs[None] = [
        f for f in app.before_request_funcs.get(None, [])
        if not getattr(f, "__name__", "").startswith("dx_")
    ]

    @app.before_request
    def dx_public_routes_auth_bypass():
        if request.path.startswith("/dx/"):
            return None

    for _f in _dx_original_before_request_funcs:
        app.before_request(_f)

    print("DX auth bypass registered")
except Exception as e:
    print(f"DX auth bypass failed: {e}")
# --- End DX Public Routes Auth Bypass ---

# --- DigiExpress Multi-Site and CSV Import Extension ---
try:
    from dx_multi_site import register_dx_multi_site
    register_dx_multi_site(app)
    print("DX Multi-Site extension loaded")
except Exception as e:
    print(f"DX Multi-Site extension load failed: {e}")
# --- End DigiExpress Extension ---


# --- DX Direct Live Data API ---
try:
    from dx_multi_site import get_site_id, get_sites, stats_for_site

    @app.route("/dx/api/live-data")
    def dx_api_live_data_direct():
        selected_site_id = get_site_id(request.args.get("site_id"))
        all_sites = get_sites(True)

        selected_site = None
        for s in all_sites:
            if int(s["id"]) == int(selected_site_id):
                selected_site = s
                break

        if selected_site is None and all_sites:
            selected_site = all_sites[0]
            selected_site_id = selected_site["id"]

        stats = stats_for_site(selected_site_id)

        latest = []
        for r in stats.get("latest", []):
            image = (
                r.get("crop_path")
                or r.get("image_path")
                or r.get("frame_path")
                or r.get("photo_path")
                or ""
            )
            image = str(image or "").strip()

            full_image = (
                r.get("image_path")
                or r.get("frame_path")
                or r.get("photo_path")
                or r.get("full_image")
                or image
                or ""
            )
            full_image = str(full_image or "").strip()

            if "/captures/" in image:
                image = "/captures/" + image.split("/captures/", 1)[1]
            elif image.startswith("captures/"):
                image = "/" + image

            if "/captures/" in full_image:
                full_image = "/captures/" + full_image.split("/captures/", 1)[1]
            elif full_image.startswith("captures/"):
                full_image = "/" + full_image

            latest.append({
                "time": r.get("created_at") or r.get("ts") or r.get("timestamp") or "-",
                "plate": r.get("plate") or r.get("plate_text") or "-",
                "driver": r.get("driver_name") or "-",
                "role": r.get("role") or r.get("gate_role") or "-",
                "source": r.get("source") or r.get("camera_name") or "-",
                "status": r.get("status") or r.get("access_type") or "-",
                "image": image,
                "full_image": full_image,
                "plate_color": r.get("plate_color") or r.get("color") or "white",
            })

        return {
            "sites": all_sites,
            "selected_site_id": int(selected_site_id) if selected_site_id else None,
            "selected_site": selected_site,
            "stats": {
                "total": stats.get("total", 0),
                "entry": stats.get("entry", 0),
                "exit": stats.get("exit", 0),
                "vehicles": stats.get("vehicles", 0),
                "latest": latest,
            },
        }

    print("DX direct live-data API registered")
except Exception as e:
    print(f"DX direct live-data API failed: {e}")
# --- End DX Direct Live Data API ---


# --- DX Camera Site Direct API ---
try:
    import sqlite3

    DX_DB_PATH = "/app/traffic.db"

    def dx_db_conn():
        con = sqlite3.connect(DX_DB_PATH)
        con.row_factory = sqlite3.Row
        return con

    def dx_table_exists(con, table):
        return bool(con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        ).fetchone())

    def dx_columns(con, table):
        if not dx_table_exists(con, table):
            return set()
        return {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}

    @app.route("/dx/api/sites")
    def dx_api_sites_direct():
        con = dx_db_conn()
        try:
            if not dx_table_exists(con, "dx_sites"):
                return {"sites": []}
            rows = con.execute(
                "SELECT id, name, code, enabled FROM dx_sites WHERE enabled=1 ORDER BY id"
            ).fetchall()
            return {"sites": [dict(r) for r in rows]}
        finally:
            con.close()

    @app.route("/dx/api/camera-site-by-name", methods=["POST"])
    def dx_api_camera_site_by_name():
        data = request.get_json(silent=True) or request.form or {}

        camera_id = data.get("camera_id") or data.get("id")
        camera_name = (
            data.get("camera_name")
            or data.get("name")
            or data.get("title")
            or ""
        )
        site_id = data.get("site_id")

        if not site_id:
            return {"ok": False, "error": "site_id is required"}, 400

        con = dx_db_conn()
        try:
            if not dx_table_exists(con, "cameras"):
                return {"ok": False, "error": "cameras table not found"}, 404

            cols = dx_columns(con, "cameras")

            if "site_id" not in cols:
                con.execute("ALTER TABLE cameras ADD COLUMN site_id INTEGER")
                cols = dx_columns(con, "cameras")

            updated = 0

            if camera_id and "id" in cols:
                cur = con.execute(
                    "UPDATE cameras SET site_id=? WHERE id=?",
                    (site_id, camera_id)
                )
                updated = cur.rowcount or 0

            if updated == 0 and camera_name:
                name_col = None
                for candidate in ["name", "camera_name", "title"]:
                    if candidate in cols:
                        name_col = candidate
                        break

                if name_col:
                    cur = con.execute(
                        f"UPDATE cameras SET site_id=? WHERE {name_col}=?",
                        (site_id, camera_name)
                    )
                    updated = cur.rowcount or 0

            if updated == 0:
                # fallback: آخرین دوربینی که ساخته شده و site_id ندارد
                if "id" in cols:
                    cur = con.execute(
                        "UPDATE cameras SET site_id=? WHERE id=(SELECT id FROM cameras ORDER BY id DESC LIMIT 1)",
                        (site_id,)
                    )
                    updated = cur.rowcount or 0

            con.commit()
            return {"ok": True, "updated": updated, "site_id": int(site_id)}
        finally:
            con.close()

    print("DX camera site direct API registered")
except Exception as e:
    print(f"DX camera site direct API failed: {e}")
# --- End DX Camera Site Direct API ---


# --- DX Mobile Entry Site API ---
try:
    import sqlite3

    DX_DB_PATH_MOBILE_SITE = "/app/traffic.db"

    def dx_mobile_site_conn():
        con = sqlite3.connect(DX_DB_PATH_MOBILE_SITE)
        con.row_factory = sqlite3.Row
        return con

    def dx_mobile_site_table_exists(con, table):
        return bool(con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        ).fetchone())

    def dx_mobile_site_columns(con, table):
        if not dx_mobile_site_table_exists(con, table):
            return set()
        return {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}

    @app.route("/dx/api/mobile-entry-site", methods=["POST"])
    def dx_api_mobile_entry_site():
        data = request.get_json(silent=True) or request.form or {}
        site_id = data.get("site_id")
        plate = str(data.get("plate") or "").strip()
        source = str(data.get("source") or "mobile").strip() or "mobile"

        if not site_id:
            return {"ok": False, "error": "site_id is required"}, 400

        con = dx_mobile_site_conn()
        try:
            if not dx_mobile_site_table_exists(con, "access_log"):
                return {"ok": False, "error": "access_log table not found"}, 404

            cols = dx_mobile_site_columns(con, "access_log")

            if "site_id" not in cols:
                con.execute("ALTER TABLE access_log ADD COLUMN site_id INTEGER")
                cols = dx_mobile_site_columns(con, "access_log")

            id_col = "id" if "id" in cols else "rowid"

            where_parts = []
            args = []

            if "source" in cols:
                where_parts.append("source=?")
                args.append(source)

            if plate and "plate" in cols:
                where_parts.append("plate=?")
                args.append(plate)

            where_sql = ""
            if where_parts:
                where_sql = "WHERE " + " AND ".join(where_parts)

            row = con.execute(
                f"SELECT {id_col} AS rid FROM access_log {where_sql} ORDER BY {id_col} DESC LIMIT 1",
                args
            ).fetchone()

            if not row:
                row = con.execute(
                    f"SELECT {id_col} AS rid FROM access_log ORDER BY {id_col} DESC LIMIT 1"
                ).fetchone()

            if not row:
                return {"ok": False, "error": "no access_log row found"}, 404

            con.execute(
                f"UPDATE access_log SET site_id=? WHERE {id_col}=?",
                (site_id, row["rid"])
            )
            con.commit()

            return {
                "ok": True,
                "updated_log_id": row["rid"],
                "site_id": int(site_id)
            }
        finally:
            con.close()

    print("DX mobile entry site API registered")
except Exception as e:
    print(f"DX mobile entry site API failed: {e}")
# --- End DX Mobile Entry Site API ---


# --- DX Logs Site API ---
try:
    import sqlite3
    import csv
    import io
    from flask import Response

    DX_LOGS_DB_PATH = "/app/traffic.db"

    def dx_logs_conn():
        con = sqlite3.connect(DX_LOGS_DB_PATH)
        con.row_factory = sqlite3.Row
        return con

    def dx_logs_table_exists(con, table):
        return bool(con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        ).fetchone())

    def dx_logs_columns(con, table):
        if not dx_logs_table_exists(con, table):
            return set()
        return {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}

    def dx_logs_img_url(value):
        value = str(value or "").strip()
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if "/captures/" in value:
            return "/captures/" + value.split("/captures/", 1)[1]
        if value.startswith("captures/"):
            return "/" + value
        return value

    def dx_logs_rows(site_id=None, limit=300):
        con = dx_logs_conn()
        try:
            if not dx_logs_table_exists(con, "access_log"):
                return []

            cols = dx_logs_columns(con, "access_log")
            id_col = "id" if "id" in cols else "rowid"

            where = []
            args = []

            if site_id and "site_id" in cols:
                where.append("l.site_id=?")
                args.append(site_id)

            where_sql = ""
            if where:
                where_sql = "WHERE " + " AND ".join(where)

            select_site_name = "s.name AS site_name" if dx_logs_table_exists(con, "dx_sites") else "NULL AS site_name"
            join_site = "LEFT JOIN dx_sites s ON s.id = l.site_id" if dx_logs_table_exists(con, "dx_sites") and "site_id" in cols else ""

            rows = con.execute(f"""
                SELECT l.*, {select_site_name}
                FROM access_log l
                {join_site}
                {where_sql}
                ORDER BY l.{id_col} DESC
                LIMIT ?
            """, args + [int(limit)]).fetchall()

            result = []
            for r in rows:
                d = dict(r)

                image = (
                    d.get("crop_path")
                    or d.get("image_path")
                    or d.get("frame_path")
                    or d.get("photo_path")
                    or ""
                )
                full_image = (
                    d.get("image_path")
                    or d.get("frame_path")
                    or d.get("photo_path")
                    or image
                    or ""
                )

                result.append({
                    "id": d.get("id"),
                    "time": d.get("created_at") or d.get("ts") or d.get("timestamp") or "-",
                    "plate": d.get("plate") or d.get("plate_text") or "-",
                    "plate_color": d.get("plate_color") or d.get("color") or "white",
                    "driver": d.get("driver_name") or "-",
                    "role": d.get("role") or d.get("gate_role") or "-",
                    "source": d.get("source") or d.get("camera_name") or "-",
                    "status": d.get("status") or d.get("access_type") or "-",
                    "operator": d.get("operator") or "-",
                    "note": d.get("note") or "-",
                    "site_id": d.get("site_id"),
                    "site_name": d.get("site_name") or "-",
                    "image": dx_logs_img_url(image),
                    "full_image": dx_logs_img_url(full_image),
                })

            return result
        finally:
            con.close()

    @app.route("/dx/api/logs")
    def dx_api_logs():
        site_id = request.args.get("site_id")
        limit = request.args.get("limit") or 300
        return {"rows": dx_logs_rows(site_id=site_id, limit=limit)}

    @app.route("/dx/api/logs.csv")
    def dx_api_logs_csv():
        site_id = request.args.get("site_id")
        rows = dx_logs_rows(site_id=site_id, limit=10000)

        out = io.StringIO()
        writer = csv.writer(out)

        writer.writerow([
            "Time",
            "Site",
            "Plate",
            "Plate Color",
            "Driver",
            "Role",
            "Source",
            "Status",
            "Operator",
            "Note",
            "Image",
            "Full Image",
        ])

        for r in rows:
            writer.writerow([
                r.get("time"),
                r.get("site_name"),
                r.get("plate"),
                r.get("plate_color"),
                r.get("driver"),
                r.get("role"),
                r.get("source"),
                r.get("status"),
                r.get("operator"),
                r.get("note"),
                r.get("image"),
                r.get("full_image"),
            ])

        data = out.getvalue().encode("utf-8-sig")
        return Response(
            data,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=traffic-logs-by-site.csv"}
        )

    print("DX logs site API registered")
except Exception as e:
    print(f"DX logs site API failed: {e}")
# --- End DX Logs Site API ---


# --- DX Vehicle CSV Preview Import ---
try:
    import csv
    import io
    import json
    import sqlite3
    import uuid
    from pathlib import Path
    from flask import make_response

    DX_IMPORT_DB_PATH = "/app/traffic.db"
    DX_IMPORT_TMP_DIR = Path("/app/data/imports")
    DX_IMPORT_TMP_DIR.mkdir(parents=True, exist_ok=True)

    def dx_import_conn():
        con = sqlite3.connect(DX_IMPORT_DB_PATH)
        con.row_factory = sqlite3.Row
        return con

    def dx_import_table_exists(con, table):
        return bool(con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        ).fetchone())

    def dx_import_columns(con, table):
        if not dx_import_table_exists(con, table):
            return set()
        return {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}

    def dx_clean_plate(value):
        value = str(value or "").strip()
        value = value.replace(" ", "").replace("-", "").replace("_", "")
        value = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        return value

    def dx_get_value(row, *names):
        normalized = {}
        for k, v in row.items():
            kk = str(k or "").strip().lower().replace(" ", "_").replace("-", "_")
            normalized[kk] = v

        for name in names:
            key = name.lower().replace(" ", "_").replace("-", "_")
            if key in normalized:
                return normalized.get(key)
        return ""

    def dx_parse_csv_upload(file_storage):
        raw = file_storage.read()
        text = raw.decode("utf-8-sig", errors="replace")
        sample = text[:2048]

        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel

        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        rows = []
        for i, row in enumerate(reader, start=2):
            rows.append({"line": i, "raw": dict(row)})
        return rows

    def dx_vehicle_exists(con, plate, site_id=None):
        cols = dx_import_columns(con, "vehicles")
        if not dx_import_table_exists(con, "vehicles"):
            return False

        if "site_id" in cols and site_id:
            row = con.execute(
                "SELECT id FROM vehicles WHERE plate=? AND site_id=? LIMIT 1",
                (plate, site_id)
            ).fetchone()
        else:
            row = con.execute(
                "SELECT id FROM vehicles WHERE plate=? LIMIT 1",
                (plate,)
            ).fetchone()

        return bool(row)

    def dx_prepare_vehicle_row(row, site_id=None):
        raw = row["raw"]

        plate = dx_clean_plate(dx_get_value(
            raw,
            "plate", "Plate", "پلاک", "license_plate", "car_plate"
        ))

        driver_name = str(dx_get_value(
            raw,
            "driver_name", "Driver Name", "driver", "نام راننده", "راننده"
        ) or "").strip()

        driver_phone = str(dx_get_value(
            raw,
            "driver_phone", "Driver Phone", "phone", "mobile", "موبایل", "شماره موبایل"
        ) or "").strip()

        employee_code = str(dx_get_value(
            raw,
            "employee_code", "Employee Code", "personnel_code", "کد پرسنلی"
        ) or "").strip()

        department = str(dx_get_value(
            raw,
            "department", "unit", "واحد", "دپارتمان"
        ) or "").strip()

        company = str(dx_get_value(
            raw,
            "company", "شرکت"
        ) or "").strip()

        car_model = str(dx_get_value(
            raw,
            "car_model", "Car Model", "vehicle", "خودرو", "مدل خودرو"
        ) or "").strip()

        car_color = str(dx_get_value(
            raw,
            "car_color", "Car Color", "color", "رنگ خودرو"
        ) or "").strip()

        status = str(dx_get_value(
            raw,
            "status", "access_status", "وضعیت"
        ) or "allowed").strip() or "allowed"

        label = str(dx_get_value(
            raw,
            "label", "tag", "برچسب"
        ) or "").strip()

        return {
            "line": row["line"],
            "plate": plate,
            "driver_name": driver_name,
            "driver_phone": driver_phone,
            "employee_code": employee_code,
            "department": department,
            "company": company,
            "car_model": car_model,
            "car_color": car_color,
            "status": status,
            "label": label,
            "site_id": int(site_id) if site_id else None,
        }

    @app.route("/dx/vehicle-import-template.csv")
    def dx_vehicle_import_template_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Plate",
            "Driver Name",
            "Driver Phone",
            "Employee Code",
            "Department",
            "Company",
            "Car Model",
            "Car Color",
            "Status",
            "Label",
        ])
        writer.writerow([
            "45ع16255",
            "نمونه راننده",
            "09120000000",
            "1001",
            "حراست",
            "DigiExpress",
            "پژو 206",
            "سفید",
            "allowed",
            "پرسنل",
        ])

        data = output.getvalue().encode("utf-8-sig")
        return make_response(
            data,
            200,
            {
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": "attachment; filename=vehicle-import-template.csv",
            }
        )

    @app.route("/dx/vehicle-import-preview")
    def dx_vehicle_import_preview_page():
        html = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<link rel="stylesheet" href="/static/dx-ui-system.css?v=2">
<meta charset="utf-8">
<title>ورود گروهی خودرو/راننده</title>
<style>
@font-face{
  font-family:DigiExpress;
  src:url("/static/fonts/DigiExpress-Regular.woff2") format("woff2");
  font-weight:400;
  font-style:normal;
  font-display:swap;
}
@font-face{
  font-family:DigiExpress;
  src:url("/static/fonts/DigiExpress-Bold.woff2") format("woff2");
  font-weight:800;
  font-style:normal;
  font-display:swap;
}
*{font-family:DigiExpress,Tahoma,Arial,sans-serif !important}
body{margin:0;background:#071426;color:#e8eef8;font-family:DigiExpress,Tahoma,Arial,sans-serif}
.wrap{max-width:1100px;margin:28px auto;padding:0 16px}
.card{background:#121b31;border:1px solid #294173;border-radius:18px;padding:18px;margin-bottom:16px}
h1,h2{margin:0 0 12px}
label{display:block;margin-bottom:6px;color:#cbd5f5;font-weight:800}
input,select{width:100%;height:44px;border-radius:12px;border:1px solid #2b3d72;background:#0f172a;color:#fff;padding:0 12px;box-sizing:border-box}
.btn{height:42px;border:0;border-radius:12px;background:#3158e5;color:#fff;padding:0 16px;font-weight:900;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center}
.btn.secondary{background:#253252}
.btn.green{background:#2f8f46}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:12px}
.stat{background:#0b1528;border:1px solid #294173;border-radius:14px;padding:12px;text-align:center}
.stat b{display:block;font-size:24px;margin-top:6px}
table{width:100%;border-collapse:collapse;margin-top:14px;background:#0b1528;border-radius:14px;overflow:hidden}
th,td{border-bottom:1px solid #263a68;padding:10px;text-align:right;font-size:13px}
th{background:#0d1b31}
.bad{color:#ffb4b4}
.ok{color:#a7f3d0}
.warn{color:#fde68a}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.small{color:#9fb0d0;font-size:13px}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>ورود گروهی خودرو و راننده</h1>
    <p class="small">ابتدا فایل CSV را انتخاب کنید. سیستم قبل از ثبت نهایی، خطاها و تکراری‌ها را نمایش می‌دهد.</p>
    <div class="actions">
      <a class="btn secondary" href="/vehicles">بازگشت به خودروها</a>
      <a class="btn secondary" href="/dx/vehicle-import-template.csv">دانلود Template CSV</a>
    </div>
  </div>

  <div class="card">
    <div class="grid">
      <div>
        <label>Site / دفتر</label>
        <select id="siteSelect"></select>
      </div>
      <div>
        <label>فایل CSV</label>
        <input id="csvFile" type="file" accept=".csv,text/csv">
      </div>
    </div>
    <div class="actions">
      <button class="btn" onclick="previewImport()">بررسی فایل و نمایش پیش‌نمایش</button>
      <button id="commitBtn" class="btn green" onclick="commitImport()" disabled>ثبت نهایی رکوردهای معتبر</button>
    </div>
  </div>

  <div id="result" class="card" style="display:none"></div>
</div>

<script>
let currentToken = "";

async function loadSites(){
  const res = await fetch("/dx/api/sites", {cache:"no-store"});
  const data = await res.json();
  const select = document.getElementById("siteSelect");
  select.innerHTML = "";
  (data.sites || []).forEach(function(site){
    const opt = document.createElement("option");
    opt.value = site.id;
    opt.textContent = site.name;
    select.appendChild(opt);
  });
  const saved = localStorage.getItem("dx_live_site_id") || localStorage.getItem("dx_logs_site_id");
  if(saved) select.value = saved;
}

function esc(v){
  return String(v ?? "").replace(/[&<>"]/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c];
  });
}

async function previewImport(){
  const file = document.getElementById("csvFile").files[0];
  const siteId = document.getElementById("siteSelect").value;
  const result = document.getElementById("result");
  const commitBtn = document.getElementById("commitBtn");

  commitBtn.disabled = true;
  currentToken = "";

  if(!file){
    alert("اول فایل CSV را انتخاب کنید");
    return;
  }

  const fd = new FormData();
  fd.append("file", file);
  fd.append("site_id", siteId);

  result.style.display = "block";
  result.innerHTML = "در حال بررسی فایل...";

  const res = await fetch("/dx/api/vehicle-import-preview", {method:"POST", body:fd});
  const data = await res.json();

  currentToken = data.token || "";
  commitBtn.disabled = !currentToken || data.valid_count === 0;

  let html = "<h2>نتیجه بررسی فایل</h2>";
  html += '<div class="stats">';
  html += '<div class="stat">کل ردیف‌ها<b>' + data.total + '</b></div>';
  html += '<div class="stat">معتبر<b class="ok">' + data.valid_count + '</b></div>';
  html += '<div class="stat">خطادار<b class="bad">' + data.error_count + '</b></div>';
  html += '<div class="stat">تکراری فایل<b class="warn">' + data.duplicate_count + '</b></div>';
  html += '<div class="stat">آپدیت دیتابیس<b class="warn">' + data.update_count + '</b></div>';
  html += '</div>';

  html += '<table><thead><tr><th>خط</th><th>پلاک</th><th>راننده</th><th>موبایل</th><th>واحد</th><th>شرکت</th><th>وضعیت</th><th>نتیجه</th></tr></thead><tbody>';

  (data.preview || []).forEach(function(r){
    const cls = r.valid ? "ok" : "bad";
    html += '<tr>';
    html += '<td>' + esc(r.line) + '</td>';
    html += '<td>' + esc(r.plate) + '</td>';
    html += '<td>' + esc(r.driver_name) + '</td>';
    html += '<td>' + esc(r.driver_phone) + '</td>';
    html += '<td>' + esc(r.department) + '</td>';
    html += '<td>' + esc(r.company) + '</td>';
    html += '<td>' + esc(r.status) + '</td>';
    html += '<td class="' + cls + '">' + esc(r.message) + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table>';
  result.innerHTML = html;
}

async function commitImport(){
  if(!currentToken){
    alert("اول Preview بگیر");
    return;
  }

  const res = await fetch("/dx/api/vehicle-import-commit", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({token:currentToken})
  });

  const data = await res.json();

  alert("ثبت نهایی انجام شد. اضافه‌شده: " + data.inserted + " | آپدیت‌شده: " + data.updated + " | خطا: " + data.errors);

  location.href = "/vehicles";
}

document.addEventListener("DOMContentLoaded", loadSites);
</script>
</body>
</html>
"""
        return html

    @app.route("/dx/api/vehicle-import-preview", methods=["POST"])
    def dx_api_vehicle_import_preview():
        upload = request.files.get("file")
        site_id = request.form.get("site_id") or request.args.get("site_id")

        if not upload:
            return {"ok": False, "error": "file is required"}, 400

        con = dx_import_conn()
        try:
            parsed = dx_parse_csv_upload(upload)
            seen = set()
            valid = []
            preview = []

            for item in parsed:
                row = dx_prepare_vehicle_row(item, site_id=site_id)
                messages = []
                is_valid = True

                if not row["plate"]:
                    is_valid = False
                    messages.append("پلاک خالی است")

                if row["plate"] in seen:
                    is_valid = False
                    messages.append("پلاک داخل فایل تکراری است")
                    row["duplicate_in_file"] = True
                else:
                    row["duplicate_in_file"] = False

                seen.add(row["plate"])

                exists = dx_vehicle_exists(con, row["plate"], site_id=site_id) if row["plate"] else False
                row["exists"] = exists

                if is_valid:
                    messages.append("آپدیت می‌شود" if exists else "اضافه می‌شود")
                    valid.append(row)

                row["valid"] = is_valid
                row["message"] = "، ".join(messages) if messages else "آماده ثبت"
                preview.append(row)

            token = uuid.uuid4().hex
            token_path = DX_IMPORT_TMP_DIR / f"{token}.json"
            token_path.write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")

            return {
                "ok": True,
                "token": token,
                "total": len(parsed),
                "valid_count": len(valid),
                "error_count": len([r for r in preview if not r["valid"]]),
                "duplicate_count": len([r for r in preview if r.get("duplicate_in_file")]),
                "update_count": len([r for r in valid if r.get("exists")]),
                "insert_count": len([r for r in valid if not r.get("exists")]),
                "preview": preview[:300],
            }
        finally:
            con.close()

    @app.route("/dx/api/vehicle-import-commit", methods=["POST"])
    def dx_api_vehicle_import_commit():
        data = request.get_json(silent=True) or {}
        token = str(data.get("token") or "").strip()

        if not token or not re.match(r"^[a-fA-F0-9]{32}$", token):
            return {"ok": False, "error": "invalid token"}, 400

        token_path = DX_IMPORT_TMP_DIR / f"{token}.json"
        if not token_path.exists():
            return {"ok": False, "error": "preview token not found"}, 404

        rows = json.loads(token_path.read_text(encoding="utf-8"))

        con = dx_import_conn()
        inserted = 0
        updated = 0
        errors = 0

        try:
            if not dx_import_table_exists(con, "vehicles"):
                return {"ok": False, "error": "vehicles table not found"}, 404

            cols = dx_import_columns(con, "vehicles")

            if "site_id" not in cols:
                con.execute("ALTER TABLE vehicles ADD COLUMN site_id INTEGER")
                cols = dx_import_columns(con, "vehicles")

            allowed_map = {
                "plate": "plate",
                "driver_name": "driver_name",
                "driver_phone": "driver_phone",
                "employee_code": "employee_code",
                "department": "department",
                "company": "company",
                "car_model": "car_model",
                "car_color": "car_color",
                "status": "status",
                "label": "label",
                "site_id": "site_id",
            }

            for row in rows:
                try:
                    plate = row.get("plate")
                    site_id = row.get("site_id")

                    if not plate:
                        errors += 1
                        continue

                    if "site_id" in cols and site_id:
                        existing = con.execute(
                            "SELECT id FROM vehicles WHERE plate=? AND site_id=? LIMIT 1",
                            (plate, site_id)
                        ).fetchone()
                    else:
                        existing = con.execute(
                            "SELECT id FROM vehicles WHERE plate=? LIMIT 1",
                            (plate,)
                        ).fetchone()

                    values = {}
                    for key, col in allowed_map.items():
                        if col in cols:
                            values[col] = row.get(key)

                    if existing:
                        set_cols = [c for c in values.keys() if c != "plate"]
                        if set_cols:
                            sql = "UPDATE vehicles SET " + ", ".join([f"{c}=?" for c in set_cols]) + " WHERE id=?"
                            con.execute(sql, [values[c] for c in set_cols] + [existing["id"]])
                        updated += 1
                    else:
                        insert_cols = list(values.keys())
                        placeholders = ",".join(["?"] * len(insert_cols))
                        con.execute(
                            "INSERT INTO vehicles (" + ",".join(insert_cols) + ") VALUES (" + placeholders + ")",
                            [values[c] for c in insert_cols]
                        )
                        inserted += 1
                except Exception:
                    errors += 1

            con.commit()
            return {"ok": True, "inserted": inserted, "updated": updated, "errors": errors}
        finally:
            con.close()
            try:
                token_path.unlink()
            except Exception:
                pass

    print("DX vehicle CSV preview import registered")
except Exception as e:
    print(f"DX vehicle CSV preview import failed: {e}")
# --- End DX Vehicle CSV Preview Import ---


# --- DX Site Admin Public Alias ---
try:
    from flask import redirect

    @app.route("/site-admin")
    def dx_site_admin_public_alias():
        return redirect("/dx/sites")

    print("DX site admin public alias registered")
except Exception as e:
    print(f"DX site admin public alias failed: {e}")
# --- End DX Site Admin Public Alias ---











# --- DX Final Role Access Override ---
try:
    from flask import request, session, redirect, jsonify
    from urllib.parse import quote
    import sqlite3

    DX_DB_PATH = "/app/traffic.db"

    def dx_normalize_role(value):
        raw = str(value or "").strip().lower()

        mapping = {
            "admin": "admin",
            "administrator": "admin",
            "مدیر": "admin",
            "ادمین": "admin",

            "security": "security",
            "guard": "security",
            "harasat": "security",
            "حراست": "security",
            "نگهبان": "security",
            "سکیوریتی": "security",

            "viewer": "viewer",
            "view": "viewer",
            "read": "viewer",
            "readonly": "viewer",
            "ویو": "viewer",
            "مشاهده": "viewer",
            "مشاهده‌گر": "viewer",
            "مشاهده گر": "viewer",
        }

        return mapping.get(raw, raw or "viewer")

    def dx_session_username():
        username = session.get("username") or session.get("user") or session.get("email")

        try:
            u = current_user()
            if isinstance(u, dict):
                username = username or u.get("username") or u.get("email")
        except Exception:
            pass

        return username

    def dx_db_role_for_user(username):
        if not username:
            return None

        try:
            c = sqlite3.connect(DX_DB_PATH)
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT role FROM users WHERE username=? AND active=1 LIMIT 1",
                (username,)
            ).fetchone()
            c.close()

            if row:
                return row["role"]
        except Exception:
            pass

        return None

    def dx_final_current_role():
        username = dx_session_username()

        db_role = dx_db_role_for_user(username)
        if db_role:
            return dx_normalize_role(db_role)

        role = None

        try:
            u = current_user()
            if u and isinstance(u, dict):
                role = u.get("role")
        except Exception:
            pass

        if not role:
            role = session.get("role")

        return dx_normalize_role(role)

    def dx_final_is_logged_in():
        if dx_session_username():
            return True

        try:
            u = current_user()
            if u:
                return True
        except Exception:
            pass

        return False

    @app.context_processor
    def dx_inject_auth_role():
        try:
            return {
                "auth_role": dx_final_current_role(),
                "auth_username": dx_session_username() or ""
            }
        except Exception:
            return {
                "auth_role": "viewer",
                "auth_username": ""
            }

    def dx_final_role_allowed(role, path, method):
        role = dx_normalize_role(role)
        path = path or "/"
        method = (method or "GET").upper()

        if path.startswith("/static/") or path.startswith("/captures/") or path.startswith("/uploads/"):
            return True

        if path in ["/login", "/logout", "/status"]:
            return True

        if role == "admin":
            return True

        # Viewer:
        # فقط داشبورد زنده تردد و گزارش ورود و خروج
        if role == "viewer":
            if path in ["/", "/logs", "/logout", "/dx/whoami"]:
                return True

            allowed_prefixes = [
                "/static/",
                "/captures/",
                "/dx/api/live-data",
                "/dx/api/logs",
                "/dx/api/sites",
                "/api/dashboard-stats",
            ]

            return any(path.startswith(x) for x in allowed_prefixes)

        # Security / Harasat:
        # داشبورد زنده، اسکن، دوربین‌ها، مدیریت Site، خودروها، ثبت دستی، گزارش
        if role == "security":
            blocked_exact = [
                "/users",
                "/settings",
                "/mobile-entry",
                "/api/log",
            ]

            blocked_prefixes = [
                "/users/",
                "/settings/",
                "/api/users",
                "/api/settings",
                "/mobile-entry/",
                "/dx/vehicle-import-preview",
                "/dx/vehicle-import-template.csv",
                "/dx/api/vehicle-import-preview",
                "/dx/api/vehicle-import-commit",
            ]

            if path in blocked_exact:
                return False

            if any(path.startswith(x) for x in blocked_prefixes):
                return False

            allowed_exact = [
                "/",
                "/scan",
                "/vehicles",
                "/manual-entry",
                "/logs",
                "/cameras",
                "/dx/sites",
                "/site-admin",
                "/logout",
                "/dx/whoami",
            ]

            allowed_prefixes = [
                "/static/",
                "/captures/",
                "/vehicle/",
                "/log-edit/",
                "/cameras/",
                "/api/vehicles",
                "/api/vehicle-profile/",
                "/api/cameras",
                "/api/camera",
                "/api/dashboard-stats",
                "/dx/api/live-data",
                "/dx/api/logs",
                "/dx/api/sites",
                "/dx/api/camera-sites",
                "/dx/sites/",
            ]

            if path in allowed_exact:
                return True

            if any(path.startswith(x) for x in allowed_prefixes):
                return True

            return False

        # Unknown role = viewer behavior
        if path in ["/", "/logs", "/logout", "/dx/whoami"]:
            return True

        if path.startswith("/static/") or path.startswith("/captures/") or path.startswith("/dx/api/live-data") or path.startswith("/dx/api/logs"):
            return True

        return False

    @app.route("/dx/whoami")
    def dx_whoami():
        if not dx_final_is_logged_in():
            return jsonify({"logged_in": False}), 401

        username = dx_session_username()
        db_role = dx_db_role_for_user(username)

        return jsonify({
            "logged_in": True,
            "username": username,
            "session_role": session.get("role"),
            "db_role": db_role,
            "normalized_role": dx_final_current_role(),
        })

    @app.before_request
    def dx_final_role_access_guard():
        path = request.path or "/"

        if path.startswith("/static/") or path.startswith("/captures/") or path.startswith("/uploads/"):
            return None

        if path in ["/login", "/logout", "/status"]:
            return None

        if not dx_final_is_logged_in():
            if path.startswith("/api/") or path.startswith("/dx/api/"):
                return jsonify({"error": "auth required"}), 401
            return redirect("/login?next=" + quote(path))

        role = dx_final_current_role()

        if path == "/dx/whoami":
            return None

        if not dx_final_role_allowed(role, path, request.method):
            if path.startswith("/api/") or path.startswith("/dx/api/"):
                return jsonify({"error": "access denied", "role": role, "path": path}), 403

            return """
            <html lang="fa" dir="rtl">
            <head><meta charset="utf-8"><title>Access Denied</title></head>
            <body style="background:#071426;color:#fff;font-family:tahoma;padding:40px">
              <h2>دسترسی غیرمجاز</h2>
              <p>شما به این بخش دسترسی ندارید.</p>
              <a style="color:#8ea0ff" href="/">بازگشت به داشبورد</a>
            </body>
            </html>
            """, 403

        return None

    print("DX final role access override registered v3 db-role")
except Exception as e:
    print(f"DX final role access override failed: {e}")
# --- End DX Final Role Access Override ---



# --- DX Force Logout First Handler ---
try:
    from flask import request, session, redirect, make_response

    def dx_force_logout_first_handler():
        path = request.path or ""

        if path in ["/logout", "/dx/logout", "/force-logout"]:
            try:
                session.clear()
            except Exception:
                pass

            resp = make_response(redirect("/login"))
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            return resp

        return None

    # Make this handler run before old auth guards.
    funcs = app.before_request_funcs.setdefault(None, [])

    # Remove previous copies if any
    funcs[:] = [
        f for f in funcs
        if getattr(f, "__name__", "") != "dx_force_logout_first_handler"
    ]

    funcs.insert(0, dx_force_logout_first_handler)

    print("DX force logout first handler registered")
except Exception as e:
    print(f"DX force logout first handler failed: {e}")
# --- End DX Force Logout First Handler ---






# ===== DSSO / OIDC Login Integration =====
try:
    from dsso_auth import register_dsso_routes
    register_dsso_routes(app, db, auth_mode)
    print("DSSO routes registered")
except Exception as e:
    print(f"DSSO route registration failed: {e}")
# ===== /DSSO / OIDC Login Integration =====

if __name__ == '__main__':
    print("Server is ready: http://localhost:5000 | سرور آماده است")
    app.run(debug=False, host='0.0.0.0', port=5000)
