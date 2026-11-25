#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Rentaly Edge Web Inspector] 라즈베리파이 AI 외관 검사 스튜디오 & 데이터 수집기
=============================================================================
- Picamera2 Continuous AutoFocus 실시간 프리뷰 (/video_feed)
- 스마트 무제한 가이드 데이터 수집기 (추천 프리셋 + 커스텀 무제한 촬영)
- VLM 지식 증류 오토 라벨링 & YOLO 파이프라인
- FactChat VLM 정밀 검사 & MQTT 단계별 텔레메트리
=============================================================================
"""

import os
import sys
import time
import io
import uuid
import json
import base64
import urllib.request
import urllib.error
import glob
import numpy as np
import cv2
from flask import Flask, render_template_string, request, jsonify, Response

# 카메라 스트리머 모듈
from camera_streamer import get_camera_streamer, HAS_PICAM2

# VLM 모듈 및 MQTT 모듈
from vlm_inspector import inspect_with_vlm, calculate_blur_score
from mqtt_publisher import get_telemetry_publisher
from auto_inspector_loop import get_auto_inspector
from led_controller import get_led_controller

app = Flask(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "")
DEVICE_SECRET = os.getenv("DEVICE_SECRET", "")
DEVICE_ID = os.getenv("DEVICE_ID", "station-01")

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATASET_RAW_DIR = os.path.join(BASE_DIR, "dataset", "raw_images")
os.makedirs(DATASET_RAW_DIR, exist_ok=True)

last_inspection_result = None
reposition_count = 0
last_inspection_bgr = None

# 체계적인 20가지 정밀 시나리오 프리셋
GUIDED_STEPS = [
    {"step": 1, "title": "🎯 [정상 1] 완벽한 정가운데 수직 정렬", "guide": "보드를 화면 정중앙에 똑바로 배치 (케이블을 완전히 치운 상태)", "category": "normal_center"},
    {"step": 2, "title": "🎯 [정상 2] 약간 좌측으로 이동", "guide": "보드를 왼쪽으로 2~3cm 슥 이동", "category": "normal_left"},
    {"step": 3, "title": "🎯 [정상 3] 약간 우측으로 이동", "guide": "보드를 오른쪽으로 2~3cm 슥 이동", "category": "normal_right"},
    {"step": 4, "title": "🎯 [정상 4] 약간 상단(위쪽)으로 이동", "guide": "보드를 위쪽으로 2~3cm 살짝 밀어두기", "category": "normal_top"},
    {"step": 5, "title": "🎯 [정상 5] 약간 하단(아래쪽)으로 이동", "guide": "보드를 아래쪽으로 2~3cm 살짝 당겨두기", "category": "normal_bottom"},
    {"step": 6, "title": "📐 [회전 1] 시계 방향 15도", "guide": "보드를 오른쪽으로 비스듬히 살짝 돌려두기", "category": "rotate_cw_15"},
    {"step": 7, "title": "📐 [회전 2] 반시계 방향 15도", "guide": "보드를 왼쪽으로 비스듬히 살짝 돌려두기", "category": "rotate_ccw_15"},
    {"step": 8, "title": "📐 [회전 3] 90도 회전 (세로 배치)", "guide": "보드를 90도 돌려 세로 모양으로 배치", "category": "rotate_90"},
    {"step": 9, "title": "💡 [거리 1] 카메라 초근접 (확대)", "guide": "보드를 살짝 들어 올려 카메라 렌즈에 가깝게 접근", "category": "dist_close"},
    {"step": 10, "title": "💡 [거리 2] 카메라 원거리 (축소)", "guide": "보드를 조금 더 멀리 내려놓기", "category": "dist_far"},
    {"step": 11, "title": "🚫 [이상 1] 리본 케이블 가림", "guide": "흰색 카메라 리본선이 보드 기판을 가로지르게 배치", "category": "cable_occlusion"},
    {"step": 12, "title": "🚫 [이상 2] 전원/USB선 가림", "guide": "검은색 케이블선이나 손가락이 기판 일부를 살짝 가리게 배치", "category": "hand_cable_occlusion"},
    {"step": 13, "title": "🚫 [이상 3] 좌측 화면 이탈 (잘림)", "guide": "보드 왼쪽 모서리가 화면 테두리 밖으로 삐져나가게 배치", "category": "cut_left"},
    {"step": 14, "title": "🚫 [이상 4] 우측 화면 이탈 (잘림)", "guide": "보드 오른쪽 모서리가 화면 테두리 밖으로 삐져나가게 배치", "category": "cut_right"},
    {"step": 15, "title": "🚫 [이상 5] 상단/하단 화면 이탈 (잘림)", "guide": "보드 위나 아래가 화면 밖으로 잘리게 배치", "category": "cut_top_bottom"},
    {"step": 16, "title": "🏷️ [라벨 1] 기판 위 자산 포스트잇", "guide": "'RPI-01' 같은 자산 번호 메모지를 기판 위에 얹기", "category": "asset_label_on"},
    {"step": 17, "title": "🏷️ [라벨 2] 보드 주변 메모지", "guide": "메모지를 보드 바로 옆에 나란히 두기", "category": "asset_label_side"},
    {"step": 18, "title": "🔴 [LED 1] 빨간 PWR LED 강조", "guide": "전원선 연결 상태에서 빨간 LED가 똑똑히 보이게 배치", "category": "pwr_led_on"},
    {"step": 19, "title": "🌑 [환경 1] 그림자/어두운 조명", "guide": "손으로 그림자를 살짝 지게 하거나 조명을 가려보세요", "category": "lighting_shadow"},
    {"step": 20, "title": "✨ [환경 2] 빛 반사/아크릴 케이스", "guide": "케이스에 빛이 반사되는 각도 연출", "category": "lighting_glare"}
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rentaly AI 외관 검사 & 학습 데이터 스튜디오</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #121212;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            max-width: 1060px;
            width: 100%;
        }
        h1 {
            color: #4caf50;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 26px;
        }
        .subtitle {
            color: #888;
            margin-top: 0;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .tab-bar {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }
        .tab-btn {
            background: #222;
            color: #aaa;
            border: 1px solid #444;
            padding: 10px 18px;
            font-size: 15px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .tab-btn.active {
            background: #2e7d32;
            color: #fff;
            border-color: #4caf50;
        }
        .view-panel {
            background: #1e1e1e;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }
        .streams-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 20px;
        }
        @media (max-width: 768px) {
            .streams-grid { grid-template-columns: 1fr; }
        }
        .screen-card {
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #333;
            display: flex;
            flex-direction: column;
        }
        .screen-header {
            background: #222;
            padding: 8px 12px;
            font-size: 13px;
            font-weight: bold;
            color: #aaa;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #333;
        }
        .screen-box {
            width: 100%;
            height: 320px;
            background: #000;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }
        .screen-box img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        .live-tag {
            background: #d50000;
            color: #fff;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }

        .guide-box {
            background: #1a2a1a;
            border: 2px solid #2e7d32;
            border-radius: 10px;
            padding: 18px;
            margin-bottom: 20px;
        }
        .guide-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .guide-step-tag {
            background: #4caf50;
            color: #000;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 800;
            font-size: 13px;
        }
        .guide-title {
            font-size: 18px;
            font-weight: bold;
            color: #fff;
            margin: 6px 0;
        }
        .guide-desc {
            color: #a5d6a7;
            font-size: 15px;
            line-height: 1.5;
            margin-bottom: 16px;
        }
        .guide-actions {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }

        button.btn-action {
            background: #2e7d32;
            color: white;
            border: none;
            padding: 11px 18px;
            font-size: 14px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        button.btn-action:hover { background: #388e3c; }
        button.btn-action:disabled { background: #555; cursor: not-allowed; }
        button.btn-free { background: #0277bd; }
        button.btn-free:hover { background: #0288d1; }
        button.btn-train { background: #6a1b9a; }
        button.btn-train:hover { background: #7b1fa2; }
        button.btn-backend { background: #e65100; }
        button.btn-backend:hover { background: #f57c00; }
        button.btn-delete { background: #c62828; padding: 6px 12px; font-size: 12px; }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 18px;
        }
        .metric-card {
            background: #2a2a2a;
            padding: 12px;
            border-radius: 8px;
            border-left: 4px solid #4caf50;
        }
        .metric-title { color: #888; font-size: 12px; margin-bottom: 4px; }
        .metric-value { font-size: 16px; font-weight: bold; color: #fff; word-break: break-all; }

        .text-detail-box {
            background: #252525;
            padding: 14px;
            border-radius: 8px;
            margin-bottom: 14px;
            border-left: 4px solid #00bcd4;
        }
        .text-detail-box h4 { margin: 0 0 8px 0; color: #00bcd4; }
        .reason-box {
            background: #282828;
            padding: 14px;
            border-radius: 8px;
            border-left: 4px solid #ab47bc;
            margin-bottom: 14px;
        }
        .reason-box h4 { margin: 0 0 6px 0; color: #ab47bc; }
        .status-badge {
            font-size: 18px;
            font-weight: 800;
            padding: 8px 16px;
            border-radius: 6px;
            display: inline-block;
            margin-bottom: 15px;
        }
        .badge-PASS { background: #00c853; color: white; }
        .badge-FAIL { background: #ff9100; color: white; }
        .badge-REPOSITION { background: #d50000; color: white; }
        .badge-READY { background: #424242; color: #aaa; }
        
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
            gap: 10px;
            max-height: 280px;
            overflow-y: auto;
            padding: 10px;
            background: #111;
            border-radius: 8px;
            border: 1px solid #333;
        }
        .gallery-item {
            height: 100px;
            background: #000;
            border-radius: 6px;
            border: 1px solid #444;
            overflow: hidden;
            position: relative;
        }
        .gallery-item img { width: 100%; height: 100%; object-fit: cover; }
        .gallery-item span {
            position: absolute;
            bottom: 2px;
            left: 2px;
            background: rgba(0,0,0,0.8);
            font-size: 10px;
            padding: 1px 4px;
            border-radius: 3px;
            max-width: 90%;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 Rentaly AI 외관 검사 & 학습 데이터 스튜디오</h1>
        <p class="subtitle">실시간 라이브 카메라 + 스마트 무제한 데이터 수집기 + FactChat VLM 검사</p>

        <!-- 탭 메뉴 -->
        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchTab('tab-inspect')">🔍 실시간 외관 검사 모드</button>
            <button class="tab-btn" onclick="switchTab('tab-collect')">📸 스마트 데이터 수집 & 학습 모드</button>
        </div>

        <div class="view-panel">
            <!-- 공통 실시간 프리뷰 영역 -->
            <div class="streams-grid">
                <div class="screen-card">
                    <div class="screen-header">
                        <span>🔴 실시간 카메라 프리뷰 (/video_feed)</span>
                        <span class="live-tag">LIVE</span>
                    </div>
                    <div class="screen-box">
                        <img src="/video_feed" alt="실시간 카메라 스트림">
                    </div>
                </div>

                <div class="screen-card">
                    <div class="screen-header">
                        <span id="preview-title">📸 캡처 스틸샷</span>
                        <span id="capture-time" style="color: #666;">-</span>
                    </div>
                    <div class="screen-box">
                        <img id="result-img" src="" style="display: none;" alt="캡처 이미지">
                        <div id="placeholder" style="color: #666; font-size: 14px;">
                            캡처 버튼을 누르면 사진이 표시됩니다
                        </div>
                    </div>
                </div>
            </div>

            <!-- [탭 1: 검사 모드] -->
            <div id="tab-inspect">
                <div style="display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap;">
                    <button class="btn-action" onclick="takeSnapshot()">
                        📸 현재 화면 캡처 & AI 정밀 검사
                    </button>
                    <button id="btn-backend" class="btn-action btn-backend" onclick="sendToBackend()" disabled>
                        🚀 백엔드 서버로 결과 전송 (POST)
                    </button>
                    <span id="loading-inspect" style="display: none; color: #ffeb3b; font-weight: bold;">⏳ 검사 진행 중...</span>
                </div>

                <div id="status-box">
                    <span class="status-badge badge-READY">READY (준비 완료)</span>
                </div>

                <div class="metrics-grid">
                    <div class="metric-card" style="border-left-color: #2196f3;">
                        <div class="metric-title">선명도 (블러 점수 / 기준: 80)</div>
                        <div class="metric-value" id="val-blur">-</div>
                    </div>
                    <div class="metric-card" style="border-left-color: #ff9800;">
                        <div class="metric-title">온보드 빨간 전원 LED</div>
                        <div class="metric-value" id="val-led">-</div>
                    </div>
                    <div class="metric-card" style="border-left-color: #e91e63;">
                        <div class="metric-title">외관 결함 유형 (Defect)</div>
                        <div class="metric-value" id="val-defect">-</div>
                    </div>
                    <div class="metric-card" style="border-left-color: #4caf50;">
                        <div class="metric-title">판정 지연시간 (Latancy)</div>
                        <div class="metric-value" id="val-infer">-</div>
                    </div>
                </div>

                <div class="text-detail-box">
                    <h4>🔤 기판 실크스크린 OCR & 식별 번호 판독</h4>
                    <div style="display: flex; flex-direction: column; gap: 6px; font-size: 14px;">
                        <div>• <b>추출 모델명:</b> <span id="val-model" style="color: #4fc3f7; font-weight: bold;">-</span></div>
                        <div>• <b>IC 전파인증 번호:</b> <span id="val-ic" style="color: #ffca28; font-weight: bold;">-</span></div>
                        <div>• <b>FCC ID 식별 번호:</b> <span id="val-fcc" style="color: #81c784; font-weight: bold;">-</span></div>
                        <div>• <b>기기 고유 번호 / 시리얼:</b> <span id="val-serial" style="color: #e040fb; font-weight: bold;">-</span></div>
                        <div>• <b>보드 온전 노출 여부:</b> <span id="val-visible" style="font-weight: bold;">-</span></div>
                    </div>
                </div>

                <div class="reason-box">
                    <h4>📝 AI 정밀 판정 소견</h4>
                    <div id="val-reason" style="line-height: 1.5; color: #ddd; font-size: 14px;">
                        검사 결과가 여기에 상세히 표시됩니다.
                    </div>
                </div>

                <div id="backend-result" style="display:none; background:#1b2e1b; border:1px solid #2e7d32; padding:12px; border-radius:6px; color:#81c784; font-family:monospace; margin-top:15px;"></div>
            </div>

            <!-- [탭 2: 수집 & 학습 모드] -->
            <div id="tab-collect" style="display: none;">
                <div class="guide-box">
                    <div class="guide-header">
                        <span class="guide-step-tag" id="guide-step-tag">추천 미션 1 / 20</span>
                        <span style="color: #888; font-size: 13px;" id="collected-summary">수집된 데이터: 0장</span>
                    </div>
                    <div class="guide-title" id="guide-title">🎯 [정상 1] 완벽한 정가운데 수직 정렬</div>
                    <div class="guide-desc" id="guide-desc">보드를 화면 정중앙에 똑바로 배치 (케이블을 완전히 치운 상태)</div>
                    <div class="guide-actions">
                        <button class="btn-action" id="btn-collect-shot" onclick="captureGuidedStep()">
                            📸 [가이드 미션 찰칵]
                        </button>
                        <button class="btn-action btn-free" onclick="captureFreeStep()">
                            ➕ [자유 촬영] 내가 원하는 구도 자유롭게 추가 촬영
                        </button>
                        <button class="btn-action" style="background:#555;" onclick="skipGuidedStep()">
                            ⏩ 다음 미션
                        </button>
                        <span id="loading-collect" style="display: none; color: #ffeb3b; font-weight: bold;">⏳ 저장 중...</span>
                    </div>
                </div>

                <div style="margin-top: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 10px;">
                        <div>
                            <h4 style="margin: 0; color: #aaa; display: inline;">📁 수집된 사진 갤러리</h4>
                            <span style="font-size: 12px; color: #777; margin-left: 8px;">(정상 작동할 때까지 계속 추가 가능)</span>
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <button class="btn-action btn-delete" onclick="clearDataset()">🗑️ 전체 초기화</button>
                            <button class="btn-action btn-train" onclick="runAutoPipeline()">
                                🤖 VLM 자동 라벨링 & YOLO 파이프라인 가동!
                            </button>
                        </div>
                    </div>
                    <div class="gallery" id="gallery-box">
                        <span style="color: #666; font-size: 13px;">아직 수집된 이미지가 없습니다.</span>
                    </div>
                </div>
            </div>

        </div>
    </div>

    <script>
        const guidedSteps = {{ guided_steps | tojson }};
        let currentStepIdx = 0;

        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            if (tabId === 'tab-inspect') {
                document.querySelectorAll('.tab-btn')[0].classList.add('active');
                document.getElementById('tab-inspect').style.display = 'block';
                document.getElementById('tab-collect').style.display = 'none';
                document.getElementById('preview-title').innerText = '📸 검사 캡처 스틸샷';
            } else {
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('tab-inspect').style.display = 'none';
                document.getElementById('tab-collect').style.display = 'block';
                document.getElementById('preview-title').innerText = '📸 수집된 훈련 이미지';
                loadGallery();
            }
        }

        function updateGuideUI() {
            const s = guidedSteps[currentStepIdx % guidedSteps.length];
            document.getElementById('guide-step-tag').innerText = `추천 미션 ${(currentStepIdx % guidedSteps.length) + 1} / ${guidedSteps.length}`;
            document.getElementById('guide-title').innerText = s.title;
            document.getElementById('guide-desc').innerText = s.guide;
        }

        async function captureGuidedStep() {
            const s = guidedSteps[currentStepIdx % guidedSteps.length];
            await doCapture(s.step, s.category);
            currentStepIdx++;
            updateGuideUI();
        }

        async function captureFreeStep() {
            const label = prompt("이 사진의 특징/라벨을 간단히 적어주세요 (예: 케이블가림, 핀휨, 비스듬)", "free_sample") || "custom";
            await doCapture(99, label);
        }

        async function doCapture(step, category) {
            document.getElementById('loading-collect').style.display = 'inline-block';
            try {
                const res = await fetch('/api/guided_capture', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ step: step, category: category })
                });
                const data = await res.json();
                if (data.success) {
                    const img = document.getElementById('result-img');
                    img.src = 'data:image/jpeg;base64,' + data.image_base64;
                    img.style.display = 'block';
                    document.getElementById('placeholder').style.display = 'none';
                    document.getElementById('capture-time').innerText = new Date().toLocaleTimeString();
                    loadGallery();
                } else {
                    alert('에러: ' + data.error);
                }
            } catch (err) {
                alert('수집 실패: ' + err);
            } finally {
                document.getElementById('loading-collect').style.display = 'none';
            }
        }

        function skipGuidedStep() {
            currentStepIdx = (currentStepIdx + 1) % guidedSteps.length;
            updateGuideUI();
        }

        async function loadGallery() {
            try {
                const res = await fetch('/api/gallery');
                const data = await res.json();
                const box = document.getElementById('gallery-box');
                document.getElementById('collected-summary').innerText = `수집된 데이터: ${data.images.length}장`;
                if (data.images.length === 0) {
                    box.innerHTML = '<span style="color: #666; font-size: 13px;">아직 수집된 이미지가 없습니다. 버튼을 눌러 촬영하세요!</span>';
                    return;
                }
                box.innerHTML = data.images.map(img => `
                    <div class="gallery-item">
                        <img src="/api/image_raw/${img.name}" alt="${img.name}">
                        <span>${img.category}</span>
                    </div>
                `).join('');
            } catch (e) {
                console.error(e);
            }
        }

        async function clearDataset() {
            if (!confirm('수집된 모든 사진을 삭제하고 처음부터 다시 찍을까요?')) return;
            await fetch('/api/clear_gallery', { method: 'POST' });
            currentStepIdx = 0;
            updateGuideUI();
            loadGallery();
        }

        async function runAutoPipeline() {
            if (!confirm('수집된 사진들에 대해 FactChat VLM 오토 라벨링 및 YOLO 데이터셋 생성을 진행할까요?')) return;
            alert('라즈베리파이에서 VLM 자동 라벨링이 백그라운드로 시작됩니다! 완료 후 콘솔 및 데이터셋에 저장됩니다.');
            fetch('/api/run_pipeline', { method: 'POST' });
        }

        // [검사 탭 로직]
        function updateUI(data) {
            document.getElementById('loading-inspect').style.display = 'none';
            document.getElementById('btn-backend').disabled = (data.primary_verdict === 'REPOSITION' || data.primary_verdict === 'ERROR');

            const badge = document.querySelector('.status-badge');
            badge.className = 'status-badge badge-' + data.primary_verdict;
            badge.innerText = data.primary_verdict + ' (결함: ' + (data.defect_type || 'NONE') + ')';

            document.getElementById('val-blur').innerText = data.blur_score + ' 점';
            document.getElementById('val-led').innerText = data.pwr_led_status ? '🔴 SOLID ON (점등)' : '⚪ OFF (소등)';
            document.getElementById('val-defect').innerText = data.defect_type || 'NONE';
            document.getElementById('val-infer').innerText = data.infer_ms + ' ms';

            document.getElementById('val-model').innerText = data.model_text || '식별 불가';
            document.getElementById('val-ic').innerText = data.ic_id_text || '미검출';
            document.getElementById('val-fcc').innerText = data.fcc_id_text || '미검출';
            document.getElementById('val-serial').innerText = data.device_unique_id || '없음 (기판 번호 사용)';
            
            const visibleSpan = document.getElementById('val-visible');
            if (data.is_fully_visible) {
                visibleSpan.style.color = '#00e676';
                visibleSpan.innerText = '✅ 완전 노출 (4면 모두 프레임 내부)';
            } else {
                visibleSpan.style.color = '#ff1744';
                visibleSpan.innerText = '❌ 잘림 감지 (보드 일부분이 화면 밖으로 나감)';
            }

            document.getElementById('val-reason').innerText = data.reason;

            const img = document.getElementById('result-img');
            img.src = 'data:image/jpeg;base64,' + data.image_base64;
            img.style.display = 'block';
            document.getElementById('placeholder').style.display = 'none';
            document.getElementById('capture-time').innerText = new Date().toLocaleTimeString();
        }

        async function takeSnapshot() {
            document.getElementById('loading-inspect').style.display = 'inline-block';
            document.getElementById('backend-result').style.display = 'none';

            try {
                const res = await fetch('/api/capture', { method: 'POST' });
                const data = await res.json();
                if (data.error) {
                    alert('에러: ' + data.error);
                } else {
                    updateUI(data);
                }
            } catch (err) {
                alert('요청 실패: ' + err);
            } finally {
                document.getElementById('loading-inspect').style.display = 'none';
            }
        }

        async function sendToBackend() {
            const btn = document.getElementById('btn-backend');
            const resBox = document.getElementById('backend-result');
            btn.disabled = true;
            btn.innerText = '⏳ 백엔드 전송 중...';

            try {
                const res = await fetch('/api/submit_backend', { method: 'POST' });
                const data = await res.json();
                resBox.style.display = 'block';
                if (data.success) {
                    resBox.innerHTML = '<b>✅ 백엔드 등록 성공!</b><br><pre>' + JSON.stringify(data.backend_response, null, 2) + '</pre>';
                } else {
                    resBox.innerHTML = '<b>❌ 백엔드 등록 실패:</b> ' + (data.error || '알 수 없는 오류');
                }
            } catch (err) {
                resBox.style.display = 'block';
                resBox.innerHTML = '<b>❌ 통신 실패:</b> ' + err;
            } finally {
                btn.disabled = false;
                btn.innerText = '🚀 백엔드 서버로 결과 전송 (POST)';
            }
        }
    </script>
</body>
</html>
"""



