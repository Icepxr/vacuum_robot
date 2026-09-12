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

ทดสอบบนโน้ตบุ๊กโดยไม่มี Pi/กล้อง/cv2: tests/test_capture_daemon.py (pty ปลอม + backend ปลอม)
"""
import argparse
import sys
import threading
import time
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mrc_protocol as P  # noqa: E402

CAPTURE_TIMEOUT_S = 5.0        # หน้าต่างของ state CAMERA_CAPTURE (system_architecture §6.1)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────
# backend กล้อง — สลับได้ เพื่อให้ตรรกะ handshake ทดสอบได้โดยไม่ต้องมี cv2
# ทุก backend ต้องมี:  latest() -> frame หรือ None   ·   save(frame) -> (ts, rid, img_name)
#                     ocr(frame, ts, rid, img_name) -> dict (record)   ·   close()
# ─────────────────────────────────────────────────────────────

class UsbCameraBackend:
    """BRIO ผ่าน OpenCV/V4L2 · MJPG 1080p เปิดค้างใน thread · เก็บเฟรม BGR ล่าสุด 1 เฟรม
    ตัวเลข: cap.read() ≈ 61 ms · imwrite 14 ms · resize 6 ms [วัดจริง 11 ก.ย. — ไฟล์ 19 §19.4.1]"""

    def __init__(self, index=0, size=(1920, 1080), engine="tesseract",
                 run_id=None, meter_type="water"):
        import cv2                                   # นำเข้าตรงนี้ให้ import โมดูลได้บนเครื่องที่ไม่มี cv2
        import meter_reader as MR
        self.cv2, self.MR = cv2, MR
        self.engine, self.run_id, self.meter_type = engine, run_id, meter_type
        self.cfg = MR.load_config()
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise RuntimeError(f"เปิดกล้อง index {index} ไม่ได้")
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # ต้องตั้งก่อนขนาด
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        got = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        log(f"กล้อง index {index}: {got[0]}x{got[1]}" + ("" if got == tuple(size) else f"  ⚠ ขอ {size}"))
        self._cap = cap
        self._frame, self._frame_ts = None, 0.0
        self._lock = threading.Lock()
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

    def latest(self, max_age_s=1.0):
        with self._lock:
            frame, ts = self._frame, self._frame_ts
        if frame is None or time.monotonic() - ts > max_age_s:
            return None                              # กล้องหลุด/ค้าง → รายงานล้ม ไม่ส่งภาพเก่า
        return frame

    def save(self, frame):
        return self.MR.save_image(frame)             # ต้นฉบับ 1080p q92 ลง data/images/

    def ocr(self, frame, ts, rid, img_name):
        MR = self.MR
        raw, conf, value, err = "", 0.0, None, None
        try:
            binimg, _ = MR.preprocess(frame, self.cfg)
            raw, conf = MR.OCR_ENGINES[self.engine](binimg)
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
    def ocr(self, *a):           return {"note": "StillImageBackend ไม่ทำ OCR"}
    def close(self):             pass


# ─────────────────────────────────────────────────────────────
# ตัว daemon — ตรรกะ handshake ล้วนๆ ไม่รู้จัก cv2
# ─────────────────────────────────────────────────────────────

class CaptureDaemon:
    def __init__(self, port, backend, baud=115200, ocr_async=True):
        self.backend = backend
        self.ocr_async = ocr_async
        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.stats = {"req": 0, "ok": 0, "fail": 0, "bad_lines": 0}
        self._stop = threading.Event()

    def handle_capture_req(self, fr):
        n = fr.fields[3]
        t0 = time.monotonic()
        frame = self.backend.latest()
        if frame is None:
            self.ser.write(P.capture_ack(n, False))
            self.stats["fail"] += 1
            log(f"CAPTURE_REQ #{n}: ไม่มีเฟรมจากกล้อง → $K,{n},0")
            return
        try:
            ts, rid, img_name = self.backend.save(frame)
        except Exception as e:                       # noqa: BLE001
            self.ser.write(P.capture_ack(n, False))
            self.stats["fail"] += 1
            log(f"CAPTURE_REQ #{n}: เขียนภาพล้ม ({e}) → $K,{n},0")
            return
        # ── ตอบตรงนี้ ก่อน OCR — จุดที่สำคัญที่สุดของไฟล์ ──
        self.stats["ok"] += 1
        self.ser.write(P.capture_ack(n, True))
        self.ser.flush()
        t_ack = (time.monotonic() - t0) * 1000
        log(f"CAPTURE_REQ #{n}: ภาพ {img_name} ลง SD · ตอบ $K ใน {t_ack:.0f} ms"
            + ("" if t_ack < CAPTURE_TIMEOUT_S * 1000 * 0.5 else "  ⚠ ช้าเกินครึ่งหน้าต่าง 5 s"))

        def _ocr():
            t1 = time.monotonic()
            rec = self.backend.ocr(frame, ts, rid, img_name)
            log(f"  OCR #{n}: value={rec.get('value')} conf={rec.get('confidence')} "
                f"raw={rec.get('raw_text')!r} ใน {(time.monotonic()-t1)*1000:.0f} ms"
                + (f"  ⚠ {rec['error']}" if rec.get("error") else ""))
        if self.ocr_async:
            threading.Thread(target=_ocr, name=f"ocr-{n}", daemon=True).start()
        else:
            _ocr()

    def run_once(self):
        """อ่าน 1 บรรทัด (หรือ timeout) แล้วจัดการ — แยกไว้ให้เทสต์เรียกได้"""
        line = self.ser.readline()
        if not line:
            return
        fr = P.decode(line)
        if fr is None:
            self.stats["bad_lines"] += 1           # boot log / CRC ผิด — ทิ้งเงียบ (§3.7 ข้อ 3)
            return
        if P.is_capture_req(fr):
            self.stats["req"] += 1
            self.handle_capture_req(fr)
        else:
            log(f"เฟรมที่ยังไม่รองรับในขั้น C: {line.strip()!r}")

    def run(self):
        log(f"ฟัง {self.ser.port} @ {self.ser.baudrate} · รอ CAPTURE_REQ (Ctrl-C เพื่อหยุด)")
        try:
            while not self._stop.is_set():
                self.run_once()
        finally:
            self.close()

    def stop(self):
        self._stop.set()

    def close(self):
        self.backend.close()
        self.ser.close()
        log(f"ปิด · สถิติ {self.stats}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--camera", type=int, default=0, help="index ของกล้อง USB")
    ap.add_argument("--image", help="ใช้รูปนี้แทนกล้อง (ทดสอบลิงก์)")
    ap.add_argument("--engine", choices=["tesseract", "ssocr"], default="tesseract")
    ap.add_argument("--meter-type", default="water")
    ap.add_argument("--run-id", default=time.strftime("run_%Y%m%d_%H%M%S"))
    args = ap.parse_args()

    if args.image:
        backend = StillImageBackend(args.image)
    else:
        backend = UsbCameraBackend(args.camera, engine=args.engine,
                                   run_id=args.run_id, meter_type=args.meter_type)
    CaptureDaemon(args.port, backend, args.baud).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
