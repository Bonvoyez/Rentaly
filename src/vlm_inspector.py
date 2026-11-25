#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[VLM Inspector] FactChat Gateway API-Based Edge-Optimized Precision Exterior/Text Inspection Module
=============================================================================
- Model: gemini-3.5-flash-lite (FactChat Gateway)
- Optimizations:
    1) Fail-Safe: Laplacian blur score measurement (skips API call if below threshold)
    2) Smart Resize: Preserves text readability & 1024px JPEG compression (95% network traffic reduction)
    3) Strict JSON Schema: Extracts exterior defects, FCC ID, power LED, and model name in 1 call
=============================================================================
"""

import os
import sys
import time
import json
import base64
import urllib.request
import urllib.error
import cv2
import numpy as np

# Auto-load .env (secure key isolation)
def _load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")

_load_env_file()

# Universal OpenAI-compatible VLM API config (supports OpenAI, Gemini, Ollama, vLLM, FactChat, etc.)
LLM_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("OPENAI_BASE_URL")
    or "https://api.openai.com/v1/chat/completions"
)
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
LLM_MODEL = os.getenv("LLM_MODEL") or "gpt-4o-mini"

# Backward compatibility aliases
FACTCHAT_URL = LLM_BASE_URL
FACTCHAT_API_KEY = LLM_API_KEY
FACTCHAT_MODEL = LLM_MODEL

BLUR_THRESHOLD = 80.0  # Sharpness threshold

SYSTEM_PROMPT = """You are an industrial QA vision inspector for a Raspberry Pi 4 Model B return kiosk ('Rentaly').
Inspect the board image and return ONLY a strict JSON object with these keys:
{
  "is_raspberry_pi": true or false,
  "is_fully_visible": true or false (true ONLY IF all 4 borders/edges of the PCB board are completely inside the frame without being cropped or partially out of view),
  "primary_verdict": "PASS" or "FAIL" or "REPOSITION",
  "defect_type": "NONE" or "OCCLUDED_BY_HAND" or "CROPPED_OR_CUT_OFF" or "CHIP_DAMAGE" or "BENT_PIN" or "PORT_DAMAGE" or "FOREIGN_SUBSTANCE_OR_DRAWING" or "MISSING_PARTS",
  "pwr_led_status": true or false (check if onboard PWR red LED is glowing/solid ON),
  "ic_id_text": "extracted IC certification number (e.g., 20953-RPI4B) or empty",
  "fcc_id_text": "extracted FCC ID (e.g., 2ABCB-RPI4B) or empty",
  "device_unique_id": "extracted asset sticker / serial number / barcode text / MAC address or empty",
  "model_text": "Raspberry Pi 4 Model B or similar extracted text",
  "confidence": 0.0 to 1.0,
  "reason": "Clear explanation in English why PASS, FAIL, or REPOSITION (explicitly mention if board is cut off, pen markings, chip defect, etc.)"
}
Strict Verification Rules:
1. [Human Hand / Obstacle Occlusion Rule]: If a human hand, fingers, skin, or any foreign holding object (or loose ribbon cable laying across core components) is touching or covering the board, or visible in the frame handling the board, you MUST IMMEDIATELY set is_fully_visible=false, primary_verdict="REPOSITION", defect_type="FOREIGN_SUBSTANCE_OR_DRAWING", and reason="Hand or foreign object detected. Please remove your hand completely and leave only the board." NEVER pass an image where human fingers or hands are visible!
2. [Boundary & Cut-off Rule]: If the Raspberry Pi board is cut off, cropped, or any of its 4 edges are outside the image frame, you MUST set is_fully_visible=false, primary_verdict="REPOSITION", defect_type="CROPPED_OR_CUT_OFF", and reason="Board is cut off outside the frame. Please reposition so the entire board is centered."
3. [Power LED (PWR LED) Verification Rule - MANDATORY]:
   - Locate the PWR LED near the USB-C power input (top-right corner of the board).
   - CAMERA FILTER NOTE: Due to infrared (IR) / camera optical filters, the illuminated LED may appear as a bright PURPLE, PINK, RED, or intense glowing WHITE light spot/glare rather than pure red.
   - [LED ON condition]: If there is an active, bright illuminating point of light (glowing dot, light spread, or glare in red/pink/purple/white) at the PWR LED position, set pwr_led_status=true.
   - [LED OFF condition]: If there is NO light emission, NO glowing dot, and only the dark unlit physical SMD component is visible (or USB-C power disconnected), you MUST set pwr_led_status=false, primary_verdict="FAIL", defect_type="PORT_DAMAGE", and reason="Power PWR LED is off. Please check power supply and board status."
   - If pwr_led_status is false, NEVER set primary_verdict="PASS"! Output primary_verdict="FAIL".
