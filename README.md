# AI License Plate Access Platform

A production-ready, Dockerized web platform for vehicle access control, license plate recognition, traffic logging, and security gate operations.

This project provides a security operations panel for registering vehicle entries and exits using AI-based license plate recognition from camera streams, uploaded images, manual entries, and mobile-based capture.

> This repository is written as a public-ready project template. It intentionally avoids internal IP addresses, real credentials, private infrastructure names, production camera URLs, and real operational data.

---

## Overview

AI License Plate Access Platform is designed for organizations that need a practical, web-based solution for monitoring and managing vehicle access at gates, parking areas, warehouses, logistics hubs, and secure facilities.

The platform combines AI-powered license plate detection, OCR, RTSP camera integration, mobile capture, manual registration, live dashboards, traffic reports, vehicle profiles, and role-based access control.

The goal is to provide an operational and easy-to-use system for security teams without requiring a dedicated desktop application.

---

## Key Features

### License Plate Recognition

- Detect license plates from uploaded images
- Read plate text using OCR
- Support camera-based recognition from RTSP streams
- Support mobile photo-based recognition
- Render a visual plate preview in the UI
- Detect and display plate background color such as white, yellow, green, red, blue, black, or unknown

### Traffic Registration

- Camera-based entry and exit logging
- Manual entry by a security operator
- Mobile-based entry and exit registration
- Image and plate crop storage
- Operator name and notes
- Entry and exit role selection
- Source tracking: camera, manual, or mobile

### Live Dashboard

- Today traffic summary
- Entry and exit counts
- Manual, mobile, and camera traffic visibility
- Latest traffic table
- Alert section for important events
- Live refresh support
- Visual plate rendering with color support

### Vehicle and Driver Management

- Register vehicles and drivers
- Store plate, driver name, phone, department, company, vehicle model, and vehicle color
- Whitelist, blacklist, and unknown status support
- Open vehicle profile directly from traffic logs
- Add a new vehicle from a detected traffic record

### Security Operations

- Mobile fallback when a physical camera is unavailable
- Manual registration for controlled gate operations
- Edit incorrect OCR results
- Keep related image evidence for traffic records
- Alert level support for unknown or important vehicles
- Designed for security operators and administrators

### Authentication and Access Control

- Login-protected panel
- Role-based access control
- Admin, security, and viewer-style access patterns
- Admin-only user management
- Session-based access protection

### Deployment

- Dockerized application
- Persistent storage for runtime data, uploads, exports, and captures
- CPU-friendly deployment
- Suitable for VM-based installation
- RTSP camera integration through OpenCV and FFmpeg

---

## Tech Stack

- Python
- Flask
- SQLite
- OpenCV
- AI plate detection model
- OCR model
- HTML, CSS, and JavaScript
- Docker and Docker Compose
- RTSP camera streams
- Mobile browser camera/file upload support

---

## Main Modules

```text
app.py                  Web application and API routes
db.py                   SQLite database layer and migrations
camera_manager.py       RTSP camera worker and detection loop
templates/              Web UI templates
static/                 Static assets, fonts, CSS, images
data/                   Runtime data and saved captures
docs/                   Project documentation
```

---

## User Flows

### Camera-based access flow

1. Add an RTSP camera in the camera management panel.
2. The camera worker reads frames from the stream.
3. Plate detection and OCR run periodically.
4. A traffic record is created when a valid plate is detected.
5. The event appears in the live dashboard and traffic reports.

### Mobile security flow

1. The security operator opens the mobile entry page.
2. The operator takes or uploads a vehicle image.
3. The platform reads the plate and estimates image quality.
4. The operator confirms entry or exit.
5. The record is saved with image evidence and operator name.

### Manual fallback flow

1. The operator opens manual entry.
2. Plate, entry/exit type, operator, and notes are entered.
3. A formal traffic record is created without using a camera.

---

## Screens and Panels

- Main dashboard
- Manual plate scan
- Camera management
- Vehicle and driver management
- Manual traffic registration
- Mobile security registration
- Traffic reports
- Vehicle profile
- User and settings management
- Live traffic dashboard

---

## Privacy and Security Notes

This repository intentionally does not include:

- Internal IP addresses
- Real production credentials
- Directory service details
- Organization-specific infrastructure names
- Passwords or secrets
- Private camera URLs
- Real operational data

Use `.env.example` as a safe template for environment configuration.

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/bahram-khakbaz/ai-license-plate-access-platform.git
cd ai-license-plate-access-platform
```

### 2. Create environment file

```bash
cp .env.example .env
```

Edit `.env` and set your own secure values.

### 3. Start with Docker Compose

```bash
docker compose up -d --build
```

### 4. Open the web panel

```text
http://localhost
```

---

## Runtime Data

Runtime-generated data should not be committed to Git:

```text
data/
uploads/
exports/
*.db
*.sqlite
*.log
.env
```

Saved camera frames and plate crops are stored under runtime capture directories.

---

## Recommended Production Setup

- Use HTTPS behind a reverse proxy
- Use strong authentication settings
- Change all default passwords
- Restrict network access to internal users
- Keep runtime data outside the application image
- Back up the SQLite database regularly
- Monitor disk usage for saved images
- Use dedicated cameras positioned for plate visibility

---

## Roadmap

Planned or recommended improvements:

- Audit log for edited traffic records
- Active vehicle/session dashboard
- Gate/location selection for mobile entries
- Advanced camera health monitoring
- Better image quality scoring
- Daily security report export
- PWA mode for mobile security operators
- Multi-site support
- Configurable retention policies
- More accurate plate color classification

---

## License

This project is provided as an operational platform template. Choose and add a license file based on your organization's open-source or private repository policy.
