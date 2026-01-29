# lcd1602_i2c.py
import time

class LCD1602_I2C:
    """
    HD44780 1602 + PCF8574 I2C backpack driver (4-bit mode)
    Requires: smbus2 (recommended) or smbus
    """
    # PCF8574 bit mapping (common)
    # P0: RS, P1: RW, P2: EN, P3: Backlight, P4..P7: D4..D7
    RS = 0x01
    RW = 0x02
    EN = 0x04
    BL = 0x08

    def __init__(self, bus=1, addr=0x27, backlight=True):
        self.addr = addr
        self.backlight = backlight

        try:
            from smbus2 import SMBus
        except Exception:
            from smbus import SMBus  # type: ignore

        self.bus = SMBus(bus)
        self._bl_mask = self.BL if self.backlight else 0x00

        self._init_lcd()

    def close(self):
        try:
            self.bus.close()
        except Exception:
            pass

    def _write_byte(self, data: int):
        self.bus.write_byte(self.addr, data | self._bl_mask)

    def _pulse_enable(self, data: int):
        self._write_byte(data | self.EN)
        time.sleep(0.0005)
        self._write_byte(data & ~self.EN)
        time.sleep(0.0001)

    def _write4(self, nibble: int, rs: bool):
        data = (nibble << 4) & 0xF0
        if rs:
            data |= self.RS
        # RW=0
        self._pulse_enable(data)

    def _send(self, value: int, rs: bool):
        hi = (value >> 4) & 0x0F
        lo = value & 0x0F
        self._write4(hi, rs)
        self._write4(lo, rs)

    def command(self, cmd: int):
        self._send(cmd, rs=False)
        # 일부 명령은 지연이 필요
        if cmd in (0x01, 0x02):  # clear, home
            time.sleep(0.002)

    def write_char(self, ch: str):
        self._send(ord(ch), rs=True)

    def write_string(self, s: str):
        for ch in s:
            self.write_char(ch)

    def set_cursor(self, col: int, row: int):
        row_offsets = [0x00, 0x40]
        self.command(0x80 | (row_offsets[row] + col))

    def clear(self):
        self.command(0x01)

    def backlight_on(self):
        self.backlight = True
        self._bl_mask = self.BL
        self._write_byte(0x00)

    def backlight_off(self):
        self.backlight = False
        self._bl_mask = 0x00
        self._write_byte(0x00)

    def _init_lcd(self):
        time.sleep(0.05)

        # init sequence (4-bit)
        self._write4(0x03, rs=False)
        time.sleep(0.005)
        self._write4(0x03, rs=False)
        time.sleep(0.005)
        self._write4(0x03, rs=False)
        time.sleep(0.001)
        self._write4(0x02, rs=False)  # 4-bit

        self.command(0x28)  # 2-line, 5x8, 4-bit
        self.command(0x0C)  # display on, cursor off
        self.command(0x06)  # entry mode
        self.clear()

    def write_lines(self, line1: str, line2: str):
        # 16 chars each
        l1 = (line1 or "")[:16].ljust(16)
        l2 = (line2 or "")[:16].ljust(16)
        self.set_cursor(0, 0)
        self.write_string(l1)
        self.set_cursor(0, 1)
        self.write_string(l2)


if __name__ == "__main__":
    import time

    lcd = LCD1602_I2C(bus=1, addr=0x27)
    lcd.write_lines("Hello", "I2C OK!")
    
    # lcd.backlight_off()
    # time.sleep(3)
    # 또는
    #lcd.backlight_on()
    
    time.sleep(5)