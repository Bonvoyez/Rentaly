#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Rentaly Edge Web Inspector] Raspberry Pi AI Exterior Inspection Studio & Data Collector
=============================================================================
- Picamera2 Continuous AutoFocus real-time preview (/video_feed)
- Smart unlimited guided data collector (recommended presets + custom unlimited capture)
- VLM knowledge distillation auto-labeling & YOLO pipeline
- FactChat VLM precision inspection & MQTT step-by-step telemetry
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

# Camera streamer module
from camera_streamer import get_camera_streamer, HAS_PICAM2

# VLM module and MQTT module
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

# Systematic 20 precision scenario presets
GUIDED_STEPS = [
    {"step": 1, "title": "🎯 [Normal 1] Perfect centered vertical alignment", "guide": "Place the board straight in the center of the frame (cables completely out of the way)", "category": "normal_center"},
    {"step": 2, "title": "🎯 [Normal 2] Slightly shifted left", "guide": "Slide the board 2-3cm to the left", "category": "normal_left"},
    {"step": 3, "title": "🎯 [Normal 3] Slightly shifted right", "guide": "Slide the board 2-3cm to the right", "category": "normal_right"},
    {"step": 4, "title": "🎯 [Normal 4] Slightly shifted up (top)", "guide": "Push the board 2-3cm upward", "category": "normal_top"},
    {"step": 5, "title": "🎯 [Normal 5] Slightly shifted down (bottom)", "guide": "Pull the board 2-3cm downward", "category": "normal_bottom"},
    {"step": 6, "title": "📐 [Rotation 1] Clockwise 15 degrees", "guide": "Tilt the board slightly to the right", "category": "rotate_cw_15"},
    {"step": 7, "title": "📐 [Rotation 2] Counter-clockwise 15 degrees", "guide": "Tilt the board slightly to the left", "category": "rotate_ccw_15"},
    {"step": 8, "title": "📐 [Rotation 3] 90-degree rotation (vertical)", "guide": "Rotate the board 90 degrees into a vertical orientation", "category": "rotate_90"},
    {"step": 9, "title": "💡 [Distance 1] Camera close-up (zoom in)", "guide": "Lift the board slightly closer to the camera lens", "category": "dist_close"},
    {"step": 10, "title": "💡 [Distance 2] Camera far (zoom out)", "guide": "Place the board slightly further away", "category": "dist_far"},
    {"step": 11, "title": "🚫 [Defect 1] Ribbon cable occlusion", "guide": "Place the white camera ribbon cable across the PCB", "category": "cable_occlusion"},
    {"step": 12, "title": "🚫 [Defect 2] Power/USB cable occlusion", "guide": "Place a black cable or finger slightly covering part of the PCB", "category": "hand_cable_occlusion"},
    {"step": 13, "title": "🚫 [Defect 3] Left edge out of frame (cropped)", "guide": "Place the board so the left edge extends outside the frame", "category": "cut_left"},
    {"step": 14, "title": "🚫 [Defect 4] Right edge out of frame (cropped)", "guide": "Place the board so the right edge extends outside the frame", "category": "cut_right"},
    {"step": 15, "title": "🚫 [Defect 5] Top/bottom out of frame (cropped)", "guide": "Place the board so the top or bottom is cut off", "category": "cut_top_bottom"},
    {"step": 16, "title": "🏷️ [Label 1] Asset sticky note on PCB", "guide": "Place an asset ID memo like 'RPI-01' on top of the PCB", "category": "asset_label_on"},
    {"step": 17, "title": "🏷️ [Label 2] Memo note near board", "guide": "Place a memo note right next to the board", "category": "asset_label_side"},
    {"step": 18, "title": "🔴 [LED 1] Red PWR LED highlight", "guide": "Ensure the red LED is clearly visible with power connected", "category": "pwr_led_on"},
    {"step": 19, "title": "🌑 [Env 1] Shadow / dark lighting", "guide": "Cast a slight shadow with your hand or dim the light", "category": "lighting_shadow"},
    {"step": 20, "title": "✨ [Env 2] Light glare / acrylic case", "guide": "Angle the case so light reflects off the surface", "category": "lighting_glare"}
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
        <h1>🔬 Rentaly AI Exterior Inspection & Training Data Studio</h1>
        <p class="subtitle">Live Camera + Smart Unlimited Data Collector + FactChat VLM Inspection</p>

        <!-- Tab Menu -->
        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchTab('tab-inspect')">🔍 Live Exterior Inspection Mode</button>
            <button class="tab-btn" onclick="switchTab('tab-collect')">📸 Smart Data Collection & Training Mode</button>
        </div>

        <div class="view-panel">
            <!-- Common Live Preview Area -->
            <div class="streams-grid">
                <div class="screen-card">
                    <div class="screen-header">
                        <span>🔴 Live Camera Preview (/video_feed)</span>
                        <span class="live-tag">LIVE</span>
                    </div>
                    <div class="screen-box">
                        <img src="/video_feed" alt="Live Camera Stream">
                    </div>
                </div>

                <div class="screen-card">
                    <div class="screen-header">
                        <span id="preview-title">📸 Captured Still Shot</span>
                        <span id="capture-time" style="color: #666;">-</span>
                    </div>
                    <div class="screen-box">
                        <img id="result-img" src="" style="display: none;" alt="Captured Image">
                        <div id="placeholder" style="color: #666; font-size: 14px;">
                            Captured image will appear here when you click Capture
                        </div>
                    </div>
                </div>
            </div>

            <!-- [Tab 1: Inspection Mode] -->
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
                document.getElementById('collected-summary').innerText = `Collected Data: ${data.images.length} images`;
                if (data.images.length === 0) {
                    box.innerHTML = '<span style="color: #666; font-size: 13px;">No images collected yet. Press the button to capture!</span>';
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
            if (!confirm('Delete all collected photos and start over?')) return;
            await fetch('/api/clear_gallery', { method: 'POST' });
            currentStepIdx = 0;
            updateGuideUI();
            loadGallery();
        }

        async function runAutoPipeline() {
            if (!confirm('Run FactChat VLM auto-labeling and YOLO dataset generation on collected photos?')) return;
            alert('VLM auto-labeling is starting in the background on the Raspberry Pi! Results will be saved to the console and dataset upon completion.');
            fetch('/api/run_pipeline', { method: 'POST' });
        }

        // [Inspection Tab Logic]
        function updateUI(data) {
            document.getElementById('loading-inspect').style.display = 'none';
            document.getElementById('btn-backend').disabled = (data.primary_verdict === 'REPOSITION' || data.primary_verdict === 'ERROR');

            const badge = document.querySelector('.status-badge');
            badge.className = 'status-badge badge-' + data.primary_verdict;
            badge.innerText = data.primary_verdict + ' (Defect: ' + (data.defect_type || 'NONE') + ')';

            document.getElementById('val-blur').innerText = data.blur_score + ' pts';
            document.getElementById('val-led').innerText = data.pwr_led_status ? '🔴 SOLID ON' : '⚪ OFF';
            document.getElementById('val-defect').innerText = data.defect_type || 'NONE';
            document.getElementById('val-infer').innerText = data.infer_ms + ' ms';

            document.getElementById('val-model').innerText = data.model_text || 'Unidentified';
            document.getElementById('val-ic').innerText = data.ic_id_text || 'Not detected';
            document.getElementById('val-fcc').innerText = data.fcc_id_text || 'Not detected';
            document.getElementById('val-serial').innerText = data.device_unique_id || 'None (using board ID)';
            
            const visibleSpan = document.getElementById('val-visible');
            if (data.is_fully_visible) {
                visibleSpan.style.color = '#00e676';
                visibleSpan.innerText = '✅ Fully Visible (all 4 sides inside frame)';
            } else {
                visibleSpan.style.color = '#ff1744';
                visibleSpan.innerText = '❌ Cropped (part of board is outside frame)';
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
                    alert('Error: ' + data.error);
                } else {
                    updateUI(data);
                }
            } catch (err) {
                alert('Request failed: ' + err);
            } finally {
                document.getElementById('loading-inspect').style.display = 'none';
            }
        }

        async function sendToBackend() {
            const btn = document.getElementById('btn-backend');
            const resBox = document.getElementById('backend-result');
            btn.disabled = true;
            btn.innerText = '⏳ Sending to backend...';

            try {
                const res = await fetch('/api/submit_backend', { method: 'POST' });
                const data = await res.json();
                resBox.style.display = 'block';
                if (data.success) {
                    resBox.innerHTML = '<b>✅ Backend registration succeeded!</b><br><pre>' + JSON.stringify(data.backend_response, null, 2) + '</pre>';
                } else {
                    resBox.innerHTML = '<b>❌ Backend registration failed:</b> ' + (data.error || 'Unknown error');
                }
            } catch (err) {
                resBox.style.display = 'block';
                resBox.innerHTML = '<b>❌ Communication failed:</b> ' + err;
            } finally {
                btn.disabled = false;
                btn.innerText = '🚀 Send Result to Backend Server (POST)';
            }
        }
    </script>
