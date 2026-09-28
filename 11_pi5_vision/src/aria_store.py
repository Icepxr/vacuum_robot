"""aria_store.py — รูปรอคนขับตัดสิน (F10) + ทะเบียนมิเตอร์ (meters.json) · design/aria-data-spec-v1.md §2.0

ถ่าย → ภาพต้นฉบับลง images/ (meter_reader.save_image) → OCR → crop ลง crops/ + แถวลง pending/<local_id>.json
คนขับกดในป๊อปอัพบน /drive:
    "เก็บ"   → แถว append เข้า readings.jsonl (พร้อม room_id/meter_type/meter_id) → รอ sync ขึ้นคลาวด์
    "ไม่เอา" → ลบภาพต้นฉบับ + crop + pending ทันที
    ไม่ได้กด → ค้างใน pending/ ไม่ sync · กดย้อนหลังได้ · ครบ 7 วันลบเอง (purge_expired)
ไม่ import cv2 — ผู้เรียกส่ง crop มาเป็น bytes ของ JPEG แล้ว (ทดสอบบนโน้ตบุ๊กได้โดยไม่ต้องมี OpenCV)
"""
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("MRC_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DEVICE_ID = os.environ.get("MRC_DEVICE_ID", "MRC-001")
PENDING_TTL = timedelta(days=7)          # F10: ไม่ได้กด = เก็บบน Pi 7 วัน
METER_TYPES = ("water", "electric")
ROOM_RE = re.compile(r"^[A-Za-z0-9]{1,10}$")   # ตรงกับ check ของ rooms.room_id บนคลาวด์
LOCAL_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def _dirs():
    # อ่านจาก DATA_DIR ตอนเรียก (เทสต์ monkeypatch ได้)
    return DATA_DIR / "pending", DATA_DIR / "crops", DATA_DIR / "images", DATA_DIR / "readings.jsonl", DATA_DIR / "meters.json"


def _fsync_dir(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_atomic(path, data: bytes):
    """เขียนผ่านไฟล์ชั่วคราว + fsync ไฟล์และโฟลเดอร์ — ไฟดับกลางคันได้ไฟล์เก่าหรือใหม่ ไม่ได้ไฟล์ครึ่งๆ"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    _fsync_dir(path.parent)


def _now():
    return datetime.now(timezone.utc)


def clock_synced():
    """F1 · นาฬิกาซิงก์แล้วหรือยัง ณ ตอนนี้ · None = ตรวจไม่ได้ (ไม่มี timedatectl เช่นบน Mac)"""
    try:
        out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                             capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return {"yes": True, "no": False}.get(out)


# ── ทะเบียนมิเตอร์ (ARIA export → scp ลง data/meters.json ตอนอยู่แล็บ) ──

def load_registry():
    """คืน dict {"registry_version": int|None, "meters": [...]} · ไม่มีไฟล์/ไฟล์เสีย = ทะเบียนว่าง (ถ่ายต่อได้)"""
    *_, reg_path = _dirs()
    try:
        d = json.loads(reg_path.read_text(encoding="utf-8"))
        meters = [m for m in d.get("meters", []) if isinstance(m, dict) and m.get("meter_id")]
        return {"registry_version": d.get("registry_version"), "meters": meters}
    except (OSError, ValueError):
        return {"registry_version": None, "meters": []}


def resolve_meter(reg, room_id, meter_type):
    """ห้อง + ชนิด → meter_id ตัวที่ติดตั้งอยู่ · หาไม่เจอหรือเจอมากกว่า 1 ตัว = None (ให้ ARIA ผูกทีหลัง ไม่เดา)"""
    hits = [m["meter_id"] for m in reg["meters"] if str(m.get("room")) == room_id and m.get("type") == meter_type]
    return hits[0] if len(hits) == 1 else None


# ── รูปรอตัดสิน ──

def save_pending(rec, crop_jpeg=None):
    """เรียกหลัง OCR เสร็จ · rec มาจาก meter_reader.build_record (ยังไม่ลง readings.jsonl)"""
    pending_dir, crop_dir, *_ = _dirs()
    lid = rec["local_id"]
    rec = dict(rec, device_id=DEVICE_ID, pending_since=_now().isoformat(), crop_path=None)
    if crop_jpeg:
        _write_atomic(crop_dir / f"{lid}.jpg", crop_jpeg)
        rec["crop_path"] = f"crops/{lid}.jpg"
    _write_atomic(pending_dir / f"{lid}.json", json.dumps(rec, ensure_ascii=False).encode("utf-8"))
    return rec


def get_pending(lid):
    pending_dir, *_ = _dirs()
    if not LOCAL_ID_RE.match(lid or ""):
        return None
    try:
        return json.loads((pending_dir / f"{lid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_pending():
    pending_dir, *_ = _dirs()
    out = []
    for p in sorted(pending_dir.glob("*.json")) if pending_dir.exists() else []:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue            # ไฟล์เสียข้ามไป ไม่ทำให้รายการทั้งหมดพัง
    return sorted(out, key=lambda r: r.get("captured_at") or "")


def attach(lid, **fields):
    """เติมข้อมูลที่ได้หลัง OCR (อากาศ ณ เวลาถ่าย, สถานะนาฬิกา) · แถวที่ตัดสินไปแล้วไม่แตะ"""
    pending_dir, *_ = _dirs()
    rec = get_pending(lid)
    if rec is None:
        return None
    rec.update(fields)
    _write_atomic(pending_dir / f"{lid}.json", json.dumps(rec, ensure_ascii=False).encode("utf-8"))
    return rec


def _in_jsonl(lid):
    *_, jsonl, _ = _dirs()
    if not jsonl.exists():
        return False
    needle = f'"local_id": "{lid}"'
    with jsonl.open(encoding="utf-8") as f:
        return any(needle in line for line in f)


def _append_jsonl(rec):
    *_, jsonl, _ = _dirs()
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    with jsonl.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    _fsync_dir(jsonl.parent)


def _delete_files(rec):
    pending_dir, crop_dir, image_dir, *_ = _dirs()
    lid = rec["local_id"]
    img = Path(rec.get("image_path") or "").name
    for p in ([image_dir / img] if img else []) + [crop_dir / f"{lid}.jpg", pending_dir / f"{lid}.json"]:
        p.unlink(missing_ok=True)
    _fsync_dir(pending_dir) if pending_dir.exists() else None


def decide(lid, keep, room_id=None, meter_type=None):
    """คืน (ok, rec|error) · keep=True ต้องมีห้อง+ชนิด (ป๊อปอัพบังคับเลือก)"""
    pending_dir, *_ = _dirs()
    rec = get_pending(lid)
    if rec is None:
        return False, "not_pending"
    if not keep:
        _delete_files(rec)
        return True, {"local_id": lid, "driver_decision": "discarded"}
    room_id = (room_id or "").strip()
    if not ROOM_RE.match(room_id):
        return False, "bad_room"
    if meter_type not in METER_TYPES:
        return False, "bad_meter_type"
    reg = load_registry()
    rec.update(room_id=room_id, meter_type=meter_type, meter_id=resolve_meter(reg, room_id, meter_type),
               registry_version=reg["registry_version"], driver_decision="kept", decided_at=_now().isoformat(),
               synced_at=None, crop_synced_at=None)
    rec.pop("pending_since", None)
    # ลำดับ: เขียน jsonl ก่อน แล้วค่อยลบ pending · ไฟดับตรงกลาง = มีทั้งสองที่ → purge_expired เก็บกวาด (ไม่ append ซ้ำ)
    if not _in_jsonl(lid):
        _append_jsonl(rec)
    (pending_dir / f"{lid}.json").unlink(missing_ok=True)
    _fsync_dir(pending_dir)
    return True, rec


def purge_expired(now=None):
    """ลบรูปที่ค้างตัดสินเกิน 7 วัน + เก็บกวาด pending ที่ลง jsonl ไปแล้ว (ไฟดับระหว่าง decide) · คืนจำนวนที่ลบ"""
    pending_dir, *_ = _dirs()
    now = now or _now()
    n = 0
    for rec in list_pending():
        lid = rec.get("local_id", "")
        if _in_jsonl(lid):
            (pending_dir / f"{lid}.json").unlink(missing_ok=True)
            continue
        try:
            since = datetime.fromisoformat(rec.get("pending_since") or rec["captured_at"])
        except (KeyError, ValueError):
            continue
        if now - since > PENDING_TTL:
            _delete_files(rec)
            n += 1
    return n


# ── สถานะการส่งขึ้นคลาวด์ ──
# แยกจาก readings.jsonl โดยตั้งใจ: jsonl เป็น append-only จริง (เว็บเขียนตอนคนขับกด "เก็บ")
# ถ้า sync เขียนทับ jsonl ทั้งไฟล์เพื่อใส่ synced_at (แบบ sync_supabase.py เดิม) แล้วคนขับกดเก็บพร้อมกัน
# แถวใหม่จะหายตอน replace → เก็บสถานะใน sync_state.json แทน · ผู้เขียนคนเดียวคือ sync_supabase.py

def sync_state_path():
    return DATA_DIR / "sync_state.json"


def load_sync_state():
    """{local_id: {"row": iso|None, "crop": iso|"expired"|None, "error": str|None}}"""
    try:
        d = json.loads(sync_state_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_sync_state(state):
    _write_atomic(sync_state_path(), json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def kept_rows():
    """แถวที่คนขับกด "เก็บ" แล้ว (F10) · แถวเก่าก่อนมีป๊อปอัพ (ไม่มี driver_decision) ไม่ส่งขึ้นคลาวด์ — อยู่บน Pi อย่างเดียว"""
    *_, jsonl, _ = _dirs()
    if not jsonl.exists():
        return []
    out = []
    with jsonl.open(encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue               # บรรทัดเสีย (ไฟดับตอนเขียน) ข้ามไป ไม่ทำให้ทั้งไฟล์ใช้ไม่ได้
            if isinstance(r, dict) and r.get("driver_decision") == "kept" and r.get("local_id"):
                out.append(r)
    return out


def sync_counts():
    st = load_sync_state()
    rows = kept_rows()
    pending_rows = sum(1 for r in rows if not (st.get(r["local_id"]) or {}).get("row") and not (st.get(r["local_id"]) or {}).get("error"))
    pending_crops = sum(1 for r in rows if r.get("crop_path") and not (st.get(r["local_id"]) or {}).get("crop"))
    errors = sum(1 for r in rows if (st.get(r["local_id"]) or {}).get("error"))
    return {"pending_rows": pending_rows, "pending_crops": pending_crops, "sync_errors": errors,
            "pending_decisions": len(list_pending())}
