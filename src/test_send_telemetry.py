import os
import sys
import time
import json
import base64
import uuid
import cv2
import paho.mqtt.client as mqtt

# Load and compress test image (15KB)
IMG_PATH = "sample_data/training/IMG_8187.png"
img = cv2.imread(IMG_PATH)
if img is None:
    print(f"❌ Image not found: {IMG_PATH}")
    sys.exit(1)

thumb = cv2.resize(img, (480, 320), interpolation=cv2.INTER_AREA)
_, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
capture_image_url = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")

print(f"📸 Compressed thumbnail created (size: {len(capture_image_url)/1024:.1f} KB)")

client = mqtt.Client("test-mac-sender", transport="websockets")
client.tls_set()
client.ws_set_options(path="/mqtt")

connected = False
def on_connect(c, userdata, flags, rc):
    global connected
    if rc == 0:
        connected = True
        print("✅ Connected to MQTT broker (wss://rentaly.duckdns.org/mqtt)!")
    else:
        print(f"❌ Connection failed rc: {rc}")

client.on_connect = on_connect
client.connect("rentaly.duckdns.org", 443, 60)
client.loop_start()

time.sleep(1.5)
if not connected:
    print("❌ MQTT connection failed")
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
    "message": "Recognizing unique serial number on the board surface...",
    "capture_image_url": capture_image_url
}

print(f"🚀 Publishing to topic [{topic}]...")
client.publish(topic, json.dumps(payload, ensure_ascii=False))
time.sleep(2)
print("🎉 Published successfully! You can check the Vercel UI!")
client.loop_stop()
