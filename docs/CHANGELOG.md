# Changelog

## 2026-07-13 - GitHub Operational Alignment

### Added

- Public-safe DigiExpress branding asset for the login page.
- Persian/RTL login page aligned with the production UI direction.
- Persian/RTL base layout and role-aware navigation.
- Persian live dashboard content matching the operational access model.
- Compatibility `dx_multi_site.py` module for deployments that still import the historical multi-site extension.
- Updated README describing the live server / Docker / GitHub sync model.

### Changed

- Repository documentation now reflects the actual operational scope:
  - AI/OCR plate recognition
  - Plate color tracking
  - Live traffic dashboard
  - Traffic report
  - Manual entry
  - Manual plate scan
  - Vehicle and driver management
  - RTSP camera management
  - Site management and camera assignment
  - RBAC for admin, security and viewer
  - CSV/Excel import support

- UI language in the public template moved from generic English to DigiExpress Persian terminology.
- `security` role remains operational and can access dashboard, scan, cameras, sites, vehicles, manual entry and reports.
- `viewer` role remains read-only and can access only live dashboard and traffic report.

### Fixed

- Removed generic login copy from the GitHub template.
- Aligned logout labels and navigation naming with the production implementation.
- Documented runtime files that must never be committed to GitHub.

## 2026-07-13 - Stable Role Access + Logout

### Added

- DB-backed role detection from the `users` table.
- `/dx/whoami` endpoint for current user and normalized role verification.
- Final RBAC profiles for `admin`, `security`, and `viewer`.
- Hard logout handler that clears the session before auth guards redirect the request.
- Role-aware dashboard navigation.
- `/dx/sites` and `/site-admin` aliases for site management.
- Site management page with integrated camera-to-site assignment.
- CSV vehicle import template and CSV import support.
- `/dx/api/live-data` endpoint for the live dashboard.
- `/dx/api/logs` endpoint for site-based traffic reports.
- Safe JavaScript fallback for hidden AI status calls.

### Changed

- Security users now have access to:
  - Live traffic dashboard
  - Manual plate scan
  - Entry/exit cameras
  - Site management
  - Vehicles and drivers
  - Manual traffic entry
  - Traffic report

- Viewer users now have access only to:
  - Live traffic dashboard
  - Traffic report

- Admin users retain full access.

### Fixed

- Fixed logout for non-admin roles.
- Fixed `/logout` returning `/login?next=/logout`; it now returns `/login` and clears the session cookie.
- Fixed role detection by reading from the database instead of relying only on session state.
- Fixed hidden AI status UI calling `dxCheckAIStatus` when the status card is not available.
- Consolidated site management and camera assignment into one workflow.

### Security Notes

- Runtime data, databases, captures, logs, secrets, and camera URLs must not be committed to Git.
- Default admin credentials are for local development only and must be changed through environment variables before real use.
