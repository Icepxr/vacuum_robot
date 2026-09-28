#!/usr/bin/env python3
"""
capture_daemon.py — ขั้น C ของแกนหลัก: ฟัง UART จาก ESP32 · ถ่าย · ตอบ · OCR ทีหลัง

    ESP32 ──#E,<ms>,CAPTURE_REQ,<n>──▶ daemon ── หยิบเฟรมล่าสุด → เขียน jpg ลง SD ──▶ $K,<n>,1 ──▶ ESP32
                                              └─ (หลังตอบแล้ว) OCR ใน thread → readings.jsonl

กติกาที่บังคับในไฟล์นี้ (software_architecture.md §3.1 · §6.1 · ไฟล์ 19 §19.4.1):
  1. ตอบ $K **ทันทีที่ภาพลง SD** — ไม่รอ OCR · ESP32 มีหน้าต่างแค่ 5 s
  2. กล้องเปิดค้างใน thread ตลอด — ห้ามเปิด-ปิดต่อรูป (1.66 s [วัดจริง])
  3. ไม่แตะเครือข่ายเลย — sync เป็นหน้าที่ของ sync_supabase.py
  4. บรรทัดที่ไม่ใช่เฟรม (boot log ของ ESP32) ทิ้งเงียบๆ

ใช้บน Pi:
    python src/capture_daemon.py                       # /dev/ttyAMA0 · กล้อง USB index 0
    python src/capture_daemon.py --port /dev/ttyUSB0   # ทดสอบผ่าน USB-TTL ก่อนต่อสาย GPIO
    python src/capture_daemon.py --image photo.jpg     # ไม่มีกล้อง: ใช้รูปนี้แทนทุกครั้ง (ทดสอบลิงก์ล้วนๆ)
    python src/capture_daemon.py --selftest            # ไม่แตะ serial: เปิดกล้อง → ถ่าย → เซฟ → OCR แล้วจับเวลา

ทดสอบบนโน้ตบุ๊กโดยไม่มี Pi/กล้อง/cv2: tests/test_capture_daemon.py (pty ปลอม + backend ปลอม)
"""
import argparse
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mrc_protocol as P  # noqa: E402
import mrc_config as CFG  # noqa: E402

CAPTURE_TIMEOUT_S = 5.0        # หน้าต่างของ state CAMERA_CAPTURE (system_architecture §6.1)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────
# backend กล้อง — สลับได้ เพื่อให้ตรรกะ handshake ทดสอบได้โดยไม่ต้องมี cv2
# ทุก backend ต้องมี:  latest() -> frame หรือ None   ·   save(frame) -> (ts, rid, img_name)
#                     ocr(frame, ts, rid, img_name) -> dict (record)   ·   close()
#                     preview_jpeg() -> bytes หรือ None  (เฟรมย่อสำหรับ /stream.mjpg ของ mrc_web.py)
# ─────────────────────────────────────────────────────────────

# ── C36 คุมกล้องผ่าน UVC (v4l2-ctl) — ซูม/แพน/ทิลต์/โฟกัส ──
# BRIO: zoom_absolute 100–500 (= 1–5×, ครอปจากเซนเซอร์ 4K → ที่เอาต์พุต 1080p ซูม ≤ 2× ไม่เสียรายละเอียด) · pan/tilt_absolute ±36000 step 3600
# (ขยับกรอบที่ครอปตอนซูม — ไม่ใช่กลไก) · focus_absolute 0–255 step 5 (ใช้ได้เมื่อปิด AF) · ชื่อ/ช่วงอ่านจาก --list-ctrls จริงตอนเปิดกล้อง ไม่ hardcode
UVC_NAMES = {"zoom": ("zoom_absolute",), "pan": ("pan_absolute",), "tilt": ("tilt_absolute",),
             "af": ("focus_automatic_continuous", "focus_auto"), "focus": ("focus_absolute",)}

