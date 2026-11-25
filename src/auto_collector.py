#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Guided Collector] Guided Interactive Data Collector
=============================================================================
- AI guides you step-by-step on the desired composition, position, and concept
- Place the board and press [Enter] to capture immediately
- Covers 10 essential inspection scenarios (normal, tilted, cable occlusion, close-up, etc.)
=============================================================================
"""

import os
import sys
import time
import cv2

from camera_streamer import get_camera_streamer

SAVE_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "raw_images")
os.makedirs(SAVE_DIR, exist_ok=True)

# 10 essential scenario guidebooks
GUIDED_STEPS = [
    {
        "step": 1,
        "title": "🎯 [Normal 1] Centered vertical alignment (ideal state)",
        "guide": "Place the board straight and centered in the camera frame. (Move ribbon cable aside)",
        "category": "normal_center"
    },
    {
        "step": 2,
        "title": "🎯 [Normal 2] Slightly shifted to the left",
        "guide": "Slide the board 2-3cm to the left. (Keep all 4 corners inside the frame)",
        "category": "normal_left"
    },
    {
        "step": 3,
        "title": "🎯 [Normal 3] Slightly shifted to the right",
        "guide": "Slide the board 2-3cm to the right.",
        "category": "normal_right"
    },
    {
        "step": 4,
        "title": "📐 [Rotation 1] Slightly tilted 15 degrees clockwise",
        "guide": "Tilt the board about 15 degrees clockwise. (Simulating casual user placement)",
        "category": "rotate_clockwise"
    },
    {
        "step": 5,
        "title": "📐 [Rotation 2] Slightly tilted 15 degrees counter-clockwise",
        "guide": "Tilt the board about 15 degrees in the opposite direction.",
        "category": "rotate_counter_clockwise"
    },
    {
        "step": 6,
        "title": "💡 [Lighting/Distance] Closer to camera (close-up) or height adjustment",
        "guide": "Raise the board slightly closer to the camera or adjust the lighting angle.",
        "category": "close_up"
    },
    {
        "step": 7,
        "title": "🚫 [Defect 1] Cable occluding the board",
        "guide": "Place the white camera ribbon cable or power cable slightly across the top of the board.",
        "category": "cable_occlusion"
    },
    {
        "step": 8,
        "title": "🚫 [Defect 2] Board corner cut off outside the frame",
        "guide": "Push the board toward a corner of the frame so part of the PCB is cut off.",
        "category": "out_of_bounds"
    },
    {
        "step": 9,
        "title": "🏷️ [Asset ID] Sticky note or label placed on/near board",
        "guide": "Place or attach a memo/label like 'RPI-01' next to or on top of the board.",
        "category": "asset_label"
    },
    {
        "step": 10,
        "title": "🔴 [LED Check] Final check with power cable connected",
        "guide": "Position the board straight so the red power LED is clearly visible.",
        "category": "pwr_led_focus"
    }
]

def run_guided_collection():
    print("=" * 70)
    print("🎬 [Rentaly Guided Collector] Step-by-Step Custom AI Data Collector")
    print("👉 Place the board as guided and press [Enter] to capture!")
    print(f"👉 Save directory: {os.path.abspath(SAVE_DIR)}")
    print("=" * 70)

    streamer = get_camera_streamer()
    time.sleep(1.5)  # Camera stabilization

    for item in GUIDED_STEPS:
        step_num = item["step"]
        print(f"\n==================== [ Step {step_num} / {len(GUIDED_STEPS)} ] ====================")
        print(f"📌 Mission: {item['title']}")
        print(f"👉 Guide: {item['guide']}")
        print("----------------------------------------------------------------------")
        
        # Wait until user is ready!
        input(f"✅ Press [Enter] once the board is positioned... ")

        # Capture
        frame = streamer.get_latest_frame()
        if frame is None:
            print("⚠️ Failed to get camera frame. Retrying.")
            continue

        filename = f"{step_num:02d}_{item['category']}_{int(time.time())}.jpg"
        save_path = os.path.join(SAVE_DIR, filename)
        cv2.imwrite(save_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"📸 Snap! Saved [{filename}]! Great job 👏")

    print("\n" + "=" * 70)
    print("🎉 Congratulations! All 10 essential inspection scenarios have been collected!")
    print("👉 Now run 'python3 src/auto_pipeline.py' to start VLM auto-labeling.")
    print("=" * 70)

if __name__ == "__main__":
    run_guided_collection()
