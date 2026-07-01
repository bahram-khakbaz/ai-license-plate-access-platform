# Quick Start

This guide is for a clean server deployment.

## 1. Install prerequisites

Install Docker, Docker Compose, and Git on your server.

For Ubuntu-based servers:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
```

Install Docker using the official Docker installation guide for your operating system.

---

## 2. Clone the project

```bash
git clone https://github.com/bahram-khakbaz/ai-license-plate-access-platform.git
cd ai-license-plate-access-platform
```

If the detector model was committed through Git LFS, install Git LFS before cloning or pull LFS files after clone:

```bash
git lfs install
git lfs pull
```

The detector model must exist at:

```text
models/best.pt
```

---

## 3. Create configuration

```bash
cp .env.example .env
nano .env
```

Set at least:

```text
SECRET_KEY=change-this-to-a-long-random-value
APP_PORT=5000
HOST_PORT=5000
AUTH_MODE=local
DETECTOR_MODEL_PATH=models/best.pt
OCR_MODEL_NAME=hezarai/crnn-fa-license-plate-recognition-v2
```

---

## 4. Create runtime directories

```bash
make init
```

Or manually:

```bash
mkdir -p data uploads exports logs backups models
```

---

## 5. Verify model file

```bash
ls -lh models/best.pt
```

If `models/best.pt` does not exist and `MODEL_DOWNLOAD_URL` is configured in `.env`, run:

```bash
make models
```

For offline servers, copy `models/best.pt` manually to the server before starting the service.

---

## 6. Start the platform

```bash
docker compose up -d --build
```

---

## 7. Check service status

```bash
docker compose ps
docker compose logs -f
```

Health check:

```bash
bash scripts/healthcheck.sh
```

Model/API status:

```bash
curl http://localhost:5000/status
```

---

## 8. Open the panel

```text
http://SERVER_ADDRESS:5000
```

If you changed `HOST_PORT`, use that port.

---

## 9. Update the platform

```bash
git pull
git lfs pull
docker compose up -d --build
```

---

## 10. Backup

```bash
bash scripts/backup.sh
```

Backups are stored under:

```text
backups/
```

---

## Important Notes

Do not upload production secrets, real camera URLs, runtime databases, captured vehicle images, or private operational data to Git.

The detector model path is configurable through `DETECTOR_MODEL_PATH`. The OCR model is loaded from `OCR_MODEL_NAME` and may require internet access during the first build/runtime unless it is already cached inside the image or provided through an internal package/cache strategy.
