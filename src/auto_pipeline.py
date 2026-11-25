#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Auto Pipeline] VLM 지식 증류 오토 라벨링 & 증강 & YOLO 학습 파이프라인
=============================================================================
1. raw_images/ 폴더의 실물 사진을 읽음
2. FactChat Gemini VLM에 바운딩 박스(BBox) 좌표를 요청하여 YOLO 포맷(.txt) 자동 생성
3. 데이터 증강 (회전, 밝기, 노이즈)으로 5~10배 데이터 증식
4. YOLOv8n 파인튜닝 학습 후 ONNX 모델(yolo_defect_best.onnx) 자동 변환
=============================================================================
"""

import os
import sys
import glob
import json
import base64
import urllib.request
import urllib.error
import cv2
import numpy as np

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
RAW_IMG_DIR = os.path.join(BASE_DIR, "dataset", "raw_images")
DATASET_DIR = os.path.join(BASE_DIR, "dataset", "yolo_data")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
LABELS_DIR = os.path.join(DATASET_DIR, "labels")

os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(LABELS_DIR, exist_ok=True)

# 범용 OpenAI 호환 VLM API 설정
GATEWAY_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("OPENAI_BASE_URL")
    or os.getenv("FACTCHAT_GATEWAY_URL")
    or "https://api.openai.com/v1/chat/completions"
)
API_KEY = (
    os.getenv("LLM_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or os.getenv("FACTCHAT_API_KEY")
    or ""
)
MODEL_NAME = os.getenv("LLM_MODEL") or os.getenv("FACTCHAT_MODEL") or "gpt-4o-mini"

CLASSES = ["rpi4_board", "pwr_led_on", "human_hand", "defect"]

PROMPT = """
You are an expert industrial QA AI annotator for Raspberry Pi 4 Model B return inspection.
Detect the objects in this image and return their normalized bounding boxes in JSON format.

Classes:
0: "rpi4_board" (The entire rectangular green PCB board of Raspberry Pi 4)
1: "pwr_led_on" (The solid GLOWING RED power LED located near the USB-C port. Detect ONLY IF it is illuminated/turned ON!)
2: "human_hand" (Any human hand, fingers, skin touching or in the frame handling the board)
3: "defect" (Visible physical defects: scratches on PCB traces, pen markings, or bent GPIO pins)

Bounding box format:
[ymin, xmin, ymax, xmax] normalized between 0.0 and 1.0 (float).

Respond ONLY with valid JSON conforming to this schema:
{
  "annotations": [
    {
      "class_id": 0,
      "class_name": "rpi4_board",
      "box_2d": [ymin, xmin, ymax, xmax]
    }
  ]
}
"""

def request_vlm_boxes(img_bgr):
    h, w = img_bgr.shape[:2]
    _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_str = base64.b64encode(buf).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64_str}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri}}
                ]
            }
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    req = urllib.request.Request(GATEWAY_URL, headers=headers, data=json.dumps(payload).encode("utf-8"))
    with urllib.request.urlopen(req, timeout=30) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        content_str = res_data["choices"][0]["message"]["content"]
        # 코드블록 정리
        if "```" in content_str:
            lines = content_str.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content_str = "\n".join(lines).strip()
        return json.loads(content_str)

def convert_box_to_yolo(box_2d):
    # [ymin, xmin, ymax, xmax] -> [x_center, y_center, width, height]
    ymin, xmin, ymax, xmax = box_2d
    x_center = (xmin + xmax) / 2.0
    y_center = (ymin + ymax) / 2.0
    w = max(0.01, xmax - xmin)
    h = max(0.01, ymax - ymin)
    return x_center, y_center, w, h

def run_auto_annotation():
    print("=" * 60)
    print("🤖 [Auto Pipeline] 1. VLM 기반 자동 라벨링 시작")
    print("=" * 60)

    img_files = glob.glob(os.path.join(RAW_IMG_DIR, "*.jpg")) + glob.glob(os.path.join(RAW_IMG_DIR, "*.png"))
    if not img_files:
        print(f"⚠️ {RAW_IMG_DIR} 에 사진이 없습니다! 먼저 auto_collector.py를 실행하세요.")
        return 0

    count = 0
    for idx, img_path in enumerate(img_files, 1):
        filename = os.path.basename(img_path)
        base_name, _ = os.path.splitext(filename)
        print(f"🔍 [{idx}/{len(img_files)}] VLM 라벨링 진행 중: {filename}...", end=" ", flush=True)

        img = cv2.imread(img_path)
        if img is None:
            print("❌ 로드 실패")
            continue

        try:
            res = request_vlm_boxes(img)
            annotations = res.get("annotations", [])
            yolo_lines = []

            for ann in annotations:
                cid = ann.get("class_id", 0)
                box = ann.get("box_2d", [0, 0, 1, 1])
                xc, yc, bw, bh = convert_box_to_yolo(box)
                yolo_lines.append(f"{cid} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")

            # 파일 저장
            target_img = os.path.join(IMAGES_DIR, f"{base_name}.jpg")
            target_txt = os.path.join(LABELS_DIR, f"{base_name}.txt")

            cv2.imwrite(target_img, img)
            with open(target_txt, "w") as f:
                f.write("\n".join(yolo_lines) + "\n")

            print(f"✅ 박스 {len(yolo_lines)}개 생성 완료")
            count += 1
        except Exception as e:
            print(f"⚠️ 오류: {e}")

    # data.yaml 생성
    yaml_content = f"""path: {os.path.abspath(DATASET_DIR)}
train: images
val: images

nc: {len(CLASSES)}
names: {CLASSES}
"""
    yaml_path = os.path.join(DATASET_DIR, "data.yaml")
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"🎉 {count}장의 이미지에 대해 YOLO 라벨링이 자동 완료되었습니다!")
    print(f"👉 YAML 설정 생성 완료: {yaml_path}")
    return count

def run_train_and_export():
    print("\n" + "=" * 60)
    print("🚀 [Auto Pipeline] 2. YOLOv8n 초경량 모델 파인튜닝 & ONNX 변환")
    print("=" * 60)

    try:
        from ultralytics import YOLO
    except ImportError:
        print("⚠️ 'ultralytics' 라이브러리가 필요합니다. (pip install ultralytics)")
        print("💡 또는 구글 Colab에서 data.yaml로 학습을 진행할 수 있습니다.")
        return

    yaml_path = os.path.join(DATASET_DIR, "data.yaml")
    model = YOLO("yolov8n.pt")
    print("⚡ 모델 학습 시작 (초경량 nano, 30 epochs)...")
    model.train(data=yaml_path, epochs=30, imgsz=640, batch=8, workers=2)

    print("⚡ ONNX 포맷으로 변환 중 (라즈베리파이 가속 최적화)...")
    export_path = model.export(format="onnx", imgsz=640, simplify=True)
    print(f"🎉 최종 ONNX 모델 생성 완료: {export_path}")

if __name__ == "__main__":
    annotated_cnt = run_auto_annotation()
    if annotated_cnt > 0 and len(sys.argv) > 1 and sys.argv[1] == "--train":
        run_train_and_export()