def _send_result_to_backend(insp_id, res_dict, img_bgr):
    if not BACKEND_URL:
        print("ℹ️ [Backend] BACKEND_URL 미설정 — 로컬 단독 모드로 동작하여 DB 전송을 건너뜁니다.")
        return None
    metadata = {
        "device_id": DEVICE_ID,
        "inspection_id": insp_id,
        "equipment_id": "rpi4-device-01",
        "recognized_serial_number": res_dict.get("device_unique_id") or None,
        "primary_verdict": res_dict.get("primary_verdict", "FAIL"),
        "blur_score": float(res_dict.get("blur_score", 0.0)),
        "pwr_led_status": bool(res_dict.get("pwr_led_status", False)),
        "fcc_id_matched": bool(res_dict.get("fcc_id_matched", False)),
        "fcc_id_text": str(res_dict.get("fcc_id_text", "")),
        "metadata": {
            "defect_type": res_dict.get("defect_type", "NONE"),
            "model_text": res_dict.get("model_text", ""),
            "confidence": res_dict.get("confidence", 0.0),
            "reason": res_dict.get("reason", "")
        }
    }
    h, w = img_bgr.shape[:2]
    if max(h, w) > 1280:
        scale = 1280 / max(h, w)
        img_send = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        img_send = img_bgr
    _, img_jpg = cv2.imencode(".jpg", img_send, [cv2.IMWRITE_JPEG_QUALITY, 85])

    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "X-Device-Secret": DEVICE_SECRET
    }
    body = [
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="metadata"',
        b"Content-Type: application/json\r\n",
        json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="image"; filename="inspection.jpg"',
        b"Content-Type: image/jpeg\r\n",
        img_jpg.tobytes(),
        f"--{boundary}--\r\n".encode()
    ]
    req = urllib.request.Request(BACKEND_URL, headers=headers, data=b"\r\n".join(body))
    with urllib.request.urlopen(req, timeout=10) as resp:
        backend_res = json.loads(resp.read().decode("utf-8"))
        print(f"🚀 [Backend DB 저장 성공!] ID={insp_id} -> {backend_res}")
        return backend_res

