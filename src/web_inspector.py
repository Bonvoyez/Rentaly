import os
import sys
import time
import io
import uuid
import json
import base64
import urllib.request
import urllib.error
import numpy as np
import cv2
from flask import Flask, render_template_string, request, jsonify

# Picamera2 라이브러리 (라즈베리파이 전용)
try:
    from picamera2 import Picamera2
    HAS_PICAM2 = True
except ImportError:
    HAS_PICAM2 = False

# VLM 모듈 및 MQTT 모듈
from vlm_inspector import inspect_with_vlm, calculate_blur_score
from mqtt_publisher import get_telemetry_publisher

app = Flask(__name__)

# 백엔드 서버 설정 (환경변수에서 우선 로드)
BACKEND_URL = os.getenv("BACKEND_URL", "https://rentaly.duckdns.org/api/v1/inspections")
DEVICE_SECRET = os.getenv("DEVICE_SECRET", "fdb58779be89e475c4b0447cb3e036dd")
DEVICE_ID = os.getenv("DEVICE_ID", "station-01")

# 마지막 검사 결과 캐시
last_inspection_result = None
last_inspection_bgr = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rentaly AI 외관 검사 스튜디오</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #121212;
            color: #eee;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            max-width: 960px;
            width: 100%;
        }
        h1 {
            color: #4caf50;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .subtitle {
            color: #888;
            margin-top: 0;
            margin-bottom: 20px;
        }
        .controls {
            display: flex;
            gap: 12px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            align-items: center;
        }
        button, label.file-btn {
            background: #2e7d32;
            color: white;
            border: none;
            padding: 12px 20px;
            font-size: 15px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        button:hover, label.file-btn:hover {
            background: #388e3c;
            transform: translateY(-1px);
        }
        button:disabled {
            background: #555;
            cursor: not-allowed;
            transform: none;
        }
        label.file-btn { background: #1565c0; }
        label.file-btn:hover { background: #1976d2; }
        button.btn-backend { background: #e65100; }
        button.btn-backend:hover { background: #f57c00; }
        input[type="file"] { display: none; }
        .view-panel {
            background: #1e1e1e;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }
        .image-box {
            width: 100%;
            min-height: 380px;
            background: #000;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            margin-bottom: 20px;
            border: 1px solid #333;
        }
        .image-box img {
            max-width: 100%;
            height: auto;
            object-fit: contain;
        }
        .status-badge {
            font-size: 20px;
            font-weight: 800;
            padding: 10px 18px;
            border-radius: 6px;
            display: inline-block;
            margin-bottom: 15px;
        }
        .badge-PASS { background: #00c853; color: white; }
        .badge-FAIL { background: #ff9100; color: white; }
        .badge-REPOSITION { background: #d50000; color: white; }
        .badge-READY { background: #424242; color: #aaa; }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: #2a2a2a;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #4caf50;
        }
        .metric-title {
            color: #888;
            font-size: 13px;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 18px;
            font-weight: bold;
            color: #fff;
            word-break: break-all;
        }
        .text-detail-box {
            background: #252525;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #00bcd4;
        }
        .text-detail-box h4 {
            margin: 0 0 10px 0;
            color: #00bcd4;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .reason-box {
            background: #282828;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #ab47bc;
            margin-bottom: 15px;
        }
        .reason-box h4 {
            margin: 0 0 8px 0;
            color: #ab47bc;
        }
        .loading {
            display: none;
            color: #ffeb3b;
            font-weight: bold;
            margin-left: 10px;
        }
        .backend-response {
            background: #1b2e1b;
            border: 1px solid #2e7d32;
            padding: 12px;
            border-radius: 6px;
            color: #81c784;
            display: none;
            margin-top: 15px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 Rentaly AI 외관 검사 & 텍스트 OCR 스튜디오</h1>
        <p class="subtitle">마인드로직 FactChat Gemini VLM 기반 정밀 검사 + 백엔드 연동</p>

        <div class="controls">
            <button id="btn-capture" onclick="takeSnapshot()">
                📸 파이카메라로 고화질 촬영 & 검사
            </button>
            <label class="file-btn">
                📁 폰 사진 업로드하여 검사
                <input type="file" id="file-upload" accept="image/*" onchange="uploadImage(event)">
            </label>
            <button id="btn-backend" class="btn-backend" onclick="sendToBackend()" disabled>
                🚀 백엔드 서버로 결과 전송 (POST)
            </button>
            <span id="loading" class="loading">⏳ 검사 진행 중...</span>
        </div>

        <div class="view-panel">
            <div id="status-box">
                <span class="status-badge badge-READY">READY (준비 완료)</span>
            </div>

            <div class="image-box">
                <img id="result-img" src="" style="display: none;" alt="검사 결과 이미지">
                <div id="placeholder" style="color: #666; font-size: 16px;">
                    위 버튼을 눌러 촬영하거나 폰 사진을 업로드하세요
                </div>
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
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <div>• <b>추출 모델명:</b> <span id="val-model" style="color: #4fc3f7; font-weight: bold;">-</span></div>
                    <div>• <b>IC 전파인증 번호:</b> <span id="val-ic" style="color: #ffca28; font-weight: bold;">-</span></div>
                    <div>• <b>FCC ID 식별 번호:</b> <span id="val-fcc" style="color: #81c784; font-weight: bold;">-</span></div>
                    <div>• <b>기기 고유 번호 / 시리얼:</b> <span id="val-serial" style="color: #e040fb; font-weight: bold;">-</span></div>
                    <div>• <b>보드 온전 노출 여부:</b> <span id="val-visible" style="font-weight: bold;">-</span></div>
                </div>
            </div>

            <div class="reason-box">
                <h4>📝 AI 정밀 판정 소견</h4>
                <div id="val-reason" style="line-height: 1.5; color: #ddd;">
                    검사 결과가 여기에 상세히 표시됩니다.
                </div>
            </div>

            <div id="backend-result" class="backend-response"></div>
        </div>
    </div>

    <script>
        function updateUI(data) {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('btn-capture').disabled = false;
            document.getElementById('btn-backend').disabled = (data.primary_verdict === 'REPOSITION' || data.primary_verdict === 'ERROR');

            // 상태 배너
            const badge = document.querySelector('.status-badge');
            badge.className = 'status-badge badge-' + data.primary_verdict;
            badge.innerText = data.primary_verdict + ' (결함: ' + (data.defect_type || 'NONE') + ')';

            // 메트릭
            document.getElementById('val-blur').innerText = data.blur_score + ' 점';
            document.getElementById('val-led').innerText = data.pwr_led_status ? '🔴 SOLID ON (점등)' : '⚪ OFF (소등)';
            document.getElementById('val-defect').innerText = data.defect_type || 'NONE';
            document.getElementById('val-infer').innerText = data.infer_ms + ' ms';

            // OCR 텍스트
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

            // 판정 소견
            document.getElementById('val-reason').innerText = data.reason;

            // 이미지 표시
            const img = document.getElementById('result-img');
            const placeholder = document.getElementById('placeholder');
            img.src = 'data:image/jpeg;base64,' + data.image_base64;
            img.style.display = 'block';
            placeholder.style.display = 'none';
        }

        async function takeSnapshot() {
            document.getElementById('loading').style.display = 'inline-block';
            document.getElementById('btn-capture').disabled = true;
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
                document.getElementById('loading').style.display = 'none';
                document.getElementById('btn-capture').disabled = false;
            }
        }

        async function uploadImage(event) {
            const file = event.target.files[0];
            if (!file) return;

            document.getElementById('loading').style.display = 'inline-block';
            document.getElementById('backend-result').style.display = 'none';
            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.error) {
                    alert('에러: ' + data.error);
                } else {
                    updateUI(data);
                }
            } catch (err) {
                alert('업로드 실패: ' + err);
            } finally {
                document.getElementById('loading').style.display = 'none';
                event.target.value = '';
            }
        }

        async function sendToBackend() {
            const btn = document.getElementById('btn-backend');
            btn.disabled = true;
            btn.innerText = '🚀 전송 중...';

            try {
                const res = await fetch('/api/submit_backend', { method: 'POST' });
                const data = await res.json();
                const resultDiv = document.getElementById('backend-result');
                resultDiv.style.display = 'block';
                if (data.success) {
                    resultDiv.style.borderColor = '#2e7d32';
                    resultDiv.style.color = '#81c784';
                    resultDiv.innerText = '🎉 백엔드 서버 등록 성공!\\n' + JSON.stringify(data.backend_response, null, 2);
                } else {
                    resultDiv.style.borderColor = '#d50000';
                    resultDiv.style.color = '#ff5252';
                    resultDiv.innerText = '❌ 백엔드 서버 등록 실패:\\n' + data.error;
                }
            } catch (err) {
                alert('백엔드 전송 실패: ' + err);
            } finally {
                btn.disabled = false;
                btn.innerText = '🚀 백엔드 서버로 결과 전송 (POST)';
            }
        }
    </script>
</body>
</html>
"""

def process_and_inspect(img_bgr):
    global last_inspection_result, last_inspection_bgr
    last_inspection_bgr = img_bgr.copy()
    insp_id = str(uuid.uuid4())
    publisher = get_telemetry_publisher()

    # 1. 화면 전송용 경량 썸네일 생성 (480x320, Base64 약 15KB)
    thumb = cv2.resize(img_bgr, (480, 320), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
    capture_image_url = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")

    # 선명도 계측
    blur_score = calculate_blur_score(img_bgr)

    # 2. [MQTT 텔레메트리 1단계: OCR 단계 시작 & 캡처 사진 전달!]
    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="OCR",
        progress_percent=25,
        message="보드 표면의 고유 시리얼 번호를 인식하고 있습니다...",
        blur_score=blur_score,
        stabilization_ms=300,
        capture_image_url=capture_image_url
    )

    # 3. VLM 및 Fail-Safe 정밀 검사 수행
    result = inspect_with_vlm(img_bgr)
    result["inspection_id"] = insp_id
    result["capture_image_url"] = capture_image_url

    # 4. [MQTT 텔레메트리 2단계: LED 점등 상태 전달]
    led_msg = "온보드 PWR LED 정상 점등 확인" if result.get("pwr_led_status") else "PWR LED 점등 확인 진행"
    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="LED_CHECK",
        progress_percent=60,
        message=led_msg,
        blur_score=blur_score,
        stabilization_ms=300
    )

    # 5. [MQTT 텔레메트리 3단계: AI 외관 검사 상태 전달]
    verdict = result.get("primary_verdict", "FAIL")
    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="AI_INFERENCE",
        progress_percent=85,
        message=f"AI 모델 외관 분석 완료 ({verdict})",
        blur_score=blur_score,
        stabilization_ms=300
    )

    # 6. [MQTT 텔레메트리 4단계: 최종 완료]
    publisher.publish_telemetry(
        inspection_id=insp_id,
        stage="COMPLETED",
        progress_percent=100,
        message=f"검사가 완료되었습니다. 최종 결과: {verdict}",
        blur_score=blur_score,
        stabilization_ms=300
    )

    # 화면 표시용 고화질 JPEG Base64
    _, full_buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    result["image_base64"] = base64.b64encode(full_buf).decode("utf-8")

    last_inspection_result = result
    return result

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/capture", methods=["POST"])
def capture_and_inspect():
    if not HAS_PICAM2:
        return jsonify({"error": "Picamera2 모듈이 없습니다."}), 500

    try:
        picam2 = Picamera2()
        config = picam2.create_still_configuration(main={"size": (1920, 1080), "format": "RGB888"})
        picam2.configure(config)
        picam2.set_controls({"AfMode": 2})  # Continuous AutoFocus
        picam2.start()
        time.sleep(1.2)  # 초점 대기
        rgb = picam2.capture_array()
        picam2.stop()
        picam2.close()

        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        res = process_and_inspect(bgr)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def upload_and_inspect():
    if "file" not in request.files:
        return jsonify({"error": "파일이 없습니다."}), 400
    file = request.files["file"]
    file_bytes = np.frombuffer(file.read(), np.uint8)
    img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return jsonify({"error": "이미지 디코딩 실패"}), 400

    res = process_and_inspect(img_bgr)
    return jsonify(res)

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

    # 이미지 압축 (최대 1280px)
    h, w = last_inspection_bgr.shape[:2]
    if max(h, w) > 1280:
        scale = 1280 / max(h, w)
        img_send = cv2.resize(last_inspection_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        img_send = last_inspection_bgr
    _, img_jpg = cv2.imencode(".jpg", img_send, [cv2.IMWRITE_JPEG_QUALITY, 85])

    # multipart/form-data 작성
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "X-Device-Secret": DEVICE_SECRET
    }

    body = []
    # 1. metadata part
    body.append(f"--{boundary}".encode())
    body.append(b'Content-Disposition: form-data; name="metadata"')
    body.append(b"Content-Type: application/json\r\n")
    body.append(json.dumps(metadata, ensure_ascii=False).encode("utf-8"))

    # 2. image part
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
    print("=" * 60)
    print("🚀 Rentaly AI 외관 검사 스튜디오 (VLM + 백엔드 연동)")
    print("👉 접속 주소: http://100.93.132.9:8080")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8080, debug=False)
