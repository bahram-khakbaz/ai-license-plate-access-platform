# AI License Plate Access Platform

A production-ready, Dockerized web platform for vehicle access control, license plate recognition, traffic logging, multi-site monitoring, and security gate operations.

This repository is maintained as a public-safe project template. It intentionally avoids internal IP addresses, real credentials, private camera URLs, organization-only infrastructure names, and real operational data.

---

## Current Stable Scope

The project now includes the latest operational changes from the production hardening phase:

- Multi-site support for dashboards, logs, cameras, vehicles, manual entries, and scan flows.
- Site management with camera assignment integrated into the same panel.
- Role-based access control backed by the `users` table.
- Admin, security, and viewer access profiles.
- Hardened logout flow that clears the session before old guards can redirect the request.
- `/dx/whoami` endpoint for verifying the logged-in user and normalized role.
- CSV vehicle import support in addition to Excel import.
- Live dashboard API through `/dx/api/live-data`.
- Site-based traffic report API through `/dx/api/logs`.
- Compatibility fallback for hidden AI-status UI calls.

---

## Key Features

### License Plate Recognition

- Detect license plates from uploaded images.
- Read plate text using OCR.
- Support camera-based recognition from RTSP streams.
- Support manual scan and mobile capture flows.
- Store traffic source as camera, scan, manual, or mobile.
- Track plate color where available.

### Live Traffic Dashboard

- Site selector for the live dashboard.
- Today traffic summary.
- Entry, exit, and manual counts.
- Vehicle count by site.
- Latest traffic feed.
- Alert list for unknown or review vehicles.
- `/dx/api/live-data` endpoint for live UI refresh.

### Traffic Registration

- Camera-based entry and exit logging.
- Manual entry by a security operator.
- Manual plate scan with AI result confirmation.
- Mobile entry flow for admin-only fallback use.
- Operator name, notes, plate color, image path, and crop path fields.

### Vehicle and Driver Management

- Register vehicles and drivers.
- Store plate, driver name, phone, unit/department, company, employee code, vehicle model, vehicle color, and access status.
- Unique vehicle records per site and plate.
- Excel and CSV import support.

### Multi-Site Management

Site management is available through:

```text
/settings/sites
/dx/sites
/site-admin
```

Capabilities:

- Create sites.
- Edit site name, code, description, and enabled status.
- Enable or disable sites.
- See camera count per site.
- See traffic count per site.
- See latest traffic per site.
- Assign cameras to sites inside the same page.

### Authentication and RBAC

The app uses the `users` table for local authentication and role detection.

Valid roles:

```text
admin
security
viewer
```

#### Admin

Full access to all panels and APIs.

#### Security / Harasat

Operational access only:

- Live traffic dashboard
- Manual plate scan
- Entry/exit cameras
- Site management
- Vehicles and drivers
- Manual traffic entry
- Traffic report

Security users do not get:

- User/settings management
- AI status card as a management panel
- Report API shortcut
- Mobile entry
- Vehicle import workflow

#### Viewer

Read-only observation access:

- Live traffic dashboard
- Traffic report

Viewer users do not get operational actions such as scan, manual entry, vehicles, cameras, site management, users/settings, imports, or admin APIs.

---

## Main Routes

```text
/                         Live dashboard
/login                    Login
/logout                   Hard logout and session clear
/dx/logout                Logout alias
/force-logout             Logout alias
/scan                     Manual AI plate scan
/manual-entry             Manual traffic entry
/mobile-entry             Mobile entry flow
/vehicles                 Vehicle and driver management
/vehicles/import          Excel/CSV vehicle import
/cameras                  Entry/exit camera management
/logs                     Traffic report
/settings/sites           Site management
/dx/sites                 Site management alias
/site-admin               Site management alias
/status                   AI/model status
/dx/whoami                Current user and role verification
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

Access to APIs is controlled by role. `/api/log` is intended for admin-level use; viewer and security users should use the UI and allowed `/dx/api/logs` flow.

---

## Database

Default SQLite database path:

```text
data/traffic.db
```

Main tables:

```text
users
sites
vehicles
cameras
events
```

### users

```text
id
username
password_hash
role
full_name
active
created
```

### sites

```text
id
name
code
description
enabled
created_at
updated_at
```

### vehicles

```text
id
site_id
plate
driver_name
phone
unit
company
employee_code
vehicle_model
vehicle_color
status
created_at
updated_at
```

### cameras

```text
id
site_id
name
stream_url
gate_role
enabled
created_at
updated_at
```

### events

```text
id
site_id
plate
gate_role
source
operator_name
note
plate_color
score
image_path
crop_path
created_at
```

---

## Default Admin User

On first setup, if the `users` table is empty, the app creates one admin user using environment variables:

```text
ADMIN_USERNAME
ADMIN_PASSWORD
```

Fallback values for local development only:

```text
admin@example.com
change-me-now
```

Change these values before using the platform in any real environment.

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/bahram-khakbaz/ai-license-plate-access-platform.git
cd ai-license-plate-access-platform
```

### 2. Configure environment

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

### 3. Start

```bash
docker compose up -d --build
```

### 4. Open

```text
http://localhost
```

---

## Vehicle Import

Excel template:

```text
/vehicles/template.xlsx
```

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

## Operational Tests

### Status

```bash
curl -I http://localhost/status
```

### Login Role

After login, open:

```text
/dx/whoami
```

Expected response:

```json
{
  "logged_in": true,
  "username": "...",
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

### Site Management

```bash
curl -I http://localhost/dx/sites
curl -I http://localhost/site-admin
```

---

## Runtime Data

Runtime-generated data should not be committed to Git:

```text
data/
uploads/
exports/
logs/
captures/
backups/
*.db
*.sqlite
*.sqlite3
.env
```

Saved camera frames and plate crops should live under runtime capture directories, not inside the repository.

---

## Recommended Production Setup

- Use HTTPS behind a reverse proxy.
- Set a strong `SECRET_KEY`.
- Change the default admin credentials immediately.
- Restrict access to internal networks or authenticated users.
- Keep runtime database and captures outside the application image.
- Back up the SQLite database regularly.
- Monitor disk usage for saved images.
- Do not commit camera URLs, screenshots, database files, or credentials.

---

## Changelog Summary

### 2026-07-13 - Stable Role Access + Logout

- Added DB-backed role detection from `users` table.
- Added final RBAC for admin, security, and viewer.
- Added `/dx/whoami` for role verification.
- Fixed logout for non-admin roles.
- Added session-clearing hard logout handler.
- Added safe fallback for hidden AI status JavaScript calls.
- Updated dashboard and navigation to be role-aware.
- Integrated camera assignment into site management.
- Added `/dx/sites` and `/site-admin` aliases.
- Added CSV vehicle import template and CSV import support.

---

## Designed for

Security gate operations, logistics hubs, parking control, enterprise facilities, and multi-site vehicle access monitoring.

## Designed by

DigiExpress Infrastructure
