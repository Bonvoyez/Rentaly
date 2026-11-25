#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
[LED Controller] 라즈베리파이 GPIO 상태 표시 LED 제어 모듈
=============================================================================
- RED    : GPIO 17 (Physical Pin 11) -> FAIL / REPOSITION / ERROR
- YELLOW : GPIO 27 (Physical Pin 13) -> INSPECTING / STABILIZING (검사 진행 중)
- GREEN  : GPIO 22 (Physical Pin 15) -> PASS (정상 완료)
=============================================================================
"""

try:
    from gpiozero import LED
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False


class StatusLedController:
    def __init__(self, red_pin=17, yellow_pin=27, green_pin=22):
        self.red = None
        self.yellow = None
        self.green = None

        if HAS_GPIO:
            try:
                self.red = LED(red_pin)
                self.yellow = LED(yellow_pin)
                self.green = LED(green_pin)
                self.all_off()
                print(f"🚦 [LED] GPIO 초기화 완료 (R={red_pin}, Y={yellow_pin}, G={green_pin})")
            except Exception as e:
                print(f"⚠️ [LED] GPIO 초기화 실패 (가상 모드): {e}")

    def all_off(self):
        for led in (self.red, self.yellow, self.green):
            if led:
                led.off()

    def set_inspecting(self):
        """검사 진행 중: 노랑 LED 점등"""
        self.all_off()
        if self.yellow:
            self.yellow.on()

    def set_pass(self):
        """정상 통과: 초록 LED 점등"""
        self.all_off()
        if self.green:
            self.green.on()

    def set_fail_or_reposition(self):
        """결함 또는 재배치: 빨강 LED 점등"""
        self.all_off()
        if self.red:
            self.red.on()


_led_instance = None

def get_led_controller():
    global _led_instance
    if _led_instance is None:
        _led_instance = StatusLedController()
    return _led_instance
