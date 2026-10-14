"""ทดสอบโมเดลชุด weights/ (13 ต.ค. 2026): counter (YOLO11n-seg · water/elec + กรอบ) → ครอป → digit (YOLO11n · 0–9) → เรียงซ้าย→ขวา
เทียบกับ engine cells (โค้ดหลัก baseline-cells-20261014) บนรูปเดียวกัน
ใช้: python eval_yolo.py <โฟลเดอร์รูป> <weights/> [conf_counter] [conf_digit]
"""
import json, sys, time
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "11_pi5_vision" / "src"))
import cellread  # noqa: E402  engine หลัก
from ultralytics import YOLO  # noqa: E402

IMG = Path(sys.argv[1]); W = Path(sys.argv[2])
CC = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
CD = float(sys.argv[4]) if len(sys.argv) > 4 else 0.25
GT = json.loads((Path(__file__).parent / "gt.json").read_text(encoding="utf-8"))
cnt = YOLO(str(W / "counter.pt"), task="segment"); dig = YOLO(str(W / "digit.pt"), task="detect")


def pad(im, x0, y0, x1, y1, p):
    w, h = x1 - x0, y1 - y0; H, Wd = im.shape[:2]
    return im[max(int(y0 - p * h), 0):min(int(y1 + p * h), H), max(int(x0 - p * w), 0):min(int(x1 + p * w), Wd)]


def yolo_read(im):
    t0 = time.perf_counter()
    rc = cnt.predict(im, imgsz=1280, conf=CC, verbose=False)[0]
    t1 = time.perf_counter()
    if not len(rc.boxes):
        return dict(type=None, cconf=0, digits="", dconf=[], t_cnt=t1 - t0, t_dig=0, n_cnt=0)
    i = int(rc.boxes.conf.argmax()); b = rc.boxes[i]
    typ = {"water_counter": "water", "elec_counter": "elec"}[cnt.names[int(b.cls)]]
    x0, y0, x1, y1 = [float(v) for v in b.xyxy[0]]
    crop = pad(im, x0, y0, x1, y1, 0.10)
    rd = dig.predict(crop, imgsz=640, conf=CD, verbose=False)[0]
    t2 = time.perf_counter()
    d = sorted((float(bb.xyxy[0][0]), dig.names[int(bb.cls)], float(bb.conf)) for bb in rd.boxes)
    return dict(type=typ, cconf=round(float(b.conf), 2), box=[round(v) for v in (x0, y0, x1, y1)], n_cnt=len(rc.boxes),
                digits="".join(x[1] for x in d), dconf=[round(x[2], 2) for x in d], t_cnt=t1 - t0, t_dig=t2 - t1)


rows = []
files = sorted(IMG.glob("*.jpg"))
yolo_read(cv2.imread(str(files[0])))  # warmup
for f in files:
    im = cv2.imread(str(f)); g = GT.get(f.name)
    y = yolo_read(im)
    t0 = time.perf_counter(); c = cellread.read_meter(im); tc = time.perf_counter() - t0
    ctext = c["text"].replace("_", "") if c["ok"] else ""
    rows.append(dict(f=f.name, gt=g, y=y, cells=ctext, cells_src=c.get("source"), t_cells=tc))
    gt_s = "neg" if g is None else f'{g["type"]:5s} {g["digits"] or "(ว่าง)"}'
    ok_y = "" if g is None else ("✓" if y["digits"] == g["digits"] else "✗")
    ok_t = "" if g is None or y["type"] is None else ("✓" if y["type"] == g["type"] else "✗")
    ok_c = "" if g is None else ("✓" if ctext == g["digits"] else "✗")
    print(f'{f.name[:15]}  gt={gt_s:13s} | YOLO type={str(y["type"]):5s}{ok_t} c={y["cconf"]:.2f} n={y["n_cnt"]} '
          f'digits={y["digits"] or "-":8s}{ok_y} {y["dconf"]} {1000*(y["t_cnt"]+y["t_dig"]):.0f}ms | cells={ctext or "-":8s}{ok_c} {1000*tc:.0f}ms')

pos = [r for r in rows if r["gt"]]; neg = [r for r in rows if not r["gt"]]
num = [r for r in pos if r["gt"]["digits"]]
print("\n=== สรุป ===")
print(f'รูปมีมิเตอร์ {len(pos)} (มีเลข {len(num)}) · รูปไม่มีมิเตอร์ {len(neg)}')
print(f'YOLO ชนิดถูก {sum(r["y"]["type"] == r["gt"]["type"] for r in pos)}/{len(pos)} · หาไม่เจอ {sum(r["y"]["type"] is None for r in pos)}')
print(f'YOLO เลขถูกทั้งชุด {sum(r["y"]["digits"] == r["gt"]["digits"] for r in num)}/{len(num)} · cells {sum(r["cells"] == r["gt"]["digits"] for r in num)}/{len(num)}')
print(f'รูปไม่มีมิเตอร์: YOLO เจอกรอบ {sum(r["y"]["type"] is not None for r in neg)}/{len(neg)} · อ่านเป็นเลข {sum(bool(r["y"]["digits"]) for r in neg)} · cells อ่านเป็นเลข {sum(bool(r["cells"]) for r in neg)}')
t = [1000 * (r["y"]["t_cnt"] + r["y"]["t_dig"]) for r in rows]; tc = [1000 * r["t_cells"] for r in rows]
print(f'เวลา (เครื่องนี้) YOLO median {np.median(t):.0f} ms (counter {1000*np.median([r["y"]["t_cnt"] for r in rows]):.0f}) · cells median {np.median(tc):.0f} ms')
json.dump(rows, open(Path(__file__).parent / f"result_{CC}_{CD}.json", "w"), ensure_ascii=False, indent=1, default=str)
