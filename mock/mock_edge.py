#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Mock Edge Controller] 가짜 엣지 검사대 시뮬레이터
=============================================================================
이 스크립트는 실제 라즈베리파이나 카메라, AI 모델 없이도
백엔드와 프론트엔드 팀원이 본인 컴퓨터에서 바로 연동 개발 및 테스트를
진행할 수 있도록 돕는 '가짜 검사대' 프로그램입니다.

[동작 방식]
1. 검사 시작 시뮬레이션 (거치 감지)
2. 0.8초 간격으로 각 검사 단계(Stage)를 거치며 실시간 MQTT 텔레메트리 발행
3. 검사 종료 시 가짜 보드 촬영 이미지와 JSON 메타데이터를 백엔드 REST API로 전송

[실행 방법]
  python mock/mock_edge.py
  (또는 옵션 지정: python mock/mock_edge.py --scenario fail --backend http://localhost:8000)
=============================================================================
"""

import sys
import os
import time
import json
import uuid
import argparse
import io

# ---------------------------------------------------------------------------
# 외부 라이브러리 (없을 경우를 대비해 안내)
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    print("[경고] 'requests' 라이브러리가 필요합니다. (설치: pip install requests)")
    requests = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[안내] 'paho-mqtt' 라이브러리가 설치되어 있지 않으면 MQTT 발행이 건너뛰어집니다. (설치: pip install paho-mqtt)")
    mqtt = None


def generate_dummy_image(text="SAMPLE INSPECTION IMAGE"):
    """
    백엔드로 업로드할 간단한 더미 JPEG 이미지를 메모리 상에서 생성합니다.
    (PIL이 있으면 글자가 적힌 이미지를 만들고, 없으면 최소 1x1 더미 바이트 반환)
    """
    try:
        from PIL import Image, ImageDraw
        # 640x480 크기의 테스트 이미지 생성 (어두운 녹색 PCB 느낌)
        img = Image.new("RGB", (640, 480), color=(20, 60, 35))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 590, 430], outline=(100, 200, 100), width=3)
        draw.text((80, 80), f"Raspberry Pi 4 Dummy Board\n{text}", fill=(255, 255, 255))
        draw.text((80, 200), f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}", fill=(200, 200, 200))
        
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except Exception:
        # PIL이 없는 환경을 위한 최소 유효 1x1 JPEG 바이트
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
        """MQTT 브로커 연결을 준비합니다."""
        if mqtt is None:
            return
        try:
            self.mqtt_client = mqtt.Client(client_id=f"mock-{self.device_id}-{int(time.time())}")
            self.mqtt_client.connect_async(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            print(f"[MQTT] 브로커 연결 시도: {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            print(f"[MQTT] 브로커 연결 실패 (MQTT 발행은 건너뜁니다): {e}")
            self.mqtt_client = None

    def publish_telemetry(self, inspection_id, stage, progress, message, blur_score=185.0):
        """프론트엔드가 실시간으로 확인할 수 있도록 MQTT 토픽을 발행합니다."""
        payload = {
            "inspection_id": inspection_id,
            "device_id": self.device_id,
            "stage": stage,
            "progress_percent": progress,
            "blur_score": blur_score,
            "stabilization_ms": 280,
            "message": message
        }
        topic = f"inspection/{self.device_id}/telemetry"
        print(f"  📡 [MQTT Telemetry] [{progress:3d}%] [{stage}] {message}")
        
        if self.mqtt_client:
            try:
                self.mqtt_client.publish(topic, json.dumps(payload, ensure_ascii=False))
            except Exception as e:
                print(f"  [MQTT 발행 오류]: {e}")

    def run_simulation(self, scenario="pass"):
        """
        시나리오에 따라 전체 검사 파이프라인을 시뮬레이션합니다.
        시나리오 종류:
          - 'pass': 모든 외관 및 LED 점등 통과 (정상 반납)
          - 'fail': 외관 결함(핀 휨) 또는 LED 미점등 발견 (관리자 검토 대기열)
          - 'reposition': 영상 흐림으로 인한 재배치 안내
        """
        inspection_id = str(uuid.uuid4())
        print("\n" + "=" * 60)
        print(f"🚀 [검사 세션 시작] ID: {inspection_id} (시나리오: {scenario.upper()})")
        print("=" * 60)

        # 1단계: 장비 거치 감지
        self.publish_telemetry(inspection_id, "MOUNTED", 10, "장비가 거치되었습니다. 검사를 시작합니다.")
        time.sleep(0.8)

        # 2단계: 카메라 안정화
        self.publish_telemetry(inspection_id, "STABILIZING", 25, "카메라 초점 및 모션을 안정화하고 있습니다...")
        time.sleep(0.8)

        # 3단계: 블러 점수 및 영상 선명도 평가
        if scenario == "reposition":
            self.publish_telemetry(inspection_id, "BLUR_CHECK", 40, "손 떨림 또는 위치 불안정이 감지되었습니다.", blur_score=45.2)
            time.sleep(0.8)
            self.publish_telemetry(inspection_id, "REPOSITION", 40, "보드가 흔들렸습니다. 보드를 바르게 다시 놓아주세요.")
            print("\n⚠️ [재배치 안내] 사용자가 보드를 다시 놓아야 하므로 세션을 일시 중단합니다.")
            return

        self.publish_telemetry(inspection_id, "BLUR_CHECK", 40, "영상 품질이 선명합니다 (블러 점수 양호).", blur_score=210.5)
        time.sleep(0.8)

        # 4단계: 시리얼 번호 광학 인식 (OCR)
        self.publish_telemetry(inspection_id, "OCR", 60, "보드 표면의 고유 시리얼 번호를 인식하고 있습니다...")
        time.sleep(0.8)

        # 5단계: 온보드 PWR LED 점등 확인
        pwr_led_ok = True if scenario != "fail_led" else False
        led_msg = "PWR LED 정상 점등 확인 완료." if pwr_led_ok else "경고: PWR LED가 켜지지 않았습니다 (전원 불량)!"
        self.publish_telemetry(inspection_id, "LED_CHECK", 75, led_msg)
        time.sleep(0.8)

        # 6단계: AI 외관 결함 탐지 (YOLOv8 추론)
        self.publish_telemetry(inspection_id, "AI_INFERENCE", 90, "AI 모델이 GPIO 핀 및 포트 파손 여부를 정밀 분석 중입니다...")
        time.sleep(1.0)

        # 판정 결과 생성
        if scenario == "pass":
            verdict = "PASS"
            defects = []
        elif scenario == "fail_led":
            verdict = "FAIL"
            defects = []
        else: # scenario == "fail" (외관 결함)
            verdict = "FAIL"
            defects = [
                {
                    "class": "bent_pin",
                    "confidence": 0.89,
                    "bbox": [150, 60, 210, 110]
                }
            ]

        # 7단계: 검사 완료 알림
        self.publish_telemetry(inspection_id, "COMPLETED", 100, f"검사가 완료되었습니다. 최종 결과: {verdict}")

        # 8단계: 백엔드로 최종 결과 전송 (REST API)
        self._send_to_backend(inspection_id, verdict, pwr_led_ok, defects)

    def _send_to_backend(self, inspection_id, verdict, pwr_led_status, defects):
        """백엔드 FastAPI의 POST /api/v1/inspections 엔드포인트로 전송합니다."""
        url = f"{self.backend_url}/api/v1/inspections"
        print(f"\n📤 [백엔드 전송 시도] {url}")

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

        # 더미 이미지 생성
        image_bytes = generate_dummy_image(f"ID: {inspection_id}\nVerdict: {verdict}\nDefects: {len(defects)}")

        if requests is None:
            print("[알림] requests 라이브러리가 없어 실제 HTTP 전송을 생략합니다. (메타데이터만 콘솔에 출력)")
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
            print(f"  📥 백엔드 응답 코드: {resp.status_code}")
            print(f"  📥 백엔드 응답 본문: {resp.text}")
            if resp.status_code in (200, 201):
                print("  ✅ [성공] 백엔드에 검사 결과가 정상 등록되었습니다!")
            else:
                print("  ⚠️ [확인 필요] 백엔드가 오류 코드를 반환했습니다. 백엔드 로그를 확인하세요.")
        except requests.exceptions.ConnectionError:
            print(f"  ❌ [연결 실패] 백엔드 서버({url})가 켜져 있지 않습니다.")
            print("     -> 백엔드 개발 팀원이 서버(FastAPI)를 구동한 뒤 다시 시도해 보세요.")
        except Exception as e:
            print(f"  ❌ [오류 발생]: {e}")


def main():
    parser = argparse.ArgumentParser(description="가짜 엣지 검사대 시뮬레이터 (Mock Edge)")
    parser.add_argument("--scenario", choices=["pass", "fail", "fail_led", "reposition"], default=None,
                        help="실행할 검사 시나리오 (pass, fail, fail_led, reposition)")
    parser.add_argument("--backend", default="http://localhost:8000",
                        help="백엔드 FastAPI 서버 주소 (기본: http://localhost:8000)")
    parser.add_argument("--mqtt-host", default="localhost",
                        help="MQTT 브로커 호스트 (기본: localhost)")
    parser.add_argument("--mqtt-port", type=int, default=1883,
                        help="MQTT 브로커 포트 (기본: 1883)")
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
        print(" [Mock Edge] 테스트할 시나리오를 선택하세요:")
        print("  1. 정상 반납 통과 (PASS)")
        print("  2. 외관 결함 발견 (FAIL - 핀 휨)")
        print("  3. 전원 불량 발견 (FAIL - PWR LED 꺼짐)")
        print("  4. 영상 흐림 / 재배치 안내 (REPOSITION)")
        print("=" * 50)
        try:
            choice = input(" 번호 입력 (1-4) [기본: 1]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n종료합니다.")
            sys.exit(0)

        choice_map = {"1": "pass", "2": "fail", "3": "fail_led", "4": "reposition", "": "pass"}
        scenario = choice_map.get(choice, "pass")

    station.run_simulation(scenario=scenario)


if __name__ == "__main__":
    main()
