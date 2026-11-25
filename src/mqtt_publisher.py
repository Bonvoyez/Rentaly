#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[MQTT Telemetry Publisher] Edge Real-Time Telemetry Publishing Module
=============================================================================
- Broker: rentaly.duckdns.org (Port: 1883 default / WebSocket supported)
- Topic: inspection/{device_id}/telemetry
- Supported fields:
    inspection_id, device_id, stage, progress_percent, blur_score,
    stabilization_ms, message, capture_image_url
=============================================================================
"""

import os
import json
import time

try:
    import paho.mqtt.client as mqtt
    HAS_PAHO = True
except ImportError:
    HAS_PAHO = False

MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
DEVICE_ID = os.getenv("DEVICE_ID", "station-01")


class MqttTelemetryClient:
    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, device_id=DEVICE_ID):
        self.host = host
        self.port = port
        self.device_id = device_id
        self.topic = f"inspection/{self.device_id}/telemetry"
        self.client = None
        self.connected = False

        if HAS_PAHO:
            try:
                client_id = f"edge-{self.device_id}-{int(time.time())}"
                # Apply WSS (WebSocket over SSL) when port is 443
                if self.port == 443:
                    try:
                        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id, transport="websockets")
                    except Exception:
                        self.client = mqtt.Client(client_id, transport="websockets")
                    self.client.tls_set()
                    self.client.ws_set_options(path="/mqtt")
                else:
                    try:
                        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
                    except Exception:
                        self.client = mqtt.Client(client_id)

                self.client.on_connect = self._on_connect
                self.client.on_disconnect = self._on_disconnect
                self.client.connect_async(self.host, self.port, keepalive=60)
                self.client.loop_start()
            except Exception as e:
                print(f"[MQTT] Connection initialization warning: {e}")
        else:
            print("[MQTT] 'paho-mqtt' package not found; running in console output mode.")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            print(f"📡 [MQTT] Connected to broker! ({self.host}:{self.port} -> {self.topic})")
        else:
            print(f"⚠️ [MQTT] Broker connection failed (code: {rc})")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.connected = False
        print("⚠️ [MQTT] Disconnected from broker")

    def publish_telemetry(self, inspection_id, stage, progress_percent, message, blur_score=180.0, stabilization_ms=300, capture_image_url=None, primary_verdict=None, reposition_count=1):
        """Publish real-time telemetry payload to the frontend kiosk."""
        payload = {
            "inspection_id": str(inspection_id),
            "device_id": self.device_id,
            "stage": stage,
            "progress_percent": int(progress_percent),
            "blur_score": float(round(blur_score, 1)),
            "stabilization_ms": int(stabilization_ms),
            "message": str(message)
        }
        if capture_image_url:
            payload["capture_image_url"] = str(capture_image_url)
        if stage == "COMPLETED":
            payload["primary_verdict"] = primary_verdict if primary_verdict in ["PASS", "FAIL"] else ("PASS" if "PASS" in message else "FAIL")
        elif stage == "REPOSITION":
            payload["reposition_count"] = int(reposition_count)

        json_str = json.dumps(payload, ensure_ascii=False)
        has_img = " (with image)" if capture_image_url else ""
        print(f"📡 [MQTT -> {self.topic}] [{stage:12s}] {progress_percent:3d}% - {message}{has_img}")

        if self.client and self.connected:
            try:
                self.client.publish(self.topic, json_str, qos=0)
            except Exception as e:
                print(f"⚠️ [MQTT] Publish failed: {e}")

    def close(self):
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass


# Singleton instance
default_publisher = None


def get_telemetry_publisher():
    global default_publisher
    if default_publisher is None:
        default_publisher = MqttTelemetryClient()
    return default_publisher
