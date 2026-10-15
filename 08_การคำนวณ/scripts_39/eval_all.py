"""เทียบ 5 วิธีอ่านมิเตอร์บนชุดเดียวกัน (ไฟล์ 39 · 15 ต.ค. 2026) — ไม่แตะโค้ดหุ่น
E1 cells (โค้ดหลัก tag baseline-cells-20261014)
E2 counter(seg)+digit ชุด weights/ 13 ต.ค. (ตัวที่หุ่นรันอยู่ · ultralytics บน Mac)
E3 text reader เต็ม (หากล่องน้ำเงิน → รูปทรง → แถบ → ดัด 4 มุม → EasyOCR + YOLO digit ใหม่)
E4 text reader YOLO อย่างเดียว (use_easyocr=False)
E5 text reader หาแถบ/ดัด + ตัวอ่าน cells (CNN ทีละช่อง)
ใช้: python eval_all.py <โฟลเดอร์รูปจากหุ่น (~/mrc/data/images)>
"""
import json, sys, time
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "11_pi5_vision" / "src"))
sys.path.insert(0, str(ROOT / "text reader"))
import cellread, reai_strip  # noqa: E402
import meter_reader as TR    # noqa: E402  — text reader/meter_reader.py (ชื่อซ้ำกับของ Pi แต่ path text reader มาก่อน)
from ultralytics import YOLO  # noqa: E402

ROBOT = Path(sys.argv[1])
GT = {k: v for k, v in json.loads((Path(__file__).parent / "gt.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
assert hasattr(TR, "MeterReader"), "import ผิดไฟล์ meter_reader"

files = [ROOT / k for k in GT if k.startswith("Meter_picture/")] + sorted(ROBOT.glob("*.jpg"))
key = lambda p: str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else p.name

W13 = ROOT / "weights"
cnt13 = YOLO(str(W13 / "counter.pt"), task="segment"); dig13 = YOLO(str(W13 / "digit.pt"), task="detect")
TRW = ROOT / "text reader" / "weights"
tr_full = TR.MeterReader(TRW / "digit.pt", easyocr_dir=TRW / "easyocr")
tr_yolo = TR.MeterReader(TRW / "digit.pt", use_easyocr=False)
cellread.warmup()


def e1(im):
    r = cellread.read_meter(im)
    return dict(type=None, text=r["text"].replace("_", "") if r["ok"] else "", conf=r["conf"] if r["ok"] else 0.0)


def e2(im):
    rc = cnt13.predict(im, imgsz=1280, conf=0.25, verbose=False)[0]
    if not len(rc.boxes):
        return dict(type=None, text="", conf=0.0)
    b = rc.boxes[int(rc.boxes.conf.argmax())]; x0, y0, x1, y1 = [float(v) for v in b.xyxy[0]]
    w, h = x1 - x0, y1 - y0; H, Wd = im.shape[:2]
    crop = im[max(int(y0 - .1 * h), 0):min(int(y1 + .1 * h), H), max(int(x0 - .1 * w), 0):min(int(x1 + .1 * w), Wd)]
    rd = dig13.predict(crop, imgsz=640, conf=0.25, verbose=False)[0]
    d = sorted((float(bb.xyxy[0][0]), dig13.names[int(bb.cls)], float(bb.conf)) for bb in rd.boxes)
    typ = {"water_counter": "water", "elec_counter": "elec"}[cnt13.names[int(b.cls)]]
    return dict(type=typ, text="".join(x[1] for x in d), conf=min([float(b.conf)] + [x[2] for x in d]) if d else 0.0)


def tr(reader, im):
    r = reader.read(im)
    if r is None:
        return dict(type=reader.last_meter, text="", conf=0.0, why=reader.last_fail)
    return dict(type=r.meter, text=r.text, conf=round(r.conf, 3), src=r.source)


def e5(im):
    strip, t = tr_yolo.locate(im)
    if strip is None:
        return dict(type=t, text="", conf=0.0)
    s = cv2.resize(strip, (480, 120))
    # แถบที่ text reader ดัดมาขยายขอบยาว 3 % ต่อข้าง → ตัดออกก่อนแบ่ง 4 ช่อง
    m = int(480 * 0.03 / 1.06); s = cv2.resize(s[:, m:480 - m], (480, 120))
    out = cellread._net.predict(reai_strip.cells(s, inset=0.08))
    text = "".join("?" if o[0] == "x" else o[0] for o in out)
    ok = text.strip("_") != "" and "?" not in text
    return dict(type=t, text=text.replace("_", "") if ok else "", conf=round(min(o[1] for o in out), 3) if ok else 0.0)


M = {"E1 cells": e1, "E2 yolo13": e2, "E3 TR เต็ม": lambda im: tr(tr_full, im), "E4 TR yolo": lambda im: tr(tr_yolo, im), "E5 TR+cells": e5}
rows = []
for f in files:
    im = cv2.imread(str(f)); k = key(f); g = GT.get(k)
    row = dict(f=k, gt=g)
    for name, fn in M.items():
        t = time.perf_counter(); r = fn(im); r["ms"] = round((time.perf_counter() - t) * 1000); row[name] = r
    rows.append(row)
    if g:
        print(f'{k[-28:]:28s} {g["type"]:5s} {g["digits"] or "-":5s} | ' + " | ".join(
            f'{n.split()[0]} {row[n]["text"] or "-":5s}{"✓" if row[n]["text"] == g["digits"] else "✗"}' for n in M))

pos = [r for r in rows if r["gt"]]; num = [r for r in pos if r["gt"]["digits"]]; neg = [r for r in rows if not r["gt"]]
print(f"\nรูปมีมิเตอร์ {len(pos)} (มีเลข {len(num)}) · ไม่มีมิเตอร์ {len(neg)}")
print(f'{"วิธี":12s} {"เลขถูก":>8s} {"ชนิดถูก":>8s} {"ผิดแต่มั่นใจ≥0.8":>16s} {"ลบที่อ่านเป็นเลข":>15s} {"ms median":>9s}')
summary = {}
for n in M:
    ok = sum(r[n]["text"] == r["gt"]["digits"] for r in num)
    ty = [r for r in pos if r[n]["type"] is not None]
    tok = sum(r[n]["type"] == r["gt"]["type"] for r in ty)
    cw = sum(1 for r in pos if r[n]["text"] and r[n]["text"] != r["gt"]["digits"] and r[n]["conf"] >= 0.8)
    fp = sum(bool(r[n]["text"]) for r in neg)
    ms = float(np.median([r[n]["ms"] for r in rows]))
    summary[n] = dict(digits_ok=ok, n_num=len(num), type_ok=tok, type_n=len(ty), confident_wrong=cw, neg_read=fp, ms_median=ms)
    print(f'{n:12s} {ok:>4d}/{len(num):<3d} {(f"{tok}/{len(ty)}" if ty else "-"):>8s} {cw:>16d} {fp:>15d} {ms:>9.0f}')
json.dump(dict(summary=summary, rows=rows), open(Path(__file__).parent / "result.json", "w"), ensure_ascii=False, indent=1, default=str)
