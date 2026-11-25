#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[MQTT Telemetry Publisher] 엣지 실시간 텔레메트리 발행 모듈
=============================================================================
- 브로커: rentaly.duckdns.org (포트: 1883 기본 / WebSocket 겸용)
- 토픽: inspection/{device_id}/telemetry
- 지원 규격:
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

MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "rentaly.duckdns.org")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "443"))
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
                # 포트 443일 경우 WSS(WebSocket over SSL) 적용
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
                print(f"[MQTT] 연결 초기화 경고: {e}")
        else:
            print("[MQTT] 'paho-mqtt' 패키지가 없어 콘솔 출력 모드로 동작합니다.")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            print(f"📡 [MQTT] 브로커 연결 성공! ({self.host}:{self.port} -> {self.topic})")
        else:
            print(f"⚠️ [MQTT] 브로커 연결 실패 (코드: {rc})")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.connected = False
        print("⚠️ [MQTT] 브로커 연결 해제됨")

    def publish_telemetry(self, inspection_id, stage, progress_percent, message, blur_score=180.0, stabilization_ms=300, capture_image_url=None, primary_verdict=None, reposition_count=1):
        """프론트엔드 키오스크로 실시간 텔레메트리 페이로드를 발행합니다."""
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
        has_img = " (사진 포함)" if capture_image_url else ""
        print(f"📡 [MQTT -> {self.topic}] [{stage:12s}] {progress_percent:3d}% - {message}{has_img}")

        if self.client and self.connected:
            try:
                self.client.publish(self.topic, json_str, qos=0)
            except Exception as e:
                print(f"⚠️ [MQTT] 발행 실패: {e}")

    def close(self):
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass


# 싱글톤 인스턴스
default_publisher = None


def get_telemetry_publisher():
    global default_publisher
    if default_publisher is None:
        default_publisher = MqttTelemetryClient()
    return default_publisher