def process_and_inspect(img_bgr):
    global last_inspection_result, last_inspection_bgr, reposition_count
    last_inspection_bgr = img_bgr.copy()
    insp_id = str(uuid.uuid4())
    publisher = get_telemetry_publisher()
    led_ctrl = get_led_controller()
    led_ctrl.set_inspecting()

    thumb = cv2.resize(img_bgr, (480, 320), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
    capture_image_url = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")

    blur_score = calculate_blur_score(img_bgr)

    # 1. OCR 단계 & 캡처 사진 전달
    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="OCR",
        progress_percent=25,
        message="보드 표면의 고유 시리얼 번호를 인식하고 있습니다...",
        blur_score=blur_score,
        stabilization_ms=300,
        capture_image_url=capture_image_url
    )

    result = inspect_with_vlm(img_bgr)
    result["inspection_id"] = insp_id
    result["capture_image_url"] = capture_image_url

    time.sleep(0.4)

    # 2. LED 확인 단계
    pwr_on = bool(result.get("pwr_led_status", False))
    if not pwr_on and result.get("primary_verdict") != "REPOSITION":
        # REPOSITION(손 가림/잘림)이 아닐 때만 PWR LED 미점등을 FAIL로 강제 전환
        result["primary_verdict"] = "FAIL"
        if not result.get("reason"):
            result["reason"] = "전원 PWR LED가 꺼져 있습니다."
        led_msg = "PWR LED 미점등 (전원 불량)"
    elif not pwr_on:
        led_msg = "보드가 가려지거나 잘려 LED 확인 불가"
    else:
        led_msg = "온보드 PWR LED 정상 점등 확인"

    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="LED_CHECK",
        progress_percent=60,
        message=led_msg,
        blur_score=blur_score,
        stabilization_ms=300
    )

    time.sleep(0.4)

    # 3. AI 외관 검사 단계
    verdict = result.get("primary_verdict", "FAIL")
    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="AI_INFERENCE",
        progress_percent=85,
        message=f"AI 모델 외관 분석 완료 ({verdict})",
        blur_score=blur_score,
        stabilization_ms=300
    )

    # 화면에서 체크마크 인지할 수 있도록 1.2초 대기
    time.sleep(1.2)

    # 4. 최종 완료 or 재배치 화면 전환
    if verdict == "PASS":
        led_ctrl.set_pass()
    else:
        led_ctrl.set_fail_or_reposition()

    if verdict == "REPOSITION":
        reposition_count += 1
        publisher.publish_telemetry(
            inspection_id=insp_id,
            stage="REPOSITION",
            progress_percent=100,
            message=result.get("reason", "보드를 다시 놓아주세요."),
            blur_score=blur_score,
            stabilization_ms=300,
            reposition_count=reposition_count
        )
    else:
        reposition_count = 0
        publisher.publish_telemetry(
            inspection_id=insp_id,
            stage="COMPLETED",
            progress_percent=100,
            message=f"검사가 완료되었습니다. 최종 결과: {verdict}",
            blur_score=blur_score,
            stabilization_ms=300
        )
    _, full_buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    result["image_base64"] = base64.b64encode(full_buf).decode("utf-8")
    last_inspection_result = result

    # 5. REPOSITION이 아닌 최종 판정(PASS / FAIL)일 때 백엔드 DB로 자동 전송!
    if verdict in ["PASS", "FAIL"]:
        try:
            _send_result_to_backend(insp_id, result, img_bgr)
        except Exception as e:
            print(f"⚠️ [Backend] 자동 전송 중 예외: {e}")

    return result


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, guided_steps=GUIDED_STEPS)


