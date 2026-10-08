"""cells engine — ฉากกล่อง REAI สังเคราะห์ (แผงน้ำเงิน · กรอบชมพู 4 ช่อง · มุมเอียง) + ตัวเลข Hershey ของ OpenCV
(ฟอนต์นี้ไม่อยู่ในชุดเทรนของ digitnet — tools/digit_cnn/fonts.py ใช้แค่ฟอนต์ระบบ macOS)"""
import sys
from pathlib import Path
import numpy as np
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import reai_strip      # noqa: E402
import cellread        # noqa: E402
import meter_reader as MR   # noqa: E402

BLUE, PINK = (230, 150, 140), (205, 150, 225)      # BGR วัดจากรูปจริง 6 ต.ค. (พื้นกล่อง / เส้นกรอบ)


def scene(text, ink=(30, 30, 30), tilt=0.06, card=None):
    """text = 4 ตัว ใช้ " " = ช่องว่าง"""
    panel = np.full((360, 560, 3), BLUE, np.uint8)
    x0, y0, cw = 40, 160, 120
    for i, ch in enumerate(text):
        x = x0 + i * cw
        if card is not None:
            cv2.rectangle(panel, (x + 12, y0 + 12), (x + cw - 12, y0 + cw - 12), card, -1)
        if ch != " ":
            cv2.putText(panel, ch, (x + 30, y0 + 95), cv2.FONT_HERSHEY_DUPLEX, 3.0, ink, 7, cv2.LINE_AA)
    cv2.rectangle(panel, (x0, y0), (x0 + 4 * cw, y0 + cw), PINK, 4)
    for i in range(1, 4):
        cv2.line(panel, (x0 + i * cw, y0), (x0 + i * cw, y0 + cw), PINK, 4)
    img = np.full((1080, 1920, 3), (215, 218, 220), np.uint8)              # ผนังเทา
    src = np.float32([[0, 0], [560, 0], [560, 360], [0, 360]])
    dst = np.float32([[700, 350], [1260, 350 + 560 * tilt], [1250, 720], [710, 700]])
    H = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(panel, H, (1920, 1080))
    mask = cv2.warpPerspective(np.full((360, 560), 255, np.uint8), H, (1920, 1080))
    img[mask > 0] = warped[mask > 0]
    img = cv2.GaussianBlur(img, (3, 3), 0)
    return img


def test_finds_strip_and_reads_dark_digits():
    r = cellread.read_meter(scene("2749"))
    assert r["ok"] and r["text"] == "2749", r


def test_reads_light_ink_and_card():
    assert cellread.read_meter(scene("5083", ink=(240, 240, 240)))["text"] == "5083"
    assert cellread.read_meter(scene("6161", ink=(20, 20, 160), card=(235, 235, 235)))["text"] == "6161"


def test_empty_box_is_not_a_reading():
    r = cellread.read_meter(scene("    "))
    assert r["strip"] is not None and r["text"] == "____" and not r["ok"]
    assert MR.ocr_cells(scene("    ")) == ("", 0.0)


def test_no_box_falls_back_to_digit_row():
    img = np.full((1080, 1920, 3), (215, 218, 220), np.uint8)
    cv2.putText(img, "1234", (600, 600), cv2.FONT_HERSHEY_DUPLEX, 6, (40, 40, 220), 12)   # เลขแดงลอยๆ ไม่มีกรอบ
    assert reai_strip.find_strip(img) is None
    r = cellread.read_meter(img)
    assert r["source"] == "row" and r["text"] == "1234", r


def test_plain_scene_gives_nothing():
    img = np.full((1080, 1920, 3), (215, 218, 220), np.uint8)
    for x in range(200, 1800, 90):                     # ขอบตู้/มู่ลี่: เส้นตั้งเรียงกัน
        cv2.line(img, (x, 200), (x, 900), (60, 60, 60), 6)
    assert MR.ocr_cells(img) == ("", 0.0)


def test_engine_registered_and_parse():
    assert "cells" in MR.OCR_ENGINES and MR.OCR_ENGINES["cells"].needs_color
    raw, conf = MR.ocr_cells(scene("0815"))
    assert raw == "0815" and 0 < conf <= 1
    assert MR.parse_value(raw, expected_digits=4) == 815.0


def test_prepare_skips_binarize_for_color_engines():
    cfg = MR.load_config()
    img = scene("3141")
    for eng in ("cells", "sevenseg"):
        b, c = MR.prepare(eng, img, cfg)
        assert b is None and c.ndim == 3
    b, c = MR.prepare("tesseract", img, cfg)
    assert b is not None and b.ndim == 2
    assert MR.run_engine("cells", None, c, cfg)[0] == "3141"


def test_warmup_loads_model():
    MR.warmup("cells")
    assert cellread._net is not None
    MR.warmup("sevenseg")                     # engine อื่นต้องไม่พัง


def drum_scene(text, red_last=2):
    """มิเตอร์ลูกกลิ้ง: เลขดำในช่องขาว · red_last หลักท้ายเป็นเลขขาวบนช่องแดง · ไม่มีกรอบ REAI"""
    img = np.full((720, 1280, 3), (70, 70, 75), np.uint8)
    cv2.rectangle(img, (380, 300), (380 + 70 * len(text) + 20, 420), (25, 25, 25), -1)
    for i, ch in enumerate(text):
        x = 390 + i * 70
        red = i >= len(text) - red_last
        cv2.rectangle(img, (x, 312), (x + 62, 408), (40, 40, 210) if red else (235, 235, 235), -1)
        cv2.putText(img, ch, (x + 9, 392), cv2.FONT_HERSHEY_DUPLEX, 2.6, (240, 240, 240) if red else (20, 20, 20), 6, cv2.LINE_AA)
    return cv2.GaussianBlur(img, (3, 3), 0)


def test_fallback_reads_drum_meter_without_reai_box():
    r = cellread.read_meter(drum_scene("0521893"))
    assert r["source"] == "row" and r["ok"] and r["text"] == "0521893", r
