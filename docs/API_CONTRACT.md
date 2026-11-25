# 📡 Shared Equipment AI Return Inspection Station - Communication Interface Specification (API Contract)

> **Author**: AI & Embedded (Edge Controller)  
> **Target Audience**: Backend and Frontend Developers  
> **Purpose**: Defines data formats and communication protocols so frontend and backend teams can develop and integrate smoothly without physical Raspberry Pi hardware.

---

## 1. Communication Architecture Summary

The inspection station uses a **dual communication architecture**:
1. **Real-time Telemetry (MQTT over WebSocket)**:
   - Edge Station → Frontend (via Mosquitto broker)
   - Quickly transmits inspection progress, camera blur score, and real-time stage guidance at ~1-second intervals.
2. **Final Inspection Result Storage (HTTPS REST API)**:
   - Edge Station → Backend FastAPI
   - After inspection completes, sends the final verdict, defect list, and captured high-resolution image to be persisted in the DB.

---

## 2. Real-time Telemetry Specification (MQTT)

### Start Inspection Command (Frontend → Inspection Station)

When the "Start Inspection" button is pressed, the frontend publishes the following command to the connected MQTT broker. `{device_id}` uses the kiosk's `VITE_DEVICE_ID`.

```text
Topic: inspection/{device_id}/command
Payload: {"action":"START"}
```

After publishing, inspection progress is received on the telemetry topic below.

### 📌 Topic
```text
inspection/{device_id}/telemetry
```
- Example: `inspection/station-01/telemetry`

### 📦 Publishing Interval & Timing
- Published at approximately **0.5s – 1s intervals** for each inspection stage, from equipment mount detection until inspection completion.

### 📝 Payload (JSON Format)
```json
{
  "inspection_id": "c9a1b8e4-7d2f-4a3e-b819-123456789abc",
  "device_id": "station-01",
  "stage": "AI_INFERENCE",
  "progress_percent": 75,
  "blur_score": 182.4,
  "stabilization_ms": 320,
  "message": "Analyzing physical defects with AI...",
  "capture_image_url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
}
```

### 📋 Field Details
| Field | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `inspection_id` | string (UUID) | Unique identifier for the inspection session | `"c9a1b8e4-..."` |
| `device_id` | string | Unique ID of the inspection station | `"station-01"` |
| `stage` | string (Enum) | Current inspection stage | See `stage list` below |
| `progress_percent`| int | Overall inspection progress (0 ~ 100) | `0` ~ `100` |
| `blur_score` | float | Camera image sharpness score (Laplacian variance) | `150.2` (higher is sharper) |
| `stabilization_ms`| int | Time taken for motion shake stabilization (ms) | `320` |
| `message` | string | User-facing guidance message to display on UI | `"Equipment is mounted."` |
| `capture_image_url` | string (Optional) | JPEG Base64 Data URL to display on the kiosk right after capture. Even if omitted in subsequent stages, the kiosk retains the image during the inspection. | `"data:image/jpeg;base64,..."` |

#### `stage` (Inspection Stage) Values:
1. `MOUNTED`: Board detected as properly seated on the cradle switch
2. `STABILIZING`: Camera exposure/focus and motion stabilization in progress
3. `BLUR_CHECK`: Evaluating image quality and blur
4. `OCR`: Performing OCR on the board's surface serial number
5. `LED_CHECK`: Checking onboard PWR LED illumination on the target board
6. `AI_INFERENCE`: Running YOLOv8-based physical defect inference (bent pins, damaged ports, etc.)
7. `COMPLETED`: Inspection complete (final result submission stage)
8. `REPOSITION`: Guidance state requesting repositioning due to blur or misalignment

---

## 3. Final Inspection Result Submission Specification (REST API)

Once the inspection is complete, the edge station sends the captured photo and detailed metadata to the backend server.

### 📌 Endpoint
```http
POST /api/v1/inspections
Content-Type: multipart/form-data
```

### 🔑 Headers
| Header | Required | Description |
| :--- | :--- | :--- |
| `X-Device-Secret` | Required | Secret key for inspection station authentication (e.g., `edge-secret-key-1234`) |
| `X-Inspection-ID` | Optional | Unique inspection session UUID (for trace logging) |

