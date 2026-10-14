"""โปรเซสแยกของ engine `yolo` (ทดลอง · ไฟล์ 38) — รันด้วย venv ของมันเอง (~/mrc-models/venv) ไม่ใช่ ~/mrc/.venv

ทำไมแยก: ncnn 1.0.20260526 ต้องการ numpy 2 + opencv-python 5 · ลงใน venv หลักแล้ว (14 ต.ค.) มันอัปเกรด numpy 1.26 → 2.5
และทับ cv2 4.10 ที่ปักไว้ · กู้กลับเป็น numpy 1.26 แล้ว ncnn segfault ตอน extract → แยกโปรเซสเพื่อไม่แตะของหลักเลย

โปรโตคอล (บรรทัดละ 1 งาน): stdin  = path ของไฟล์ .npy (ภาพ BGR uint8) หรือ "warmup"
                          stdout = JSON 1 บรรทัด {text, conf, kind, kind_conf, box, digit_conf, ms_counter, ms_digit} หรือ {"error": …}
ใช้ได้แค่ ncnn / numpy / cv2 — ห้าม import โมดูลของโปรเจกต์ (คนละ venv)
"""
import json
import os
import sys
import time
from pathlib import Path

import cv2
import ncnn
import numpy as np

MODEL_DIR = Path(os.environ.get("MRC_YOLO_DIR", Path.home() / "mrc-models" / "yolo"))
THREADS = int(os.environ.get("MRC_YOLO_THREADS", "2"))     # วัด 14 ต.ค.: 2 threads เร็วกว่า 4 (1659 vs 2069 ms)
COUNTER_SZ, DIGIT_SZ = 1280, 640
COUNTER_CONF, DIGIT_CONF = 0.25, 0.25
KINDS = ("water", "elec")                                   # ลำดับ names ใน metadata.yaml ของ counter


def load(name):
    n = ncnn.Net(); n.opt.num_threads = THREADS
    p = MODEL_DIR / name
    if n.load_param(str(p / "model.ncnn.param")) != 0 or n.load_model(str(p / "model.ncnn.bin")) != 0:
        raise FileNotFoundError(f"โหลดโมเดล {p} ไม่ได้ (ตั้ง MRC_YOLO_DIR?)")
    return n


def letterbox(im, size):
    h, w = im.shape[:2]; r = size / max(h, w); nh, nw = int(round(h * r)), int(round(w * r))
    out = np.full((size, size, 3), 114, np.uint8); top, left = (size - nh) // 2, (size - nw) // 2
    out[top:top + nh, left:left + nw] = cv2.resize(im, (nw, nh)); return out, r, left, top


def detect(net, im, size, nc, conf):
    """[(x, y, w, h, score, cls)] พิกัดภาพต้นฉบับ · NMS ไม่แยกคลาส (เลขสองตัวซ้อนที่เดียวกันไม่ได้)"""
    lb, r, left, top = letterbox(im, size)
    x = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB).transpose(2, 0, 1).astype(np.float32) / 255.
    ex = net.create_extractor(); ex.input("in0", ncnn.Mat(np.ascontiguousarray(x)))
    _, o = ex.extract("out0"); o = np.array(o)              # (4 + nc [+32 สัมประสิทธิ์ mask ของ seg], N)
    sc = o[4:4 + nc].max(0); cl = o[4:4 + nc].argmax(0); k = sc > conf
    if not k.any():
        return []
    b = o[:4, k].T; b = np.c_[b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2, b[:, 2], b[:, 3]]
    idx = cv2.dnn.NMSBoxes(b.tolist(), sc[k].tolist(), conf, 0.45)
    idx = np.array(idx).ravel() if len(idx) else []
    return [((b[i, 0] - left) / r, (b[i, 1] - top) / r, b[i, 2] / r, b[i, 3] / r, float(sc[k][i]), int(cl[k][i])) for i in idx]


def read(cnt, dig, bgr):
    t0 = time.perf_counter()
    boxes = detect(cnt, bgr, COUNTER_SZ, len(KINDS), COUNTER_CONF)
    t1 = time.perf_counter()
    res = dict(text="", conf=0.0, kind=None, kind_conf=0.0, box=None, digit_conf=[], ms_counter=round((t1 - t0) * 1000), ms_digit=0)
    if boxes:
        x, y, w, h, s, c = max(boxes, key=lambda d: d[4])
        H, W = bgr.shape[:2]
        x0, y0 = max(int(x - .1 * w), 0), max(int(y - .1 * h), 0)
        x1, y1 = min(int(x + 1.1 * w), W), min(int(y + 1.1 * h), H)
        digits = sorted(detect(dig, bgr[y0:y1, x0:x1], DIGIT_SZ, 10, DIGIT_CONF)) if x1 > x0 and y1 > y0 else []
        res.update(kind=KINDS[c], kind_conf=round(s, 2), box=[x0, y0, x1, y1],
                   text="".join(str(d[5]) for d in digits), digit_conf=[round(d[4], 2) for d in digits],
                   ms_digit=round((time.perf_counter() - t1) * 1000))
        if digits:   # ความมั่นใจรวม = ตัวที่อ่อนที่สุด (กรอบ × เลข) — แถวที่มีเลขตัวเดียวพลาดต้องไม่ดูมั่นใจ
            res["conf"] = round(min(s, min(d[4] for d in digits)), 4)
    return res


def main():
    try:
        cnt, dig = load("counter_ncnn_model"), load("digit_ncnn_model")
    except Exception as e:                                  # noqa: BLE001 — บอกตัวเรียกแล้วจบ
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False), flush=True); return 1
    # 14 ต.ค. วัดบน Pi: forward รอบแรกหลังโหลดได้ผลว่าง (รูปเดียวกัน รอบ 2–3 อ่าน 5977 ได้ 0.78) → รันทิ้งทั้งสองโมเดล 2 รอบก่อนรับงาน
    for _ in range(2):
        detect(cnt, np.zeros((720, 1280, 3), np.uint8), COUNTER_SZ, len(KINDS), 1.1)
        detect(dig, np.zeros((64, 256, 3), np.uint8), DIGIT_SZ, 10, 1.1)
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        job = line.strip()
        try:
            if job == "warmup":
                read(cnt, dig, np.zeros((360, 640, 3), np.uint8)); out = {"ok": True}
            else:
                out = read(cnt, dig, np.load(job))
        except Exception as e:                              # noqa: BLE001 — งานเดียวพังไม่ล้ม worker
            out = {"error": f"{type(e).__name__}: {e}"}
        print(json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
