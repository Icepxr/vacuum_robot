"""โปรเซสแยกของ engine `tr` (ไฟล์ 39) — รันด้วย ~/mrc-models/venv (ncnn · numpy 2 · opencv 5) ไม่ใช่ ~/mrc/.venv

ขั้นตอน = MeterReader.read ของ "text reader" แบบ use_easyocr=False (E4 ในไฟล์ 39) แต่เรียก YOLO digit ด้วย ncnn ตรง
(ไม่ต้องมี ultralytics/torch บน Pi):
  textreader_meter.find_body → meter_type → find_strip → strip_quad → warp_quad → normalize_strip
  → digit (letterbox 640 จัตุรัส เหมือน ultralytics ตอนรันโมเดล ncnn) conf 0.05 · NMS ไม่แยกคลาส · เลือก n กล่องที่มั่นใจสุด → เรียงซ้าย→ขวา
  ได้ครบ n หลักเท่านั้นถึงคืนเลข (เหมือนต้นฉบับ)
โปรโตคอลเดียวกับ yolo_worker.py (worker_client.py) · ใช้ได้แค่ ncnn/numpy/cv2 + textreader_meter (ไฟล์นี้ import แค่ cv2/numpy)
"""
import json
import os
import sys
import time
from pathlib import Path

import cv2
import ncnn
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import textreader_meter as T  # noqa: E402

MODEL_DIR = Path(os.environ.get("MRC_TR_DIR", Path.home() / "mrc-models" / "tr"))
THREADS = int(os.environ.get("MRC_YOLO_THREADS", "2"))
DIGIT_SZ, DIGIT_CONF = 640, 0.05                          # ค่าเดียวกับ MeterReader.yolo_digits (conf=0.05)
SHM = Path("/dev/shm") if Path("/dev/shm").is_dir() else Path("/tmp")


def load():
    n = ncnn.Net(); n.opt.num_threads = THREADS
    p = MODEL_DIR / "digit_ncnn_model"
    if n.load_param(str(p / "model.ncnn.param")) != 0 or n.load_model(str(p / "model.ncnn.bin")) != 0:
        raise FileNotFoundError(f"โหลดโมเดล {p} ไม่ได้ (ตั้ง MRC_TR_DIR?)")
    return n


def letterbox(im, size):
    h, w = im.shape[:2]; r = size / max(h, w); nh, nw = int(round(h * r)), int(round(w * r))
    out = np.full((size, size, 3), 114, np.uint8); top, left = (size - nh) // 2, (size - nw) // 2
    out[top:top + nh, left:left + nw] = cv2.resize(im, (nw, nh)); return out, r, left, top


def detect(net, im, size=DIGIT_SZ, nc=10, conf=DIGIT_CONF):
    lb, r, left, top = letterbox(im, size)
    x = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB).transpose(2, 0, 1).astype(np.float32) / 255.
    ex = net.create_extractor(); ex.input("in0", ncnn.Mat(np.ascontiguousarray(x)))
    _, o = ex.extract("out0"); o = np.array(o)
    sc = o[4:4 + nc].max(0); cl = o[4:4 + nc].argmax(0); k = sc > conf
    if not k.any():
        return []
    b = o[:4, k].T; b = np.c_[b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2, b[:, 2], b[:, 3]]
    idx = cv2.dnn.NMSBoxes(b.tolist(), sc[k].tolist(), conf, 0.7)   # ultralytics ค่าเริ่ม iou 0.7
    idx = np.array(idx).ravel() if len(idx) else []
    return [((b[i, 0] - left) / r, (b[i, 1] - top) / r, b[i, 2] / r, b[i, 3] / r, float(sc[k][i]), int(cl[k][i])) for i in idx]


def read(net, frame, job_id="x"):
    t0 = time.perf_counter()
    res = dict(text="", conf=0.0, kind=None, kind_conf=0.0, quad=None, digit_conf=[], strip_path=None, why="", ms=0)
    body = T.find_body(frame)
    if body is None:
        res.update(why="no_meter", ms=round((time.perf_counter() - t0) * 1000)); return res
    kind, misfit = T.meter_type(body, frame.shape[:2])
    res.update(kind=kind, kind_conf=round(float(min(1.0, abs(np.log(misfit / T.SHAPE_THR)) / np.log(2))), 2))
    cnt = T.find_strip(frame, body)
    if cnt is None:
        res.update(why="no_strip", ms=round((time.perf_counter() - t0) * 1000)); return res
    q = T.strip_quad(cnt)
    strip = T.warp_quad(frame, q)
    sp = SHM / f"mrc_strip_{job_id}.jpg"; cv2.imwrite(str(sp), strip)
    res.update(quad=[[round(float(a)), round(float(b))] for a, b in q], strip_path=str(sp))
    n = T.N_DIGITS.get(kind, 4)
    d = sorted(detect(net, T.normalize_strip(strip)), key=lambda z: -z[4])[:n]
    d.sort(key=lambda z: z[0])
    text = "".join(str(z[5]) for z in d)
    res["digit_conf"] = [round(z[4], 2) for z in d]
    if len(text) == n:
        res.update(text=text, conf=round(float(np.mean([z[4] for z in d])), 4))
    else:
        res["why"] = "no_digits"
    res["ms"] = round((time.perf_counter() - t0) * 1000)
    return res


def main():
    try:
        net = load()
    except Exception as e:                                  # noqa: BLE001
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False), flush=True); return 1
    for _ in range(2):                                      # forward รอบแรกหลังโหลดได้ผลว่าง (ไฟล์ 38 §38.7) → รันทิ้งก่อน
        detect(net, np.zeros((96, 400, 3), np.uint8), conf=1.1)
    print(json.dumps({"ready": True}), flush=True)
    for i, line in enumerate(sys.stdin):
        job = line.strip()
        try:
            out = {"ok": True} if job == "warmup" else read(net, np.load(job), f"{os.getpid()}_{i}")
        except Exception as e:                              # noqa: BLE001 — งานเดียวพังไม่ล้ม worker
            out = {"error": f"{type(e).__name__}: {e}"}
        print(json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
