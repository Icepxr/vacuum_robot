"""oled_status.py — จอ OLED เล็กบนหุ่น โชว์สถานะที่ต้องรู้โดยไม่ต้องเปิดเว็บ (19 ก.ย. 2026)

⚠ สมมติฐาน [ยังไม่ยืนยันกับจอที่ซื้อ]: SSD1306 128×64 I²C address 0x3C (จอ 0.96" ที่พบบ่อยสุด) — ถ้าเป็น SH1106 / 0x3D / 128×32
   แก้ค่า DRIVER / ADDR / SIZE ด้านล่าง (luma.oled รองรับ ssd1306, sh1106, ssd1309, ssd1315 …)
ต่อสาย: VCC ← 3V3 pin 1 · GND pin 6/9 · SDA pin 3 · SCL pin 5 — แชร์บัสเดียวกับ ENS160/AHT21 ได้ (address ต่างกัน 0x3C / 0x53 / 0x38)
ฟอนต์: ใช้ ASCII เท่านั้น (ฟอนต์ bitmap ในตัวไม่มีไทย) — ถ้าอยากได้ไทยต้องใส่ TTF (Noto Sans Thai) แล้วใช้ ImageFont.truetype
ไม่มีจอ → available False · ลองใหม่ทุก 10 s · ไม่ล้มเว็บ
"""
import threading
import time

DRIVER, ADDR, SIZE = "ssd1306", 0x3C, (128, 64)


class OledStatus:
    def __init__(self, get_status, bus_no=1, period_s=1.0):
        """get_status() → dict จาก Hub.status() (ip, link, tele, last_capture, air)"""
        self.get_status, self.bus_no, self.period_s = get_status, bus_no, period_s
        self.available = False
        self.error = None
        self._dev = None
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, name="oled", daemon=True)

    def _open(self):
        from luma.core.interface.serial import i2c
        from luma.oled import device as dev
        drv = getattr(dev, DRIVER)
        self._dev = drv(i2c(port=self.bus_no, address=ADDR), width=SIZE[0], height=SIZE[1])
        self._dev.contrast(128)

    @staticmethod
    def lines(s):
        """4 บรรทัด ASCII ≤ 21 ตัวอักษร (ฟอนต์ 6 px บนจอ 128 px)"""
        ip = (s.get("ip") or ["no-net"])[0]
        link = s.get("link") or {}
        tele = s.get("tele") or {}
        state = tele.get("state_name", "--") if link.get("alive") else "NO LINK"
        cap = s.get("last_reading") or {}
        rd = cap.get("value"); rd = f"{rd:g}" if isinstance(rd, (int, float)) else "--"
        air = s.get("air") or {}
        co2 = air.get("eco2_ppm"); t = air.get("temp_c"); rh = air.get("rh_pct")
        l4 = (f"CO2 {co2}" if co2 is not None else "CO2 --") + (f" {t:.0f}C" if t is not None else "") + (f" {rh:.0f}%" if rh is not None else "")
        if air.get("validity") in (1, 2): l4 += " warm"
        return [f"IP {ip}"[:21], f"ESP32 {state}"[:21], f"READ {rd}  cam {'ok' if s.get('cam_ok') else '--'}"[:21], l4[:21]]

    def _draw(self, ls):
        from luma.core.render import canvas
        with canvas(self._dev) as d:
            for i, l in enumerate(ls):
                d.text((0, i * 16), l, fill=255)

    def _run(self):
        while not self._stop.is_set():
            if not self.available:
                try:
                    self._open(); self.available = True; self.error = None
                except Exception as e:      # noqa: BLE001 — ไม่มีจอ/ไม่มี luma/ไม่มี i2c
                    self.error = f"{type(e).__name__}: {e}"; self._stop.wait(10.0); continue
            try:
                self._draw(self.lines(self.get_status()))
            except Exception as e:          # noqa: BLE001 — สายหลุดกลางทาง
                self.error = f"วาดไม่ได้: {e}"; self.available = False
            self._stop.wait(self.period_s)

    def start(self): self._th.start(); return self
    def stop(self):  self._stop.set()


if __name__ == "__main__":
    demo = {"ip": ["172.20.10.2"], "link": {"alive": True}, "tele": {"state_name": "MANUAL"}, "cam_ok": True,
            "last_capture": {"value": 1509}, "air": {"eco2_ppm": 620, "temp_c": 28.4, "rh_pct": 55.2, "validity": 0}}
    print("\n".join(OledStatus.lines(demo)))
    o = OledStatus(lambda: demo).start(); time.sleep(3); print("oled:", o.available, o.error)
