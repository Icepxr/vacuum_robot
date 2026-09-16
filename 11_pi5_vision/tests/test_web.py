"""ทดสอบ mrc_web.py บนโน้ตบุ๊ก — FastAPI TestClient + backend ปลอม + pty ปลอมแทน ESP32
ครอบคลุม: /api/status · /api/readings · /stream.mjpg · WS capture → เหตุการณ์ capture+reading · nack คำสั่งที่ ESP32 ยังไม่รองรับ
· CAPTURE_REQ จาก ESP32 ปลอม ยังทำงานเหมือนเดิมขณะเว็บรันอยู่"""
import json
import os
import pty
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import mrc_protocol as P            # noqa: E402
import mrc_web as W                 # noqa: E402
from test_capture_daemon import FakeBackend, read_line  # noqa: E402

FAKE_JPG = b"\xff\xd8\xff\xe0FAKEJPEG\xff\xd9"


class FakeCamBackend(FakeBackend):
    def preview_jpeg(self):
        return FAKE_JPG if self.have_frame else None


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "DATA_DIR", tmp_path)
    monkeypatch.setattr(W, "IMAGE_DIR", tmp_path / "images")
    monkeypatch.setattr(W, "JSONL_PATH", tmp_path / "readings.jsonl")
    (tmp_path / "images").mkdir()
    (tmp_path / "readings.jsonl").write_text(json.dumps({
        "local_id": "old1", "captured_at": "2026-09-15T01:00:00+00:00", "value": 42.5,
        "confidence": 0.9, "raw_text": "42.5", "image_path": "images/old.jpg", "synced_at": None,
        "status": "ocr", "meter_id": None, "confirmed_value": None}) + "\n", encoding="utf-8")
    (tmp_path / "images" / "old.jpg").write_bytes(FAKE_JPG)

    master, slave = pty.openpty()
    backend = FakeCamBackend(tmp_path / "images")
    hub = W.Hub(); monkeypatch.setattr(W, "hub", hub)
    d = W.start_daemon(os.ttyname(slave), backend)
    with TestClient(W.app) as c:
        yield c, master, backend, hub
    d.stop()
    os.close(master)


def test_status_and_readings(web):
    c, master, backend, hub = web
    s = c.get("/api/status").json()
    assert s["cam_ok"] is True and s["link"]["alive"] is False and "CAPTURE_REQ" in s["esp32_supports"]
    rows = c.get("/api/readings").json()
    assert rows[0]["local_id"] == "old1" and rows[0]["status"] == "ocr"
    assert c.get("/images/old.jpg").content == FAKE_JPG
    assert c.get("/images/../secret").status_code == 404


def test_index_and_static_have_no_cdn(web):
    c = web[0]
    html = c.get("/").text
    assert "app.js" in html and "http://" not in html and "https://" not in html   # สนามไม่มีเน็ต
    assert c.get("/static/app.js").status_code == 200


def test_mjpeg_stream_yields_frame(web):
    c = web[0]
    with c.stream("GET", "/stream.mjpg?frames=2") as r:
        assert r.headers["content-type"].startswith("multipart/x-mixed-replace")
        chunk = next(r.iter_bytes())
        assert b"Content-Type: image/jpeg" in chunk and FAKE_JPG in chunk


def test_ws_capture_from_web(web):
    c, master, backend, hub = web
    with c.websocket_connect("/ws") as ws:
        assert ws.receive_json()["t"] == "hello"
        assert ws.receive_json()["t"] == "sys"
        ws.send_json({"t": "capture"})
        got = {}
        for _ in range(6):
            ev = ws.receive_json()
            if ev["t"] in ("capture", "reading"):
                got[ev["t"]] = ev
            if len(got) == 2:
                break
        assert got["capture"]["ok"] and got["capture"]["source"] == "web"
        assert got["reading"]["value"] == 123.4 and got["reading"]["source_req"] == "web"
        assert backend.saved == ["img_0.jpg"]
        # ห้ามมีอะไรถูกส่งไป ESP32 (ถ่ายจากเว็บไม่เกี่ยวกับ $K)
        assert read_line(master, timeout=0.3) == b""


