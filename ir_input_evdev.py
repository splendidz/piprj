# ir_input_evdev.py
from dataclasses import dataclass
import threading

@dataclass
class IRKeyEvent:
    key: str

class IRInputEvdev:
    """
    Read IR remote as /dev/input/eventX (keyboard-like).
    Requires: python-evdev
      pip install evdev
    """
    def __init__(self, device_path: str):
        self.device_path = device_path
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.on_key = None  # callback(IRKeyEvent)
        self.prev_evt = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        from evdev import InputDevice, categorize, ecodes

        def get_interval(event1, event2):
            t1 = event1.sec + (event1.usec / 1000000.0)
            t2 = event2.sec + (event2.usec / 1000000.0)
            return abs(t2 - t1)

        dev = InputDevice(self.device_path)
        for event in dev.read_loop(): # block waitting
            print(f"remove controller input: {event}\n")
            if self._stop.is_set():
                break
            if event.code == 0 and event.type == 0 or event.value == 0:
                continue

            if self.prev_evt == None:
                self.prev_evt = event
            else:
                if get_interval(self.prev_evt, event) < 0.2: #0.2 msec
                    continue
                self.prev_evt = event

            keycode = f"code={event.code:02d},type={event.type:02d},val={event.value:02d}"
            # if event.type != ecodes.EV_KEY:
            #     continue
            # key_event = categorize(event)
            # # key_event.keystate: 1=down, 0=up, 2=hold
            # if key_event.keystate != 1:
            #     continue
            # keycode = key_event.keycode
            # # keycode가 리스트로 올 때도 있음
            # if isinstance(keycode, list):
            #     keycode = keycode[0]
            if self.on_key:
                self.on_key(IRKeyEvent(key=str(keycode)))
