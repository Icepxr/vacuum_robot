"""F10 ป๊อปอัพตัดสินรูป + ทะเบียนมิเตอร์ + สถานะ sync (aria_store) — ไม่ต้องมี cv2/กล้อง/Pi"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import aria_store as S  # noqa: E402

JPG = b"\xff\xd8\xff\xe0crop\xff\xd9"


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "DATA_DIR", tmp_path)
    (tmp_path / "images").mkdir()
    return tmp_path


def make(data, lid="0123456789ab", crop=True, captured=None):
    (data / "images" / f"{lid}.jpg").write_bytes(b"orig")
    rec = {"local_id": lid, "captured_at": (captured or datetime.now(timezone.utc)).isoformat(), "value": 1234,
           "confidence": 0.9, "raw_text": "01234", "image_path": f"images/{lid}.jpg", "meter_type": "water",
           "status": "ocr", "confirmed_value": None, "meter_id": None, "synced_at": None}
    return S.save_pending(rec, JPG if crop else None)


def registry(data, meters, version=3):
    (data / "meters.json").write_text(json.dumps({"registry_version": version, "meters": meters}), encoding="utf-8")


def jsonl(data):
    p = data / "readings.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_capture_goes_to_pending_not_jsonl(data):
    rec = make(data)
    assert (data / "pending" / f"{rec['local_id']}.json").is_file()
    assert (data / "crops" / f"{rec['local_id']}.jpg").read_bytes() == JPG
    assert rec["crop_path"] == f"crops/{rec['local_id']}.jpg" and rec["device_id"] == S.DEVICE_ID
    assert jsonl(data) == []                          # ยังไม่เก็บ = ยังไม่มีอะไรให้ sync


def test_keep_resolves_meter_from_registry(data):
    registry(data, [{"meter_id": "W-204-01", "room": "204", "type": "water"},
                    {"meter_id": "E-204-01", "room": "204", "type": "electric"}])
    rec = make(data)
    S.attach(rec["local_id"], air={"eco2_ppm": 600, "validity": 0}, clock_synced=True)
    ok, r = S.decide(rec["local_id"], True, "204", "electric")
    assert ok and r["meter_id"] == "E-204-01" and r["registry_version"] == 3
    rows = jsonl(data)
    assert len(rows) == 1 and rows[0]["driver_decision"] == "kept" and rows[0]["room_id"] == "204"
    assert rows[0]["meter_type"] == "electric" and rows[0]["air"]["eco2_ppm"] == 600 and rows[0]["clock_synced"] is True
    assert "pending_since" not in rows[0] and rows[0]["decided_at"]
    assert not (data / "pending" / f"{rec['local_id']}.json").exists()
    assert (data / "crops" / f"{rec['local_id']}.jpg").exists()          # crop ต้องอยู่ต่อเพื่อ sync
    assert (data / "images" / f"{rec['local_id']}.jpg").exists()         # ต้นฉบับอยู่บน Pi เสมอ


def test_keep_without_registry_or_ambiguous_leaves_meter_null(data):
    rec = make(data)
    ok, r = S.decide(rec["local_id"], True, "999", "water")
    assert ok and r["meter_id"] is None and r["room_id"] == "999"
    registry(data, [{"meter_id": "W-1-01", "room": "1", "type": "water"}, {"meter_id": "W-1-02", "room": "1", "type": "water"}])
    rec2 = make(data, "abcdefabcdef")
    ok, r = S.decide(rec2["local_id"], True, "1", "water")
    assert ok and r["meter_id"] is None                 # 2 ตัวชนิดเดียวกัน = ไม่เดา


def test_discard_deletes_everything(data):
    rec = make(data)
    ok, r = S.decide(rec["local_id"], False)
    assert ok and r["driver_decision"] == "discarded"
    lid = rec["local_id"]
    assert not any(p.exists() for p in [data / "pending" / f"{lid}.json", data / "crops" / f"{lid}.jpg", data / "images" / f"{lid}.jpg"])
    assert jsonl(data) == []


@pytest.mark.parametrize("room,mtype,reason", [("", "water", "bad_room"), ("2 04", "water", "bad_room"),
                                               ("204", "gas", "bad_meter_type"), ("204", None, "bad_meter_type")])
def test_keep_validates_room_and_type(data, room, mtype, reason):
    rec = make(data)
    assert S.decide(rec["local_id"], True, room, mtype) == (False, reason)
    assert S.get_pending(rec["local_id"]) is not None      # ยังค้างอยู่ ไม่หาย


def test_decide_unknown_or_twice(data):
    assert S.decide("ffffffffffff", True, "1", "water") == (False, "not_pending")
    assert S.decide("../../etc", True, "1", "water") == (False, "not_pending")
    rec = make(data)
    assert S.decide(rec["local_id"], True, "1", "water")[0]
    assert S.decide(rec["local_id"], True, "1", "water") == (False, "not_pending")
    assert len(jsonl(data)) == 1


def test_purge_expired_after_7_days_only(data):
    old = make(data, "aaaaaaaaaaaa")
    new = make(data, "bbbbbbbbbbbb")
    later = datetime.now(timezone.utc) + timedelta(days=7, hours=1)
    # new ถูกสร้างตอนนี้เหมือนกัน → ขยับ pending_since ของ new ให้ใหม่กว่า
    S.attach(new["local_id"], pending_since=(later - timedelta(days=1)).isoformat())
    assert S.purge_expired(later) == 1
    assert S.get_pending(old["local_id"]) is None and not (data / "images" / "aaaaaaaaaaaa.jpg").exists()
    assert S.get_pending(new["local_id"]) is not None


def test_purge_cleans_pending_already_in_jsonl(data):
    """ไฟดับหลัง append jsonl แต่ก่อนลบ pending → รอบถัดไปต้องไม่เหลือแถวค้างซ้ำ และไม่ลบรูป"""
    rec = make(data)
    ok, r = S.decide(rec["local_id"], True, "1", "water")
    S.save_pending(dict(rec), JPG)                       # จำลองว่า pending ยังอยู่
    assert S.purge_expired() == 0
    assert S.get_pending(rec["local_id"]) is None and (data / "images" / f"{rec['local_id']}.jpg").exists()
    assert len(jsonl(data)) == 1


def test_sync_counts_and_legacy_rows(data):
    (data / "readings.jsonl").write_text(json.dumps({"local_id": "legacy000001", "value": 1}) + "\nnot json\n", encoding="utf-8")
    a, b = make(data, "aaaaaaaaaaaa"), make(data, "bbbbbbbbbbbb", crop=False)
    S.decide(a["local_id"], True, "1", "water"); S.decide(b["local_id"], True, "1", "electric")
    make(data, "cccccccccccc")
    assert [r["local_id"] for r in S.kept_rows()] == ["aaaaaaaaaaaa", "bbbbbbbbbbbb"]   # แถวเก่าไม่ส่ง · บรรทัดเสียข้าม
    assert S.sync_counts() == {"pending_rows": 2, "pending_crops": 1, "sync_errors": 0, "pending_decisions": 1}
    S.save_sync_state({"aaaaaaaaaaaa": {"row": "t", "crop": "t", "error": None}, "bbbbbbbbbbbb": {"row": None, "crop": None, "error": "x"}})
    assert S.sync_counts() == {"pending_rows": 0, "pending_crops": 0, "sync_errors": 1, "pending_decisions": 1}
