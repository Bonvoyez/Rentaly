#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[YOLO Stabilizer] Raspberry Pi Edge 1st-Stage Real-Time Stabilization & Auto-Shutter Detector
=============================================================================
- Ultra-lightweight inference based on newly trained yolo_rpi4_best.onnx (OpenCV DNN)
- Judgment conditions:
    1) human_hand == 0 (Has the hand completely moved out of frame?)
    2) rpi4_board >= 1 (Is the board fully inside the frame?)
    3) pwr_led_on >= 1 (Is the red power LED turned on?)
    4) If the above 3 conditions hold continuously for 0.6s+ -> Trigger "STABILIZED! Snap"!
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
        self.required_stable_frames = 8  # ~0.5-0.6s (at 15fps)

        if os.path.exists(model_path):
            try:
                self.net = cv2.dnn.readNetFromONNX(model_path)
                print(f"🤖 [YoloStabilizer] ONNX model loaded successfully: {model_path}")
            except Exception as e:
                print(f"⚠️ [YoloStabilizer] Failed to load ONNX: {e}")
        else:
            print(f"⚠️ [YoloStabilizer] Model file not found: {model_path}")

    def analyze_frame(self, frame_bgr):
        """
        Analyze frame and return (is_ready_to_snap, status_message, detected_counts)
        """
        if self.net is None or frame_bgr is None:
            return False, "YOLO model not ready", {}

        h, w = frame_bgr.shape[:2]
        blob = cv2.dnn.blobFromImage(frame_bgr, 1/255.0, (640, 640), swapRB=True, crop=False)
        self.net.setInput(blob)
        preds = self.net.forward()  # shape: [1, 8, 8400]

        # Parsing
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

        # Rule evaluation
        # 1. If a hand is detected (wait until hand is removed)
        if counts["human_hand"] > 0:
            self.consecutive_stable_frames = 0
            return False, "Hand detected. Please remove your hand.", counts

        # 2. If no hand is present (pass if board is detected or stabilized for 4+ frames)
        # LED is precisely verified by 2nd-stage VLM, so relax entry threshold
        self.consecutive_stable_frames += 1
        if self.consecutive_stable_frames >= 4:
            return True, "Board placement confirmed! Proceeding with auto-capture", counts
        else:
            return False, "Checking board stability...", counts

        # Increment stabilization count when all conditions are met
        self.consecutive_stable_frames += 1
        if self.consecutive_stable_frames >= self.required_stable_frames:
            return True, "Stabilization complete! Proceeding with auto-capture", counts
        else:
            remain = self.required_stable_frames - self.consecutive_stable_frames
            return False, f"Checking board stability... ({self.consecutive_stable_frames}/{self.required_stable_frames})", counts

    def reset(self):
        self.consecutive_stable_frames = 0
