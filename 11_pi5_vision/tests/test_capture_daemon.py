"""ทดสอบ handshake ของ capture_daemon.py บนโน้ตบุ๊ก — ไม่ต้องมี Pi/กล้อง/cv2
ใช้ pty ปลอมแทน /dev/ttyAMA0 และ backend ปลอมแทนกล้อง  ·  python -m pytest tests/ -q"""
import os
import pty
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import mrc_protocol as P            # noqa: E402
import capture_daemon as D          # noqa: E402


class FakeBackend:
    def __init__(self, tmp, have_frame=True, save_delay=0.0, ocr_delay=0.0):
        self.tmp, self.have_frame = tmp, have_frame
        self.save_delay, self.ocr_delay = save_delay, ocr_delay
        self.saved, self.ocr_done = [], []
        self.closed = False

    def latest(self):
        return b"FRAME" if self.have_frame else None

    def save(self, frame):
        time.sleep(self.save_delay)
        ts = datetime.now(timezone.utc)
        name = f"img_{len(self.saved)}.jpg"
        (self.tmp / name).write_bytes(frame)
        self.saved.append(name)
        return ts, f"rid{len(self.saved)}", name

    def ocr(self, frame, ts, rid, img_name):
        time.sleep(self.ocr_delay)
        self.ocr_done.append(img_name)
        return {"value": 123.4, "confidence": 0.9, "raw_text": "123.4"}

    def close(self):
        self.closed = True


@pytest.fixture
def link(tmp_path):
    """คืน (master_fd, daemon, backend) — daemon รันใน thread บน pty slave"""
    master, slave = pty.openpty()
    backend = FakeBackend(tmp_path)
    d = D.CaptureDaemon(os.ttyname(slave), backend)
    th = threading.Thread(target=d.run, daemon=True)
    th.start()
    yield master, d, backend
    d.stop()
    th.join(timeout=2)
    os.close(master)


def read_line(fd, timeout=2.0):
    """อ่าน 1 บรรทัดจาก pty master · คืน b"" ถ้าไม่มีอะไรมาใน timeout (ไม่บล็อกค้าง)"""
    import select
    buf = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        r, _, _ = select.select([fd], [], [], max(0.0, end - time.monotonic()))
        if not r:
            break
        ch = os.read(fd, 1)
        buf += ch
        if ch == b"\n":
            return buf
    return buf


def test_capture_req_gets_ack_and_image_saved(link):
    master, d, backend = link
    os.write(master, P.capture_req(5000, 3))
    reply = P.decode(read_line(master))
    assert reply is not None and reply.kind == "$" and reply.fields == ["K", "3", "1"]
    assert backend.saved == ["img_0.jpg"]
    assert d.stats["ok"] == 1


def test_ack_sent_before_ocr_finishes(link):
    """กติกาข้อ 1: $K ต้องมาก่อน OCR เสร็จ — OCR ช้า 1 s แต่ $K ต้องมาใน < 0.5 s"""
    master, d, backend = link
    backend.ocr_delay = 1.0
    t0 = time.monotonic()
    os.write(master, P.capture_req(1, 1))
    reply = P.decode(read_line(master))
    dt = time.monotonic() - t0
    assert reply.fields == ["K", "1", "1"]
    assert dt < 0.5, f"$K มาช้า {dt:.2f}s — รอ OCR ก่อนตอบ?"
    assert backend.ocr_done == []           # OCR ยังไม่เสร็จตอนที่ $K มาแล้ว
    time.sleep(1.2)
    assert backend.ocr_done == ["img_0.jpg"]


def test_no_frame_replies_fail(link):
    master, d, backend = link
    backend.have_frame = False
    os.write(master, P.capture_req(1, 9))
    reply = P.decode(read_line(master))
    assert reply.fields == ["K", "9", "0"]
    assert backend.saved == [] and d.stats["fail"] == 1


def test_boot_log_and_bad_crc_ignored(link):
    master, d, backend = link
    os.write(master, b"ESP-ROM:esp32s3-20210327\r\nrst:0x1 (POWERON)\n")
    os.write(master, b"#E,1,CAPTURE_REQ,2*00\n")            # CRC ผิด
    time.sleep(0.5)
    assert backend.saved == [] and d.stats["req"] == 0 and d.stats["bad_lines"] >= 2
    os.write(master, P.capture_req(1, 2))                     # ของจริงตามหลังต้องยังทำงาน
    assert P.decode(read_line(master)).fields == ["K", "2", "1"]


def test_seq_echoes_request_n(link):
    master, d, backend = link
    for n in (10, 11, 12):
        os.write(master, P.capture_req(n * 100, n))
        assert P.decode(read_line(master)).fields[1] == str(n)
    assert len(backend.saved) == 3


def test_serial_loss_does_not_kill_daemon(tmp_path):
    """สายหลุดกลางทาง: thread ต้องไม่ตาย และเมื่อพอร์ตกลับมาต้องรับ CAPTURE_REQ ได้ต่อ"""
    master, slave = pty.openpty()
    name = os.ttyname(slave)
    backend = FakeBackend(tmp_path)
    d = D.CaptureDaemon(name, backend)
    th = threading.Thread(target=d.run, daemon=True); th.start()
    os.write(master, P.capture_req(1, 1))
    assert P.decode(read_line(master)).fields == ["K", "1", "1"]
    os.close(master)                         # "ดึงสาย"
    time.sleep(0.6)
    assert th.is_alive()
    assert getattr(d, "port_errors", 0) >= 1
    d.stop(); th.join(timeout=5)
    assert not th.is_alive()
