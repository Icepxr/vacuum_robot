#!/usr/bin/env python3
"""
sync_supabase.py — ส่งแถวที่คนขับกด "เก็บ" + รูป crop + สถานะ Pi ขึ้น ARIA ผ่าน Edge Function `ingest`

**แยกจากเว็บ/การถ่ายโดยตั้งใจ** — การถ่ายต้องไม่รอเครือข่าย · เน็ตล้ม = หยุดเงียบๆ ข้อมูลในเครื่องครบ รอบหน้าส่งต่อ
เปลี่ยน 29 ก.ย. 2026 (D6 · design/aria-data-spec-v1.md §3):
  - ไม่ถือ service key / anon key แล้ว — ใช้ token ของอุปกรณ์ (x-device-token) คลาวด์เก็บแค่ SHA-256
  - ส่งเฉพาะแถวที่ driver_decision = "kept" (F10) · แถวเก่าก่อนมีป๊อปอัพอยู่บน Pi อย่างเดียว
  - ไม่เขียนทับ readings.jsonl แล้ว — สถานะการส่งอยู่ใน data/sync_state.json (aria_store) · เหตุผลอยู่ที่ aria_store
  - ส่งแถวก่อน แล้วค่อยส่ง crop (คลาวด์ใช้แถวพิสูจน์ว่า local_id เป็นของอุปกรณ์นี้)

ตั้งค่า (อย่าใส่ token ลงไฟล์ที่ commit):
    ARIA_DEVICE_TOKEN_FILE=/etc/mrc/aria_device_token   (ค่าเริ่ม · สิทธิ์ 600)   หรือ  ARIA_DEVICE_TOKEN=...
    ARIA_INGEST_URL=https://brvlfwrmkoyjnrhvfesq.supabase.co/functions/v1/ingest   (ค่าเริ่ม)

ใช้งาน:
    python sync_supabase.py                 # ส่งที่ค้าง
    python sync_supabase.py --dry-run       # ดูว่าจะส่งอะไร ไม่ส่งจริง
    python sync_supabase.py --retry-errors  # ส่งแถวที่คลาวด์เคยปฏิเสธซ้ำอีกรอบ
"""
import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aria_store as S  # noqa: E402

