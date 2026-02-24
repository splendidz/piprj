from pathlib import Path  # main.py
import time
import signal
import threading
from lcd1602_i2c import LCD1602_I2C
from mplayer_slave import MPlayerSlave, is_cd_present
from ir_input_evdev import IRInputEvdev, IRKeyEvent
from led_gpio import LedGpio
from dht11_read import DHT11Reader
from indoor_outdoor_display import WeatherCurrentSubscriber, build_lcd_lines, OutdoorWeather


def fmt_time(sec: float) -> str:
    if sec <= 0:
        return "00:00"
    s = int(sec + 0.5)
    mm = s // 60
    ss = s % 60
    return f"{mm:02d}:{ss:02d}"


def main():
    running = True

    def handle_sig(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    lcd = LCD1602_I2C(bus=1, addr=0x27, backlight=True)
    player = MPlayerSlave(
        cd_url="cdda://",
        cache_kb=2048,
        min_percent=5,
        ao="alsa",
    )

    IR_PATH = Path("/dev/input/by-path/platform-ir-receiver@12-event")

    for _ in range(200):  # 20초
        if IR_PATH.exists():
            break
        time.sleep(0.1)

    if not IR_PATH.exists():
        raise FileNotFoundError(f"IR device not found: {IR_PATH}")

    ir = IRInputEvdev(str(IR_PATH))

    dht_reader = None
    weather_sub = None
    try:
        dht_reader = DHT11Reader(pin=4, read_interval=5.0, failure_threshold_sec=60.0)
        dht_reader.read()
    except Exception:
        pass
    led = None
    try:
        led = LedGpio(pin=23)
    except Exception:
        pass
    try:
        weather_sub = WeatherCurrentSubscriber("127.0.0.1", 1883)
        weather_sub.start()
    except Exception:
        pass

    display_mode = "cd"

    TRACK_JUMP_WAIT = 0.3
    pending_track_delta = 0
    pending_track_deadline: float | None = None

    KEYMAP = {
        "code=04,type=04,val=69": "ch-",
        "code=04,type=04,val=70": "ch",
        "code=04,type=04,val=71": "ch+",
        "code=04,type=04,val=64": "next",
        "code=04,type=04,val=68": "prev",
        "code=04,type=04,val=67": "start_pause",
        "code=04,type=04,val=21": "volup",
        "code=04,type=04,val=07": "voldown",
        "code=04,type=04,val=09": "eq",
        "code=04,type=04,val=22": "0key",
        "code=04,type=04,val=12": "1key",
        "code=04,type=04,val=24": "2key",
        "code=04,type=04,val=94": "3key",
        "code=04,type=04,val=08": "4key",
        "code=04,type=04,val=28": "5key",
        "code=04,type=04,val=90": "6key",
        "code=04,type=04,val=66": "7key",
        "code=04,type=04,val=82": "8key",
        "code=04,type=04,val=74": "9key",
        "code=04,type=04,val=25": "100+",
        "code=04,type=04,val=13": "200+",
    }

    def on_ir_key(ev: IRKeyEvent):
        nonlocal pending_track_delta, pending_track_deadline, display_mode
        if led is not None:
            led.on()
            threading.Timer(0.15, led.off).start()
        action = KEYMAP.get(ev.key)
        if not action:
            return
        if action == "ch":
            display_mode = "weather" if display_mode == "cd" else "cd"
            return
        if action == "start_pause":
            player.toggle_pause()
        # elif action == "0key":
        #     player.send("stop")
        elif action == "next":
            pending_track_delta += 1
            pending_track_deadline = time.time() + TRACK_JUMP_WAIT
        elif action == "prev":
            pending_track_delta -= 1
            pending_track_deadline = time.time() + TRACK_JUMP_WAIT
        elif action == "volup":
            player.mute(False)
            player.set_volume(1)
        elif action == "voldown":
            player.mute(False)
            player.set_volume(-1)
        elif action == "0key":
            player.mute(True)

    ir.on_key = on_ir_key

    lcd.write_lines("CD Player boot", "Starting mplayer")
    if is_cd_present():
        player.start()
    else:
        player.status.stopped = True
    ir.start()

    last_lcd = 0.0
    last_cd_check = 0.0
    last_dht_read = 0.0
    CD_CHECK_INTERVAL = 2.0
    DHT_READ_INTERVAL = 5.0

    while running:
        now = time.time()

        if pending_track_deadline is not None and now >= pending_track_deadline:
            if pending_track_delta != 0 and not player.status.stopped:
                current = player.status.track
                total = player.status.track_count or 99
                target = max(1, min(current + pending_track_delta, total))
                player.goto_track(target)
            pending_track_delta = 0
            pending_track_deadline = None

        player.poll_and_advance_track(now)

        if now - last_cd_check >= CD_CHECK_INTERVAL:
            last_cd_check = now
            if player.status.stopped and is_cd_present():
                player.start()
            elif not player.status.stopped and not is_cd_present():
                player.stop()
                player.status.stopped = True

        if now - last_lcd >= 0.2:
            if display_mode == "weather" and dht_reader is not None:
                if now - last_dht_read >= DHT_READ_INTERVAL:
                    dht_reader.read()
                    last_dht_read = now
                outdoor = weather_sub.get_outdoor() if weather_sub else OutdoorWeather()
                line1, line2 = build_lcd_lines(
                    dht_reader.last_temperature,
                    dht_reader.last_humidity,
                    outdoor,
                )
                lcd.write_lines(line1, line2)
            else:
                st = player.status
                try:
                    vol = player.get_volume_percent()
                except Exception:
                    vol = 0
                vol_str = f"vol{vol:02d}"

                if st.stopped:
                    line1 = ("Insert CD " + vol_str).ljust(16)[:16]
                    line2 = "--:--/--:--".ljust(16)[:16]
                else:
                    total = st.track_count if st.track_count > 0 else 0
                    if total > 0:
                        head = f"Tr {st.track:02d}/{total:02d}"
                    else:
                        head = f"Tr {st.track:02d}/--"
                    title = (st.title or "")
                    rest = 16 - len(vol_str) - 1
                    line1 = (head + " " + title)[:rest].strip() + " " + vol_str
                    line1 = line1[:16].ljust(16)

                    pos = fmt_time(st.time_pos)
                    length = fmt_time(st.time_len)
                    line2 = f"{pos}/{length}"[:16].ljust(16)

                lcd.write_lines(line1, line2)
            last_lcd = now

        time.sleep(0.01)

    lcd.write_lines("Shutting down", "Bye")
    ir.stop()
    player.stop()
    if weather_sub is not None:
        try:
            weather_sub.stop()
        except Exception:
            pass
    if dht_reader is not None:
        try:
            dht_reader.close()
        except Exception:
            pass
    if led is not None:
        led.close()
    time.sleep(0.2)
    lcd.clear()
    lcd.close()


if __name__ == "__main__":
    main()