def test_ws_unsupported_command_gets_honest_nack(web):
    """คำสั่งที่ ESP32 ยังไม่รับ (ยกเสาจาก Pi = $M) ต้องได้ nack ตรงๆ ไม่แกล้งส่ง"""
    c, master, backend, hub = web
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"t": "mast", "up": 1})
        ev = ws.receive_json()
        while ev["t"] in ("sys", "log", "tele"):
            ev = ws.receive_json()
        assert ev["t"] == "nack" and ev["cmd"] == "mast"
        assert read_line(master, timeout=0.3) == b""      # ไม่มีอะไรออกไป ESP32


def test_esp32_capture_req_still_works_and_reaches_ws(web):
    c, master, backend, hub = web
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        os.write(master, P.capture_req(1000, 7))
        reply = P.decode(read_line(master))
        assert reply.fields == ["K", "7", "1"]
        ev = ws.receive_json()
        while ev["t"] != "capture":
            ev = ws.receive_json()
        assert ev["n"] == "7" and ev["source"] == "esp32" and ev["ok"]
        time.sleep(0.2)
        assert c.get("/api/status").json()["link"]["alive"] is True


# ── ขั้น E: ขับเอง · deadman ฝั่ง Pi · #T · nack จาก ESP32 ──

def _drain_until(ws, kind, n=20):
    for _ in range(n):
        ev = ws.receive_json()
        if ev["t"] == kind:
            return ev
    raise AssertionError(f"ไม่เจอ {kind}")


def test_drive_repeats_V_at_10hz_then_deadman_sends_S(web):
    c, master, backend, hub = web
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"t": "drive", "v": 120, "w": -300})
        # browser เงียบ: Pi ต้องส่ง $V ซ้ำ ≥ 2 ครั้งใน 300 ms แล้วตามด้วย $S ครั้งเดียว
        got = []
        end = time.time() + 0.9
        while time.time() < end:
            line = read_line(master, timeout=0.2)
            if line:
                got.append(P.decode(line))
        kinds = [g.type for g in got if g]
        assert kinds.count("V") >= 2, kinds
        assert kinds[-1] == "S" and kinds.count("S") == 1, kinds
        v = next(g for g in got if g and g.type == "V")
        assert v.fields[2:] == ["120", "-300"]
        assert hub.drive_tripped == 1


def test_drive_clamped_to_user_limits_default_150(web):
    c, master, backend, hub = web
    hub.drive(999, -9999)
    assert (hub.drive_v, hub.drive_w) == (150, -1500)


def test_user_limits_raise_cap_and_send_L_clamped_at_hw(web):
    """C28: ผู้ใช้ตั้งเพดานเอง → Pi clamp ที่ฮาร์ดแวร์ 716/7950 · ส่ง $L · broadcast limits · drive ใช้เพดานใหม่"""
    c, master, backend, hub = web
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"t": "limits", "v_max": 300, "w_max": 2000})
        fr = P.decode(read_line(master))
        assert fr.type == "L" and fr.fields[2:] == ["300", "2000"]
        ev = _drain_until(ws, "limits")
        assert ev["v_max"] == 300 and ev["w_max"] == 2000 and ev["v_hw_max"] == 716
        hub.drive(999, -9999)
        assert (hub.drive_v, hub.drive_w) == (300, -2000)
        ws.send_json({"t": "limits", "v_max": 5000, "w_max": 99999})     # เกินฮาร์ดแวร์ → clamp
        fr = P.decode(read_line(master))
        assert fr.fields[2:] == ["716", "7950"]
        assert _drain_until(ws, "limits")["v_max"] == 716
        s = c.get("/api/status").json()
        assert s["limits"]["v_max"] == 716 and "$L" in s["esp32_supports"]


