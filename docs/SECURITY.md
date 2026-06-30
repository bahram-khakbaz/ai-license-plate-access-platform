# Security Guide

## Sensitive Data Policy

Never commit the following:

- Passwords
- Tokens
- Directory service credentials
- Camera usernames and passwords
- Internal IP addresses
- Production server names
- Real employee or driver data
- Real operational traffic logs
- SQLite production database
- Captured vehicle images from production

---

## Environment Variables

Use `.env` for environment-specific configuration.

Commit only `.env.example`.

---

## Authentication

Recommended:

- Use strong passwords
- Apply role-based access
- Disable unused accounts
- Restrict admin access
- Rotate credentials regularly

---

## Network Security

Recommended:

- Keep the service behind a firewall
- Restrict access to trusted internal networks
- Use HTTPS
- Avoid exposing camera streams publicly
- Use separate camera credentials for the application

---

## Image and Log Retention

Saved images may contain sensitive information.

Recommended:

- Define a retention policy
- Clean old images regularly
- Limit who can view traffic reports
- Avoid exporting real images unless necessary

---

## Operational Audit

Recommended future improvements:

- Store edit history for traffic records
- Track who changed plate values
- Require a reason for critical edits
- Track vehicle status changes
- Keep admin action logs

---

## Reporting Security Issues

If this is used as an open-source project, add a responsible disclosure process here.

For private deployments, security issues should be reported to the internal platform owner or security team.