def uvc_list_ctrls(dev):
    """{ชื่อ: {min,max,step,default,value}} จาก `v4l2-ctl -d dev --list-ctrls` · ไม่มี v4l2-ctl/ไม่ใช่ UVC → {}"""
    try:
        out = subprocess.run(["v4l2-ctl", "-d", str(dev), "--list-ctrls"], capture_output=True, text=True, timeout=3).stdout
    except Exception:                                # noqa: BLE001
        return {}
    ctrls = {}
    for line in out.splitlines():
        m = re.match(r"\s*(\w+)\s+0x[0-9a-f]+\s+\((\w+)\)\s*:(.*)", line)
        if not m:
            continue
        name, kind, rest = m.groups()
        kv = {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", rest)}
        if kind == "bool":
            kv.setdefault("min", 0); kv.setdefault("max", 1); kv.setdefault("step", 1)
        ctrls[name] = kv
    return ctrls


def find_camera(index=CFG.CAMERA_INDEX):
    """C45 เลือกอุปกรณ์กล้อง: index ≥ 0 = ใช้ตามนั้น · -1 = ชื่อคงที่ใน /dev/v4l/by-id (BRIO ขึ้นก่อน) · ไม่เจอ = 0
    (เลข /dev/videoN เปลี่ยนได้ทุกครั้งที่ USB หลุด-กลับ แต่ by-id ผูกกับรุ่น+serial ของกล้อง)"""
    if isinstance(index, int) and index >= 0:
        return index
    import glob
    found = sorted(glob.glob(CFG.CAMERA_BY_ID_GLOB), key=lambda p: ("BRIO" not in p, p))
    return found[0] if found else 0


class UsbCameraBackend:
    """BRIO ผ่าน OpenCV/V4L2 · MJPG 1080p เปิดค้างใน thread · เก็บเฟรม BGR ล่าสุด 1 เฟรม
    ตัวเลข: cap.read() ≈ 61 ms · imwrite 14 ms · resize 6 ms [วัดจริง 11 ก.ย. — ไฟล์ 19 §19.4.1]
    C36: ซูม/แพน/ทิลต์/โฟกัสผ่าน UVC ถ้ากล้องมี (BRIO) · ไม่มีก็ซูมแบบซอฟต์แวร์ (ครอปเฟรม 1080p — ใช้กับภาพสด/ถ่าย/OCR เหมือนกันหมด)"""

    def __init__(self, index=CFG.CAMERA_INDEX, size=CFG.CAMERA_SIZE, engine="sevenseg",
                 run_id=None, meter_type="water"):
        import cv2                                   # นำเข้าตรงนี้ให้ import โมดูลได้บนเครื่องที่ไม่มี cv2
        import meter_reader as MR
        self.cv2, self.MR = cv2, MR
        self.engine, self.run_id, self.meter_type = engine, run_id, meter_type
        self.cfg = MR.load_config()
        index = find_camera(index)
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise RuntimeError(f"เปิดกล้อง index {index} ไม่ได้")
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # ต้องตั้งก่อนขนาด
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        got = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        log(f"กล้อง {index}: {got[0]}x{got[1]}" + ("" if got == tuple(size) else f"  ⚠ ขอ {size}"))
        self._cap = cap
        self._frame, self._frame_ts = None, 0.0
        self._lock = threading.Lock()
        self.dev = f"/dev/video{index}" if isinstance(index, int) else str(index)
        self.uvc = uvc_list_ctrls(self.dev)                        # {} = ไม่มี v4l2-ctl หรือกล้องไม่เปิดเผย control
        self.ctl = {"zoom": 1.0, "pan": 0.0, "tilt": 0.0, "af": True, "focus": 0.5}   # ค่าที่ผู้ใช้ตั้ง (normalized)
        self.hw = {k: next((n for n in names if n in self.uvc), None) for k, names in UVC_NAMES.items()}
        if self.hw["zoom"]:
            z = self.uvc[self.hw["zoom"]]; self.zoom_max = z["max"] / max(1, z["min"])   # BRIO 500/100 = 5×
        else:
            self.zoom_max = 4.0                                    # ซอฟต์แวร์: 1080p/4 = 480×270 — เกินนี้ภาพแตกจนอ่านไม่ได้
        log(f"กล้อง control: " + (", ".join(f"{k}={v}" for k, v in self.hw.items() if v) or "ไม่มี UVC — ซูมซอฟต์แวร์") + f" · ซูมสูงสุด {self.zoom_max:g}×")
        self.set_control(zoom=1.0, pan=0.0, tilt=0.0, af=True)     # เริ่มที่ค่าเป็นกลางเสมอ (กล้องจำค่าเก่าข้ามการรีบูตได้)
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._reader, name="cam-reader", daemon=True)
        self._th.start()

    def _reader(self):
        while not self._stop.is_set():
            ok, frame = self._cap.read()             # บล็อก ~61 ms — จึงต้องอยู่ใน thread นี้
            if ok:
                with self._lock:
                    self._frame, self._frame_ts = frame, time.monotonic()
            else:
                time.sleep(0.05)

    def frame_age_s(self):
        """C45 วินาทีตั้งแต่เฟรมล่าสุด (inf = ยังไม่เคยได้) — camera_hotplug ใช้ตัดสินว่ากล้องหลุดกลางทาง"""
        with self._lock:
            return time.monotonic() - self._frame_ts if self._frame is not None else float("inf")

    def latest(self, max_age_s=1.0):
        with self._lock:
            frame, ts = self._frame, self._frame_ts
        if frame is None or time.monotonic() - ts > max_age_s:
            return None                              # กล้องหลุด/ค้าง → รายงานล้ม ไม่ส่งภาพเก่า
        if not self.hw["zoom"] and self.ctl["zoom"] > 1.001:       # ซูมซอฟต์แวร์: ครอปให้ทุกทาง (สด/ถ่าย/OCR) เห็นภาพเดียวกัน
            h, w = frame.shape[:2]; z = self.ctl["zoom"]
            cw, ch = int(w / z), int(h / z)
            cx = int((w - cw) / 2 * (1 + self.ctl["pan"])); cy = int((h - ch) / 2 * (1 - self.ctl["tilt"]))
            frame = frame[cy:cy + ch, cx:cx + cw]
        return frame

    # ── C36 ซูม/แพน/ทิลต์/โฟกัส ──
    def controls(self):
        """สิ่งที่หน้าเว็บต้องรู้: ทำอะไรได้บ้าง + ค่าปัจจุบัน (normalized: zoom 1..zoom_max · pan/tilt −1..1 · focus 0..1)"""
        return {"zoom_max": self.zoom_max, "hw": {k: bool(v) for k, v in self.hw.items()},
                "sw_zoom": not self.hw["zoom"], **self.ctl}

    def _uvc_set(self, key, raw):
        name = self.hw.get(key)
        if not name: return False
        try:
            subprocess.run(["v4l2-ctl", "-d", self.dev, f"--set-ctrl={name}={int(raw)}"], capture_output=True, timeout=2)
            return True
        except Exception:                            # noqa: BLE001
            return False

    def set_control(self, **kw):
        """ตั้งค่าที่ให้มา (zoom/pan/tilt/af/focus) · clamp เอง · คืน controls() หลังตั้ง"""
        if "zoom" in kw:
            self.ctl["zoom"] = max(1.0, min(self.zoom_max, float(kw["zoom"])))
            if self.hw["zoom"]:
                z = self.uvc[self.hw["zoom"]]; self._uvc_set("zoom", round(z["min"] * self.ctl["zoom"]))
        for k in ("pan", "tilt"):
            if k in kw:
                self.ctl[k] = max(-1.0, min(1.0, float(kw[k])))
                if self.hw[k]:
                    c = self.uvc[self.hw[k]]; step = max(1, c.get("step", 1))
                    raw = round(self.ctl[k] * c["max"] / step) * step                 # BRIO step 3600 — ต้องลงตัว ไม่งั้นกล้องปฏิเสธ
                    self._uvc_set(k, raw)
        if "af" in kw:
            self.ctl["af"] = bool(kw["af"])
            self._uvc_set("af", 1 if self.ctl["af"] else 0)
        if "focus" in kw:
            self.ctl["focus"] = max(0.0, min(1.0, float(kw["focus"])))
        if ("focus" in kw or ("af" in kw and not self.ctl["af"])) and self.hw["focus"] and not self.ctl["af"]:
            c = self.uvc[self.hw["focus"]]; step = max(1, c.get("step", 1))
            self._uvc_set("focus", round((c["min"] + self.ctl["focus"] * (c["max"] - c["min"])) / step) * step)
        return self.controls()

    def save(self, frame):
        return self.MR.save_image(frame)             # ต้นฉบับ 1080p q92 ลง data/images/

    def preview_jpeg(self, size=(640, 360), quality=80):
        """เฟรมย่อสำหรับภาพสด — resize+encode ≈ 6 ms · ~39 kB [วัดจริง ไฟล์ 19 §19.4.1]"""
        frame = self.latest()
        if frame is None:
            return None
        small = self.cv2.resize(frame, size, interpolation=self.cv2.INTER_AREA)
        ok, buf = self.cv2.imencode(".jpg", small, [self.cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else None

    def ocr(self, frame, ts, rid, img_name):
        MR = self.MR
        raw, conf, value, err = "", 0.0, None, None
        try:
            binimg, cropped = MR.preprocess(frame, self.cfg)
            raw, conf = MR.run_engine(self.engine, binimg, cropped, self.cfg)
            value = MR.parse_value(raw, self.cfg.get("expected_digits"), self.cfg.get("decimal_places"))
        except Exception as e:                       # noqa: BLE001 — OCR พังต้องไม่ล้ม daemon
            err = f"{type(e).__name__}: {e}"
        rec = MR.save_reading(ts, rid, img_name, raw, value, conf, self.run_id, self.meter_type, "usb")
        if err:
            rec["error"] = err
        return rec

    def close(self):
        self._stop.set()
        self._th.join(timeout=1.0)
        self._cap.release()


class StillImageBackend:
    """ไม่มีกล้อง: ใช้รูปเดิมทุกครั้ง — ไว้ทดสอบลิงก์/จังหวะเวลาโดยไม่ต้องเล็งมิเตอร์"""

    def __init__(self, path, **kw):
        import cv2
        import meter_reader as MR
        self.MR = MR
        self._img = cv2.imread(str(path))
        if self._img is None:
            raise RuntimeError(f"อ่านรูปไม่ได้: {path}")
        self._real = None

    def latest(self):            return self._img
    def save(self, frame):       return self.MR.save_image(frame)
    def ocr(self, frame, ts, rid, img_name):
        # ไม่ทำ OCR แต่ต้องเขียน record ให้ครบเหมือนกล้องจริง ไม่งั้นหน้าเว็บ/sync ได้แถวไม่มี captured_at
        return self.MR.save_reading(ts, rid, img_name, "", None, 0.0, None, "stub", "image-stub")
    def preview_jpeg(self, size=(640, 360), quality=80):
        import cv2
        ok, buf = cv2.imencode(".jpg", cv2.resize(self._img, size), [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else None
    def close(self):             pass


# ─────────────────────────────────────────────────────────────
# ตัว daemon — ตรรกะ handshake ล้วนๆ ไม่รู้จัก cv2
# ─────────────────────────────────────────────────────────────

class CaptureDaemon:
    """on_event(dict) ถูกเรียกจาก thread ของ daemon ทุกครั้งที่มีอะไรเกิดขึ้น (mrc_web.py ใช้ส่งขึ้น WebSocket)
    ชนิดเหตุการณ์: link · capture · reading · log — ห้ามบล็อกใน callback"""

    def __init__(self, port, backend, baud=115200, ocr_async=True, on_event=None):
        self.backend = backend
        self.ocr_async = ocr_async
        self.on_event = on_event or (lambda ev: None)
        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.stats = {"req": 0, "ok": 0, "fail": 0, "bad_lines": 0, "manual": 0, "tx": 0, "ack": 0, "nack": 0}
        self.last_rx_mono = None            # เวลาที่ได้เฟรมถูกต้องล่าสุด (ดูว่า ESP32 ยังคุยอยู่ไหม)
        self.tele = None                    # #T ล่าสุด (dict) — ขั้น E
        self.tele_mono = None
        self._seq = 0
        self._tx_lock = threading.Lock()    # ส่งจากหลาย thread (deadman/repeat/ws) ห้ามสลับ byte กัน
        self._stop = threading.Event()
        self._cap_lock = threading.Lock()   # กัน CAPTURE_REQ กับปุ่มบนเว็บถ่ายพร้อมกัน

    # ── ส่งคำสั่งไป ESP32 (ขั้น E) — คืน seq ที่ใช้ เพื่อจับคู่กับ #A/#N ──
    def send(self, builder, *args):
        with self._tx_lock:
            self._seq = (self._seq + 1) % 1_000_000
            seq = self._seq
            try:
                self.ser.write(builder(seq, *args))
                self.stats["tx"] += 1
            except (serial.SerialException, OSError) as e:
                log(f"ส่งไม่ได้: {e}")
                return None
        return seq

    def send_velocity(self, v, w):   return self.send(P.cmd_velocity, v, w)
    def send_stop(self):             return self.send(P.cmd_stop)
    def send_estop(self):            return self.send(P.cmd_estop)
    def send_clean(self, suc, br):   return self.send(P.cmd_clean, suc, br)
    def send_ping(self):             return self.send(P.cmd_ping)
    def send_limits(self, v, w):     return self.send(P.cmd_limits, v, w)
    def send_servo_x(self, us):      return self.send(P.cmd_servo_x, us)
    def send_mast(self, us):         return self.send(P.cmd_mast, us)
    def send_display(self, *a):      return self.send(P.cmd_display, *a)

    def _emit(self, ev):
        try:
            self.on_event(ev)
        except Exception as e:              # noqa: BLE001 — callback พังต้องไม่ล้ม daemon
            log(f"on_event พัง: {e}")

    def _save_then_ocr(self, frame, n, source):
        """เส้นทางร่วมของ CAPTURE_REQ และปุ่มบนเว็บ: เซฟ → (ผู้เรียกตอบ $K) → OCR ใน thread
        คืน (ok, img_name, t_save_ms)"""
        t0 = time.monotonic()
        try:
            ts, rid, img_name = self.backend.save(frame)
        except Exception as e:              # noqa: BLE001
            return False, None, (time.monotonic() - t0) * 1000, str(e)
        t_save = (time.monotonic() - t0) * 1000

        def _ocr():
            t1 = time.monotonic()
            rec = self.backend.ocr(frame, ts, rid, img_name)
            rec = dict(rec, ocr_ms=round((time.monotonic() - t1) * 1000), source_req=source, n=n)
            log(f"  OCR #{n}: value={rec.get('value')} conf={rec.get('confidence')} "
                f"raw={rec.get('raw_text')!r} ใน {rec['ocr_ms']} ms"
                + (f"  ⚠ {rec['error']}" if rec.get("error") else ""))
            self._emit({"t": "reading", **rec})
        if self.ocr_async:
            threading.Thread(target=_ocr, name=f"ocr-{n}", daemon=True).start()
        else:
            _ocr()
        return True, img_name, t_save, None

    def capture_now(self):
        """ถ่ายจากปุ่มบนเว็บ — ไม่เกี่ยวกับ ESP32 ไม่ส่ง $K · ไว้จูน ROI ที่สนามโดยไม่ต้องยกเสา"""
        with self._cap_lock:
            self.stats["manual"] += 1
            n = f"m{self.stats['manual']}"
            frame = self.backend.latest()
            if frame is None:
                self._emit({"t": "capture", "n": n, "ok": False, "reason": "no_frame", "source": "web"})
                return False
            ok, img_name, t_save, err = self._save_then_ocr(frame, n, "web")
            self._emit({"t": "capture", "n": n, "ok": ok, "image": img_name, "t_ack_ms": round(t_save),
                        "source": "web", **({"reason": err} if err else {})})
            log(f"ถ่ายจากเว็บ #{n}: {'ภาพ ' + img_name if ok else 'ล้ม ' + str(err)} ({t_save:.0f} ms)")
            return ok

    def handle_capture_req(self, fr):
        n = fr.fields[3]
        with self._cap_lock:
            t0 = time.monotonic()
            frame = self.backend.latest()
            if frame is None:
                self.stats["fail"] += 1
                self.ser.write(P.capture_ack(n, False))
                log(f"CAPTURE_REQ #{n}: ไม่มีเฟรมจากกล้อง → $K,{n},0")
                self._emit({"t": "capture", "n": n, "ok": False, "reason": "no_frame", "source": "esp32"})
                return
            ok, img_name, t_save, err = self._save_then_ocr(frame, n, "esp32")
            if not ok:
                self.stats["fail"] += 1
                self.ser.write(P.capture_ack(n, False))
                log(f"CAPTURE_REQ #{n}: เขียนภาพล้ม ({err}) → $K,{n},0")
                self._emit({"t": "capture", "n": n, "ok": False, "reason": err, "source": "esp32"})
                return
            # ── ตอบตรงนี้ ก่อน OCR — จุดที่สำคัญที่สุดของไฟล์ ──
            self.stats["ok"] += 1
            self.ser.write(P.capture_ack(n, True))
            self.ser.flush()
            t_ack = (time.monotonic() - t0) * 1000
        log(f"CAPTURE_REQ #{n}: ภาพ {img_name} ลง SD · ตอบ $K ใน {t_ack:.0f} ms"
            + ("" if t_ack < CAPTURE_TIMEOUT_S * 1000 * 0.5 else "  ⚠ ช้าเกินครึ่งหน้าต่าง 5 s"))
        self._emit({"t": "capture", "n": n, "ok": True, "image": img_name, "t_ack_ms": round(t_ack), "source": "esp32"})

    def run_once(self):
        """อ่าน 1 บรรทัด (หรือ timeout) แล้วจัดการ — แยกไว้ให้เทสต์เรียกได้"""
        line = self.ser.readline()
        if not line:
            return
        fr = P.decode(line)
        if fr is None:
            self.stats["bad_lines"] += 1           # boot log / CRC ผิด — ทิ้งเงียบ (§3.7 ข้อ 3)
            return
        self.last_rx_mono = time.monotonic()
        if fr.type == "T":                                  # telemetry 10 Hz — ไม่ log ทุกเฟรม
            t = P.parse_tele(fr)
            if t is not None:
                self.tele, self.tele_mono = t, time.monotonic()
                self._emit({"t": "tele", **t})
            else:
                self.stats["bad_lines"] += 1
        elif fr.type == "A" and len(fr.fields) >= 2:
            self.stats["ack"] += 1
            self._emit({"t": "ack", "seq": int(fr.fields[1]) if fr.fields[1].isdigit() else fr.fields[1]})
        elif fr.type == "N" and len(fr.fields) >= 3:
            self.stats["nack"] += 1
            log(f"ESP32 ปฏิเสธ seq {fr.fields[1]}: {fr.fields[2]}")
            self._emit({"t": "nack", "seq": int(fr.fields[1]) if fr.fields[1].isdigit() else fr.fields[1], "reason": fr.fields[2]})
        elif P.is_capture_req(fr):
            self.stats["req"] += 1
            self.handle_capture_req(fr)
        elif fr.type == "E" and len(fr.fields) >= 3:
            log(f"เหตุการณ์จาก ESP32: {fr.fields[2]} {fr.fields[3] if len(fr.fields) > 3 else ''}")
            self._emit({"t": "event", "code": fr.fields[2], "detail": fr.fields[3] if len(fr.fields) > 3 else ""})
        else:
            log(f"เฟรมที่ยังไม่รองรับ: {line.strip()!r}")

    def run(self):
        """วนอ่านตลอด · ถ้าพอร์ตหาย (สายหลุด/USB-TTL ถูกดึง) จะพยายามเปิดใหม่ทุก 2 s แทนที่จะตายเงียบ"""
        log(f"ฟัง {self.ser.port} @ {self.ser.baudrate} · รอ CAPTURE_REQ (Ctrl-C เพื่อหยุด)")
        try:
            while not self._stop.is_set():
                try:
                    self.run_once()
                except (serial.SerialException, OSError) as e:
                    if self._stop.is_set():
                        break
                    self.port_errors = getattr(self, "port_errors", 0) + 1
                    log(f"พอร์ต {self.ser.port} มีปัญหา ({e}) — จะลองเปิดใหม่ใน 2 s")
                    self._emit({"t": "log", "level": "bad", "msg": f"serial หลุด: {e}"})
                    self._reopen()
        finally:
            self.close()

    def _reopen(self):
        port, baud = self.ser.port, self.ser.baudrate
        try:
            self.ser.close()
        except Exception:                    # noqa: BLE001
            pass
        while not self._stop.is_set():
            self._stop.wait(2.0)
            if self._stop.is_set():
                return
            try:
                self.ser = serial.Serial(port, baud, timeout=0.2)
                log(f"เปิด {port} ใหม่สำเร็จ")
                self._emit({"t": "log", "level": "good", "msg": f"serial กลับมา: {port}"})
                return
            except (serial.SerialException, OSError):
                continue

    def stop(self):
        self._stop.set()

    def close(self):
        self.backend.close()
        try:
            self.ser.close()
        except Exception:                    # noqa: BLE001
            pass
        log(f"ปิด · สถิติ {self.stats}")


def selftest(backend, rounds=3):
    """เส้นทางกล้อง→SD→OCR แบบเดียวกับตอนรับ CAPTURE_REQ แต่ไม่มี serial — ไว้เช็คบน Pi ก่อนต่อสาย
    ตัวเลขที่ได้ = t_capture + t_write ของไฟล์ 19 §19.4.1 (เอาไปเทียบ 71 + 14 ms)"""
    log("selftest: รอเฟรมแรกจากกล้อง…")
    t0 = time.monotonic()
    while backend.latest() is None:
        if time.monotonic() - t0 > 5:
            log("✗ ไม่ได้เฟรมใน 5 s — กล้องไม่ส่งภาพ"); return 1
        time.sleep(0.05)
    log(f"  เฟรมแรกหลัง {(time.monotonic()-t0)*1000:.0f} ms")
    for i in range(1, rounds + 1):
        t1 = time.monotonic()
        frame = backend.latest()
        t2 = time.monotonic()
        ts, rid, img_name = backend.save(frame)
        t3 = time.monotonic()
        rec = backend.ocr(frame, ts, rid, img_name)
        t4 = time.monotonic()
        log(f"  รอบ {i}: หยิบเฟรม {(t2-t1)*1000:.0f} ms · เซฟ {img_name} {(t3-t2)*1000:.0f} ms "
            f"(= t_ack ก่อนบวก UART) · OCR {(t4-t3)*1000:.0f} ms → value={rec.get('value')} "
            f"conf={rec.get('confidence')} raw={rec.get('raw_text')!r}"
            + (f"  ⚠ {rec['error']}" if rec.get("error") else ""))
        time.sleep(0.3)
    log("selftest จบ — ภาพอยู่ใน data/images/ · บรรทัดใน data/readings.jsonl")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=CFG.SERIAL_PORT)
    ap.add_argument("--baud", type=int, default=CFG.SERIAL_BAUD)
    ap.add_argument("--camera", type=int, default=CFG.CAMERA_INDEX, help="index ของกล้อง USB · -1 = หาเองจาก /dev/v4l/by-id")
    ap.add_argument("--image", help="ใช้รูปนี้แทนกล้อง (ทดสอบลิงก์)")
    ap.add_argument("--engine", choices=["sevenseg", "tesseract", "ssocr"], default="sevenseg")
    ap.add_argument("--meter-type", default="water")
    ap.add_argument("--run-id", default=time.strftime("run_%Y%m%d_%H%M%S"))
    ap.add_argument("--selftest", action="store_true", help="ทดสอบกล้อง→SD→OCR โดยไม่แตะ serial")
    args = ap.parse_args()

    if args.image:
        backend = StillImageBackend(args.image)
    else:
        backend = UsbCameraBackend(args.camera, engine=args.engine,
                                   run_id=args.run_id, meter_type=args.meter_type)
    if args.selftest:
        try:
            sys.exit(selftest(backend))
        finally:
            backend.close()
    CaptureDaemon(args.port, backend, args.baud).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