def test_estop_and_clean_frames(web):
    c, master, backend, hub = web
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"t": "estop"})
        assert P.decode(read_line(master)).type == "E"
        ws.send_json({"t": "clean", "suction": 100, "brush": 60})   # brush เกิน 40 → clamp
        fr = P.decode(read_line(master))
        assert fr.type == "C" and fr.fields[2:] == ["100", "40"]


def test_tele_from_esp32_reaches_ws_and_status(web):
    c, master, backend, hub = web
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        os.write(master, P.encode("#", "T", 12345, 1, 120, 0, 168, 168, 0, 0, 0, 0, 0, 2))
        ev = _drain_until(ws, "tele")
        assert ev["state_name"] == "MANUAL" and ev["v"] == 120 and ev["duty_l"] == 168 and ev["comm_lost"] is True
        assert ev["spinup_hold"] is False
        os.write(master, P.encode("#", "T", 12445, 1, 120, 0, 0, 0, 0, 0, 0, 0, 0, 4))    # flag 0x04 = R2 hold
        assert _drain_until(ws, "tele")["spinup_hold"] is True
        time.sleep(0.1)
        s = c.get("/api/status").json()
        assert s["tele"]["state"] == 1 and s["link"]["alive"] is True


def test_nack_from_esp32_forwarded(web):
    c, master, backend, hub = web
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        os.write(master, P.encode("#", "N", 7, "MAST_UP"))
        ev = _drain_until(ws, "nack")
        assert ev["seq"] == 7 and ev["reason"] == "MAST_UP"


def test_roi_get_set(web, tmp_path, monkeypatch):
    c = web[0]
    monkeypatch.setattr(W, "ROI_PATH", tmp_path / "roi.json")
    assert c.get("/api/roi").json()["crop"]["w"] == 1
    r = c.post("/api/roi", json={"crop": {"x": 0.3, "y": 0.4, "w": 0.3, "h": 0.2}}).json()
    assert r["ok"] and r["crop"]["x"] == 0.3
    assert json.loads((tmp_path / "roi.json").read_text())["crop"]["h"] == 0.2
    assert c.post("/api/roi", json={"crop": {"x": 0, "y": 0, "w": 0.001, "h": 1}}).status_code == 400


def test_boot_event_resends_limits(web):
    """ESP32 ส่ง #E BOOT,TASK_WDT → Pi ส่ง $L ซ้ำ (ค่าเพดานอยู่ใน RAM ของ ESP32 หายตอนรีบูต) + log เตือน"""
    c, master, backend, hub = web
    hub.set_limits(300, 2000)
    assert P.decode(read_line(master)).type == "L"
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        os.write(master, P.encode("#", "E", 1234, "BOOT", "TASK_WDT"))
        fr = P.decode(read_line(master))
        assert fr.type == "L" and fr.fields[2:] == ["300", "2000"]
        ev = _drain_until(ws, "log")
        assert "watchdog" in ev["msg"] and ev["level"] == "warn"


def test_camera_fallback_keeps_service_alive(tmp_path, monkeypatch):
    """ไม่มีกล้อง (เปิด index ไม่ได้) → ไม่ raise · ได้ backend ภาพนิ่ง · cam_ok False (บอกตรงๆ) — กัน systemd วน restart"""
    import types
    monkeypatch.setattr(W, "DATA_DIR", tmp_path)
    monkeypatch.setattr(W, "IMAGE_DIR", tmp_path / "images")
    def boom(*a, **k): raise RuntimeError("เปิดกล้อง index 0 ไม่ได้")
    monkeypatch.setattr(W.D, "UsbCameraBackend", boom)
    args = types.SimpleNamespace(camera=0, engine="tesseract", run_id="t")
    b = W.open_camera_or_fallback(args)
    assert b.latest() is not None and W.hub.cam_fallback is True and (tmp_path / "no_camera.jpg").exists()
    W.hub.backend = b
    assert W.hub.status()["cam_ok"] is False
    W.hub.cam_fallback = False
