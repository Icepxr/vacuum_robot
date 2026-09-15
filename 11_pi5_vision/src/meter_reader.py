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


def grab_usb(index=0, size=(1920, 1080)):
    """กล้อง USB ผ่าน OpenCV — ขอ MJPG ที่ 1920×1080 ตรงๆ
    ค่า default ของ OpenCV/V4L2 จะได้ YUYV 640×480 · Logitech BRIO บน USB 2.0 ให้ YUYV 1080p แค่ 5 fps
    แต่ MJPG 1080p ได้ 30 fps (วัดจริง 11 ก.ย. 2026 · C22 ไฟล์ 10)"""
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"เปิดกล้อง index {index} ไม่ได้")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # ต้องตั้งก่อนขนาด
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
    got = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    if got != tuple(size):
        print(f"⚠ กล้องให้ {got[0]}x{got[1]} ไม่ใช่ {size[0]}x{size[1]}", file=sys.stderr)
    for _ in range(10):                      # ทิ้งเฟรมแรกๆ ที่ exposure/autofocus ยังไม่นิ่ง
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
            if img is None:
                print(f"  ข้าม {p.name} — อ่านไฟล์ภาพไม่ได้")
                continue
            yield p.name, img


# ─────────────────────────────────────────────────────────────
# 2. preprocess
#    ค่าทั้งหมดอยู่ใน roi_config.json เพื่อให้ปรับได้โดยไม่ต้องแก้โค้ด
# ─────────────────────────────────────────────────────────────

def load_config():
    defaults = {
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
        "decimal_places": None,   # ใส่ถ้ารู้รูปแบบแน่นอน แล้วเราหารเอง ไม่ให้ OCR เดาจุด
    }
    if CONFIG_PATH.exists():
        # merge ทับ default เพื่อให้ไฟล์ที่ขาด key บางตัวยังใช้ได้ ไม่ KeyError
        defaults.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return defaults


