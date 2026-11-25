#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Guided Collector] 가이드 인터랙티브 데이터 수집기
=============================================================================
- AI가 단계별로 "원하는 구도, 위치, 컨셉"을 한국어로 친절하게 가이드
- 사용자가 보드를 배치하고 [Enter]를 누르면 즉시 찰칵 촬영
- 총 10가지 필수 검사 시나리오(정상, 삐뚤어짐, 케이블 가림, 근접 등) 완전 정복
=============================================================================
"""

import os
import sys
import time
import cv2

from camera_streamer import get_camera_streamer

SAVE_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "raw_images")
os.makedirs(SAVE_DIR, exist_ok=True)

# 10가지 필수 시나리오 가이드북
GUIDED_STEPS = [
    {
        "step": 1,
        "title": "🎯 [정상 1] 정가운데 수직 정렬 (가장 완벽한 상태)",
        "guide": "보드를 카메라 화면 정가운데에 수평/수직 똑바로 놓아주세요. (리본 케이블 치우기)",
        "category": "normal_center"
    },
    {
        "step": 2,
        "title": "🎯 [정상 2] 약간 왼쪽으로 치우침",
        "guide": "보드를 왼쪽으로 2~3cm 정도 슥 밀어주세요. (보드 4개 모서리는 화면 안에 들어오게)",
        "category": "normal_left"
    },
    {
        "step": 3,
        "title": "🎯 [정상 3] 약간 오른쪽으로 치우침",
        "guide": "보드를 오른쪽으로 2~3cm 정도 슥 밀어주세요.",
        "category": "normal_right"
    },
    {
        "step": 4,
        "title": "📐 [회전 1] 시계 방향으로 15도 살짝 비틀기",
        "guide": "보드를 비스듬하게 15도 정도 살짝 돌려주세요. (실제 사용자가 대충 놓는 상황)",
        "category": "rotate_clockwise"
    },
    {
        "step": 5,
        "title": "📐 [회전 2] 반시계 방향으로 15도 살짝 비틀기",
        "guide": "보드를 반대 방향으로 15도 정도 비스듬하게 돌려주세요.",
        "category": "rotate_counter_clockwise"
    },
    {
        "step": 6,
        "title": "💡 [조명/거리] 카메라 살짝 가깝게 (초근접) or 높이 조절",
        "guide": "보드를 살짝 높여서 카메라와 가깝게 대거나 살짝 비춰주세요.",
        "category": "close_up"
    },
    {
        "step": 7,
        "title": "🚫 [이상/불량 1] 케이블이 보드를 가린 상황",
        "guide": "흰색 카메라 리본 케이블이나 전원선을 보드 기판 위로 살짝 지나가게 올려놓으세요.",
        "category": "cable_occlusion"
    },
    {
        "step": 8,
        "title": "🚫 [이상/불량 2] 보드 모서리가 화면 밖으로 잘린 상황",
        "guide": "보드를 화면 구석으로 밀어서, 기판 일부가 화면 밖으로 잘리게 놓아주세요.",
        "category": "out_of_bounds"
    },
    {
        "step": 9,
        "title": "🏷️ [자산 식별] 포스트잇 또는 메모지 올려두기",
        "guide": "보드 옆이나 위에 'RPI-01' 같은 메모지/라벨을 살짝 올려두거나 붙여주세요.",
        "category": "asset_label"
    },
    {
        "step": 10,
        "title": "🔴 [LED 점검] 전원선 연결 상태에서 최종 확인",
        "guide": "빨간 전원 LED가 가장 또렷하게 보이도록 정면에서 비춰주세요.",
        "category": "pwr_led_focus"
    }
]

def run_guided_collection():
    print("=" * 70)
    print("🎬 [Rentaly Guided Collector] 단계별 맞춤형 AI 데이터 수집기")
    print("👉 AI가 알려주는 위치/컨셉대로 보드를 두고 [Enter]를 누르면 찰칵 찍힙니다!")
    print(f"👉 저장 폴더: {os.path.abspath(SAVE_DIR)}")
    print("=" * 70)

    streamer = get_camera_streamer()
    time.sleep(1.5)  # 카메라 안정화

    for item in GUIDED_STEPS:
        step_num = item["step"]
        print(f"\n==================== [ {step_num} / {len(GUIDED_STEPS)} 단계 ] ====================")
        print(f"📌 미션: {item['title']}")
        print(f"👉 방법: {item['guide']}")
        print("----------------------------------------------------------------------")
        
        # 사용자가 준비될 때까지 대기!
        input(f"✅ 보드를 세팅하셨으면 [Enter] 키를 눌러주세요... ")

        # 캡처
        frame = streamer.get_latest_frame()
        if frame is None:
            print("⚠️ 카메라 프레임을 가져오지 못했습니다. 다시 시도합니다.")
            continue

        filename = f"{step_num:02d}_{item['category']}_{int(time.time())}.jpg"
        save_path = os.path.join(SAVE_DIR, filename)
        cv2.imwrite(save_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"📸 찰칵! [{filename}] 저장 완료! 멋집니다 👏")

    print("\n" + "=" * 70)
    print("🎉 축하합니다! 10가지 필수 검사 시나리오 데이터 수집이 모두 끝났습니다!")
    print("👉 이제 'python3 src/auto_pipeline.py' 를 실행하면 VLM 자동 라벨링이 진행됩니다.")
    print("=" * 70)

if __name__ == "__main__":
    run_guided_collection()
