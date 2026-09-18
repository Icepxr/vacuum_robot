"""sevenseg — ตัวเลข 7-segment สังเคราะห์ (ปากกาแดงบนพื้นขาว) ทุกหลัก 0–9 + แถว 1509 ที่หลักชนกัน"""
import sys
from pathlib import Path
import numpy as np
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import sevenseg as S          # noqa: E402
import meter_reader as MR     # noqa: E402

SEGS = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg"}
RED = (60, 60, 220)   # BGR ≈ ปากกาแดง

def draw_digit(img, x, y, w, h, segs, t=6, ext=0):
    # ext > 0 = ลากขีดล่างยาวเกินไปแตะหลักถัดไป (เลียนแบบลายมือ 5→0 ในภาพจริง 18 ก.ย.)
    L = {"a": ((x, y), (x + w, y)), "b": ((x + w, y), (x + w, y + h // 2)), "c": ((x + w, y + h // 2), (x + w, y + h)),
         "d": ((x, y + h), (x + w + ext, y + h)), "e": ((x, y + h // 2), (x, y + h)), "f": ((x, y), (x, y + h // 2)),
         "g": ((x, y + h // 2), (x + w, y + h // 2))}
    for s in segs:
        (x0, y0), (x1, y1) = L[s]
        cv2.line(img, (x0, y0), (x1, y1), RED, t)

def scene(text, w=70, h=120, gap=30, touching=False):
    img = np.full((400, 700, 3), 245, np.uint8)
    cv2.rectangle(img, (40, 40), (660, 360), (200, 200, 200), 2)    # ขอบ "การ์ด" สีเทาไม่ใช่แดง
    x = 120
    for ch in text:
        dw = w // 3 if ch == "1" else w
        draw_digit(img, x, 140, dw, h, SEGS[ch], ext=(14 if touching else 0))
        x += dw + (14 if touching else gap)
    return img

def test_each_digit_alone():
    for ch in "0123456789":
        r = S.read(scene(ch))
        assert r["text"] == ch, (ch, r)

def test_row_with_gaps():
    assert S.read(scene("1509"))["text"] == "1509"

def test_row_touching_digits_gets_split():
    r = S.read(scene("1509", touching=True))
    assert r["text"] == "1509", r

def test_engine_wiring_uses_color_image():
    cfg = MR.load_config(); cfg["crop"] = {"x": 0, "y": 0, "w": 1, "h": 1}; cfg["ink"] = "red"
    img = scene("42")
    binimg, cropped = MR.preprocess(img, cfg)
    raw, conf = MR.run_engine("sevenseg", binimg, cropped, cfg)
    assert raw == "42" and conf >= 0.9

def test_no_ink_returns_empty_not_crash():
    r = S.read(np.full((200, 300, 3), 240, np.uint8))
    assert r["text"] == "" and r["ok"] is False
