"""digit อย่างเดียวบนแถบที่ครอปด้วยมือ (crops_manual.json) — วัดความสามารถของ digit แยกจาก counter"""
import json, sys, time
from pathlib import Path
import cv2
from ultralytics import YOLO
IMG = Path(sys.argv[1]); W = Path(sys.argv[2]); here = Path(__file__).parent
GT = json.loads((here / "gt.json").read_text(encoding="utf-8")); CR = json.loads((here / "crops_manual.json").read_text(encoding="utf-8"))
dig = YOLO(str(W / "digit.pt"), task="detect")
ok = 0; n = 0
for name, box in CR.items():
    if name.startswith("_"): continue
    x0, y0, x1, y1 = box
    crop = cv2.imread(str(IMG / name))[y0:y1, x0:x1]
    for conf in (0.25,):
        t = time.perf_counter(); r = dig.predict(crop, imgsz=640, conf=conf, verbose=False)[0]; dt = time.perf_counter() - t
        d = sorted((float(b.xyxy[0][0]), dig.names[int(b.cls)], round(float(b.conf), 2)) for b in r.boxes)
        s = "".join(x[1] for x in d); g = GT[name]["digits"]; n += 1; ok += s == g
        print(f'{name[:15]} gt={g} digit={s:6s} {"✓" if s == g else "✗"} {[x[2] for x in d]} {1000*dt:.0f}ms')
print(f"digit อย่างเดียว ถูกทั้งชุด {ok}/{n}")
