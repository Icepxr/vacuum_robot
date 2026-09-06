#!/usr/bin/env python3
"""
meter_reader.py — ถ่ายรูปมิเตอร์ · preprocess · OCR · เขียนลงเครื่องทันที

กติกาข้อเดียวที่ห้ามละเมิด: **เขียนลงเครื่องก่อนเสมอ แล้วค่อย sync ขึ้น cloud**
ถ้าสนามแข่งไม่มีเน็ตหรือหลุดกลางคัน หุ่นต้องทำงานต่อได้และข้อมูลต้องไม่หาย
สคริปต์นี้จึงไม่ยุ่งกับเครือข่ายเลย — การ sync เป็นหน้าที่ของ sync_supabase.py

รันบนโน้ตบุ๊กด้วยรูปที่ถ่ายจากมือถือได้เลย ไม่ต้องรอ Pi หรือกล้อง:
    python meter_reader.py --source folder --path ./photos

บน Pi 5 กับกล้องจริง:
    python meter_reader.py --source picamera2
"""
import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

# ── ที่เก็บข้อมูลในเครื่อง ────────────────────────────────────
DATA_DIR = Path(os.environ.get("MRC_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
IMAGE_DIR = DATA_DIR / "images"
JSONL_PATH = DATA_DIR / "readings.jsonl"
CONFIG_PATH = Path(__file__).resolve().parent / "roi_config.json"


# ─────────────────────────────────────────────────────────────
# 1. รับภาพเข้ามา
# ─────────────────────────────────────────────────────────────

def grab_picamera2():
    """กล้องของ Raspberry Pi ผ่าน picamera2"""
    from picamera2 import Picamera2          # นำเข้าตรงนี้ เพื่อให้รันบนโน้ตบุ๊กได้โดยไม่ต้องมีไลบรารีนี้
    cam = Picamera2()
    cam.configure(cam.create_still_configuration())
    cam.start()
    import time
    time.sleep(1.5)                          # รอ auto exposure/white balance นิ่ง
    frame = cam.capture_array()
    cam.stop()
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


def grab_usb(index=0):
    """กล้อง USB ผ่าน OpenCV"""
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"เปิดกล้อง index {index} ไม่ได้")
    for _ in range(5):                       # ทิ้งเฟรมแรกๆ ที่ exposure ยังไม่นิ่ง
        cap.read()
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("อ่านเฟรมจากกล้องไม่ได้")
    return frame


def iter_folder(path):
    """อ่านรูปจากโฟลเดอร์ — ใช้ตอนพัฒนาบนโน้ตบุ๊ก"""
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    for p in sorted(Path(path).iterdir()):
        if p.suffix.lower() in exts:
            img = cv2.imread(str(p))
            if img is not None:
                yield p.name, img


# ─────────────────────────────────────────────────────────────
# 2. preprocess
#    ค่าทั้งหมดอยู่ใน roi_config.json เพื่อให้ปรับได้โดยไม่ต้องแก้โค้ด
# ─────────────────────────────────────────────────────────────

def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {
        # กรอบที่จะตัด (สัดส่วนของภาพ 0..1) — ตั้งให้ครอบเฉพาะแถวตัวเลข
        "crop": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
        # ถ้ากล้องมองเฉียง ใส่มุมทั้งสี่ของหน้าปัด (พิกเซล) เพื่อดัดให้ตรง
        "perspective": None,
        "rotate_deg": 0,
        "invert": False,          # จอ 7-segment มักเป็นตัวอักษรสว่างบนพื้นมืด
        "clahe_clip": 2.0,
        "threshold": "otsu",      # "otsu" | "adaptive" | "none"
        "scale": 2.0,             # ขยายก่อน OCR ช่วยกับตัวเลขเล็ก
        "expected_digits": None,  # ใส่จำนวนหลักถ้ารู้ ช่วยกรองผลที่เพี้ยน
    }


def preprocess(img, cfg):
    """คืน (ภาพที่ผ่านการเตรียมแล้ว, ภาพกลางทางไว้ดูตอนปรับจูน)"""
    h, w = img.shape[:2]

    if cfg.get("rotate_deg"):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), cfg["rotate_deg"], 1.0)
        img = cv2.warpAffine(img, m, (w, h))

    pts = cfg.get("perspective")
    if pts:
        src = np.array(pts, dtype=np.float32)          # [[x,y] × 4] ซ้ายบน→ขวาบน→ขวาล่าง→ซ้ายล่าง
        tw = int(max(np.linalg.norm(src[0] - src[1]), np.linalg.norm(src[3] - src[2])))
        th = int(max(np.linalg.norm(src[0] - src[3]), np.linalg.norm(src[1] - src[2])))
        dst = np.array([[0, 0], [tw, 0], [tw, th], [0, th]], dtype=np.float32)
        img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (tw, th))
        h, w = img.shape[:2]

    c = cfg["crop"]
    x0, y0 = int(c["x"] * w), int(c["y"] * h)
    x1, y1 = int((c["x"] + c["w"]) * w), int((c["y"] + c["h"]) * h)
    img = img[max(0, y0):min(h, y1), max(0, x0):min(w, x1)]
    if img.size == 0:
        raise ValueError("กรอบ crop ใน roi_config.json ตัดจนไม่เหลือภาพ")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 60, 60)        # ลด noise แต่ยังเก็บขอบตัวเลข

    clahe = cv2.createCLAHE(clipLimit=cfg.get("clahe_clip", 2.0), tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    if cfg.get("scale", 1.0) != 1.0:
        s = cfg["scale"]
        gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)

    mode = cfg.get("threshold", "otsu")
    if mode == "otsu":
        _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif mode == "adaptive":
        out = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 9)
    else:
        out = gray

    if cfg.get("invert"):
        out = cv2.bitwise_not(out)

    return out, img


