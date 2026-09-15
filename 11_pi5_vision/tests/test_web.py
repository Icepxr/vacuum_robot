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
    c = web[0]
    with c.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"t": "estop"})
        ev = ws.receive_json()
        while ev["t"] == "sys":
            ev = ws.receive_json()
        assert ev["t"] == "nack" and ev["cmd"] == "estop"


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
