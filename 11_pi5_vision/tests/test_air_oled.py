"""air_sensor / oled_status — ไม่มีฮาร์ดแวร์: ต้องไม่ล้ม · สูตรแปลงค่า AHT21/ENS160 ตรงตามที่จดในหัวไฟล์"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import air_sensor as A     # noqa: E402
import oled_status as O    # noqa: E402


class FakeBus:
    """ENS160 ที่ 0x53 + AHT21 ที่ 0x38 — ค่าคงที่: eCO2 620 · TVOC 100 · AQI 2 · validity 0 · AHT raw ตั้งให้ได้ 25.0 °C / 50.0 %"""
    def __init__(self): self.w = []
    def read_i2c_block_data(self, addr, reg, n):
        if addr == 0x53:
            return {0x00: [0x60, 0x01], 0x22: [100, 0], 0x24: [620 & 0xFF, 620 >> 8]}[reg]
        if addr == 0x38:                       # H = 0.5×2^20 = 0x80000 · T = (25+50)/200×2^20 = 0x60000
            h, t = 0x80000, 0x60000
            return [0x1C, (h >> 12) & 0xFF, (h >> 4) & 0xFF, ((h & 0xF) << 4) | ((t >> 16) & 0xF), (t >> 8) & 0xFF, t & 0xFF]
        raise OSError("no device")
    def read_byte_data(self, addr, reg): return {0x20: 0x02, 0x21: 0x02}[reg]
    def read_byte(self, addr): return 0x18 if addr == 0x38 else (_ for _ in ()).throw(OSError())
    def write_byte_data(self, a, r, v): self.w.append((a, r, v))
    def write_i2c_block_data(self, a, r, d): self.w.append((a, r, tuple(d)))


def test_conversion_with_fake_bus():
    s = A.AirSensor(); s._bus = FakeBus()
    assert s._ens_probe() and s.ens_addr == 0x53 and (0x53, 0x10, 0x02) in s._bus.w
    assert s._aht_init()
    t, h = s._aht_read(); assert (t, h) == (25.0, 50.0)
    s._ens_compensate(t, h)
    tk = int(round((25 + 273.15) * 64)); assert (0x53, 0x13, (tk & 0xFF, tk >> 8)) in s._bus.w      # Kelvin×64 = 0x4A8A ตาม datasheet
    assert tk == 0x4A8A
    assert (0x53, 0x15, (50 * 512 & 0xFF, 50 * 512 >> 8)) in s._bus.w                             # %RH×512
    v, aqi, tvoc, eco2 = s._ens_read(); assert (v, aqi, tvoc, eco2) == (0, 2, 100, 620)
    assert A.eco2_rating(620) == "good" and A.eco2_rating(1600) == "bad" and A.eco2_rating(450) == "excellent"


def test_no_hardware_does_not_crash():
    s = A.AirSensor(bus_no=99).start()
    import time; time.sleep(0.3)
    assert s.available is False and s.latest["error"]
    s.stop()
    o = O.OledStatus(lambda: {}).start(); time.sleep(0.3)
    assert o.available is False and o.error
    o.stop()


def test_oled_lines_fit_and_handle_missing():
    ls = O.OledStatus.lines({})
    assert len(ls) == 4 and all(len(l) <= 21 for l in ls) and ls[0] == "IP no-net" and "NO LINK" in ls[1]
    ls = O.OledStatus.lines({"ip": ["172.20.10.2"], "link": {"alive": True}, "tele": {"state_name": "MANUAL"}, "cam_ok": True,
                             "last_capture": {"value": 1509.0}, "air": {"eco2_ppm": 620, "temp_c": 28.4, "rh_pct": 55.2, "validity": 1}})
    assert ls == ["IP 172.20.10.2", "ESP32 MANUAL", "READ 1509  cam ok", "CO2 620 28C 55% warm"]
