import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

APP_ENV = os.getenv("APP_ENV", "production")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "5000"))
AUTH_MODE = os.getenv("AUTH_MODE", "local")

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", BASE_DIR / "exports"))
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
CAPTURE_DIR = DATA_DIR / "captures"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "traffic.db"))

DETECTOR_MODEL_PATH = Path(os.getenv("DETECTOR_MODEL_PATH", "models/best.pt"))
if not DETECTOR_MODEL_PATH.is_absolute():
    DETECTOR_MODEL_PATH = BASE_DIR / DETECTOR_MODEL_PATH
OCR_MODEL_NAME = os.getenv("OCR_MODEL_NAME", "hezarai/crnn-fa-license-plate-recognition-v2")
DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.40"))

SAVE_VEHICLE_IMAGES = os.getenv("SAVE_VEHICLE_IMAGES", "1") == "1"
CAMERA_RECONNECT_SECONDS = int(os.getenv("CAMERA_RECONNECT_SECONDS", "10"))
CAMERA_SNAPSHOT_INTERVAL_SECONDS = int(os.getenv("CAMERA_SNAPSHOT_INTERVAL_SECONDS", "2"))
CAMERA_DEFAULT_CONFIDENCE = float(os.getenv("CAMERA_DEFAULT_CONFIDENCE", "0.50"))
IMAGE_RETENTION_DAYS = int(os.getenv("IMAGE_RETENTION_DAYS", "30"))
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "180"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))

for path in [DATA_DIR, UPLOAD_DIR, EXPORT_DIR, LOG_DIR, CAPTURE_DIR]:
    path.mkdir(parents=True, exist_ok=True)
