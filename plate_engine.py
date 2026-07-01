import re
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image

from config import DETECTION_CONFIDENCE, DETECTOR_MODEL_PATH, OCR_MODEL_NAME, UPLOAD_DIR

_detector = None
_ocr = None
_model_error = None


def normalize_plate(text):
    value = str(text or '').strip()
    value = value.replace(' ', '').replace('-', '').replace('_', '')
    value = value.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
    return value


def fa_digits(text):
    return str(text or '').translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


def extract_ocr_text(raw):
    if raw is None:
        return ''
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list) and raw:
        return extract_ocr_text(raw[0])
    if isinstance(raw, dict):
        for key in ('text', 'label', 'prediction', 'transcription'):
            if raw.get(key):
                return str(raw[key]).strip()
    text = getattr(raw, 'text', None) or getattr(raw, 'prediction', None)
    return str(text or raw).strip()


def clean_ocr_plate(text):
    value = normalize_plate(text)
    value = re.sub(r'[^0-9A-Za-z\u0600-\u06FF]', '', value)
    return value


def load_models():
    global _detector, _ocr, _model_error
    if _detector is not None and _ocr is not None:
        return True
    try:
        if not DETECTOR_MODEL_PATH.exists():
            raise FileNotFoundError(f'Detector model not found: {DETECTOR_MODEL_PATH}')
        from ultralytics import YOLO
        from hezar.models import Model
        _detector = YOLO(str(DETECTOR_MODEL_PATH))
        _ocr = Model.load(OCR_MODEL_NAME)
        _model_error = None
        return True
    except Exception as exc:
        _model_error = str(exc)
        return False


def status():
    ready = load_models()
    return {
        'ready': ready,
        'error': _model_error,
        'detector_model': str(DETECTOR_MODEL_PATH),
        'ocr_model': OCR_MODEL_NAME,
    }


def save_upload(file_storage):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file_storage.filename or 'upload.jpg').suffix or '.jpg'
    output = UPLOAD_DIR / f'{uuid4().hex}{suffix}'
    file_storage.save(output)
    return str(output)


def read_image(path):
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError('Could not read uploaded image')
    return img


def crop_best_plate(img):
    if not load_models():
        return None, 0.0
    results = _detector.predict(source=img, conf=DETECTION_CONFIDENCE, verbose=False)
    if not results or not getattr(results[0], 'boxes', None):
        return None, 0.0
    boxes = results[0].boxes
    if len(boxes) == 0:
        return None, 0.0
    best = None
    best_conf = 0.0
    h, w = img.shape[:2]
    for box in boxes:
        conf = float(box.conf[0]) if getattr(box, 'conf', None) is not None else 0.0
        if conf < best_conf:
            continue
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        best = img[y1:y2, x1:x2].copy()
        best_conf = conf
    return best, best_conf


def run_ocr(crop):
    if crop is None:
        return ''
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    raw = _ocr.predict(pil)
    return clean_ocr_plate(extract_ocr_text(raw))


def detect_plate_color(crop):
    if crop is None or crop.size == 0:
        return 'white'
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, np.array([15, 60, 80]), np.array([40, 255, 255]))
    green = cv2.inRange(hsv, np.array([40, 40, 60]), np.array([90, 255, 255]))
    blue = cv2.inRange(hsv, np.array([90, 40, 60]), np.array([135, 255, 255]))
    red1 = cv2.inRange(hsv, np.array([0, 50, 60]), np.array([10, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([170, 50, 60]), np.array([180, 255, 255]))
    total = max(crop.shape[0] * crop.shape[1], 1)
    scores = {
        'yellow': float(np.count_nonzero(yellow)) / total,
        'green': float(np.count_nonzero(green)) / total,
        'blue': float(np.count_nonzero(blue)) / total,
        'red': float(np.count_nonzero(red1 | red2)) / total,
    }
    color, score = max(scores.items(), key=lambda x: x[1])
    return color if score > 0.10 else 'white'


def save_crop(crop):
    if crop is None:
        return None
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    output = UPLOAD_DIR / f'{uuid4().hex}_crop.jpg'
    cv2.imwrite(str(output), crop)
    return str(output)


def recognize(file_storage=None, manual_plate=None, plate_color=None):
    image_path = save_upload(file_storage) if file_storage else None
    crop_path = None
    confidence = 1.0 if manual_plate else 0.0
    plate = normalize_plate(manual_plate)
    detected_color = plate_color or 'white'

    if image_path:
        img = read_image(image_path)
        crop, confidence = crop_best_plate(img)
        if crop is not None:
            crop_path = save_crop(crop)
            detected_color = plate_color or detect_plate_color(crop)
            ocr_plate = run_ocr(crop)
            if ocr_plate:
                plate = ocr_plate

    return {
        'plate': plate,
        'confidence': confidence,
        'plate_color': detected_color,
        'image_path': image_path,
        'crop_path': crop_path,
        'engine': 'yolo-hezar',
    }