INGEST_URL = os.environ.get("ARIA_INGEST_URL", "https://brvlfwrmkoyjnrhvfesq.supabase.co/functions/v1/ingest").rstrip("/")
TOKEN_FILE = Path(os.environ.get("ARIA_DEVICE_TOKEN_FILE", "/etc/mrc/aria_device_token"))
LOCAL_STATUS_URL = os.environ.get("MRC_STATUS_URL", "http://127.0.0.1:8000/api/status")
TIMEOUT = 15
BATCH = 50
# ต้องตรงกับ whitelist ใน public.ingest_readings (aria/supabase/migrations/…_ingest.sql)
ROW_FIELDS = ("local_id", "captured_at", "decided_at", "run_id", "room_id", "meter_type", "raw_text", "value",
              "confidence", "image_path", "source", "meter_id", "registry_version", "clock_synced", "ocr_engine", "air")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def token():
    t = os.environ.get("ARIA_DEVICE_TOKEN", "").strip()
    if t:
        return t
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def http(method, path, tok, body=None, ctype="application/json"):
    """คืน (status, dict) · เครือข่ายล้ม = (None, {"error": ...})"""
    data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
    req = urllib.request.Request(INGEST_URL + path, data=data, method=method,
                                 headers={"x-device-token": tok, "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return None, {"error": str(e)}


def local_status():
    """สถานะจากเว็บบน Pi (กล้อง/อากาศ/อุณหภูมิ/รหัสเตือน) · เว็บไม่รัน = ไม่มีค่าพวกนี้ ไม่ใช่ error"""
    try:
        with urllib.request.urlopen(LOCAL_STATUS_URL, timeout=2) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError):
        return {}


def heartbeat(counts):
    st = local_status()
    air = st.get("air") or {}
    try:
        disk = shutil.disk_usage(S.DATA_DIR if S.DATA_DIR.exists() else Path("/")).free // 2**20
    except OSError:
        disk = None
    return {"pending_rows": counts["pending_rows"], "pending_crops": counts["pending_crops"],
            "pending_decisions": counts["pending_decisions"], "app_version": os.environ.get("MRC_APP_VERSION"),
            "disk_free_mb": disk, "clock_synced": S.clock_synced(), "warn": st.get("warn"),
            "cam_ok": st.get("cam_ok"), "air_available": air.get("available") if air else None,
            "cpu_temp_c": st.get("cpu_temp_c")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--retry-errors", action="store_true")
    args = ap.parse_args()

    state = S.load_sync_state()
    rows = S.kept_rows()
    ent = lambda lid: state.setdefault(lid, {"row": None, "crop": None, "error": None})   # noqa: E731
    todo = [r for r in rows if not (state.get(r["local_id"]) or {}).get("row")
            and (args.retry_errors or not (state.get(r["local_id"]) or {}).get("error"))]
    print(f"แถวที่เก็บแล้ว {len(rows)} · รอส่ง {len(todo)} · รอตัดสินบน Pi {len(S.list_pending())}")

    if args.dry_run:
        for r in todo[:10]:
            print(f"  {r.get('captured_at')}  ห้อง {r.get('room_id')} {r.get('meter_type')}  value={r.get('value')}")
        return 0

    tok = token()
    if not tok:
        print(f"ไม่มี token ของอุปกรณ์ — ตั้ง ARIA_DEVICE_TOKEN หรือวางไฟล์ที่ {TOKEN_FILE}", file=sys.stderr)
        return 2

    # 1) แถว (ส่ง heartbeat ไปกับชุดแรก · ไม่มีแถวก็ส่ง heartbeat อย่างเดียว ให้ ARIA รู้ว่า Pi ยังอยู่)
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)] or [[]]
    sent = 0
    for n, chunk in enumerate(batches):
        body = {"rows": [{k: r.get(k) for k in ROW_FIELDS} for r in chunk]}
        if n == 0:
            body["heartbeat"] = heartbeat(S.sync_counts())
        code, resp = http("POST", "/readings", tok, body)
        if code != 200:
            print(f"  ส่งแถวไม่สำเร็จ ({code}): {resp.get('error', resp)} — หยุดไว้ก่อน ข้อมูลในเครื่องครบ")
            S.save_sync_state(state)
            return 1
        t = now_iso()
        for lid in resp.get("accepted", []):
            ent(lid).update(row=t, error=None)
        for rej in resp.get("rejected", []):
            if rej.get("local_id"):
                ent(rej["local_id"])["error"] = str(rej.get("reason"))[:300]
                print(f"  คลาวด์ปฏิเสธ {rej.get('local_id')}: {rej.get('reason')}")
        sent += len(resp.get("accepted", []))
        S.save_sync_state(state)      # บันทึกทุกชุด — ตายกลางคันเสียแค่ชุดเดียว (ส่งซ้ำก็เป็น no-op ฝั่งคลาวด์)

    # 2) crop ของแถวที่ขึ้นแล้ว
    crops = 0
    for r in rows:
        e = state.get(r["local_id"]) or {}
        if not e.get("row") or e.get("crop") or not r.get("crop_path"):
            continue
        p = S.DATA_DIR / r["crop_path"]
        if not p.is_file():
            continue                   # crop หาย (ลบมือ?) — แถวยังใช้ได้ ARIA โชว์ "ไม่มีรูป"
        code, resp = http("PUT", f"/crops/{r['local_id']}", tok, p.read_bytes(), "image/jpeg")
        if code == 200:
            ent(r["local_id"])["crop"] = now_iso(); crops += 1
        elif code == 410:
            ent(r["local_id"])["crop"] = "expired"     # F8 คลาวด์ลบรูปอายุเกิน 12 เดือนแล้ว ไม่ต้องส่งซ้ำ
        elif code is None:
            print(f"  ส่ง crop ไม่สำเร็จ (เครือข่าย): {resp.get('error')} — รอบหน้าส่งต่อ")
            break
        else:
            print(f"  crop {r['local_id']} ได้ {code}: {resp.get('error', resp)}")
        S.save_sync_state(state)

    S.save_sync_state(state)
    print(f"เสร็จ — แถว {sent} · crop {crops}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
