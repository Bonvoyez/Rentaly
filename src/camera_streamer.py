#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[Camera Streamer] Raspberry Pi Camera Module v3 Background Streaming & Still Capture Manager
=============================================================================
- Continuously captures 640x480 video in a background daemon thread
- Provides MJPEG real-time stream on client connection (/video_feed)
- Returns the latest frame immediately without focus delay on capture request
=============================================================================
"""

import os
import time
import threading
import cv2
import numpy as np

try:
    from picamera2 import Picamera2
    HAS_PICAM2 = True
except ImportError:
    HAS_PICAM2 = False


class CameraStreamer:
    def __init__(self, width=640, height=480, fps=20, test_image_path=None):
        self.width = width
        self.height = height
        self.fps = fps
        self.picam2 = None
        self.running = False
        self.lock = threading.Lock()
        self.latest_frame_bgr = None
        self.latest_jpeg = None
        self.thread = None
        self.test_image_path = test_image_path or os.getenv("TEST_IMAGE_PATH", "")

        if self.test_image_path:
            self._init_test_image(self.test_image_path)
        elif HAS_PICAM2:
            self._init_camera()
        else:
            self._init_fallback_sample()

    def _init_test_image(self, image_path):
        """Load a single test image file as a virtual camera stream"""
        if not os.path.exists(image_path):
            print(f"⚠️ [CameraStreamer] Test image not found: {image_path}")
            return False
        bgr = cv2.imread(image_path)
        if bgr is None:
            print(f"⚠️ [CameraStreamer] Failed to decode image: {image_path}")
            return False
        _, jpeg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with self.lock:
            self.latest_frame_bgr = bgr
            self.latest_jpeg = jpeg.tobytes()
        self.running = True
        print(f"🖼️ [CameraStreamer] Virtual test image stream enabled: {image_path}")
        return True

    def _init_fallback_sample(self):
        """Automatically load the first sample_data image on non-Picamera2 environments (Mac/PC)"""
        sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample_data", "training"))
        if os.path.isdir(sample_dir):
            for fname in sorted(os.listdir(sample_dir)):
                if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                    if self._init_test_image(os.path.join(sample_dir, fname)):
                        return
        print("ℹ️ [CameraStreamer] No camera or sample image found (idle state)")

    def _init_camera(self):
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"}
            )
            self.picam2.configure(config)
            self.picam2.set_controls({"AfMode": 2})  # Continuous AutoFocus
            self.picam2.start()
            self.running = True

            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            print(f"📷 [CameraStreamer] Camera started ({self.width}x{self.height} @ ~{self.fps}fps, AfMode=Continuous)")
        except Exception as e:
            print(f"⚠️ [CameraStreamer] Camera initialization failed: {e}")
            self.running = False

    def _capture_loop(self):
        interval = 1.0 / self.fps
        while self.running:
            start_t = time.time()
            try:
                rgb = self.picam2.capture_array()
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                _, jpeg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])

                with self.lock:
                    self.latest_frame_bgr = bgr
                    self.latest_jpeg = jpeg.tobytes()
            except Exception as e:
                time.sleep(0.1)

            elapsed = time.time() - start_t
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def get_latest_frame(self):
        """Return the most recent BGR image (for capture)"""
        with self.lock:
            if self.latest_frame_bgr is not None:
                return self.latest_frame_bgr.copy()
        return None

    def generate_mjpeg(self):
        """Generator for MJPEG HTTP streaming"""
        while self.running:
            with self.lock:
                frame_data = self.latest_jpeg

            if frame_data is not None:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n")
            time.sleep(1.0 / self.fps)

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
        print("📷 [CameraStreamer] Camera stopped")


# Singleton
_streamer_instance = None

def get_camera_streamer(test_image_path=None):
    global _streamer_instance
    if _streamer_instance is None:
        _streamer_instance = CameraStreamer(test_image_path=test_image_path)
    elif test_image_path:
        _streamer_instance._init_test_image(test_image_path)
    return _streamer_instance
