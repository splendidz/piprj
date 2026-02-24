#!/usr/bin/env python3
"""
DHT11 온습도 센서 (GPIO4 = BCM 4). RPi.GPIO + dht11 사용.
"""

import sys
from dataclasses import dataclass
from typing import Any

GPIO: Any | None = None
dht11: Any | None = None


def _require_dht_deps() -> None:
    global GPIO, dht11
    if GPIO is not None and dht11 is not None:
        return
    try:
        import RPi.GPIO as _GPIO  # type: ignore
        import dht11 as _dht11  # type: ignore
    except ImportError as e:
        raise ImportError(
            "DHT11 의존성 없음. 설치: "
            f"{sys.executable} -m pip install RPi.GPIO dht11"
        ) from e
    GPIO = _GPIO
    dht11 = _dht11


try:
    from lcd1602_i2c import LCD1602_I2C
except Exception:
    LCD1602_I2C = None


@dataclass
class DHT11Reading:
    temperature: float | None
    humidity: float | None
    is_valid: bool


class DHT11Reader:
    def __init__(
        self,
        pin: int = 4,
        read_interval: float = 5.0,
        failure_threshold_sec: float = 60.0,
    ):
        self.pin = pin
        self.read_interval = read_interval
        self.failure_threshold_sec = failure_threshold_sec
        self._last_temperature: float | None = None
        self._last_humidity: float | None = None
        self._consecutive_failures = 0
        self._instance: Any = None
        self._gpio_initialized = False

    def _ensure_gpio(self) -> None:
        _require_dht_deps()
        if self._gpio_initialized:
            return
        assert GPIO is not None
        assert dht11 is not None
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.cleanup()
        self._instance = dht11.DHT11(pin=self.pin)
        self._gpio_initialized = True

    def read(self) -> DHT11Reading:
        self._ensure_gpio()
        assert self._instance is not None
        result = self._instance.read()
        if result.is_valid():
            self._last_temperature = float(result.temperature)
            self._last_humidity = float(result.humidity)
            self._consecutive_failures = 0
            return DHT11Reading(
                temperature=self._last_temperature,
                humidity=self._last_humidity,
                is_valid=True,
            )
        self._consecutive_failures += 1
        return DHT11Reading(
            temperature=self._last_temperature,
            humidity=self._last_humidity,
            is_valid=False,
        )

    @property
    def last_temperature(self) -> float | None:
        return self._last_temperature

    @property
    def last_humidity(self) -> float | None:
        return self._last_humidity

    def close(self) -> None:
        if self._gpio_initialized and GPIO is not None:
            try:
                GPIO.cleanup()
            except Exception:
                pass
            self._gpio_initialized = False
            self._instance = None
