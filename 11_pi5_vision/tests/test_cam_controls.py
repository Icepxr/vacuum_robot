"""C36 ซูม/แพน/ทิลต์/โฟกัสผ่าน UVC — parse `v4l2-ctl --list-ctrls` + แปลงค่า normalized → raw ตาม step ของกล้อง (ไม่ต้องมีกล้อง)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import capture_daemon as D   # noqa: E402

BRIO_LIST = """
User Controls
                     brightness 0x00980900 (int)    : min=0 max=255 step=1 default=128 value=128
Camera Controls
                  focus_absolute 0x009a090a (int)    : min=0 max=255 step=5 default=0 value=20 flags=inactive
     focus_automatic_continuous 0x009a090c (bool)   : default=1 value=1
                   zoom_absolute 0x009a090d (int)    : min=100 max=500 step=1 default=100 value=100
                    pan_absolute 0x009a0908 (int)    : min=-36000 max=36000 step=3600 default=0 value=0
                   tilt_absolute 0x009a0909 (int)    : min=-36000 max=36000 step=3600 default=0 value=0
"""


def test_parse_list_ctrls(monkeypatch):
    class R: stdout = BRIO_LIST
    monkeypatch.setattr(D.subprocess, "run", lambda *a, **k: R())
    c = D.uvc_list_ctrls("/dev/video0")
    assert c["zoom_absolute"] == {"min": 100, "max": 500, "step": 1, "default": 100, "value": 100}
    assert c["pan_absolute"]["step"] == 3600 and c["focus_automatic_continuous"] == {"min": 0, "max": 1, "step": 1, "default": 1, "value": 1}
    assert c["focus_absolute"]["max"] == 255


def _backend_stub(monkeypatch, ctrls):
    """UsbCameraBackend โดยไม่เปิดกล้อง: ประกอบ object เปล่าแล้วรัน logic control อย่างเดียว · จับสิ่งที่ส่งให้ v4l2-ctl"""
    sent = []
    class R: stdout = ""
    def run(cmd, **k):
        sent.append(cmd[-1]); return R()
    monkeypatch.setattr(D.subprocess, "run", run)
    b = D.UsbCameraBackend.__new__(D.UsbCameraBackend)
    b.dev = "/dev/video0"; b.uvc = ctrls
    b.ctl = {"zoom": 1.0, "pan": 0.0, "tilt": 0.0, "af": True, "focus": 0.5}
    b.hw = {k: next((n for n in names if n in ctrls), None) for k, names in D.UVC_NAMES.items()}
    b.zoom_max = ctrls["zoom_absolute"]["max"] / ctrls["zoom_absolute"]["min"] if "zoom_absolute" in ctrls else 4.0
    return b, sent


def test_set_control_maps_to_uvc_raw_with_step(monkeypatch):
    class R: stdout = BRIO_LIST
    monkeypatch.setattr(D.subprocess, "run", lambda *a, **k: R())
    ctrls = D.uvc_list_ctrls("/dev/video0")
    b, sent = _backend_stub(monkeypatch, ctrls)
    assert b.zoom_max == 5.0
    r = b.set_control(zoom=2.5)
    assert r["zoom"] == 2.5 and "--set-ctrl=zoom_absolute=250" in sent
    b.set_control(zoom=9); assert b.ctl["zoom"] == 5.0 and sent[-1] == "--set-ctrl=zoom_absolute=500"
    b.set_control(pan=0.5); assert sent[-1] == "--set-ctrl=pan_absolute=18000"          # ลงตัว step 3600
    b.set_control(pan=0.51); assert sent[-1] == "--set-ctrl=pan_absolute=18000"         # ปัดเข้า step
    b.set_control(tilt=-1); assert sent[-1] == "--set-ctrl=tilt_absolute=-36000"
    b.set_control(focus=0.3); assert not any("focus_absolute" in x for x in sent)        # AF เปิดอยู่ → ยังไม่ส่งระยะ
    b.set_control(af=False)
    assert "--set-ctrl=focus_automatic_continuous=0" in sent and sent[-1] == "--set-ctrl=focus_absolute=75"   # 0.3×255 = 76.5 → step 5 → 75
    b.set_control(focus=1.0); assert sent[-1] == "--set-ctrl=focus_absolute=255"


def test_software_zoom_when_no_uvc(monkeypatch):
    import numpy as np
    b, sent = _backend_stub(monkeypatch, {})
    assert b.zoom_max == 4.0 and b.controls()["sw_zoom"] is True
    b._frame = np.zeros((1080, 1920, 3), np.uint8); b._frame[540, 960] = 255
    import time, threading
    b._frame_ts = time.monotonic(); b._lock = threading.Lock()
    b.set_control(zoom=2.0)
    f = b.latest(); assert f.shape[:2] == (540, 960) and f[270, 480, 0] == 255            # ครอปกลางภาพ พิกเซลกลางยังอยู่กลาง
    b.set_control(zoom=2.0, pan=1.0, tilt=1.0)
    f = b.latest(); assert f.shape[:2] == (540, 960) and f[0, 0, 0] == 0                  # เลื่อนไปมุมขวาบน (pan +1 = ขวา · tilt +1 = บน)
    assert sent == []                                                                     # ไม่มี UVC → ไม่เรียก v4l2-ctl เลย
