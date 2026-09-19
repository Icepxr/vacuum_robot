"""air_sensor.py — ENS160 (eCO2/TVOC/AQI) + AHT21 (อุณหภูมิ/ความชื้น) บน I²C ของ Pi 5 (ไฟล์ 21 · 19 ก.ย. 2026)

ต่อสาย (ไฟล์ 21 §21.3): VIN ← 3V3 (pin 1) · GND pin 6 · SDA pin 3 · SCL pin 5 · ปล่อย 3V3/ADO/CS/INT ว่าง
ที่มาของ register/สูตร:
  ENS160 — datasheet v1.3 ในโปรเจกต์ (datasheet_component/ENS160.PDF) Table 16/18/23/25/26, §14.1:
    address 0x52 (ADDR ต่ำ) / 0x53 (ADDR สูง) · PART_ID 0x00 = 0x60,0x01 · OPMODE 0x10 (0x02 = STANDARD) ·
    TEMP_IN 0x13 = Kelvin×64 (LSB ก่อน) · RH_IN 0x15 = %RH×512 · DEVICE_STATUS 0x20 (bit1 NEWDAT · bit2-3 VALIDITY 0 ปกติ/1 warm-up 3 นาที/2 initial 1 ชม./3 invalid) ·
    DATA_AQI 0x21 (1–5) · DATA_TVOC 0x22 ppb · DATA_ECO2 0x24 ppm (LE)
  AHT21 — PDF ในโปรเจกต์อ่านข้อความไม่ได้ (เป็นรูป) → ใช้ตาม Adafruit_AHTX0 (รองรับ AHT20/21) [อ้างจาก library ไม่ใช่ datasheet]:
    address 0x38 · status bit7 busy · bit3 calibrated · init 0xBE 0x08 0x00 (AHT20/21) · trigger 0xAC 0x33 0x00 รอ ≥80 ms ·
    อ่าน 6 ไบต์: [status][H19..12][H11..4][H3..0|T19..16][T15..8][T7..0] · RH = raw/2^20×100 · T = raw/2^20×200 − 50
ไม่มีเซนเซอร์ → available False · ลองใหม่ทุก 10 s · ไม่ล้มเว็บ
"""
import threading
import time

ENS_ADDRS = (0x53, 0x52)
AHT_ADDR = 0x38
ECO2_RATING = ((600, "excellent"), (800, "good"), (1000, "fair"), (1500, "poor"))   # ENS160 Table 5


def eco2_rating(ppm):
    if ppm is None: return None
    for limit, name in ECO2_RATING:
        if ppm < limit: return name
    return "bad"


class AirSensor:
    def __init__(self, bus_no=1, period_s=2.0):
        self.bus_no, self.period_s = bus_no, period_s
        self.available = False
        self.ens_addr = None
        self.latest = {"eco2_ppm": None, "tvoc_ppb": None, "aqi": None, "validity": None,
                       "temp_c": None, "rh_pct": None, "rating": None, "ts": None, "error": None}
        self._stop = threading.Event()
        self._bus = None
        self._th = threading.Thread(target=self._run, name="air-sensor", daemon=True)

    # ── I²C helpers ──
    def _open(self):
        from smbus2 import SMBus, i2c_msg   # noqa: F401
        self._bus = SMBus(self.bus_no)

    def _ens_probe(self):
        for a in ENS_ADDRS:
            try:
                pid = self._bus.read_i2c_block_data(a, 0x00, 2)
                if pid == [0x60, 0x01]:
                    self.ens_addr = a
                    self._bus.write_byte_data(a, 0x10, 0x02)        # OPMODE STANDARD
                    return True
            except OSError:
                continue
        return False

    def _aht_init(self):
        try:
            st = self._bus.read_byte(AHT_ADDR)
            if not (st & 0x08):
                self._bus.write_i2c_block_data(AHT_ADDR, 0xBE, [0x08, 0x00])
                time.sleep(0.01)
            return True
        except OSError:
            return False

    def _aht_read(self):
        self._bus.write_i2c_block_data(AHT_ADDR, 0xAC, [0x33, 0x00])
        time.sleep(0.08)
        for _ in range(10):
            d = self._bus.read_i2c_block_data(AHT_ADDR, 0x00, 6)
            if not (d[0] & 0x80): break
            time.sleep(0.01)
        h = ((d[1] << 16) | (d[2] << 8) | d[3]) >> 4
        t = ((d[3] & 0x0F) << 16) | (d[4] << 8) | d[5]
        return round(t * 200 / 2**20 - 50, 1), round(h * 100 / 2**20, 1)

    def _ens_compensate(self, temp_c, rh):
        tk = int(round((temp_c + 273.15) * 64)); rr = int(round(rh * 512))
        self._bus.write_i2c_block_data(self.ens_addr, 0x13, [tk & 0xFF, tk >> 8])
        self._bus.write_i2c_block_data(self.ens_addr, 0x15, [rr & 0xFF, rr >> 8])

    def _ens_read(self):
        st = self._bus.read_byte_data(self.ens_addr, 0x20)
        validity = (st >> 2) & 0x03
        aqi = self._bus.read_byte_data(self.ens_addr, 0x21) & 0x07
        tv = self._bus.read_i2c_block_data(self.ens_addr, 0x22, 2)
        co = self._bus.read_i2c_block_data(self.ens_addr, 0x24, 2)
        return validity, aqi, tv[0] | (tv[1] << 8), co[0] | (co[1] << 8)

    # ── loop ──
    def _run(self):
        while not self._stop.is_set():
            if not self.available:
                try:
                    if self._bus is None: self._open()
                    ens = self._ens_probe(); aht = self._aht_init()
                    self.available = ens or aht
                    self.latest["error"] = None if self.available else "ไม่พบ ENS160 (0x52/0x53) และ AHT21 (0x38) บน I2C-%d" % self.bus_no
                    self._has_ens, self._has_aht = ens, aht
                except Exception as e:      # noqa: BLE001 — smbus2 ไม่มี / ไม่มี /dev/i2c-1
                    self.latest["error"] = f"{type(e).__name__}: {e}"
                if not self.available:
                    self._stop.wait(10.0); continue
            try:
                if self._has_aht:
                    t, h = self._aht_read()
                    self.latest["temp_c"], self.latest["rh_pct"] = t, h
                    if self._has_ens: self._ens_compensate(t, h)
                if self._has_ens:
                    v, aqi, tvoc, eco2 = self._ens_read()
                    self.latest.update(validity=v, aqi=aqi, tvoc_ppb=tvoc, eco2_ppm=eco2, rating=eco2_rating(eco2))
                self.latest["ts"] = time.time(); self.latest["error"] = None
            except OSError as e:
                self.latest["error"] = f"อ่านไม่ได้: {e}"; self.available = False   # สายหลุด → กลับไป probe
            self._stop.wait(self.period_s)

    def start(self): self._th.start(); return self
    def stop(self):  self._stop.set()


if __name__ == "__main__":
    s = AirSensor().start()
    for _ in range(8):
        time.sleep(2.5); print(s.available, s.latest)
