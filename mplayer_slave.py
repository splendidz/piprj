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
    """LCD 등 표시용. track은 mplayer가 보낸 실제 재생 트랙 번호만 반영."""
    track: int = 1
    track_count: int = 0
    title: str = ""
    time_pos: float = 0.0
    time_len: float = 0.0
    paused: bool = False
    stopped: bool = False


def is_cd_present(cdrom: str = "/dev/cdrom", timeout: float = 3.0) -> bool:
    try:
        r = subprocess.run(
            ["cdparanoia", "-Q", "-d", cdrom],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


class MPlayerSlave:
    def __init__(self, cd_url="cdda://", cache_kb=8192, min_percent=20, ao="alsa"):
        self.cd_url = cd_url
        self.cache_kb = cache_kb
        self.min_percent = min_percent
        self.ao = ao

        self.proc: subprocess.Popen | None = None
        self._stdout_thread: threading.Thread | None = None
        self._stdout_queue: queue.Queue[str] = queue.Queue()
        self._stop_flag = threading.Event()

        self.status = PlayerStatus()
        self._cdrom = "/dev/cdrom"
        self._current_track = 1

        self._last_poll = 0.0
        self._last_advance_track = -1
        self._last_time_pos: float | None = None
        self._stall_start: float | None = None

        self._re_ans_int = re.compile(r"^ANS_([A-Za-z0-9_]+)=(.*)$")
        self._re_cdda_track = re.compile(r"CDDA.*track\s+(\d+)", re.IGNORECASE)

    def start(self):
        if self.is_running():
            self.status.stopped = False
            self._current_track = 1
            self.status.track = 1
            self.send("loadfile cdda://1 0")
            return
        self.stop()
        time.sleep(0.2)

        self.status.stopped = False
        self.status.track = 1
        self._current_track = 1
        self.status.track_count = 0
        self.status.title = ""
        self.status.time_pos = 0.0
        self.status.time_len = 0.0
        self.status.paused = False

        cmd = [
            "mplayer",
            "-cache", str(self.cache_kb),
            "-cache-min", str(self.min_percent),
            "-ao", self.ao,
            "-slave",
            "-idle",
            "-quiet",
            "-identify",
        ]
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception:
            self.status.stopped = True
            self.proc = None
            return

        self.send("loadfile cdda://1 0")
        self._stop_flag.clear()
        self._stdout_thread = threading.Thread(target=self._read_stdout_loop, daemon=True)
        self._stdout_thread.start()

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _mark_process_dead(self) -> None:
        self.status.stopped = True
        self.status.paused = False
        self.proc = None

    def stop(self):
        self._stop_flag.set()
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.send("quit")
            except Exception:
                pass
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None

    def send(self, command: str) -> None:
        if not self.proc or not self.proc.stdin:
            return
        try:
            self.proc.stdin.write(command.strip() + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self._mark_process_dead()

    def mute(self, is_mute: bool):
        mute_val = "1" if is_mute else "0"
        subprocess.run(
            ["pactl", "set-sink-mute", "@DEFAULT_SINK@", mute_val],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def get_volume_percent(self):
        out = subprocess.check_output(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"], text=True
        )
        m = re.search(r"(\d+)%", out)
        return int(m.group(1)) if m else 0

    def set_volume(self, offset_vol_per: int):
        b = self.get_volume_percent()
        new_vol = max(0, min(b + offset_vol_per, 100))
        subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{new_vol}%"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def toggle_pause(self):
        self.send("pause")
        self.status.paused = not self.status.paused

    def next_track(self) -> None:
        track_count = self.status.track_count
        if track_count > 0 and self._current_track >= track_count:
            return
        self._current_track += 1
        self.send(f"loadfile cdda://{self._current_track} 0")

    def prev_track(self) -> None:
        if self._current_track <= 1:
            return
        self._current_track -= 1
        self.send(f"loadfile cdda://{self._current_track} 0")

    def goto_track(self, track: int) -> None:
        track = max(1, track)
        if self.status.track_count > 0:
            track = min(track, self.status.track_count)
        self._current_track = track
        self.send(f"loadfile cdda://{track} 0")

    def poll_status(self):
        if not self.is_running():
            return
        self.send("get_time_pos")
        self.send("get_time_length")
        self.send("get_file_name")
        self.send("get_property titles")
        self.send("get_meta_title")

    POLL_INTERVAL = 0.5
    MIN_POSITION = 5.0
    STALL_AFTER_90PCT = 0.5
    STALL_BEFORE_90PCT = 1.5
    NINETY_PCT = 0.9

    def poll_and_advance_track(self, now: float | None = None) -> None:
        if now is None:
            now = time.time()
        if not self.is_running():
            self._mark_process_dead()
            return
        if now - self._last_poll < self.POLL_INTERVAL:
            return
        self.poll_status()
        self._last_poll = now
        st = self.status

        if st.paused:
            self._last_time_pos = None
            self._stall_start = None
            return

        time_len = st.time_len
        time_pos = st.time_pos

        if time_len > 0 and time_pos >= time_len:
            if st.track != self._last_advance_track:
                self.next_track()
                self._last_advance_track = st.track
            self._last_time_pos = time_pos
            self._stall_start = None
            return

        if time_pos < self.MIN_POSITION:
            self._last_time_pos = time_pos
            self._stall_start = None
            return

        if self._last_time_pos is not None and time_pos <= self._last_time_pos:
            if self._stall_start is None:
                self._stall_start = now
            else:
                at_90pct = time_len > 0 and time_pos >= self.NINETY_PCT * time_len
                threshold = self.STALL_AFTER_90PCT if at_90pct else self.STALL_BEFORE_90PCT
                if now - self._stall_start >= threshold:
                    if st.track != self._last_advance_track:
                        self.next_track()
                        self._last_advance_track = st.track
                    self._stall_start = None
        else:
            self._stall_start = None

        self._last_time_pos = time_pos

    def _read_stdout_loop(self):
        try:
            if not self.proc or not self.proc.stdout:
                return
            for line in self.proc.stdout:
                if self._stop_flag.is_set():
                    break
                line = line.strip()
                if not line:
                    continue
                self._stdout_queue.put(line)
                self._parse_line(line)
        except Exception:
            pass
        finally:
            self._mark_process_dead()

    def _parse_line(self, line: str):
        m = self._re_ans_int.match(line)
        if m:
            key = m.group(1).upper()
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
                v = val.strip()
                if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                    v = v[1:-1]
                t = None
                if v.isdigit():
                    t = int(v)
                elif "cdda://" in v:
                    try:
                        t_str = v.split("cdda://", 1)[1]
                        t_str = re.split(r"[^\d]", t_str)[0]
                        if t_str.isdigit():
                            t = int(t_str)
                    except Exception:
                        pass
                if t is not None:
                    self.status.track = t
                    self._current_track = t
            elif key == "TITLES":
                try:
                    n = int(val)
                    if n > 0 and self.status.track_count <= 0:
                        self.status.track_count = n
                except ValueError:
                    pass
            elif key == "META_TITLE":
                v = val.strip().strip("'\"")
                if v:
                    self.status.title = v
            return

        m2 = self._re_cdda_track.search(line)
        if m2:
            try:
                t = int(m2.group(1))
                self.status.track = t
                self._current_track = t
            except ValueError:
                pass

        if line.lower().startswith(" title:"):
            self.status.title = line.split(":", 1)[1].strip()
