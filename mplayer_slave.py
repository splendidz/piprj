# mplayer_slave.py
import subprocess
import threading
import time
import queue
import re
from dataclasses import dataclass

from pathlib import Path

@dataclass
class PlayerStatus:
    track: int = 1
    track_count: int = 0
    title: str = ""
    time_pos: float = 0.0      # seconds
    time_len: float = 0.0      # seconds
    paused: bool = False
    stopped: bool = False

def detect_track_count(cdrom="/dev/cdrom"):
    # cdparanoia -Q 출력에서 트랙 수 파싱 (설치 필요: sudo apt install cdparanoia)
    out = subprocess.check_output(["cdparanoia", "-Q", "-d", cdrom], text=True, stderr=subprocess.STDOUT)
    tracks = re.findall(r"^\s*\d+\.\s+\d+\s+\[", out, flags=re.M)
    return len(tracks)
    
class MPlayerSlave:
    def __init__(self, cd_url="cdda://", cache_kb=8192, min_percent=20, ao="alsa"):
        self.cd_url = cd_url
        self.cache_kb = cache_kb
        self.min_percent = min_percent
        self.ao = ao

        self.proc: subprocess.Popen | None = None
        self._stdout_thread: threading.Thread | None = None
        self._stdout_queue: "queue.Queue[str]" = queue.Queue()
        self._stop_flag = threading.Event()

        self.status = PlayerStatus()

        # mplayer output patterns
        self._re_ans_int = re.compile(r"^ANS_([A-Z0-9_]+)=(.*)$")
        self._re_cdda_track = re.compile(r"CDDA.*track\s+(\d+)", re.IGNORECASE)
        self.curr_track = 0
    def start(self):
        m3u_path = str(Path(__file__).resolve().parent / "cd.m3u")
        cmd = [
            "mplayer",
            # self.cd_url,
            "-cache", str(self.cache_kb),
            "-cache-min", str(self.min_percent),
            "-ao", self.ao,
            # important additions:
            "-slave",
            "-idle",
            "-quiet",
            "-identify",
        ]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self.curr_track = 1
        self.send("loadfile cdda://1 0")

        #time.sleep(1)
        self.tr_cnt = detect_track_count()
        self._stop_flag.clear()
        self._stdout_thread = threading.Thread(target=self._read_stdout_loop, daemon=True)
        self._stdout_thread.start()

    def stop(self):
        self._stop_flag.set()
        if self.proc and self.proc.poll() is None:
            try:
                self.send("quit")
            except Exception:
                pass
            try:
                self.proc.terminate()
            except Exception:
                pass

    def send(self, command: str):
        if not self.proc or not self.proc.stdin:
            return
        self.proc.stdin.write(command.strip() + "\n")
        self.proc.stdin.flush()

    # --- basic controls ---


    def mute(self, is_mute: bool):
        mute_val = "1" if is_mute else "0"
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", mute_val], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    def get_volume_percent(self):
        out = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], text=True)
        m = re.search(r'(\d+)%', out)
        return int(m.group(1)) if m else 0

    def set_volume(self, offset_vol_per: int):
        b = self.get_volume_percent()
        new_vol = b + offset_vol_per
        new_vol = max(0, min(new_vol, 100))
        print(f"set volume: {new_vol}")
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{new_vol}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    def toggle_pause(self):
        self.send("pause")
        self.status.paused = not self.status.paused

    def next_track(self):
        #self.send("pt_step 1")
        if self.curr_track == self.tr_cnt:
            return
        new_track = self.curr_track + 1
        self.curr_track += 1
        self.send(f"loadfile cdda://{new_track} 0")
        print(f"play next: {self.curr_track}tr")

    def prev_track(self):
        #self.send("pt_step -1")
        if self.curr_track == 1 :
            return        
        new_track = self.curr_track - 1
        self.send(f"loadfile cdda://{new_track} 0")
        self.curr_track -= 1
        print(f"play prev: {self.curr_track}tr")

    def poll_status(self):
        # slave query
        self.send("get_time_pos")
        self.send("get_time_length")
        self.send("get_file_name")   # cdda:// 형태
        # track count는 cdda에서 바로 안 주는 경우가 많아서,
        # 일단 로그/추후 확장으로 잡는 걸 추천

    def _read_stdout_loop(self):
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            if self._stop_flag.is_set():
                break
            line = line.strip()
            if not line:
                continue
            self._stdout_queue.put(line)
            self._parse_line(line)

    def _parse_line(self, line: str):

        #print(f"mplayer log: {line}")

        # ANS_... responses
        m = self._re_ans_int.match(line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()

            if key == "TIME_POSITION":
                try:
                    self.status.time_pos = float(val)
                except ValueError:
                    pass
            elif key == "LENGTH":
                try:
                    self.status.time_len = float(val)
                except ValueError:
                    pass
            elif key == "FILENAME":
                # cdda://N 형태로 나올 때가 있음
                # 예: ANS_FILENAME=cdda://3
                if "cdda://" in val:
                    try:
                        t = val.split("cdda://", 1)[1]
                        # "3" 또는 "3/..." 같은 변형 대비
                        t = re.split(r"[^\d]", t)[0]
                        if t.isdigit():
                            self.status.track = int(t)
                    except Exception:
                        pass
            return

        # CDDA track log (경우에 따라)
        m2 = self._re_cdda_track.search(line)
        if m2:
            try:
                self.status.track = int(m2.group(1))
            except ValueError:
                pass

        # CD-Text 등 title이 출력되는 경우 대비 (환경마다 다름)
        # 예: " Title: ...."
        if line.lower().startswith(" title:"):
            self.status.title = line.split(":", 1)[1].strip()

    def drain_logs(self, max_lines=200) -> list[str]:
        out = []
        for _ in range(max_lines):
            try:
                out.append(self._stdout_queue.get_nowait())
            except queue.Empty:
                break
        return out
