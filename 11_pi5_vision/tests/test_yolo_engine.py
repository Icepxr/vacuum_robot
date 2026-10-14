"""engine yolo (ทดลอง · ไฟล์ 38): ลงทะเบียนแล้ว · worker หาย/เริ่มไม่ได้ต้อง raise (capture_daemon จับไว้ ไม่ล้มการถ่าย)
มี worker จริง (ตั้ง MRC_YOLO_PY + MRC_YOLO_DIR) → อ่านภาพเปล่าได้ไม่พัง และไม่อ่านเป็นเลข"""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import meter_reader as MR   # noqa: E402
import yolo_meter           # noqa: E402


def test_registered_as_color_engine():
    assert "yolo" in MR.OCR_ENGINES and MR.OCR_ENGINES["yolo"].needs_color


def test_missing_worker_python_raises(monkeypatch):
    monkeypatch.setattr(yolo_meter, "PY", "/nonexistent/python")
    yolo_meter._kill()
    with pytest.raises(OSError):
        yolo_meter.read(np.zeros((72, 128, 3), np.uint8))


def test_missing_models_reported(monkeypatch, tmp_path):
    if not os.environ.get("MRC_YOLO_PY"):
        pytest.skip("ต้องตั้ง MRC_YOLO_PY ชี้ python ที่มี ncnn")
    monkeypatch.setattr(yolo_meter, "PY", os.environ["MRC_YOLO_PY"])
    monkeypatch.setenv("MRC_YOLO_DIR", str(tmp_path))
    yolo_meter._kill()
    with pytest.raises(RuntimeError, match="เริ่มไม่ได้"):
        yolo_meter.read(np.zeros((72, 128, 3), np.uint8))
    yolo_meter._kill()


def test_blank_frame_reads_nothing(monkeypatch):
    if not (os.environ.get("MRC_YOLO_PY") and os.environ.get("MRC_YOLO_DIR")):
        pytest.skip("ต้องตั้ง MRC_YOLO_PY + MRC_YOLO_DIR")
    monkeypatch.setattr(yolo_meter, "PY", os.environ["MRC_YOLO_PY"])
    yolo_meter._kill()
    r = yolo_meter.read(np.full((1080, 1920, 3), 200, np.uint8))
    assert r["text"] == "" and r["conf"] == 0.0 and yolo_meter.last["ms_counter"] > 0
    assert MR.ocr_yolo(np.full((1080, 1920, 3), 200, np.uint8)) == ("", 0.0)
    yolo_meter._kill()
