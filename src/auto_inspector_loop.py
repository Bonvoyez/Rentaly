#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Auto Inspector Loop] Frontend-Integrated Fully Unmanned Lifecycle Manager
=============================================================================
Operation Scenario:
1. Idle state: YOLO off (CPU 0%), preview streaming only
2. On receiving "Start Inspection" signal from frontend (MQTT topic: inspection/station-01/command, payload: START)
   or clicking Start Inspection on the kiosk dashboard:
   -> Start YOLO (begin 1st-stage stabilization detection)
   -> Publish real-time telemetry when hand is detected / LED is off
3. Immediately upon detecting all 3 conditions (hand removed + board uncropped + red LED on):
   -> "Snap!" high-resolution capture
   -> Stop YOLO immediately (save CPU)
   -> Start VLM precision inspection with captured image (capture_image_url)
4. After inspection completes (COMPLETED) and results are reported:
   -> Automatically return to step 1 (IDLE state)!
=============================================================================
"""

import os
import time
import threading
import json
import uuid
import cv2

from camera_streamer import get_camera_streamer
from yolo_stabilizer import YoloStabilizer
from vlm_inspector import inspect_with_vlm, calculate_blur_score
from mqtt_publisher import get_telemetry_publisher, DEVICE_ID, MQTT_HOST, MQTT_PORT, HAS_PAHO

if HAS_PAHO:
    import paho.mqtt.client as mqtt

STATE_IDLE = "IDLE"
STATE_STABILIZING = "STABILIZING"
STATE_INSPECTING = "INSPECTING"
STATE_DONE = "DONE"

class AutoInspectionManager:
    def __init__(self):
        self.state = STATE_IDLE
        self.stabilizer = YoloStabilizer()
        self.streamer = get_camera_streamer()
        self.publisher = get_telemetry_publisher()
        self.lock = threading.Lock()
        self.current_insp_id = None
        self.sub_client = None

        if HAS_PAHO:
            self._init_mqtt_subscriber()

    def _init_mqtt_subscriber(self):
        """Subscribe to frontend control commands (START, RESET)"""
        try:
            client_id = f"edge-sub-{DEVICE_ID}-{int(time.time())}"
            if MQTT_PORT == 443:
                try:
                    self.sub_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id, transport="websockets")
                except Exception:
                    self.sub_client = mqtt.Client(client_id, transport="websockets")
                self.sub_client.tls_set()
                self.sub_client.ws_set_options(path="/mqtt")
            else:
                try:
                    self.sub_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
                except Exception:
                    self.sub_client = mqtt.Client(client_id)

            def on_connect(c, userdata, flags, rc, properties=None):
                cmd_topic = f"inspection/{DEVICE_ID}/command"
                self.sub_client.subscribe(cmd_topic)
                print(f"👂 [MQTT Subscriber] Subscribed to command topic: {cmd_topic}")

            def on_message(c, userdata, msg):
                try:
                    payload = json.loads(msg.payload.decode("utf-8"))
                    cmd = payload.get("action", "").upper()
                    print(f"📩 [MQTT Command Received]: {cmd}")
                    if cmd in ["START", "START_INSPECTION"]:
                        self.trigger_start()
                    elif cmd in ["RESET", "CANCEL"]:
                        self.reset_to_idle()
                except Exception as e:
                    print(f"⚠️ Command parsing error: {e}")

            self.sub_client.on_connect = on_connect
            self.sub_client.on_message = on_message
            self.sub_client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.sub_client.loop_start()
        except Exception as e:
            print(f"⚠️ MQTT Subscriber connection failed: {e}")

    def trigger_start(self):
        """Start inspection: start YOLO and stabilization detection loop"""
        with self.lock:
            if self.state != STATE_IDLE:
                return False, f"Cannot start in current state ({self.state})."
            self.state = STATE_STABILIZING
            self.current_insp_id = str(uuid.uuid4())
            self.stabilizer.reset()

        print(f"\n🚀 [Inspection Lifecycle Started] ID: {self.current_insp_id}")
        threading.Thread(target=self._run_stabilization_and_inspect, daemon=True).start()
        return True, "YOLO stabilization detection started"

    def _run_stabilization_and_inspect(self):
        insp_id = self.current_insp_id
        start_wait_time = time.time()
        last_pub_time = 0

        # [Stage 1: YOLO real-time stabilization detection (hand removed + board intact + LED on)]
        print("👁️ [YOLO Running] Detecting real-time stabilization...")
        captured_frame = None

        while self.state == STATE_STABILIZING:
            frame = self.streamer.get_latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            ready_to_snap, message, counts = self.stabilizer.analyze_frame(frame)

            # Real-time guide telemetry to kiosk (0.5s interval)
            now = time.time()
            if now - last_pub_time >= 0.5:
                self.publisher.publish_telemetry(
                    inspection_id=insp_id,
                    stage="OCR",
                    progress_percent=10,
                    message=message
                )
                last_pub_time = now

            if ready_to_snap:
                print(f"📸 [Stabilization Succeeded!] Snap! Auto-capture (elapsed: {now - start_wait_time:.1f}s)")
                captured_frame = frame.copy()
                break

            # 30s timeout
            if now - start_wait_time > 30:
                print("⏱️ Timeout: stabilization failed")
                self.reset_to_idle()
                return

            time.sleep(0.03)

        if captured_frame is None:
            print("🛑 Stabilization loop ended without capture.")
            return

        # [Stage 2: Stop YOLO and enter VLM precision inspection]
        with self.lock:
            self.state = STATE_INSPECTING

        print("⚡ [YOLO Stopped] Starting VLM precision analysis pipeline...")
        from web_inspector import process_and_inspect
        result = process_and_inspect(captured_frame)

        # [Stage 3: Wait 3s after inspection completes, then return to IDLE]
        with self.lock:
            self.state = STATE_DONE
        print("🎉 [Inspection Complete] Result reported. Returning to IDLE state in 3s.")
        time.sleep(3.0)
        self.reset_to_idle()

    def reset_to_idle(self):
        with self.lock:
            self.state = STATE_IDLE
            self.current_insp_id = None
            self.stabilizer.reset()
        print("💤 [Reset Complete] Returned to IDLE standby state (YOLO off, CPU 0%).")

# Singleton
_manager = None
def get_auto_inspector():
    global _manager
    if _manager is None:
        _manager = AutoInspectionManager()
    return _manager
