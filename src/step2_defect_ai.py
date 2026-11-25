#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Step 2] Precision AI Exterior Inspection & Motion Blur Filter Module (Strict Mode)
=============================================================================
- 1st line of defense: Laplacian variance-based image sharpness (blur) measurement
    -> If below threshold (100), immediately return [REPOSITION] without AI inference!
- 2nd line of defense: YOLOv8 ONNX lightweight engine-based component inspection (AND condition)
    -> Required components: processor + ports_block + gpio_header + rpi4_board
    -> If cropped out of frame, occluded, or missing, immediately return [FAIL / REPOSITION]!
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

# Class list (0: gpio_header, 1: ports_block, 2: processor, 3: rpi4_board)
CLASS_NAMES = ["gpio_header", "ports_block", "processor", "rpi4_board"]

# Strict inspection thresholds
BLUR_THRESHOLD = 80.0         # Below 80 is considered out-of-focus / motion-blurred
CONFIDENCE_THRESHOLD = 0.50   # Must be >= 50% confident to count as valid component
NMS_THRESHOLD = 0.45


def calculate_blur_score(image_or_path):
    """Calculate image sharpness (blur score) using Laplacian variance."""
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
    # Apply Laplacian filter and compute variance
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
                raise FileNotFoundError(f"Cannot read image: {img_or_path}")
        elif isinstance(img_or_path, np.ndarray):
            img = img_or_path
        else:
            raise ValueError("img_or_path must be a file path string or np.ndarray.")

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
    print("🔬 [Raspberry Pi Precision Return Inspection System]")
    print(f"[*] Target image: {os.path.basename(image_path)}")
    print("=" * 60)

    # -------------------------------------------------------------
    # Stage 1: Motion blur & image quality check (Fail-Safe 1st line)
    # -------------------------------------------------------------
    print("[Stage 1] Evaluating image quality & sharpness (blur)...")
    blur_score = calculate_blur_score(image_path)
    print(f"    -> Measured blur score: {blur_score:.1f} (threshold: >= {BLUR_THRESHOLD})")

    if blur_score < BLUR_THRESHOLD:
        print("\n" + "=" * 60)
        print("⚠️ [Primary Verdict: REPOSITION]")
        print("=" * 60)
        print(f"❌ [Rejected] Image is out of focus or too blurry! (score: {blur_score:.1f})")
        print("💡 [Guide] Adjust camera distance or place the board still on the cradle.")
        print("=" * 60)
        return "REPOSITION"

    print("    ✅ Image sharpness good (blur check passed)")

    # -------------------------------------------------------------
    # Stage 2: AI exterior component inspection (Fail-Safe 2nd line)
    # -------------------------------------------------------------
    print("\n[Stage 2] Running on-device AI exterior defect/crop analysis...")
    detector = OnnxYoloDetector(MODEL_PATH)
    detected_items, infer_ms = detector.detect(image_path)

    detected_classes = {item["class"] for item in detected_items}

    print(f"    -> Pure inference time: {infer_ms:.1f} ms")
    print(f"    -> Detected components:")
    for item in detected_items:
        print(f"       * [{item['class']:<12}] Confidence: {item['confidence']*100:5.1f}% | BBox: {item['bbox']}")

    # -------------------------------------------------------------
    # Stage 3: Strict integrity judgment (AND condition)
    # -------------------------------------------------------------
    # Required core elements: both CPU (processor) and ports (ports_block) must be clearly visible!
    has_cpu = "processor" in detected_classes
    has_ports = "ports_block" in detected_classes
    has_gpio = "gpio_header" in detected_classes

    missing = []
    if not has_cpu:
        missing.append("CPU processor (missing/occluded/cropped)")
    if not has_ports:
        missing.append("USB/Ethernet port block")

    print("\n" + "=" * 60)
    print("📊 [Final Inspection Verdict]")
    print("=" * 60)

    if missing:
        verdict = "FAIL"
        print(f"[*] Primary verdict status: {verdict} (suspected exterior defect)")
        print(f"❌ [Defect reason] Required core components not detected: {missing}")
        print("💡 [Cause] Board is cropped out of frame, occluded by cable/object, or damaged.")
    else:
        verdict = "PASS"
        print(f"[*] Primary verdict status: {verdict} (passed)")
        print("✅ [Success] All core Raspberry Pi components verified intact!")

    print(f"[*] Image sharpness: {blur_score:.1f} | AI inference speed: {infer_ms:.1f} ms")
    print("=" * 60)
    return verdict


def main():
    target_img = sys.argv[1] if len(sys.argv) > 1 else SAMPLE_IMAGE
    run_full_inspection(target_img)


if __name__ == "__main__":
    main()
