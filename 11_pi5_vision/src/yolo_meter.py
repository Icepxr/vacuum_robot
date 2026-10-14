"""engine `yolo` (ทดลอง · branch yolo-live-test · 14 ต.ค. 2026) — ตัวเรียกฝั่งเว็บ · งานจริงอยู่ใน yolo_worker.py (โปรเซส/venv แยก)

flow ที่ผู้ใช้ออกแบบ: ภาพ → counter (YOLO11n-seg · 1280 · water_counter / elec_counter + กรอบแถบตัวเลข) → ครอป +10 %
→ digit (YOLO11n · 640 · 0–9) → เรียงซ้าย→ขวา

ผลทดสอบนอกระบบ (ไฟล์ 38): อ่านถูก 3/8 เท่า cells · ชนิดน้ำ/ไฟกลับด้าน 4/4 → **ชนิดโชว์เป็นคำใบ้เท่านั้น ไม่เลือกให้**
· Pi 5 NCNN 2 threads ~1.7 s/รูป (OCR รันใน thread แยกหลังถ่าย — ป๊อปอัพมาช้าลง ไม่บล็อกการขับ)

ตั้งค่า (env ของ service): MRC_YOLO_PY  = python ของ venv แยก (ค่าเริ่ม ~/mrc-models/venv/bin/python)
                          MRC_YOLO_DIR = โฟลเดอร์โมเดล (ค่าเริ่ม ~/mrc-models/yolo — อยู่นอก ~/mrc เพราะ deploy ใช้ rsync --delete)
"""
import json
import os
import subprocess
import threading
from pathlib import Path

import numpy as np

PY = os.environ.get("MRC_YOLO_PY", str(Path.home() / "mrc-models" / "venv" / "bin" / "python"))
WORKER = Path(__file__).with_name("yolo_worker.py")
SHM = Path("/dev/shm") if Path("/dev/shm").is_dir() else Path("/tmp")
TIMEOUT_S = 20.0                                            # วัดได้ ~1.7 s/รูป · โหลดโมเดลครั้งแรก ~1 s

_proc = None
_lock = threading.Lock()
last = {}                                                   # รายละเอียดผลล่าสุด ให้ capture_daemon แนบไปกับแถว (model_hint)


def _readline(p):
    """อ่าน 1 บรรทัดจาก worker พร้อม timeout (worker ค้าง/ตาย = ไม่ให้ thread OCR ค้างตลอดไป)"""
    box = {}
    t = threading.Thread(target=lambda: box.setdefault("line", p.stdout.readline()), daemon=True)
    t.start(); t.join(TIMEOUT_S)
    line = box.get("line")
    if not line:
        _kill()
        raise RuntimeError("yolo worker ไม่ตอบ" + ("" if line is None else " (ปิดตัวไปแล้ว)"))
    return json.loads(line)


def _kill():
    global _proc
    if _proc is not None:
        try: _proc.kill()
        except OSError: pass
    _proc = None


def _start():
    global _proc
    if _proc is not None and _proc.poll() is None:
        return _proc
    _proc = subprocess.Popen([PY, str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
                             env=dict(os.environ))
    hello = _readline(_proc)
    if "error" in hello:
        _kill()
        raise RuntimeError(f"yolo worker เริ่มไม่ได้: {hello['error']}")
    return _proc


def _ask(job):
    with _lock:                                             # ถ่ายติดกันเร็วๆ → เข้าคิว (worker ทำทีละงาน)
        p = _start()
        p.stdin.write(job + "\n"); p.stdin.flush()
        out = _readline(p)
    if "error" in out:
        raise RuntimeError(f"yolo: {out['error']}")
    return out


def read(bgr):
    """คืน dict(text, conf, kind, kind_conf, box, digit_conf, ms_counter, ms_digit) · ไม่เจอกรอบ → text "" """
    f = SHM / f"mrc_yolo_{os.getpid()}_{threading.get_ident()}.npy"
    np.save(f, np.ascontiguousarray(bgr))
    try:
        res = _ask(str(f))
    finally:
        try: f.unlink()
        except OSError: pass
    last.clear(); last.update(res)
    return res


def warmup():
    _ask("warmup")
