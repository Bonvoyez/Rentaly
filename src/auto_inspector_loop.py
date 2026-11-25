#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Auto Inspector Loop] 프론트엔드 연동 완전 무인 생명주기 관리자
=============================================================================
동작 시나리오:
1. 대기 상태: YOLO 꺼짐 (CPU 0%), 프리뷰 스트리밍만 대기
2. 프론트엔드에서 "검사 시작" 신호(MQTT 토픽: inspection/station-01/command, payload: START) 수신
   또는 키오스크 대시보드에서 검사 시작 버튼 클릭 시:
   -> YOLO 가동 (1차 안정화 감지 시작)
   -> 손 감지 시 / LED 꺼짐 시 실시간 텔레메트리 발행
3. 3가지 조건(손 뗌 + 보드 안 잘림 + 빨간 LED 켜짐) 안정화 감지 즉시:
   -> "찰칵!" 고화질 캡처
   -> YOLO 즉시 종료 (CPU 절전)
   -> 캡처 사진(capture_image_url)과 함께 VLM 정밀 검사 시작
4. 검사 완료(COMPLETED) 및 결과 보고 후:
   -> 자동으로 다시 1번 초기 대기 상태로 복귀!
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
        """프론트엔드 제어 명령(START, RESET) 구독"""
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
                print(f"👂 [MQTT Subscriber] 명령 토픽 구독 완료: {cmd_topic}")

            def on_message(c, userdata, msg):
                try:
                    payload = json.loads(msg.payload.decode("utf-8"))
                    cmd = payload.get("action", "").upper()
                    print(f"📩 [MQTT Command 수신]: {cmd}")
                    if cmd in ["START", "START_INSPECTION"]:
                        self.trigger_start()
                    elif cmd in ["RESET", "CANCEL"]:
                        self.reset_to_idle()
                except Exception as e:
                    print(f"⚠️ 명령 파싱 오류: {e}")

            self.sub_client.on_connect = on_connect
            self.sub_client.on_message = on_message
            self.sub_client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.sub_client.loop_start()
        except Exception as e:
            print(f"⚠️ MQTT Subscriber 연결 실패: {e}")

    def trigger_start(self):
        """검사 시작: YOLO 가동 및 안정화 감지 루프 시작"""
        with self.lock:
            if self.state != STATE_IDLE:
                return False, f"현재 상태({self.state})에서는 시작할 수 없습니다."
            self.state = STATE_STABILIZING
            self.current_insp_id = str(uuid.uuid4())
            self.stabilizer.reset()

        print(f"\n🚀 [검사 라이프사이클 시작] ID: {self.current_insp_id}")
        threading.Thread(target=self._run_stabilization_and_inspect, daemon=True).start()
        return True, "YOLO 안정화 감지 시작"

    def _run_stabilization_and_inspect(self):
        insp_id = self.current_insp_id
        start_wait_time = time.time()
        last_pub_time = 0

        # [1단계: YOLO 실시간 안정화 감지 (손 뗌 + 보드 온전 + LED 켜짐)]
        print("👁️ [YOLO 가동] 실시간 안정화 감지 중...")
        captured_frame = None

        while self.state == STATE_STABILIZING:
            frame = self.streamer.get_latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            ready_to_snap, message, counts = self.stabilizer.analyze_frame(frame)

            # 키오스크로 실시간 가이드 텔레메트리 (0.5초 주기)
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
                print(f"📸 [안정화 성공!] 찰칵! 자동 촬영 (소요시간: {now - start_wait_time:.1f}초)")
                captured_frame = frame.copy()
                break

            # 30초 타임아웃
            if now - start_wait_time > 30:
                print("⏱️ 타임아웃: 안정화 실패")
                self.reset_to_idle()
                return

            time.sleep(0.03)

        if captured_frame is None:
            print("🛑 캡처 없이 안정화 루프가 종료되었습니다.")
            return

        # [2단계: YOLO 끄고 VLM 정밀 검사 진입]
        with self.lock:
            self.state = STATE_INSPECTING

        print("⚡ [YOLO 정지] VLM 정밀 분석 파이프라인 가동...")
        from web_inspector import process_and_inspect
        result = process_and_inspect(captured_frame)

        # [3단계: 검사 완료 후 3초 대기 뒤 초기 상태 복귀]
        with self.lock:
            self.state = STATE_DONE
        print("🎉 [검사 완료] 결과 보고 완료. 3초 후 초기 IDLE 상태로 복귀합니다.")
        time.sleep(3.0)
        self.reset_to_idle()

    def reset_to_idle(self):
        with self.lock:
            self.state = STATE_IDLE
            self.current_insp_id = None
            self.stabilizer.reset()
        print("💤 [초기화 완료] IDLE 대기 상태로 복귀했습니다 (YOLO 꺼짐, CPU 0%).")

# 싱글톤
_manager = None
def get_auto_inspector():
    global _manager
    if _manager is None:
        _manager = AutoInspectionManager()
    return _manager
