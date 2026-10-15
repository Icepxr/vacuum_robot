"""ตัวเรียก worker อ่านเลขที่รันในโปรเซส/venv แยก (ไฟล์ 38 §38.7) — ใช้ร่วมกันระหว่าง engine `yolo` และ `tr`

ทำไมแยกโปรเซส: ncnn ต้องการ numpy 2 + opencv 5 · venv หลัก (~/mrc/.venv) ปัก numpy 1.26 + opencv 4.10 ไว้
โปรโตคอล: stdin = path .npy (ภาพ BGR) หรือ "warmup" · stdout = JSON 1 บรรทัด · บรรทัดแรกหลังเริ่ม = {"ready": true} หรือ {"error": …}
"""
import json
import os
import subprocess
import threading
from pathlib import Path

import numpy as np

SHM = Path("/dev/shm") if Path("/dev/shm").is_dir() else Path("/tmp")
DEFAULT_PY = str(Path.home() / "mrc-models" / "venv" / "bin" / "python")


class WorkerClient:
    def __init__(self, script, timeout_s=20.0):
        self.script = Path(__file__).with_name(script)
        self.py = os.environ.get("MRC_YOLO_PY", DEFAULT_PY)
        self.timeout_s = timeout_s
        self.proc = None
        self.lock = threading.Lock()
        self.last = {}                                      # ผลล่าสุด ให้ capture_daemon แนบไปกับแถว

    def _readline(self):
        """อ่าน 1 บรรทัดพร้อม timeout — worker ค้าง/ตาย ต้องไม่ทำให้ thread OCR ค้างตลอดไป"""
        box = {}
        p = self.proc
        t = threading.Thread(target=lambda: box.setdefault("line", p.stdout.readline()), daemon=True)
        t.start(); t.join(self.timeout_s)
        line = box.get("line")
        if not line:
            self.kill()
            raise RuntimeError(f"{self.script.name} ไม่ตอบ" + ("" if line is None else " (ปิดตัวไปแล้ว)"))
        return json.loads(line)

    def kill(self):
        if self.proc is not None:
            try: self.proc.kill()
            except OSError: pass
        self.proc = None

    def _start(self):
        if self.proc is not None and self.proc.poll() is None:
            return
        self.proc = subprocess.Popen([self.py, str(self.script)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     text=True, bufsize=1, env=dict(os.environ))
        hello = self._readline()
        if "error" in hello:
            self.kill()
            raise RuntimeError(f"{self.script.name} เริ่มไม่ได้: {hello['error']}")

    def ask(self, job):
        with self.lock:                                     # ถ่ายติดกันเร็วๆ → เข้าคิว (worker ทำทีละงาน)
            self._start()
            self.proc.stdin.write(job + "\n"); self.proc.stdin.flush()
            out = self._readline()
        if "error" in out:
            raise RuntimeError(f"{self.script.name}: {out['error']}")
        return out

    def read(self, bgr):
        f = SHM / f"mrc_ocr_{os.getpid()}_{threading.get_ident()}.npy"
        np.save(f, np.ascontiguousarray(bgr))
        try:
            res = self.ask(str(f))
        finally:
            try: f.unlink()
            except OSError: pass
        self.last.clear(); self.last.update(res)
        return res

    def warmup(self):
        self.ask("warmup")
