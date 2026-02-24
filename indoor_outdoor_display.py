#!/usr/bin/env python3
"""
실내(DHT11) + 실외(MQTT weather/current) 표시.
weather/current 의 items[0] 을 실외(현재 장소)로 사용.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any

try:
    import paho.mqtt.client as mqtt  # type: ignore
except ImportError:
    mqtt = None

from dht11_read import DHT11Reader

TOPIC_CURRENT = "weather/current"


@dataclass
class OutdoorWeather:
    temperature_c: float | None = None
    humidity_pct: float | None = None
    updated_at: float | None = None


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s in ("", "-", "nan"):
            return None
        return float(s)
    except Exception:
        return None


def _fmt_temp(t: float | None) -> str:
    if t is None:
        return "--.-"
    return f"{t:4.1f}".replace(" ", "")


def _fmt_hum(h: float | None) -> str:
    if h is None:
        return "---"
    ih = max(0, min(100, int(round(h))))
    return f"{ih:3d}"


def build_lcd_lines(
    indoor_temp: float | None,
    indoor_hum: float | None,
    outdoor: OutdoorWeather,
) -> tuple[str, str]:
    in_line = f"In {_fmt_temp(indoor_temp)}C {_fmt_hum(indoor_hum)}%".ljust(16)[:16]
    if outdoor.updated_at is None:
        out_line = "Out waiting...".ljust(16)[:16]
    else:
        out_line = f"Out {_fmt_temp(outdoor.temperature_c)}C {_fmt_hum(outdoor.humidity_pct)}%".ljust(16)[:16]
    return in_line, out_line


class WeatherCurrentSubscriber:
    def __init__(self, host: str, port: int, keepalive: int = 60):
        self.host = host
        self.port = port
        self.keepalive = keepalive
        self._lock = threading.Lock()
        self._outdoor = OutdoorWeather()
        self._client: Any | None = None

    def start(self) -> None:
        if mqtt is None:
            raise RuntimeError("paho-mqtt 필요. pip install paho-mqtt")
        client = mqtt.Client(client_id="piprj_indoor_outdoor")
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(self.host, self.port, self.keepalive)
        client.loop_start()
        self._client = client

    def stop(self) -> None:
        c = self._client
        self._client = None
        if c is None:
            return
        try:
            c.loop_stop()
        except Exception:
            pass
        try:
            c.disconnect()
        except Exception:
            pass

    def get_outdoor(self) -> OutdoorWeather:
        with self._lock:
            return OutdoorWeather(
                temperature_c=self._outdoor.temperature_c,
                humidity_pct=self._outdoor.humidity_pct,
                updated_at=self._outdoor.updated_at,
            )

    def _on_connect(self, client, userdata, flags, rc):
        client.subscribe(TOPIC_CURRENT, qos=1)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return
        first = items[0]
        if not isinstance(first, dict):
            return
        t = _to_float(first.get("TA_C"))
        h = _to_float(first.get("HM_%"))
        with self._lock:
            self._outdoor.temperature_c = t
            self._outdoor.humidity_pct = h
            self._outdoor.updated_at = time.time()
