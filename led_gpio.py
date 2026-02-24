#!/usr/bin/env python3
"""
GPIO 23번 LED 제어. BCM 번호 사용.
"""

from __future__ import annotations

import sys
from typing import Any

_GPIO: Any | None = None


def _gpio():
    global _GPIO
    if _GPIO is None:
        try:
            import RPi.GPIO as G  # type: ignore
            _GPIO = G
        except ImportError as e:
            raise ImportError(
                "RPi.GPIO가 필요합니다. 설치: "
                f"{sys.executable} -m pip install RPi.GPIO"
            ) from e
    return _GPIO


class LedGpio:
    def __init__(self, pin: int = 23, active_high: bool = True):
        self.pin = pin
        self.active_high = active_high
        self._initialized = False
        self._closed = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        G = _gpio()
        G.setwarnings(False)
        G.setmode(G.BCM)
        G.setup(self.pin, G.OUT)
        G.output(self.pin, G.LOW)
        self._initialized = True

    def on(self) -> None:
        if self._closed:
            return
        self._ensure_init()
        _gpio().output(self.pin, _gpio().HIGH if self.active_high else _gpio().LOW)

    def off(self) -> None:
        if self._closed:
            return
        self._ensure_init()
        _gpio().output(self.pin, _gpio().LOW if self.active_high else _gpio().HIGH)

    def toggle(self) -> bool:
        if self._closed:
            return False
        self._ensure_init()
        on_level = _gpio().HIGH if self.active_high else _gpio().LOW
        is_on = _gpio().input(self.pin) == on_level
        if is_on:
            self.off()
            return False
        self.on()
        return True

    def close(self) -> None:
        self._closed = True
        if not self._initialized:
            return
        try:
            _gpio().output(self.pin, _gpio().LOW if self.active_high else _gpio().HIGH)
            _gpio().cleanup()
        except Exception:
            pass
        self._initialized = False