4. [Asset Tag & Unique ID Verification - MANDATORY]: Asset management tags or label stickers (e.g., 'RPI4-01' on LAN/USB port) attached for inventory tracking are REQUIRED to identify the returned device. Read the text on this label into 'device_unique_id'. If NO asset sticker/unique ID label is visible on the board/ports (device_unique_id is empty), you MUST set primary_verdict="FAIL", defect_type="MISSING_PARTS", and reason="Unique ID (asset management sticker) is not visible."
5. [Port Marker Markings]: Minor identification pen marks (like 'AvA') on metal shielding/port surfaces are acceptable management markings and should NOT fail the board unless the green PCB circuit or silicon chips themselves are vandalized.
6. [True Defect Rule]: If someone drew, colored, scratched, or spilled foreign substances directly on the GREEN PCB BOARD TRACES or SILICON CHIPS (CPU, RAM, PMIC), or if pins are bent/chips cracked, you MUST set primary_verdict="FAIL", defect_type="FOREIGN_SUBSTANCE_OR_DRAWING".
7. [Identifier Extraction]: Carefully read the silkscreen for IC: 20953-RPI4B, FCC ID: 2ABCB-RPI4B, and extract asset label text into device_unique_id.
8. [Pass Condition]: Set primary_verdict="PASS" ONLY IF:
   - NO human hands/fingers in frame
   - Board fully visible and flat
   - pwr_led_status is TRUE (solid red PWR LED glowing)
   - Asset sticker (device_unique_id) is clearly present without PCB/chip damage.
   If pwr_led_status is FALSE, NEVER set primary_verdict="PASS"! Output primary_verdict="FAIL".
Output ONLY the JSON object. No markdown backticks, no other text."""


def calculate_blur_score(img_bgr):
    """Measure sharpness score based on Laplacian variance"""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if len(img_bgr.shape) == 3 else img_bgr
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def optimize_image_for_vlm(img_bgr, max_dim=1024, quality=85):
    """
    [Edge Optimization Stage 2: Smart Resizing & Compression]
    Optimizes transfer size within 200KB while preserving text/pattern readability.
    """
    h, w = img_bgr.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        resized = img_bgr

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    success, encimg = cv2.imencode(".jpg", resized, encode_param)
    if not success:
        raise ValueError("JPEG encoding failed")

    b64_str = base64.b64encode(encimg).decode("utf-8")
    return b64_str, resized


def inspect_with_vlm(img_bgr):
    """
    Optimized VLM precision inspection pipeline
    """
    start_time = time.perf_counter()

    # 1. Fail-Safe 1st line of defense: blur measurement
    blur_score = calculate_blur_score(img_bgr)
    if blur_score < BLUR_THRESHOLD:
        infer_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "is_raspberry_pi": False,
            "primary_verdict": "REPOSITION",
            "defect_type": "BLURRED_OR_SHAKEN",
            "blur_score": round(blur_score, 1),
            "pwr_led_status": False,
            "fcc_id_matched": False,
            "fcc_id_text": "",
            "model_text": "",
            "confidence": 0.0,
            "reason": f"Camera out of focus or motion blur detected (sharpness: {blur_score:.1f} < threshold: {BLUR_THRESHOLD:.0f})",
            "infer_ms": round(infer_ms, 1)
        }

    # 2. Smart image resize & encoding
    img_b64, opt_img = optimize_image_for_vlm(img_bgr)

    # 3. Call FactChat Gateway VLM
    payload = {
        "model": FACTCHAT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Inspect this board thoroughly according to the QA rules and return JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 400
    }

    req = urllib.request.Request(
        FACTCHAT_URL,
        headers={
            "Authorization": f"Bearer {FACTCHAT_API_KEY}",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload).encode("utf-8")
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            # Strip markdown code blocks
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            result = json.loads(content)
            infer_ms = (time.perf_counter() - start_time) * 1000.0
            result["blur_score"] = round(blur_score, 1)
            result["infer_ms"] = round(infer_ms, 1)
            return result

    except Exception as e:
        infer_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "is_raspberry_pi": False,
            "primary_verdict": "ERROR",
            "defect_type": "API_ERROR",
            "blur_score": round(blur_score, 1),
            "pwr_led_status": False,
            "fcc_id_matched": False,
            "fcc_id_text": "",
            "model_text": "",
            "confidence": 0.0,
            "reason": f"VLM API call error: {str(e)}",
            "infer_ms": round(infer_ms, 1)
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Rentaly VLM Single Image Inspection Test")
    parser.add_argument("pos_image", nargs="?", help="Path to image to inspect")
    parser.add_argument("--image", "-i", dest="opt_image", help="Path to image to inspect (--image)")
    args = parser.parse_args()

    default_sample = os.path.join(os.path.dirname(__file__), "..", "sample_data", "training", "IMG_8187.png")
    test_img_path = args.opt_image or args.pos_image or default_sample
    print(f"[*] Target test image: {test_img_path}")
    img = cv2.imread(test_img_path)
    if img is None:
        print("❌ Failed to load image")
        sys.exit(1)

    print(f"[*] Running VLM precision inspection... (Endpoint: {LLM_BASE_URL}, Model: {LLM_MODEL})")
    res = inspect_with_vlm(img)
    print("\n" + "=" * 50)
    print("📊 [Inspection Result Summary]")
    print("=" * 50)
    for k, v in res.items():
        print(f"  - {k:18s}: {v}")
    print("=" * 50)
