# Features

## 1. License Plate Recognition

The platform supports AI-based license plate recognition from:

- Uploaded images
- Mobile-captured images
- RTSP camera streams
- Saved camera snapshots

Recognition results include:

- Plate text
- Normalized plate value
- Confidence score
- Plate crop image
- Full vehicle frame
- Optional plate background color

---

## 2. Plate Color Visualization

The system can store and render plate background color in the UI.

Supported values:

- white
- yellow
- green
- red
- blue
- black
- unknown

This helps operators quickly distinguish plate types visually in dashboards and reports.

---

## 3. Traffic Sources

Each traffic record includes a source:

| Source | Description |
|---|---|
| camera | Automatically detected from an RTSP camera |
| mobile | Registered from the mobile security entry page |
| manual | Entered manually by an operator |

---

## 4. Live Dashboard

The live dashboard provides:

- Today traffic total
- Entry count
- Exit count
- Manual traffic count
- Registered vehicle count
- Whitelist, blacklist, and unknown counts
- Latest traffic records
- Alerts for important records

---

## 5. Mobile Security Entry

The mobile entry page is designed for security guards and gate operators.

Use cases:

- A camera is offline
- A plate was not detected by the fixed camera
- A vehicle is stopped at a gate
- An operator needs to take a quick photo and register traffic

Features:

- Mobile-friendly UI
- Image upload or camera capture
- Plate OCR
- Plate correction before submit
- Entry/exit selection
- Operator name
- Optional note
- Image quality warning
- Plate color selection and correction

---

## 6. Manual Entry

Manual entry is useful when:

- No camera is available
- OCR result is unreliable
- The operator needs to officially register a controlled event

Fields:

- Plate
- Entry or exit
- Operator
- Note

---

## 7. Vehicle Management

Vehicle records can include:

- Plate
- Driver name
- Driver phone
- Employee code
- Department
- Company
- Vehicle model
- Vehicle color
- Access list/status
- Access label

---

## 8. Traffic Reports

Traffic report features:

- Latest traffic records
- Plate preview
- Vehicle image thumbnail
- Entry/exit type
- Source
- Driver details
- Operator details
- Notes
- Edit traffic record
- Add vehicle from traffic record

---

## 9. Camera Management

Camera features:

- Add RTSP cameras
- Enable or disable cameras
- Entry/exit role assignment
- Snapshot preview
- Background worker for detection
- Reconnect support
- Configurable detection interval

---

## 10. User and Settings Management

The platform supports administrative controls for:

- Users
- Roles
- System settings
- Image retention
- Camera reconnect settings
- Detection interval
- Cleanup options
- Alert levels
