# main.py
import time
import signal
from lcd1602_i2c import LCD1602_I2C
from mplayer_slave import MPlayerSlave
from ir_input_evdev import IRInputEvdev, IRKeyEvent

def fmt_time(sec: float) -> str:
    if sec <= 0:
        return "00:00"
    s = int(sec + 0.5)
    mm = s // 60
    ss = s % 60
    return f"{mm:02d}:{ss:02d}"

def progress_bar(pos: float, length: float, width: int = 16) -> str:
    if length <= 0:
        return "-" * width
    ratio = max(0.0, min(1.0, pos / length))
    filled = int(ratio * width)
    return ("#" * filled).ljust(width, "-")

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
        cache_kb=2048,  # cache_kb=8192,
        min_percent=5,     # min_percent=20,
        ao="alsa",
    )

    # IR device path는 환경마다 다름:
    # ir-keytable 명령어로 rc 드라이버의 event 번호를 확인해야함.
    ir = IRInputEvdev("/dev/input/event4")

    # 리모컨 키 매핑 (너 키트 리모컨에 맞게 바꾸면 됨)
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
        action = KEYMAP.get(ev.key)
        if not action:
            return
        if action == "start_pause":
            player.toggle_pause()
        elif action == "0key":
            # mplayer stop은 케이스에 따라 다름. 일단 quit 후 재시작 전략이 안전할 때가 많음.
            player.send("stop")  # 일부 빌드에서 동작
        elif action == "next":
            player.next_track()
        elif action == "prev":
            player.prev_track()
        elif action == "volup":
            player.mute(False)
            player.set_volume(1) # offset volume value
        elif action == "voldown":
            player.mute(False)
            player.set_volume(-1) # offset volume value
        elif action == "0key":
            player.mute(True)
        

    ir.on_key = on_ir_key

    # boot splash
    lcd.write_lines("CD Player boot", "Starting mplayer")
    player.start()
    ir.start()

    last_poll = 0.0
    last_lcd = 0.0

    # track count / title은 CD-Text 지원/환경에 따라 얻기 어려울 수 있음.
    # 일단: track/pos/len 위주로 표시. title은 나오면 붙임.
    while running:
        now = time.time()

        # mplayer 상태 폴링
        if now - last_poll >= 0.5:
            player.poll_status()
            last_poll = now

        # LCD 갱신
        if now - last_lcd >= 0.2:
            st = player.status

            # 1st line: Tr 01/?? Title...
            total = st.track_count if st.track_count > 0 else 0
            if total > 0:
                head = f"Tr {st.track:02d}/{total:02d}"
            else:
                head = f"Tr {st.track:02d}/--"

            title = (st.title or "")
            line1 = head
            if title:
                # 공백 하나 두고 title 일부 표시
                line1 = (head + " " + title)[:16]
            else:
                line1 = line1[:16]

            # 2nd line: time + bar
            # 예: "01:23 03:45" (11 chars) + bar 5 chars 등도 가능
            pos = fmt_time(st.time_pos)
            length = fmt_time(st.time_len)
            # 16칸에 맞춰: "01:23/03:45 ####"
            # 11 chars + space + 4 chars = 16
            bar = progress_bar(st.time_pos, st.time_len, width=4)
            line2 = f"{pos}/{length} {bar}"[:16]

            lcd.write_lines(line1, line2)
            last_lcd = now

        time.sleep(0.01)

    # shutdown
    lcd.write_lines("Shutting down", "Bye")
    ir.stop()
    player.stop()
    time.sleep(0.2)
    lcd.clear()
    lcd.close()

if __name__ == "__main__":
    main()
