# Deployment Guide

## Requirements

Recommended minimum server resources:

```text
CPU: 4 cores or higher
RAM: 8 GB or higher
Storage: Depends on image retention policy
OS: Linux server
Docker: Latest stable version
Docker Compose: Latest stable version
```

For camera-heavy deployments, increase CPU, RAM, and storage.

---

## Docker Deployment

### 1. Clone repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-license-plate-access-platform.git
cd ai-license-plate-access-platform
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```bash
nano .env
```

### 3. Start service

```bash
docker compose up -d --build
```

### 4. Check logs

```bash
docker compose logs -f
```

### 5. Open panel

```text
http://SERVER_ADDRESS
```

---

## Recommended Volumes

Use persistent volumes for:

```text
data/
uploads/
exports/
logs/
```

These should not be stored inside the container image.

---

## Reverse Proxy

For production, use a reverse proxy such as Nginx or Traefik.

Recommended:

- Enable HTTPS
- Restrict access to trusted internal networks
- Set upload size limits
- Add request timeout settings for image uploads

---

## Camera Setup

For RTSP camera integration:

1. Create a camera user with a strong password.
2. Enable RTSP on the camera.
3. Use a low-latency stream when possible.
4. Position the camera to capture plates clearly.
5. Avoid extreme angles and glare.
6. Prefer a dedicated lane-facing camera.

Example RTSP format:

```text
rtsp://USERNAME:PASSWORD@CAMERA_HOST:554/STREAM_PATH
```

Do not commit real camera URLs to Git.

---

## Storage Planning

Storage depends on:

- Number of cameras
- Number of events per day
- Whether full frames are saved
- Whether plate crops are saved
- JPEG quality
- Retention period

Approximate formula:

```text
Daily storage = events_per_day × average_image_size × images_per_event
Required storage = daily_storage × retention_days
```

Example:

```text
2,000 events/day × 300 KB × 2 images × 30 days ≈ 36 GB
```

Keep extra storage for database, logs, backups, and growth.

---

## Backup

Recommended backup targets:

- SQLite database
- Captured images if required
- Environment configuration
- Uploaded files
- Exported reports

Suggested backup frequency:

```text
Database: daily
Images: based on retention policy
Configuration: after each change
```

---

## Upgrade Process

1. Back up database and runtime directories.
2. Pull latest code.
3. Rebuild container.
4. Run migrations by starting the application.
5. Check logs.
6. Test login, scan, mobile entry, and reports.

```bash
docker compose down
docker compose up -d --build
docker compose logs -f
```
