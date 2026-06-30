from pathlib import Path
from uuid import uuid4

from config import UPLOAD_DIR


def normalize_plate(text):
    return (text or '').replace(' ', '').replace('-', '').strip()


def save_upload(file_storage):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file_storage.filename or 'upload.jpg').suffix or '.jpg'
    output = UPLOAD_DIR / f'{uuid4().hex}{suffix}'
    file_storage.save(output)
    return str(output)


def recognize(file_storage=None, manual_plate=None, plate_color='white'):
    image_path = save_upload(file_storage) if file_storage else None
    plate = normalize_plate(manual_plate)
    return {
        'plate': plate,
        'confidence': 1.0 if plate else 0.0,
        'plate_color': plate_color or 'white',
        'image_path': image_path,
        'crop_path': None,
        'engine': 'placeholder'
    }