# ─────────────────────────────────────────────────────────────
# 3. OCR — เปลี่ยนเอนจินได้โดยไม่แตะส่วนอื่น
#    ยังเลือกไม่ได้ว่าจะใช้ตัวไหนจนกว่าจะเห็นมิเตอร์จริง:
#      ตัวเลขกลไกหมุน  → tesseract ใช้ได้
#      จอ 7-segment    → tesseract อ่านแทบไม่ได้ ต้องใช้ ssocr
#      เข็มชี้         → OCR ใช้ไม่ได้เลย ต้องหามุมเข็ม
# ─────────────────────────────────────────────────────────────

def ocr_tesseract(binimg):
    import pytesseract
    cfg = "--psm 7 -c tessedit_char_whitelist=0123456789."
    data = pytesseract.image_to_data(binimg, config=cfg,
                                     output_type=pytesseract.Output.DICT)
    parts, confs = [], []
    for txt, conf in zip(data["text"], data["conf"]):
        txt = txt.strip()
        if not txt:
            continue
        try:
            c = float(conf)
        except (TypeError, ValueError):
            continue
        if c < 0:
            continue
        parts.append(txt)
        confs.append(c)
    raw = "".join(parts)
    conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return raw, conf


def ocr_ssocr(binimg):
    """สำหรับจอ 7-segment — ต้องติดตั้ง ssocr แยก (apt install ssocr)"""
    tmp = DATA_DIR / "_ssocr_tmp.png"
    cv2.imwrite(str(tmp), binimg)
    try:
        out = subprocess.run(["ssocr", "-t", "40", "crop", "0", "0", "-1", "-1", str(tmp)],
                             capture_output=True, text=True, timeout=10)
        raw = out.stdout.strip()
        return raw, (0.8 if raw else 0.0)      # ssocr ไม่คืนค่าความมั่นใจ ให้ค่าคงที่ไว้
    except FileNotFoundError:
        raise RuntimeError("ไม่พบคำสั่ง ssocr — ติดตั้งด้วย: sudo apt install ssocr")
    finally:
        tmp.unlink(missing_ok=True)


