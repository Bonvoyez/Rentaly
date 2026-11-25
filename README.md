# 🔬 Shared Equipment AI Return Inspection Station (Edge AI & IoT)

An on-device vision inspection system based on Raspberry Pi 4 that automatically checks **hardware power status (PWR LED), unique serial number (OCR), and physical defects (YOLOv8)** when shared equipment (Raspberry Pi boards) is returned.

---

## 📂 Directory Structure

```
rentaly/
├── docs/
│   └── API_CONTRACT.md    # 📡 Detailed API and MQTT specification for frontend/backend integration
├── mock/
│   └── mock_edge.py       # 🚀 Mock inspection station for local integration testing without a Raspberry Pi
├── src/                   # 🛠️ Embedded & AI pipeline running on the actual Raspberry Pi
│   └── test.py
├── sample_data/           # 🖼️ Sample images and data for testing
└── README.md
```

---

## 👥 Developer Guide for Frontend & Backend Teams

Even without a physical Raspberry Pi, camera, or AI model, you can use **`mock/mock_edge.py`** to build and test the web UI and server locally on your machine!

### 1. Create a Virtual Environment & Install Packages

To keep your Python environment clean, we recommend activating a virtual environment (`venv`) before installing dependencies:

#### 🍎 Mac / Linux:
```bash
# 1. Create virtual environment (first time only)
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

#### 🪟 Windows:
```bash
# 1. Create virtual environment (first time only)
python -m venv venv

# 2. Activate virtual environment
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### 2. Check Interface Specifications
- The frontend/backend communication data formats are detailed in [docs/API_CONTRACT.md](docs/API_CONTRACT.md).
  - **Real-time UI Guidance (MQTT)**: Subscribe to `inspection/{device_id}/telemetry`
  - **Save Inspection Result (REST API)**: `POST /api/v1/inspections` (multipart/form-data)

### 3. Running the Mock Inspection Station Simulator (Local Testing)

Run the commands below in your terminal to simulate a real inspection—publishing progress updates every second and sending mock results and images to the backend:

```bash
# Default run (interactive scenario selection)
python mock/mock_edge.py

# Run pass scenario immediately
python mock/mock_edge.py --scenario pass

# Run defect detection (bent pin) scenario immediately
python mock/mock_edge.py --scenario fail

# Run power fault (PWR LED off) scenario immediately
python mock/mock_edge.py --scenario fail_led

# Run blurry image / reposition guidance scenario immediately
python mock/mock_edge.py --scenario reposition
```

#### Options:
- `--backend http://localhost:8000`: Specify your backend FastAPI server URL
- `--mqtt-host localhost`: Specify your MQTT broker host

---

## 🛠️ Embedded & AI Implementation Plan

1. **PiCamera Capture & Motion Blur Measurement (`Picamera2`, Laplacian Variance)**
2. **Onboard PWR LED Solid ON Detection**
3. **Board Serial Number Optical Character Recognition (OCR)**
4. **YOLOv8n-based Physical Defect Detection (bent GPIO pins, damaged ports, etc.)**
5. **Real-time MQTT Publishing & Backend REST API Integration**
