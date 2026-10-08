"""F10 API ป๊อปอัพบน /drive: /api/pending · ตัดสิน · /crops · เหตุการณ์ reading ติดป้าย pending + อากาศ/นาฬิกา"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import aria_store as S             # noqa: E402
import mrc_web as W                # noqa: E402
from test_aria_store import JPG, make, registry  # noqa: E402
from test_web import web as _web   # noqa: E402,F401 — fixture เดิม (daemon + pty + TestClient)


@pytest.fixture
def web(_web, tmp_path, monkeypatch):
    monkeypatch.setattr(S, "DATA_DIR", tmp_path)       # aria_store อ่านที่เก็บเดียวกับเว็บในเทสต์
    return _web


def test_pending_list_and_crop(web, tmp_path):
    c, *_ = web
    registry(tmp_path, [{"meter_id": "W-204-01", "room": "204", "type": "water"}, {"meter_id": "E-110-01", "room": "110", "type": "electric"}])
    rec = make(tmp_path)
    d = c.get("/api/pending").json()
    assert d["rooms"] == ["110", "204"] and d["ttl_days"] == 7 and d["registry_version"] == 3
    assert [i["local_id"] for i in d["items"]] == [rec["local_id"]] and d["items"][0]["crop_url"] == f"/crops/{rec['local_id']}.jpg"
    assert c.get(d["items"][0]["crop_url"]).content == JPG
    assert c.get("/crops/../readings.jsonl").status_code == 404
    assert c.get("/api/status").json()["pending_decisions"] == 1


def test_keep_via_api_then_status_counts(web, tmp_path):
    c, *_ = web
    registry(tmp_path, [{"meter_id": "W-204-01", "room": "204", "type": "water"}])
    rec = make(tmp_path)
    r = c.post(f"/api/pending/{rec['local_id']}", json={"keep": True, "room_id": "204", "meter_type": "water"})
    assert r.status_code == 200 and r.json()["meter_id"] == "W-204-01"
    s = c.get("/api/status").json()
    assert s["pending_decisions"] == 0 and s["pending_sync"] == 1 and s["pending_crops"] == 1 and "warn" in s
    assert c.post(f"/api/pending/{rec['local_id']}", json={"keep": False}).status_code == 404   # ตัดสินไปแล้ว


def test_bad_input_keeps_pending(web, tmp_path):
    c, *_ = web
    rec = make(tmp_path)
    r = c.post(f"/api/pending/{rec['local_id']}", json={"keep": True, "room_id": "", "meter_type": "water"})
    assert r.status_code == 400 and r.json()["reason"] == "bad_room"
    assert len(c.get("/api/pending").json()["items"]) == 1


def test_discard_via_api(web, tmp_path):
    c, *_ = web
    rec = make(tmp_path)
    assert c.post(f"/api/pending/{rec['local_id']}", json={"keep": False}).json()["keep"] is False
    assert c.get("/api/pending").json()["items"] == []
    assert not (tmp_path / "images" / f"{rec['local_id']}.jpg").exists()


def test_reading_event_marks_pending_and_attaches(web, tmp_path, monkeypatch):
    c, master, backend, hub = web
    monkeypatch.setattr(S, "clock_synced", lambda: False)
    rec = make(tmp_path)
    ev = {"t": "reading", **rec}
    hub.on_event(ev)
    assert hub.events[-1]["pending"] is True and hub.events[-1]["crop_url"] == f"/crops/{rec['local_id']}.jpg"
    assert S.get_pending(rec["local_id"])["clock_synced"] is False


def test_rooms_without_meters_and_pull_button(web, tmp_path, monkeypatch):
    """8 ต.ค.: ทะเบียนจาก ARIA มี rooms → ห้องที่ยังไม่มีมิเตอร์อยู่ใน dropdown · ปุ่มดึงทันทีคืนรายชื่อใหม่"""
    import sync_supabase as SY
    c, *_ = web
    (tmp_path / "meters.json").write_text(json.dumps({"registry_version": 5, "pulled_at": "2026-10-08T03:00:00+00:00",
        "rooms": [{"room_id": "A101"}, {"room_id": "A103"}], "meters": [{"meter_id": "W-A101-01", "room": "A101", "type": "water"}]}))
    d = c.get("/api/pending").json()
    assert d["rooms"] == ["A101", "A103"] and d["registry_version"] == 5 and d["registry_pulled_at"]
    monkeypatch.setattr(SY, "pull_registry", lambda tok, sha=None: (False, "ดึงทะเบียนไม่ได้ (None): offline"))
    r = c.post("/api/registry/pull")
    assert r.status_code == 502 and r.json()["rooms"] == ["A101", "A103"]     # เน็ตล้ม = ใช้รายชื่อเดิม