</body>
</html>
"""



def _send_result_to_backend(insp_id, res_dict, img_bgr):
    if not BACKEND_URL:
        print("ℹ️ [Backend] BACKEND_URL not set — running in local standalone mode and skipping DB upload.")
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
        print(f"🚀 [Backend DB Save Succeeded!] ID={insp_id} -> {backend_res}")
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

    # 1. OCR stage & send captured image
    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="OCR",
        progress_percent=25,
        message="Recognizing unique serial number on the board surface...",
        blur_score=blur_score,
        stabilization_ms=300,
        capture_image_url=capture_image_url
    )

    result = inspect_with_vlm(img_bgr)
    result["inspection_id"] = insp_id
    result["capture_image_url"] = capture_image_url

    time.sleep(0.4)

    # 2. LED check stage
    pwr_on = bool(result.get("pwr_led_status", False))
    if not pwr_on and result.get("primary_verdict") != "REPOSITION":
        # Force FAIL for unlit PWR LED only when not REPOSITION (hand occlusion / cropped)
        result["primary_verdict"] = "FAIL"
        if not result.get("reason"):
            result["reason"] = "Power PWR LED is off."
        led_msg = "PWR LED off (power failure)"
    elif not pwr_on:
        led_msg = "Board occluded or cropped; unable to verify LED"
    else:
        led_msg = "Onboard PWR LED verified lit"

    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="LED_CHECK",
        progress_percent=60,
        message=led_msg,
        blur_score=blur_score,
        stabilization_ms=300
    )

    time.sleep(0.4)

    # 3. AI exterior inspection stage
    verdict = result.get("primary_verdict", "FAIL")
    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="AI_INFERENCE",
        progress_percent=85,
        message=f"AI model exterior analysis complete ({verdict})",
        blur_score=blur_score,
        stabilization_ms=300
    )

    # Wait 1.2s so the checkmark is visible on screen
    time.sleep(1.2)

    # 4. Switch to final completion or reposition screen
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
            message=result.get("reason", "Please reposition the board."),
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
            message=f"Inspection complete. Final result: {verdict}",
            blur_score=blur_score,
            stabilization_ms=300
        )
    _, full_buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    result["image_base64"] = base64.b64encode(full_buf).decode("utf-8")
    last_inspection_result = result

    # 5. Auto-send to backend DB when final verdict is PASS / FAIL (not REPOSITION)!
    if verdict in ["PASS", "FAIL"]:
        try:
            _send_result_to_backend(insp_id, result, img_bgr)
        except Exception as e:
            print(f"⚠️ [Backend] Exception during auto-upload: {e}")

    return result


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, guided_steps=GUIDED_STEPS)


@app.route("/video_feed")
def video_feed():
    streamer = get_camera_streamer()
    get_auto_inspector() # Start MQTT command receiver and loop
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
    get_auto_inspector() # Start MQTT command receiver and loop
    bgr = streamer.get_latest_frame()
    if bgr is None:
        return jsonify({"error": "Unable to get camera frame."}), 500

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
    get_auto_inspector() # Start MQTT command receiver and loop
    bgr = streamer.get_latest_frame()
    if bgr is None:
        return jsonify({"success": False, "error": "Failed to capture camera frame"}), 500

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
    return jsonify({"success": True, "message": "Pipeline started in background"})


@app.route("/api/submit_backend", methods=["POST"])
def submit_to_backend():
    global last_inspection_result, last_inspection_bgr
    if last_inspection_result is None or last_inspection_bgr is None:
        return jsonify({"error": "No recent inspection result to send."}), 400

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