def preprocess(img, cfg):
    """คืน (ภาพที่ผ่านการเตรียมแล้ว, ภาพกลางทางไว้ดูตอนปรับจูน)"""
    h, w = img.shape[:2]

    if cfg.get("rotate_deg"):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), cfg["rotate_deg"], 1.0)
        img = cv2.warpAffine(img, m, (w, h))

    pts = cfg.get("perspective")
    if pts:
        if len(pts) != 4 or any(len(q) != 2 for q in pts):
            raise ValueError("perspective ต้องมี 4 จุด จุดละ [x, y] — ได้ " + repr(pts))
        src = np.array(pts, dtype=np.float32)          # [[x,y] × 4] ซ้ายบน→ขวาบน→ขวาล่าง→ซ้ายล่าง
        tw = int(max(np.linalg.norm(src[0] - src[1]), np.linalg.norm(src[3] - src[2])))
        th = int(max(np.linalg.norm(src[0] - src[3]), np.linalg.norm(src[1] - src[2])))
        if tw < 2 or th < 2:
            raise ValueError(f"จุด perspective ใกล้กันเกินไป ได้กรอบ {tw}×{th} px")
        dst = np.array([[0, 0], [tw, 0], [tw, th], [0, th]], dtype=np.float32)
        img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (tw, th))
        h, w = img.shape[:2]

    c = cfg["crop"]
    # ต้อง clamp ทั้งสองด้าน — เดิม clamp แค่ด้านล่าง ทำให้ค่าติดลบหลุดเข้าไปเป็น
    # index นับจากท้ายของ Python แล้วได้ภาพที่ "ไม่ว่าง แต่ผิดกรอบ" โดยไม่มี exception
    x0 = max(0, min(w, int(c["x"] * w)))
    x1 = max(0, min(w, int((c["x"] + c["w"]) * w)))
    y0 = max(0, min(h, int(c["y"] * h)))
    y1 = max(0, min(h, int((c["y"] + c["h"]) * h)))
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"กรอบ crop ไม่ถูกต้อง: x {x0}-{x1}, y {y0}-{y1} บนภาพ {w}×{h}")
    img = img[y0:y1, x0:x1]

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
    DATA_DIR.mkdir(parents=True, exist_ok=True)   # ครั้งแรกบนเครื่องสะอาดโฟลเดอร์ยังไม่มี
    tmp = DATA_DIR / "_ssocr_tmp.png"
    if not cv2.imwrite(str(tmp), binimg):         # imwrite คืน False เงียบๆ ไม่โยน exception
        raise RuntimeError(f"เขียนไฟล์ชั่วคราวสำหรับ ssocr ไม่ได้: {tmp}")
    try:
        # ไม่ส่ง crop เพราะ preprocess() ตัดกรอบมาให้แล้ว
        out = subprocess.run(["ssocr", "-t", "40", str(tmp)],
                             capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            raise RuntimeError(f"ssocr คืนรหัส {out.returncode}: {out.stderr.strip()[:200]}")
        raw = out.stdout.strip()
        return raw, (0.8 if raw else 0.0)   # ssocr ไม่คืนค่าความมั่นใจ ใช้ค่าคงที่แทน
    except FileNotFoundError:
        raise RuntimeError("ไม่พบคำสั่ง ssocr — ติดตั้งด้วย: sudo apt install ssocr")
    except subprocess.TimeoutExpired:
        raise RuntimeError("ssocr ค้างเกิน 10 วินาที")
    finally:
        tmp.unlink(missing_ok=True)


OCR_ENGINES = {"tesseract": ocr_tesseract, "ssocr": ocr_ssocr}


def parse_value(raw, expected_digits=None, decimal_places=None):
    """ดึงตัวเลขออกจากข้อความดิบ · คืน None ถ้าไม่น่าเชื่อถือ

    ⚠ กับดักที่อันตรายที่สุด: ถ้า OCR อ่าน "12.34" พลาดเป็น "1234" จะได้ 1234.0
    ซึ่ง **ผิดไป 100 เท่าโดยดูเหมือนค่าปกติทุกประการ** และ confidence อาจสูงด้วยซ้ำ
    ทางแก้: ถ้ารู้รูปแบบมิเตอร์แน่นอน ให้ตั้ง expected_digits + decimal_places
    แล้วอย่าให้ OCR เป็นคนตัดสินตำแหน่งจุด — เราหารเอง
    """
    if decimal_places is not None:
        # โหมดรูปแบบตายตัว: สนใจเฉพาะตัวเลข ไม่สนจุดที่ OCR เดามา
        digits = re.sub(r"\D", "", raw)
        if not digits:
            return None
        if expected_digits and len(digits) != expected_digits:
            return None
        return int(digits) / (10 ** decimal_places)

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

def save_image(img_bgr):
    """เซฟภาพ **ต้นฉบับ** ลง SD · เรียกก่อน OCR เสมอ

    เหตุผลที่ต้องเป็นต้นฉบับ ไม่ใช่ภาพที่ crop แล้ว: ถ้าจูน roi_config.json ผิด
    ตอนแข่ง แล้วเก็บแต่ภาพที่ crop ผิดไว้ จะกลับมารันใหม่ด้วยค่าที่ถูกไม่ได้เลย
    ต้องไปถ่ายมิเตอร์ใหม่ ซึ่งในสนามแข่งทำไม่ได้
    """
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    rid = uuid.uuid4().hex[:12]
    img_name = f"{ts:%Y%m%d_%H%M%S}_{rid}.jpg"
    path = IMAGE_DIR / img_name
    if not cv2.imwrite(str(path), img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise RuntimeError(f"เขียนภาพไม่สำเร็จ: {path}")   # imwrite คืน False เงียบๆ
    return ts, rid, img_name


def _fsync_dir(path):
    """บังคับให้ directory entry ลง disk — ไม่งั้นไฟดับแล้วอาจได้ record ที่ชี้ไปยัง
    ไฟล์ภาพที่ยังไม่ปรากฏใน directory"""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save_reading(ts, rid, img_name, raw, value, conf, run_id, meter_type, source_name=None):

    rec = {
        "local_id": rid,
        "captured_at": ts.isoformat(),
        "run_id": run_id,
        "meter_type": meter_type,
        "raw_text": raw,
        "value": value,                    # ค่าที่ OCR อ่านได้ — ห้ามเขียนทับ (C23 ข้อ 2)
        "confidence": round(conf, 4),
        "image_path": f"images/{img_name}",
        "source": source_name,
        "synced_at": None,
        # ── ฟิลด์ schema กลางที่ ARIA (ระบบหอพัก) ต้องใช้ — ใส่ตั้งแต่แถวแรกเพื่อไม่ต้อง migrate (C23 ข้อ 1–2) ──
        "meter_id": None,                  # ผูกห้อง/มิเตอร์ — ยังไม่มีทะเบียนมิเตอร์ ใส่ทีหลังได้
        "status": "ocr",                   # ocr → confirmed | rejected (ผู้ให้เช่าเป็นคนเปลี่ยน ไม่ใช่หุ่น)
        "confirmed_value": None,           # ค่าที่คนยืนยัน — คนละฟิลด์กับ value เสมอ
    }
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())          # บังคับให้ลงแผ่นจริง กันไฟดับแล้วข้อมูลหาย
    _fsync_dir(JSONL_PATH.parent)
    _fsync_dir(IMAGE_DIR)
    return rec


# ─────────────────────────────────────────────────────────────

def process_one(img, cfg, engine, run_id, meter_type, name=None, debug_dir=None):
    # ลำดับสำคัญ: เซฟภาพต้นฉบับ **ก่อน** ทำ OCR
    # ถ้า OCR พัง (pytesseract ไม่พบ binary, ssocr timeout, crop ผิด) เฟรมที่เพิ่งถ่าย
    # จะยังอยู่บน SD ไม่หายไปพร้อมกับ exception
    ts, rid, img_name = save_image(img)

    raw, conf, value, err = "", 0.0, None, None
    try:
        binimg, cropped = preprocess(img, cfg)
        raw, conf = OCR_ENGINES[engine](binimg)
        value = parse_value(raw, cfg.get("expected_digits"), cfg.get("decimal_places"))
        if debug_dir:
            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(Path(debug_dir) / f"{rid}_bin.png"), binimg)
            cv2.imwrite(str(Path(debug_dir) / f"{rid}_crop.png"), cropped)
    except Exception as e:                     # noqa: BLE001 — ตั้งใจจับทุกอย่าง
        err = f"{type(e).__name__}: {e}"
        print(f"    ⚠ ประมวลผลไม่สำเร็จ ({err}) — ภาพถูกเซฟไว้แล้วที่ images/{img_name}")

    rec = save_reading(ts, rid, img_name, raw, value, conf, run_id, meter_type, name)
    if err:
        rec["error"] = err
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
            try:
                rec = process_one(img, cfg, args.engine, args.run_id, args.meter_type,
                                  name, args.debug_dir)
            except Exception as e:             # noqa: BLE001 — รูปหนึ่งพังต้องไม่หยุดทั้งชุด
                print(f"  ล้มเหลว {name:26s} {type(e).__name__}: {e}")
                continue
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
