# DigiExpress AI License Plate Access Platform

A public-safe, Dockerized platform for intelligent vehicle access control, license plate recognition, traffic registration, site-based monitoring, camera management, and operational reporting.

This project represents the source-code and documentation layer of the DigiExpress license plate recognition system. It is designed to keep the application structure, routes, templates, static assets, database schema, and operational documentation in GitHub while intentionally excluding runtime data and sensitive production assets.

The repository does **not** include operational databases, captured vehicle images, plate crops, real RTSP camera URLs, credentials, backup archives, large model binaries, internal IP addresses, or organization-only secrets.

---

## Current Synchronization Scope

This repository has been updated to reflect the current operational direction of the server and Docker deployment in a public-safe form:

- Persian / RTL DigiExpress login page and branded UI structure.
- Role-Based Access Control for `admin`, `security`, and `viewer` users.
- Hard logout flow that clears the session before older guards can redirect the request.
- Live dashboard, traffic reports, site management, cameras, vehicles, and manual entry flows.
- Compatibility `dx_multi_site.py` module for deployments that still import the old multi-site extension.
- Public-safe documentation describing what belongs in GitHub and what must remain runtime-only.
- Runtime data such as `traffic.db`, captures, uploads, exports, logs, backups, model caches, and secrets are excluded from Git.

---

## What the System Does

The platform is built to support the full operational workflow of vehicle traffic management:

```text
Vehicle arrives
Camera or operator captures the plate
AI / OCR reads the license plate
Plate color and traffic metadata are stored
Vehicle and driver data are checked
Traffic is registered as entry / exit / manual / scan
Dashboard and reports are updated
```

It is intended for security gates, logistics hubs, enterprise facilities, parking control, and multi-site vehicle access monitoring.

---

## Key Features

### 1. License Plate Recognition with OCR / AI

- Processes vehicle and license plate images.
- Supports manual image scan.
- Stores OCR output and confidence score where available.
- Stores full image and cropped plate paths as runtime data.
- Supports plate color registration in traffic events.
- Supports AI / OCR based plate reading workflows.

### 2. Live Traffic Dashboard

- Shows live traffic statistics.
- Displays entry, exit, manual, and total traffic counts.
- Supports site selection for site-based monitoring.
- Displays latest traffic events.
- Displays review / alert items for unknown or suspicious records.
- Uses `/dx/api/live-data` for live dashboard refresh.

### 3. Traffic Report

- Displays traffic history in a centralized report.
- Supports filtering by Site.
- Displays plate number, traffic type, source, vehicle status, plate color, and timestamp.
- Supports site-based reporting through `/dx/api/logs`.
- Designed for operational review and follow-up.

### 4. Manual Traffic Entry

- Allows security operators to register official entry / exit records manually.
- Supports Site selection.
- Stores operator name and notes.
- Useful when a camera, RTSP stream, or OCR result is not available.

### 5. Manual Plate Scan

- Allows an operator to upload a vehicle or plate image.
- Processes the image with the AI / OCR pipeline.
- Stores the confirmed result into the traffic report.
- Supports plate color registration.

### 6. Vehicle and Driver Management

- Registers vehicle plates.
- Stores driver name, phone number, employee code, unit / department, company, vehicle model, vehicle color, and access status.
- Supports vehicle data import from Excel and CSV files.
- Keeps vehicle records linked to a Site where applicable.

### 7. RTSP Camera Management

- Defines entry / exit cameras.
- Stores camera role such as `entry` or `exit`.
- Connects cameras to Sites.
- Keeps the application ready for RTSP-based processing in operational deployments.

### 8. Multi-Site Management

Site management is exposed through:

```text
/settings/sites
/dx/sites
/site-admin
```

Capabilities:

- Create a new Site.
- Edit Site name, code, description, and enabled / disabled status.
- View the number of cameras per Site.
- View the number of traffic records per Site.
- Assign cameras to Sites from the same management flow.

---

## Roles and Access Control

The application uses the local `users` table for authentication and role detection.

Valid roles:

```text
admin
security
viewer
```

### Admin

Full access to all panels, settings, import workflows, model status views, management APIs, and operational sections.

### Security / Harasat

Operational access only:

- Live traffic dashboard
- Manual plate scan
- Entry / exit cameras
- Site management
- Vehicles and drivers
- Manual traffic entry
- Traffic report

Security users do **not** have access to user management, admin settings, report API shortcuts, management import workflows, or mobile-entry fallback flows.

### Viewer

Read-only observation access:

- Live traffic dashboard
- Traffic report

Viewer users do not have access to scanning, manual entry, vehicles, cameras, site management, user management, imports, or admin APIs.

---

## Technology Stack

```text
Python
Flask
SQLite
Docker
HTML / CSS / JavaScript
RTSP Stream
OCR / AI Model
Multi-Site Architecture
CSV / Excel Import & Export
```

This stack keeps the platform lightweight, portable, easy to maintain, and suitable for operational environments.

---

## Main Routes

