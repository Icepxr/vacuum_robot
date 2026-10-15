"""engine ทดลองที่รันใน worker แยกโปรเซส (ไฟล์ 38 `yolo` · ไฟล์ 39 `tr`)
ลงทะเบียนแล้ว · worker หาย/เริ่มไม่ได้ต้อง raise (capture_daemon จับไว้ ไม่ล้มการถ่าย)
มี worker จริง (ตั้ง MRC_YOLO_PY + MRC_YOLO_DIR / MRC_TR_DIR) → อ่านภาพเปล่าได้ไม่พัง และไม่อ่านเป็นเลข"""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import meter_reader as MR   # noqa: E402
import tr_meter             # noqa: E402
import yolo_meter           # noqa: E402

ENGINES = [("yolo", yolo_meter, "MRC_YOLO_DIR"), ("tr", tr_meter, "MRC_TR_DIR")]


@pytest.mark.parametrize("name,mod,_", ENGINES)
def test_registered_as_color_engine(name, mod, _):
    assert name in MR.OCR_ENGINES and MR.OCR_ENGINES[name].needs_color


@pytest.mark.parametrize("name,mod,_", ENGINES)
def test_missing_worker_python_raises(monkeypatch, name, mod, _):
    monkeypatch.setattr(mod.client, "py", "/nonexistent/python")
    mod.client.kill()
    with pytest.raises(OSError):
        mod.read(np.zeros((72, 128, 3), np.uint8))


@pytest.mark.parametrize("name,mod,env", ENGINES)
def test_missing_models_reported(monkeypatch, tmp_path, name, mod, env):
    if not os.environ.get("MRC_YOLO_PY"):
        pytest.skip("ต้องตั้ง MRC_YOLO_PY ชี้ python ที่มี ncnn")
    monkeypatch.setattr(mod.client, "py", os.environ["MRC_YOLO_PY"])
    monkeypatch.setenv(env, str(tmp_path))
    mod.client.kill()
    with pytest.raises(RuntimeError, match="เริ่มไม่ได้"):
        mod.read(np.zeros((72, 128, 3), np.uint8))
    mod.client.kill()


@pytest.mark.parametrize("name,mod,env", ENGINES)
def test_blank_frame_reads_nothing(monkeypatch, name, mod, env):
    if not (os.environ.get("MRC_YOLO_PY") and os.environ.get(env)):
        pytest.skip(f"ต้องตั้ง MRC_YOLO_PY + {env}")
    monkeypatch.setattr(mod.client, "py", os.environ["MRC_YOLO_PY"])
    mod.client.kill()
    blank = np.full((1080, 1920, 3), 200, np.uint8)
    r = mod.read(blank)
    assert r["text"] == "" and r["conf"] == 0.0
    assert MR.OCR_ENGINES[name](blank) == ("", 0.0)
    if name == "tr":
        assert r["why"] == "no_meter"
    mod.client.kill()