@app.route("/video_feed")
def video_feed():
    streamer = get_camera_streamer()
    get_auto_inspector() # MQTT 명령 수신기 및 루프 기동
    if not streamer.running:
        return "Camera not running", 503
    return Response(streamer.generate_mjpeg(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/start_inspection", methods=["POST"])
def start_inspection_endpoint():
    mgr = get_auto_inspector()
    ok, msg = mgr.trigger_start()
    return jsonify({"success": ok, "message": msg})

@app.route("/api/capture", methods=["POST"])
def capture_and_inspect():
    streamer = get_camera_streamer()
    get_auto_inspector() # MQTT 명령 수신기 및 루프 기동
    bgr = streamer.get_latest_frame()
    if bgr is None:
        return jsonify({"error": "카메라 프레임을 가져올 수 없습니다."}), 500

    try:
        res = process_and_inspect(bgr)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/guided_capture", methods=["POST"])
def guided_capture():
    data = request.json or {}
    step = data.get("step", 1)
    category = data.get("category", "sample")

    streamer = get_camera_streamer()
    get_auto_inspector() # MQTT 명령 수신기 및 루프 기동
    bgr = streamer.get_latest_frame()
    if bgr is None:
        return jsonify({"success": False, "error": "카메라 프레임 획득 실패"}), 500

    filename = f"{step:02d}_{category}_{int(time.time())}.jpg"
    save_path = os.path.join(DATASET_RAW_DIR, filename)
    cv2.imwrite(save_path, bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])

    _, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_str = base64.b64encode(buf).decode("utf-8")

    return jsonify({
        "success": True,
        "filename": filename,
        "image_base64": b64_str
    })


@app.route("/api/gallery", methods=["GET"])
def get_gallery():
    files = glob.glob(os.path.join(DATASET_RAW_DIR, "*.jpg"))
    files.sort(reverse=True)
    images = []
    for f in files:
        name = os.path.basename(f)
        parts = name.split("_")
        cat = parts[1] if len(parts) > 1 else "sample"
        images.append({"name": name, "category": cat})
    return jsonify({"images": images})


@app.route("/api/clear_gallery", methods=["POST"])
def clear_gallery():
    files = glob.glob(os.path.join(DATASET_RAW_DIR, "*.jpg"))
    for f in files:
        try:
            os.remove(f)
        except Exception:
            pass
    return jsonify({"success": True})


@app.route("/api/image_raw/<path:filename>")
def get_raw_image(filename):
    path = os.path.join(DATASET_RAW_DIR, filename)
    if not os.path.exists(path):
        return "Not found", 404
    with open(path, "rb") as f:
        return Response(f.read(), mimetype="image/jpeg")


@app.route("/api/run_pipeline", methods=["POST"])
def trigger_pipeline():
    os.system(f"python3 {os.path.join(os.path.dirname(__file__), 'auto_pipeline.py')} &")
    return jsonify({"success": True, "message": "파이프라인 백그라운드 구동 시작"})


@app.route("/api/submit_backend", methods=["POST"])
def submit_to_backend():
    global last_inspection_result, last_inspection_bgr
    if last_inspection_result is None or last_inspection_bgr is None:
        return jsonify({"error": "전송할 최근 검사 결과가 없습니다."}), 400

    insp_id = str(uuid.uuid4())
    metadata = {
        "device_id": DEVICE_ID,
        "inspection_id": insp_id,
        "equipment_id": "rpi4-device-01",
        "recognized_serial_number": res_dict.get("device_unique_id") or None,
        "primary_verdict": last_inspection_result.get("primary_verdict", "FAIL"),
        "blur_score": float(last_inspection_result.get("blur_score", 0.0)),
        "pwr_led_status": bool(last_inspection_result.get("pwr_led_status", False)),
        "fcc_id_matched": bool(last_inspection_result.get("fcc_id_matched", False)),
        "fcc_id_text": str(last_inspection_result.get("fcc_id_text", "")),
        "metadata": {
            "defect_type": last_inspection_result.get("defect_type", "NONE"),
            "model_text": last_inspection_result.get("model_text", ""),
            "confidence": last_inspection_result.get("confidence", 0.0),
            "reason": last_inspection_result.get("reason", "")
        }
    }

    h, w = last_inspection_bgr.shape[:2]
    if max(h, w) > 1280:
        scale = 1280 / max(h, w)
        img_send = cv2.resize(last_inspection_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        img_send = last_inspection_bgr
    _, img_jpg = cv2.imencode(".jpg", img_send, [cv2.IMWRITE_JPEG_QUALITY, 85])

    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "X-Device-Secret": DEVICE_SECRET
    }

    body = []
    body.append(f"--{boundary}".encode())
    body.append(b'Content-Disposition: form-data; name="metadata"')
    body.append(b"Content-Type: application/json\r\n")
    body.append(json.dumps(metadata, ensure_ascii=False).encode("utf-8"))

    body.append(f"--{boundary}".encode())
    body.append(b'Content-Disposition: form-data; name="image"; filename="inspection.jpg"')
    body.append(b"Content-Type: image/jpeg\r\n")
    body.append(img_jpg.tobytes())

    body.append(f"--{boundary}--\r\n".encode())
    payload_data = b"\r\n".join(body)

    req = urllib.request.Request(BACKEND_URL, headers=headers, data=payload_data)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            backend_res = json.loads(resp.read().decode("utf-8"))
            return jsonify({"success": True, "backend_response": backend_res})
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return jsonify({"success": False, "error": f"HTTP {e.code}: {err_msg}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Rentaly AI 외관 검사 & 엣지 서버")
    parser.add_argument("--image", "-i", dest="image", help="카메라 대신 사용할 테스트 이미지 경로")
    parser.add_argument("--port", "-p", type=int, default=8080, help="웹 서버 포트 (기본 8080)")
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 Rentaly AI 외관 검사 & 학습 데이터 스튜디오")
    print(f"👉 대시보드 주소: http://localhost:{args.port}")
    if args.image:
        print(f"🖼️ 테스트 이미지 모드: {args.image}")
    print("=" * 60)
    get_camera_streamer(test_image_path=args.image)
    get_auto_inspector()  # MQTT 명령 수신기 및 루프 기동
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
