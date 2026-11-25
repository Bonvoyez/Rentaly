import os
import sys
import time
import json
import base64
import uuid
import cv2
import paho.mqtt.client as mqtt

# 테스트용 이미지 로드 및 압축 (15KB)
IMG_PATH = "sample_data/training/IMG_8187.png"
img = cv2.imread(IMG_PATH)
if img is None:
    print(f"❌ 이미지 없음: {IMG_PATH}")
    sys.exit(1)

thumb = cv2.resize(img, (480, 320), interpolation=cv2.INTER_AREA)
_, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
capture_image_url = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")

print(f"📸 압축 썸네일 생성 완료 (용량: {len(capture_image_url)/1024:.1f} KB)")

client = mqtt.Client("test-mac-sender", transport="websockets")
client.tls_set()
client.ws_set_options(path="/mqtt")

connected = False
def on_connect(c, userdata, flags, rc):
    global connected
    if rc == 0:
        connected = True
        print("✅ MQTT 브로커(wss://rentaly.duckdns.org/mqtt) 연결 성공!")
    else:
        print(f"❌ 연결 실패 rc: {rc}")

client.on_connect = on_connect
client.connect("rentaly.duckdns.org", 443, 60)
client.loop_start()

time.sleep(1.5)
if not connected:
    print("❌ MQTT 연결 실패")
    sys.exit(1)

insp_id = str(uuid.uuid4())
topic = "inspection/station-01/telemetry"

payload = {
    "inspection_id": insp_id,
    "device_id": "station-01",
    "stage": "OCR",
    "progress_percent": 30,
    "blur_score": 182.4,
    "stabilization_ms": 320,
    "message": "보드 표면의 고유 시리얼 번호를 인식하고 있습니다...",
    "capture_image_url": capture_image_url
}

print(f"🚀 토픽 [{topic}] 발행 중...")
client.publish(topic, json.dumps(payload, ensure_ascii=False))
time.sleep(2)
print("🎉 성공적으로 발행되었습니다! Vercel 화면 확인 가능!")
client.loop_stop()