OCR_ENGINES = {"tesseract": ocr_tesseract, "ssocr": ocr_ssocr}


def parse_value(raw, expected_digits=None):
    """ดึงตัวเลขออกจากข้อความดิบ · คืน None ถ้าไม่น่าเชื่อถือ"""
    digits = re.sub(r"[^\d.]", "", raw)
    if not digits:
        return None
    if expected_digits and len(re.sub(r"\D", "", digits)) != expected_digits:
        return None                       # จำนวนหลักไม่ตรง = อ่านพลาด ไม่เดา
    try:
        return float(digits)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────
# 4. เขียนลงเครื่อง — ทำก่อนเสมอ ไม่ยุ่งกับเครือข่าย
# ─────────────────────────────────────────────────────────────

def save_reading(img_bgr, raw, value, conf, run_id, meter_type, source_name=None):
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    rid = uuid.uuid4().hex[:12]
    img_name = f"{ts:%Y%m%d_%H%M%S}_{rid}.jpg"
    cv2.imwrite(str(IMAGE_DIR / img_name), img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])

    rec = {
        "local_id": rid,
        "captured_at": ts.isoformat(),
        "run_id": run_id,
        "meter_type": meter_type,
        "raw_text": raw,
        "value": value,
        "confidence": round(conf, 4),
        "image_path": f"images/{img_name}",
        "source": source_name,
        "synced_at": None,
    }
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())          # บังคับให้ลงแผ่นจริง กันไฟดับแล้วข้อมูลหาย
    return rec


# ─────────────────────────────────────────────────────────────

def process_one(img, cfg, engine, run_id, meter_type, name=None, debug_dir=None):
    binimg, cropped = preprocess(img, cfg)
    raw, conf = OCR_ENGINES[engine](binimg)
    value = parse_value(raw, cfg.get("expected_digits"))
    rec = save_reading(cropped, raw, value, conf, run_id, meter_type, name)
    if debug_dir:
        Path(debug_dir).mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(Path(debug_dir) / f"{rec['local_id']}_bin.png"), binimg)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["picamera2", "usb", "folder"], default="folder")
    ap.add_argument("--path", help="โฟลเดอร์รูป เมื่อ --source folder")
    ap.add_argument("--engine", choices=list(OCR_ENGINES), default="tesseract")
    ap.add_argument("--meter-type", default="water", help="water | electric")
    ap.add_argument("--run-id", default=datetime.now().strftime("run_%Y%m%d_%H%M%S"))
    ap.add_argument("--debug-dir", help="เซฟภาพหลัง threshold ไว้ดูตอนปรับจูน")
    args = ap.parse_args()

    cfg = load_config()
    print(f"ที่เก็บข้อมูล: {DATA_DIR}")
    print(f"เอนจิน OCR : {args.engine}")

    ok_count = total = 0
    if args.source == "folder":
        if not args.path:
            sys.exit("ต้องระบุ --path เมื่อใช้ --source folder")
        for name, img in iter_folder(args.path):
            total += 1
            rec = process_one(img, cfg, args.engine, args.run_id, args.meter_type,
                              name, args.debug_dir)
            ok = rec["value"] is not None
            ok_count += ok
            print(f"  {'OK ' if ok else 'ไม่ได้'} {name:28s} raw={rec['raw_text']!r:16s} "
                  f"value={rec['value']} conf={rec['confidence']:.2f}")
        if total:
            print(f"\nอ่านได้ {ok_count}/{total} = {100*ok_count/total:.1f} %")
            print("ถ้าเปอร์เซ็นต์ต่ำ ให้ปรับ roi_config.json แล้วรันซ้ำ — ดูภาพใน --debug-dir ประกอบ")
    else:
        img = grab_picamera2() if args.source == "picamera2" else grab_usb()
        rec = process_one(img, cfg, args.engine, args.run_id, args.meter_type,
                          args.source, args.debug_dir)
        print(json.dumps(rec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
