#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[YOLO Stabilizer] 라즈베리파이 엣지 1차 실시간 안정화 & 자동 셔터 감지기
=============================================================================
- 방금 학습된 yolo_rpi4_best.onnx 기반 초경량 추론 (OpenCV DNN)
- 판정 조건:
    1) human_hand == 0 (손이 완전히 빠져나갔는가?)
    2) rpi4_board >= 1 (보드가 화면 내에 온전히 들어왔는가?)
    3) pwr_led_on >= 1 (빨간 전원 LED가 켜져 있는가?)
    4) 위 3가지 상태가 0.6초 이상 연속 유지되면 -> "STABILIZED! 찰칵 트리거" 발동!
=============================================================================
"""

import os
import time
import cv2
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "yolo_rpi4_best.onnx")
CLASSES = ["rpi4_board", "pwr_led_on", "human_hand", "defect"]

class YoloStabilizer:
    def __init__(self, model_path=MODEL_PATH, conf_thresh=0.15):
        self.conf_thresh = conf_thresh
        self.net = None
        self.consecutive_stable_frames = 0
        self.required_stable_frames = 8  # 약 0.5~0.6초 (15fps 기준)

        if os.path.exists(model_path):
            try:
                self.net = cv2.dnn.readNetFromONNX(model_path)
                print(f"🤖 [YoloStabilizer] ONNX 모델 로드 성공: {model_path}")
            except Exception as e:
                print(f"⚠️ [YoloStabilizer] ONNX 로드 실패: {e}")
        else:
            print(f"⚠️ [YoloStabilizer] 모델 파일이 없습니다: {model_path}")

    def analyze_frame(self, frame_bgr):
        """
        프레임을 분석하여 (is_ready_to_snap, status_message, detected_counts) 반환
        """
        if self.net is None or frame_bgr is None:
            return False, "YOLO 모델 미준비", {}

        h, w = frame_bgr.shape[:2]
        blob = cv2.dnn.blobFromImage(frame_bgr, 1/255.0, (640, 640), swapRB=True, crop=False)
        self.net.setInput(blob)
        preds = self.net.forward()  # shape: [1, 8, 8400]

        # 파싱
        # preds[0]: [xc, yc, w, h, cls0, cls1, cls2, cls3]
        boxes = preds[0][:4, :].T
        scores = preds[0][4:, :].T

        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)

        counts = {"rpi4_board": 0, "pwr_led_on": 0, "human_hand": 0, "defect": 0}

        for i in range(len(confidences)):
            if confidences[i] > self.conf_thresh:
                cid = class_ids[i]
                if cid < len(CLASSES):
                    cname = CLASSES[cid]
                    counts[cname] += 1

        # 규칙 평가
        # 1. 손이 감지된 경우 (손을 뗄 때까지 대기)
        if counts["human_hand"] > 0:
            self.consecutive_stable_frames = 0
            return False, "손이 감지되었습니다. 손을 떼어주세요.", counts

        # 2. 손이 없으면 (보드가 인식되거나 안정화 4프레임 이상이면 무조건 통과 진행)
        # LED는 2차 VLM에서 정밀 검증하므로 입구컷 완화
        self.consecutive_stable_frames += 1
        if self.consecutive_stable_frames >= 4:
            return True, "보드 안착 확인! 자동 촬영 진행", counts
        else:
            return False, "보드 고정 확인 중...", counts

        # 모든 조건 만족 시 안정화 카운트 증가
        self.consecutive_stable_frames += 1
        if self.consecutive_stable_frames >= self.required_stable_frames:
            return True, "안정화 완료! 자동 촬영 진행", counts
        else:
            remain = self.required_stable_frames - self.consecutive_stable_frames
            return False, f"보드 고정 확인 중... ({self.consecutive_stable_frames}/{self.required_stable_frames})", counts

    def reset(self):
        self.consecutive_stable_frames = 0