### 📦 Request Body (Form Data)
1. **`metadata`** (Text / JSON String, Required): Detailed inspection result metadata
2. **`image`** (File / Binary, Required): Original board photo captured during inspection (`.jpg`)

---

### 📝 `metadata` JSON Detailed Specification

```json
{
  "inspection_id": "c9a1b8e4-7d2f-4a3e-b819-123456789abc",
  "equipment_id": "RPI4-001",
  "recognized_serial_number": "10000000a1b2c3d4",
  "primary_verdict": "PASS",
  "reposition_count": 0,
  "pwr_led_status": true,
  "detected_defects": [],
  "metrics": {
    "blur_score": 182.4,
    "stabilization_ms": 320,
    "serial_recognition_ms": 410,
    "visual_inspection_ms": 350,
    "inference_ms": 185,
    "total_duration_ms": 2265
  }
}
```

#### 📋 `metadata` Field Details:
- `inspection_id` (string): Inspection UUID
- `equipment_id` (string): Target equipment model ID (default: `"RPI4-001"`)
- `recognized_serial_number` (string | null): Board serial number recognized via OCR (`null` if recognition fails)
- `primary_verdict` (string, Enum): Primary inspection verdict
  - **`PASS`**: Passed all physical and LED illumination checks (normal return processed)
  - **`REPOSITION`**: Repositioning needed due to blur/hand obstruction (manual return if > 3 attempts)
  - **`FAIL`**: Physical defect detected or LED off (transitions to `PENDING_REVIEW` admin review queue)
  - **`ERROR`**: System fault such as camera error or sensor failure (`SYSTEM_FAULT`)
- `reposition_count` (int): Number of reposition requests that occurred (0 ~ 3)
- `pwr_led_status` (boolean): Whether the target Raspberry Pi's red PWR LED is lit (`true`: normally lit, `false`: unlit/power fault)
- `detected_defects` (Array): List of detected defects (empty array `[]` if none)
  ```json
  [
    {
      "class": "bent_pin",
      "confidence": 0.89,
      "bbox": [120, 45, 160, 85]
    }
  ]
  ```
  - `class`: `"bent_pin"`, `"damaged_port"`, `"missing_sd"`, etc.
  - `confidence`: 0.0 ~ 1.0 (detection confidence)
  - `bbox`: `[x_min, y_min, x_max, y_max]` (defect bounding box coordinates on the image)
- `metrics` (Object): Performance and latency measurement data (in ms)

---

### 📥 Backend Response Specification

#### On Success (`201 Created` or `200 OK`)
```json
{
  "status": "SUCCESS",
  "inspection_id": "c9a1b8e4-7d2f-4a3e-b819-123456789abc",
  "final_status": "PASSED",
  "created_at": "2026-11-16T17:30:00Z"
}
```
*(If a defect is found, `final_status` is saved as `"PENDING_REVIEW"` awaiting administrator review.)*

#### On Validation Failure (`422 Unprocessable Entity` or `400 Bad Request`)
```json
{
  "status": "ERROR",
  "error_code": "INVALID_METADATA",
  "message": "Missing required field: pwr_led_status."
}
```

---

## 4. Backend & Frontend Integration Tips

1. **Frontend Developers**:
   - Subscribe to the `inspection/{device_id}/telemetry` MQTT topic to reactively render the progress bar (`progress_percent`), current stage (`stage`), and user guidance message (`message`).
   - When `stage == "REPOSITION"`, display a modal prompting the user to reposition the board.
2. **Backend Developers**:
   - In FastAPI, receive `metadata` via `Form(...)`, parse it with a Pydantic model, and save the uploaded `UploadFile` image to a persistent directory (`/app/storage/images/{inspection_id}.jpg`).
   - Split and store the data across the DB tables (`INSPECTION`, `AI_RESULT`, `IMAGE`) to match the specification structure.
3. **Using the Mock Inspector**:
   - `mock/mock_edge.py` is provided for development without hardware. See [README.md](../README.md) for usage instructions.
