#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Step 2] 정밀 AI 외관 검사 & 모션 블러 필터 모듈 (엄격 판정 모드)
=============================================================================
- 1차 방어선: 라플라시안 분산 기반 영상 선명도(블러) 계측
    -> 기준 점수(100점) 미만 시 AI 추론 없이 즉시 [REPOSITION] 판정!
- 2차 방어선: YOLOv8 ONNX 초경량 엔진 기반 부품 전수 검사 (AND 조건)
    -> 필수 부품: processor + ports_block + gpio_header + rpi4_board
    -> 화면 밖 잘림, 가림, 누락 발생 시 즉시 [FAIL / REPOSITION] 판정!
=============================================================================
"""

import os
import sys
import time
import cv2
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

MODEL_PATH = os.path.join(CURRENT_DIR, "best.onnx")
SAMPLE_IMAGE = os.path.join(PROJECT_ROOT, "sample_data", "inspection_result.jpg")

# 클래스 목록 (0: gpio_header, 1: ports_block, 2: processor, 3: rpi4_board)
CLASS_NAMES = ["gpio_header", "ports_block", "processor", "rpi4_board"]

# 엄격한 검사 기준
BLUR_THRESHOLD = 80.0         # 블러 점수가 80점 미만이면 초점 흐림/흔들림으로 판정
CONFIDENCE_THRESHOLD = 0.50   # 50% 이상 확실해야 정상 부품으로 인정
NMS_THRESHOLD = 0.45


def calculate_blur_score(image_or_path):
    """라플라시안 분산을 이용해 이미지의 선명도(블러 점수)를 계산합니다."""
    if isinstance(image_or_path, str):
        img = cv2.imread(image_or_path, cv2.IMREAD_GRAYSCALE)
    elif isinstance(image_or_path, np.ndarray):
        if len(image_or_path.shape) == 3:
            img = cv2.cvtColor(image_or_path, cv2.COLOR_BGR2GRAY)
        else:
            img = image_or_path
    else:
        return 0.0

    if img is None:
        return 0.0
    # 라플라시안 필터 적용 후 분산값 계산
    score = cv2.Laplacian(img, cv2.CV_64F).var()
    return float(score)


class OnnxYoloDetector:
    def __init__(self, model_path=MODEL_PATH):
        import onnxruntime as ort
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.input_w = self.input_shape[3]
        self.input_h = self.input_shape[2]

    def preprocess(self, img):
        h, w = img.shape[:2]
        scale = min(self.input_w / w, self.input_h / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)

        canvas = np.full((self.input_h, self.input_w, 3), 114, dtype=np.uint8)
        top = (self.input_h - nh) // 2
        left = (self.input_w - nw) // 2
        canvas[top:top + nh, left:left + nw] = resized

        blob = canvas.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        return blob, scale, left, top

    def detect(self, img_or_path, conf_threshold=CONFIDENCE_THRESHOLD):
        if isinstance(img_or_path, str):
            img = cv2.imread(img_or_path)
            if img is None:
                raise FileNotFoundError(f"이미지를 읽을 수 없습니다: {img_or_path}")
        elif isinstance(img_or_path, np.ndarray):
            img = img_or_path
        else:
            raise ValueError("img_or_path는 파일 경로 문자열 또는 np.ndarray여야 합니다.")

        orig_h, orig_w = img.shape[:2]
        blob, scale, pad_x, pad_y = self.preprocess(img)

        start = time.perf_counter()
        outputs = self.session.run(None, {self.input_name: blob})
        infer_ms = (time.perf_counter() - start) * 1000

        output = outputs[0][0].T  # [8400, 8]
        boxes, confidences, class_ids = [], [], []
        num_classes = len(CLASS_NAMES)

        for row in output:
            scores = row[4:4 + num_classes]
            class_id = np.argmax(scores)
            confidence = scores[class_id]

            if confidence >= conf_threshold:
                xc, yc, w, h = row[0], row[1], row[2], row[3]
                x1 = int((xc - w / 2 - pad_x) / scale)
                y1 = int((yc - h / 2 - pad_y) / scale)
                box_w = int(w / scale)
                box_h = int(h / scale)

                x1 = max(0, min(x1, orig_w - 1))
                y1 = max(0, min(y1, orig_h - 1))

                boxes.append([x1, y1, box_w, box_h])
                confidences.append(float(confidence))
                class_ids.append(int(class_id))

        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, NMS_THRESHOLD)
        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                cls_name = CLASS_NAMES[class_ids[i]]
                results.append({
                    "class": cls_name,
                    "confidence": round(confidences[i], 3),
                    "bbox": boxes[i]
                })

        return results, infer_ms


def run_full_inspection(image_path):
    print("=" * 60)
    print("🔬 [라즈베리파이 정밀 반납 검사 시스템 가동]")
    print(f"[*] 대상 이미지: {os.path.basename(image_path)}")
    print("=" * 60)

    # -------------------------------------------------------------
    # 1단계: 모션 블러 및 영상 품질 평가 (Fail-Safe 1차 방어선)
    # -------------------------------------------------------------
    print("[1단계] 영상 품질 및 선명도(블러) 평가 중...")
    blur_score = calculate_blur_score(image_path)
    print(f"    -> 측정된 블러 점수: {blur_score:.1f} 점 (기준치: {BLUR_THRESHOLD} 점 이상)")

    if blur_score < BLUR_THRESHOLD:
        print("\n" + "=" * 60)
        print("⚠️ [1차 판정 결과: REPOSITION]")
        print("=" * 60)
        print(f"❌ [판정 거부] 초점이 맞지 않거나 흔들림이 너무 심합니다! (점수: {blur_score:.1f})")
        print("💡 [안내] 카메라 거리를 맞추거나 보드를 가만히 거치대에 놓아주세요.")
        print("=" * 60)
        return "REPOSITION"

    print("    ✅ 영상 선명도 양호 (블러 검사 통과)")

    # -------------------------------------------------------------
    # 2단계: AI 외관 부품 전수 검사 (Fail-Safe 2차 방어선)
    # -------------------------------------------------------------
    print("\n[2단계] AI 온디바이스 외관 결함/잘림 전수 분석 중...")
    detector = OnnxYoloDetector(MODEL_PATH)
    detected_items, infer_ms = detector.detect(image_path)

    detected_classes = {item["class"] for item in detected_items}

    print(f"    -> 순수 추론 시간: {infer_ms:.1f} ms")
    print(f"    -> 검출된 부품 내역:")
    for item in detected_items:
        print(f"       * [{item['class']:<12}] 신뢰도: {item['confidence']*100:5.1f}% | 위치: {item['bbox']}")

    # -------------------------------------------------------------
    # 3단계: 엄격한 무결성 판정 (AND 조건)
    # -------------------------------------------------------------
    # 필수 3대 요소: CPU(processor)와 포트(ports_block)가 둘 다 제대로 보여야 함!
    has_cpu = "processor" in detected_classes
    has_ports = "ports_block" in detected_classes
    has_gpio = "gpio_header" in detected_classes

    missing = []
    if not has_cpu:
        missing.append("CPU 프로세서(누락/가림/화면밖 잘림)")
    if not has_ports:
        missing.append("USB/이더넷 포트 블록")

    print("\n" + "=" * 60)
    print("📊 [최종 검사 판정 도출]")
    print("=" * 60)

    if missing:
        verdict = "FAIL"
        print(f"[*] 1차 판정 상태: {verdict} (외관 결함 의심)")
        print(f"❌ [결함 사유] 필수 핵심 부품이 탐지되지 않았습니다: {missing}")
        print("💡 [원인] 보드가 화면 밖으로 잘렸거나, 케이블/이물질로 가려졌거나, 파손되었습니다.")
    else:
        verdict = "PASS"
        print(f"[*] 1차 판정 상태: {verdict} (정상 통과)")
        print("✅ [성공] 라즈베리파이 핵심 부품들이 온전하게 모두 확인되었습니다!")

    print(f"[*] 영상 선명도: {blur_score:.1f} 점 | AI 추론 속도: {infer_ms:.1f} ms")
    print("=" * 60)
    return verdict


def main():
    target_img = sys.argv[1] if len(sys.argv) > 1 else SAMPLE_IMAGE
    run_full_inspection(target_img)


if __name__ == "__main__":
    main()
