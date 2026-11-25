#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Mock Edge Controller] Mock Edge Inspection Station Simulator
=============================================================================
This script allows backend and frontend team members to develop and test
integrations locally without a physical Raspberry Pi, camera, or AI model.

[How it works]
1. Simulates inspection start (mount detection)
2. Publishes real-time MQTT telemetry across each stage at 0.8s intervals
3. Sends a dummy board image and JSON metadata to the backend REST API on completion

[Usage]
  python mock/mock_edge.py
  (or with options: python mock/mock_edge.py --scenario fail --backend http://localhost:8000)
=============================================================================
"""

import sys
import os
import time
import json
import uuid
import argparse
import base64
import io

# ---------------------------------------------------------------------------
# External libraries (with fallback notices if missing)
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    print("[Warning] 'requests' library is required. (Install: pip install requests)")
    requests = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[Info] 'paho-mqtt' is not installed; MQTT publishing will be skipped. (Install: pip install paho-mqtt)")
    mqtt = None


def generate_dummy_image(text="SAMPLE INSPECTION IMAGE"):
    """
    Generate a simple dummy JPEG image in memory to upload to the backend.
    (Uses PIL to draw text if available; otherwise returns minimal 1x1 dummy bytes)
    """
    try:
        from PIL import Image, ImageDraw
        # Create 640x480 test image (dark green PCB style)
        img = Image.new("RGB", (640, 480), color=(20, 60, 35))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 590, 430], outline=(100, 200, 100), width=3)
        draw.text((80, 80), f"Raspberry Pi 4 Dummy Board\n{text}", fill=(255, 255, 255))
        draw.text((80, 200), f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}", fill=(200, 200, 200))
        
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except Exception:
        # Minimal valid 1x1 JPEG bytes for environments without PIL
        return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"


class MockEdgeStation:
    def __init__(self, device_id="station-01", backend_url="http://localhost:8000", mqtt_host="localhost", mqtt_port=1883):
        self.device_id = device_id
        self.backend_url = backend_url.rstrip("/")
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_client = None
        self._setup_mqtt()

    def _setup_mqtt(self):
        """Prepare MQTT broker connection."""
        if mqtt is None:
            return
        try:
            self.mqtt_client = mqtt.Client(client_id=f"mock-{self.device_id}-{int(time.time())}")
            self.mqtt_client.connect_async(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            print(f"[MQTT] Connecting to broker: {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            print(f"[MQTT] Broker connection failed (skipping MQTT publish): {e}")
            self.mqtt_client = None

    def publish_telemetry(self, inspection_id, stage, progress, message, blur_score=185.0,
                          primary_verdict=None, reposition_count=None, capture_image_url=None):
        """Publish MQTT topic so the frontend can monitor in real time."""
        payload = {
            "inspection_id": inspection_id,
            "device_id": self.device_id,
            "stage": stage,
            "progress_percent": progress,
            "blur_score": blur_score,
            "stabilization_ms": 280,
            "message": message
        }
        if primary_verdict is not None:
            payload["primary_verdict"] = primary_verdict
        if reposition_count is not None:
            payload["reposition_count"] = reposition_count
        if capture_image_url is not None:
            payload["capture_image_url"] = capture_image_url
        topic = f"inspection/{self.device_id}/telemetry"
        print(f"  📡 [MQTT Telemetry] [{progress:3d}%] [{stage}] {message}")
        
        if self.mqtt_client:
            try:
                self.mqtt_client.publish(topic, json.dumps(payload, ensure_ascii=False))
            except Exception as e:
                print(f"  [MQTT publish error]: {e}")

    def run_simulation(self, scenario="pass"):
        """
        Simulate the full inspection pipeline based on the scenario.
        Scenarios:
          - 'pass': All exterior & LED checks pass (normal return)
          - 'fail': Exterior defect (bent pin) or LED off detected (admin review queue)
          - 'reposition': Reposition prompt due to image blur
          - 'error': Station hardware error notice
          - 'manual_return': Manual return notice after exceeding 3 reposition attempts
        """
        inspection_id = str(uuid.uuid4())
        print("\n" + "=" * 60)
        print(f"🚀 [Inspection Session Started] ID: {inspection_id} (Scenario: {scenario.upper()})")
        print("=" * 60)

        # Stage 1: Device mount detection
        self.publish_telemetry(inspection_id, "MOUNTED", 10, "Device mounted. Starting inspection.")
        time.sleep(0.8)

        if scenario == "error":
            self.publish_telemetry(inspection_id, "ERROR", 10, "Camera connection error occurred. Please return directly to an administrator.")
            return

        if scenario == "manual_return":
            self.publish_telemetry(inspection_id, "REPOSITION", 40, "Please reposition the board.", reposition_count=3)
            time.sleep(0.8)
            self.publish_telemetry(inspection_id, "MANUAL_RETURN", 40, "Maximum reposition attempts exceeded. Please return directly to an administrator.")
            return

        # Stage 2: Camera stabilization
        self.publish_telemetry(inspection_id, "STABILIZING", 25, "Stabilizing camera focus and motion...")
        time.sleep(0.8)

        # Stage 3: Blur score & image sharpness evaluation
        if scenario == "reposition":
            self.publish_telemetry(inspection_id, "BLUR_CHECK", 40, "Hand shake or unstable positioning detected.", blur_score=45.2)
            time.sleep(0.8)
            self.publish_telemetry(inspection_id, "REPOSITION", 40, "Board moved. Please place the board flat and still.", reposition_count=1)
            print("\n⚠️ [Reposition Notice] Pausing session so user can reposition the board.")
            return

        self.publish_telemetry(inspection_id, "BLUR_CHECK", 40, "Image quality is sharp (blur score good).", blur_score=210.5)
        time.sleep(0.8)

        # Stage 4: Serial number OCR
        capture_image_url = "data:image/jpeg;base64," + base64.b64encode(
            generate_dummy_image(f"ID: {inspection_id}\nOCR TEST IMAGE")
        ).decode("ascii")
        self.publish_telemetry(
            inspection_id,
            "OCR",
            60,
            "Recognizing unique serial number on the board surface...",
            capture_image_url=capture_image_url,
        )
        time.sleep(0.8)

        # Stage 5: Onboard PWR LED check
        pwr_led_ok = True if scenario != "fail_led" else False
        led_msg = "PWR LED verified lit." if pwr_led_ok else "Warning: PWR LED is off (power failure)!"
        self.publish_telemetry(inspection_id, "LED_CHECK", 75, led_msg)
        time.sleep(0.8)

        # Stage 6: AI exterior defect detection (YOLOv8 inference)
        self.publish_telemetry(inspection_id, "AI_INFERENCE", 90, "AI model is analyzing GPIO pins and ports for damage...")
        time.sleep(1.0)

        # Generate verdict
        if scenario == "pass":
            verdict = "PASS"
            defects = []
        elif scenario == "fail_led":
            verdict = "FAIL"
            defects = []
        else: # scenario == "fail" (exterior defect)
            verdict = "FAIL"
            defects = [
                {
                    "class": "bent_pin",
                    "confidence": 0.89,
                    "bbox": [150, 60, 210, 110]
                }
            ]

        # Stage 7: Inspection complete notification
        self.publish_telemetry(inspection_id, "COMPLETED", 100, f"Inspection complete. Final result: {verdict}", primary_verdict=verdict)

        # Stage 8: Send final result to backend (REST API)
        self._send_to_backend(inspection_id, verdict, pwr_led_ok, defects)

    def _send_to_backend(self, inspection_id, verdict, pwr_led_status, defects):
        """Send to backend FastAPI POST /api/v1/inspections endpoint."""
        url = f"{self.backend_url}/api/v1/inspections"
        print(f"\n📤 [Sending to Backend] {url}")

        metadata = {
            "inspection_id": inspection_id,
            "equipment_id": "RPI4-001",
            "recognized_serial_number": "10000000b3d8e5f2",
            "primary_verdict": verdict,
            "reposition_count": 0,
            "pwr_led_status": pwr_led_status,
            "detected_defects": defects,
            "metrics": {
                "blur_score": 210.5,
                "stabilization_ms": 280,
                "serial_recognition_ms": 420,
                "visual_inspection_ms": 310,
                "inference_ms": 195,
                "total_duration_ms": 2250
            }
        }

        # Generate dummy image
        image_bytes = generate_dummy_image(f"ID: {inspection_id}\nVerdict: {verdict}\nDefects: {len(defects)}")

        if requests is None:
            print("[Notice] 'requests' library not found; skipping HTTP upload. (Printing metadata to console)")
            print(json.dumps(metadata, indent=2, ensure_ascii=False))
            return

        headers = {
            "X-Device-Secret": "edge-secret-key-1234",
            "X-Inspection-ID": inspection_id
        }

        files = {
            "image": ("capture.jpg", image_bytes, "image/jpeg")
        }
        data = {
            "metadata": json.dumps(metadata, ensure_ascii=False)
        }

        try:
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=5)
            print(f"  📥 Backend response code: {resp.status_code}")
            print(f"  📥 Backend response body: {resp.text}")
            if resp.status_code in (200, 201):
                print("  ✅ [Success] Inspection result registered on backend!")
            else:
                print("  ⚠️ [Check Required] Backend returned an error code. Check backend logs.")
        except requests.exceptions.ConnectionError:
            print(f"  ❌ [Connection Failed] Backend server ({url}) is not running.")
            print("     -> Ask the backend developer to start the FastAPI server and try again.")
        except Exception as e:
            print(f"  ❌ [Error]: {e}")


def main():
    parser = argparse.ArgumentParser(description="Mock Edge Inspection Station Simulator (Mock Edge)")
    parser.add_argument("--scenario", choices=["pass", "fail", "fail_led", "reposition", "error", "manual_return"], default=None,
                        help="Inspection scenario to run (pass, fail, fail_led, reposition, error, manual_return)")
    parser.add_argument("--backend", default="http://localhost:8000",
                        help="Backend FastAPI server URL (default: http://localhost:8000)")
    parser.add_argument("--mqtt-host", default="localhost",
                        help="MQTT broker host (default: localhost)")
    parser.add_argument("--mqtt-port", type=int, default=1883,
                        help="MQTT broker port (default: 1883)")
    args = parser.parse_args()

    station = MockEdgeStation(
        device_id="station-01",
        backend_url=args.backend,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port
    )

    scenario = args.scenario
    if scenario is None:
        print("\n" + "=" * 50)
        print(" [Mock Edge] Select a scenario to test:")
        print("  1. Normal return pass (PASS)")
        print("  2. Exterior defect detected (FAIL - bent pin)")
        print("  3. Power failure detected (FAIL - PWR LED off)")
        print("  4. Image blur / reposition notice (REPOSITION)")
        print("  5. Station error (ERROR)")
        print("  6. Reposition limit exceeded (MANUAL_RETURN)")
        print("=" * 50)
        try:
            choice = input(" Enter number (1-6) [default: 1]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)

        choice_map = {"1": "pass", "2": "fail", "3": "fail_led", "4": "reposition", "5": "error", "6": "manual_return", "": "pass"}
        scenario = choice_map.get(choice, "pass")

    station.run_simulation(scenario=scenario)


if __name__ == "__main__":
    main()
