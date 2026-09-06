#!/usr/bin/env python3
"""
sync_supabase.py — ส่งค่าที่อ่านไว้ในเครื่องขึ้น Supabase

**แยกจาก meter_reader.py โดยตั้งใจ** — การอ่านมิเตอร์ต้องไม่รอเครือข่าย
ถ้าเน็ตหลุด สคริปต์นี้ล้มเหลวได้โดยไม่กระทบภารกิจ แล้วค่อยรันใหม่ทีหลัง

ตั้งค่าผ่านตัวแปรสภาพแวดล้อม (อย่าใส่คีย์ลงในไฟล์ที่ commit):
    export SUPABASE_URL="https://<ref>.supabase.co"
    export SUPABASE_KEY="<anon or service key>"

ใช้งาน:
    python sync_supabase.py            # ส่งเฉพาะที่ยังไม่ได้ส่ง
    python sync_supabase.py --dry-run  # ดูว่าจะส่งอะไรบ้าง ไม่ส่งจริง
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA_DIR = Path(os.environ.get("MRC_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
JSONL_PATH = DATA_DIR / "readings.jsonl"
TABLE = "meter_readings"
TIMEOUT = 10
BATCH = 50


def load_records():
    """คืน (records, bad_lines) — บรรทัดที่ parse ไม่ได้ต้องเก็บไว้เขียนกลับ
    ไม่งั้น rewrite() จะลบมันทิ้งถาวร ทั้งที่อาจกู้ด้วยมือได้"""
    if not JSONL_PATH.exists():
        return [], []
    out, bad = [], []
    for i, line in enumerate(JSONL_PATH.read_text(encoding="utf-8").splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            out.append((i, json.loads(stripped)))
        except json.JSONDecodeError:
            print(f"  บรรทัดที่ {i+1} JSON เสีย — เก็บไว้ไม่ลบทิ้ง", file=sys.stderr)
            bad.append(line)
    return out, bad


def rewrite(records, bad_lines=()):
    """เขียนไฟล์ใหม่ทั้งไฟล์ผ่านไฟล์ชั่วคราว กันไฟดับกลางคันแล้วไฟล์พัง"""
    tmp = JSONL_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for _, r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for line in bad_lines:        # บรรทัดที่ parse ไม่ได้ ต้องอยู่ต่อ ไม่ใช่หายไป
            f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(JSONL_PATH)
    # os.replace เป็น atomic แต่ตัว rename ยังค้างใน directory cache
    # ถ้าไฟดับตรงนี้อาจได้ไฟล์เก่ากลับมา = เสีย synced_at ทั้งชุด = ส่งซ้ำ
    fd = os.open(str(JSONL_PATH.parent), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not args.dry_run and (not url or not key):
        sys.exit("ต้องตั้ง SUPABASE_URL และ SUPABASE_KEY ก่อน")

    records, bad_lines = load_records()
    pending = [(i, r) for i, r in records if not r.get("synced_at")]
    print(f"ทั้งหมด {len(records)} รายการ · ยังไม่ได้ส่ง {len(pending)} รายการ")
    if not pending:
        return

    if args.dry_run:
        for _, r in pending[:10]:
            print(f"  {r.get('captured_at')}  value={r.get('value')}  raw={r.get('raw_text')!r}")
        if len(pending) > 10:
            print(f"  ... และอีก {len(pending)-10} รายการ")
        return

    # 🔴 ต้องเป็น upsert ไม่ใช่ insert ธรรมดา
    # local_id เป็น unique — ถ้าส่งซ้ำด้วย insert PostgREST จะมองทั้ง array เป็น
    # INSERT statement เดียว → duplicate key ทำให้ rollback ทั้ง batch รวมรายการใหม่
    # ที่ยังไม่เคยส่งด้วย → ได้ 409 → break → ทุกรอบต่อจากนี้ค้างที่เดิมถาวร
    # และการส่งซ้ำเกิดได้ง่ายมาก: กด Ctrl-C, ไฟดับ, หรือ response หายกลางทาง
    # หลังเซิร์ฟเวอร์บันทึกไปแล้ว (ซึ่งเกิดแน่ในสนามแข่ง)
    # ด้วย merge-duplicates การส่งซ้ำกลายเป็น no-op — ระบบกู้ตัวเองได้
    endpoint = f"{url}/rest/v1/{TABLE}?on_conflict=local_id"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }

    sent = 0
    for start in range(0, len(pending), BATCH):
        chunk = pending[start:start + BATCH]
        payload = [{
            "local_id":    r["local_id"],
            "captured_at": r["captured_at"],
            "run_id":      r.get("run_id"),
            "meter_type":  r.get("meter_type"),
            "raw_text":    r.get("raw_text"),
            "value":       r.get("value"),
            "confidence":  r.get("confidence"),
            "image_path":  r.get("image_path"),
        } for _, r in chunk]
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=TIMEOUT)
        except requests.RequestException as e:
            print(f"  ส่งไม่สำเร็จ (เครือข่าย): {e} — หยุดไว้ก่อน ข้อมูลในเครื่องยังครบ")
            break
        if resp.status_code not in (200, 201, 204):
            print(f"  เซิร์ฟเวอร์ตอบ {resp.status_code}: {resp.text[:300]}")
            print("  หยุดไว้ก่อน ข้อมูลในเครื่องยังครบ ไม่มีอะไรหาย")
            break
        now = datetime.now(timezone.utc).isoformat()
        for _, r in chunk:
            r["synced_at"] = now
        sent += len(chunk)
        # บันทึกทุก chunk ไม่ใช่รอตอนจบ — ถ้าโปรเซสตายกลางคัน หน้าต่างความเสียหาย
        # จะเหลือแค่ 1 chunk (50 แถว) แทนที่จะเป็นทั้งไฟล์
        rewrite(records, bad_lines)
        print(f"  ส่งแล้ว {sent}/{len(pending)}")

    rewrite(records, bad_lines)   # เผื่อกรณี break ออกมาก่อนส่งได้สักรายการ
    print(f"เสร็จ — ส่งสำเร็จ {sent} รายการ · เหลือ {len(pending)-sent} รายการไว้รอบหน้า")


if __name__ == "__main__":
    main()