```text
/                         Live dashboard
/login                    Login page
/logout                   Logout and session cleanup
/dx/logout                Logout alias
/force-logout             Logout alias
/scan                     Manual plate scan
/manual-entry             Manual traffic entry
/mobile-entry             Admin-only mobile entry fallback
/vehicles                 Vehicles and drivers
/vehicles/import          Excel / CSV import workflow
/cameras                  Camera management
/logs                     Traffic report
/settings/sites           Site management
/dx/sites                 Site management alias
/site-admin               Site management alias
/status                   AI / OCR service status
/dx/whoami                Current user and normalized role
```

---

## API Routes

```text
GET /dx/whoami
GET /dx/api/live-data
GET /dx/api/logs
GET /dx/api/sites
GET /api/dashboard-stats
GET /api/sites
GET /api/vehicles
GET /api/log
GET /dx/vehicle-import-template.csv
```

API access is controlled by role. Some endpoints are intended for admin-level use only.

---

## Database

Default SQLite database path in the template version:

```text
data/traffic.db
```

In the operational server deployment, the runtime database may exist inside the container, for example:

```text
/app/traffic.db
```

The operational database must **not** be committed to Git.

Main tables in the public-safe template:

```text
users
sites / dx_sites in some operational deployments
vehicles
cameras
events / access_log in some operational deployments
```

Valid user roles:

```text
admin
security
viewer
```

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/bahram-khakbaz/ai-license-plate-access-platform.git
cd ai-license-plate-access-platform
```

### 2. Create environment configuration

```bash
cp .env.example .env
```

Set at least:

```text
SECRET_KEY
ADMIN_USERNAME
ADMIN_PASSWORD
DB_PATH
```

### 3. Start with Docker

```bash
docker compose up -d --build
```

### 4. Open the application

```text
http://localhost
```

---

## Required Post-Deploy Tests

### Service health

```bash
curl -I http://localhost/status
```

### Current user and role

After login, open:

```text
/dx/whoami
```

Expected example:

```json
{
  "logged_in": true,
  "username": "user@example.com",
  "db_role": "security",
  "normalized_role": "security"
}
```

### Logout

```bash
curl -I http://localhost/logout
```

Correct behavior:

```text
HTTP/1.1 302 FOUND
Location: /login
Set-Cookie: session=; Expires=Thu, 01 Jan 1970...
```

### Site management

```bash
curl -I http://localhost/dx/sites
curl -I http://localhost/site-admin
```

---

## Runtime Data That Must Not Be Committed

```text
traffic.db
*.db
*.sqlite
*.sqlite3
data/
uploads/
exports/
logs/
captures/
backups/
.env
.env.*
*.pem
*.key
*.crt
```

Also do not commit:

```text
Real RTSP camera URLs
Internal IP addresses
Production credentials
Operational screenshots
License plate images
Vehicle captures
Plate crops
Backup archives
Large AI model binaries
Model caches
Docker runtime cache
```

---

## Correct Sync Model: Server, Container, and GitHub

In the operational environment, there are usually three separate layers:

```text
1. Live code inside Docker container: /app
2. Server working directory: /opt/pelak-khan/IranPlate-Vision
3. Public-safe GitHub repository
```

The Docker container and server working directory may be synchronized for deployment, but GitHub must only receive clean source files and documentation.

The GitHub repository should contain:

```text
app.py
storage.py
config.py
import_tools.py
plate_engine/
templates/
static/
Dockerfile
docker-compose.yml
requirements.txt
README.md
docs/
.gitignore
```

The GitHub repository should not contain:

```text
traffic.db
best.pt if it is a large/private runtime model
app.py.bak-*
*.bak-*
docker-cache/
__pycache__/
data/
logs/
backups/
captures/
uploads/
.env.ldap
Real camera URLs
Production images
```

See also:

```text
docs/SERVER_SYNC_GUIDE.md
```

---

## Safe Server-to-Git Checklist

Before moving server changes to GitHub, check:

```bash
git status
git diff --stat
git diff --name-only
```

Search for sensitive values before committing:

```bash
grep -RIn "rtsp://\|password\|SECRET\|TOKEN\|digikala.services\|internal" . \
  --exclude-dir=.git \
  --exclude-dir=__pycache__ \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='*.png' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' || true
```

Only commit clean source code, templates, static assets, and documentation.

---

## Vehicle Import

CSV template:

```text
/dx/vehicle-import-template.csv
```

Supported fields:

```text
Plate
Driver Name
Phone
Unit / Department
Company
Employee Code
Vehicle Model
Vehicle Color
Status
```

---

## Operational Value

The platform is designed to provide:

- Lower human error in vehicle traffic registration.
- Faster plate checking and traffic monitoring.
- Centralized vehicle, driver, camera, and Site information.
- Reliable reporting for operational review.
- Site-based visibility across multiple locations.
- Role-based access for different operational teams.
- A maintainable internal system aligned with DigiExpress needs.

---

## Security Notes

- Always set a strong `SECRET_KEY`.
- Change default admin credentials before any real deployment.
- Do not expose the application publicly without authentication and network controls.
- Keep camera URLs and credentials outside Git.
- Back up the SQLite database regularly.
- Monitor disk usage for saved images and captures.
- Keep runtime data outside the application image when possible.

---

## Designed For

Security gate operations, logistics hubs, parking control, enterprise facilities, and multi-site vehicle access monitoring.

## Designed By

DigiExpress Infrastructure
