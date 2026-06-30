# Roadmap

## Completed

- AI license plate recognition
- Manual image scan
- Mobile security entry
- Manual traffic entry
- RTSP camera support
- Live dashboard
- Traffic reports
- Vehicle and driver management
- Plate image thumbnails
- Traffic record editing
- Add vehicle from traffic record
- Plate color rendering
- Image quality warning for mobile capture
- Role-based access control
- Dockerized deployment

---

## Next Priorities

### 1. Active Vehicle Sessions

Show vehicles currently inside or waiting near the gate.

Possible fields:

- Plate
- First seen
- Last seen
- Dwell time
- Source
- Gate/camera
- Review status

---

### 2. Review Workflow for Unknown Vehicles

Add review statuses:

- Waiting for review
- Under coordination
- Approved for entry
- Entry denied
- Referred to supervisor
- OCR correction needed

---

### 3. Audit Log

Track traffic record edits:

- Old plate
- New plate
- Old role
- New role
- Edited by
- Edited at
- Reason

---

### 4. Gate and Location Selection

Add gate/location selector for mobile and manual entries.

Example values:

- Main gate
- Staff entrance
- Truck entrance
- Visitor entrance

---

### 5. PWA Support

Make the mobile entry page installable as a PWA:

- Home screen icon
- Full-screen mode
- Offline-friendly UI shell
- Fast camera access

---

### 6. Camera Health Monitoring

Track:

- Camera online/offline
- Last frame time
- Last detection time
- Reconnect count
- Error logs

---

### 7. Daily Security Report

Generate summary reports:

- Total traffic
- Entry count
- Exit count
- Unknown vehicles
- Denied entries
- Mobile registrations
- Manual registrations
- Long dwell sessions

---

### 8. Better Plate Color Detection

Improve plate color classification using:

- Better crop preprocessing
- ROI-based background sampling
- Confidence score
- Operator correction feedback
