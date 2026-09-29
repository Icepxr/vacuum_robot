# ARIA — ฝั่งคลาวด์ (Supabase `aria-mrc`)

โปรเจกต์ Supabase **`aria-mrc`** ref `brvlfwrmkoyjnrhvfesq` (ap-southeast-1 · Free) · ⚠ **ห้ามรันอะไรในโปรเจกต์ MCCMU's Project**
สเปกข้อมูลที่ตัดสินแล้ว: [`design/aria-data-spec-v1.md`](../design/aria-data-spec-v1.md)

| ไฟล์ | สถานะ 29 ก.ย. 2026 |
|---|---|
| `supabase/migrations/…0100_core_schema.sql` | apply แล้ว — 11 ตาราง · RLS (anon ทำอะไรไม่ได้ · เจ้าของหอผ่าน `owners`) · trigger ค่ายืนยันห้ามถอยหลัง |
| `supabase/migrations/…0200_ingest.sql` | apply แล้ว — `ingest_readings/heartbeat/crop_attach` (service role เท่านั้น) · bucket `crops` private |
| `supabase/migrations/…0300_demo_seed.sql` | apply แล้ว — ห้อง 101–110 · 20 มิเตอร์ · ผู้เช่าสมมติ (`is_demo`) · ลบด้วย `select public.delete_demo_data();` |
| `supabase/migrations/20260929000100_demo_readings.sql` | apply แล้ว — ค่าที่หุ่นอ่านตัวอย่าง 19 แถวจากอุปกรณ์ `DEMO-01` (revoke แล้ว) · `delete_demo_data()` ลบรวมให้ |
| `web/` | **เว็บหลังบ้าน** (vanilla JS) · **ออนไลน์ที่ https://aria-th.netlify.app** (Netlify Free · base `aria/web`) · ล็อกอิน Google ใช้ได้ 29 ก.ย. — ขั้นตอนตั้งค่าใน [`web/README.md`](web/README.md) |
| `supabase/functions/ingest/index.ts` | deploy แล้ว (verify_jwt = false · ยืนยันตัวด้วย `x-device-token`) |

อุปกรณ์ที่ลงทะเบียน: `MRC-001` (หุ่นจริง) · `TEST-01` (ทดสอบจาก Mac) — token จริงอยู่ที่ `~/.config/mrc/aria_device_token_*` บน Mac ของผู้ใช้ (สิทธิ์ 600) · คลาวด์เก็บแค่ SHA-256

## Auth (ตั้ง 29 ก.ย.)
- Provider เหลือ **Google อย่างเดียว** (Email ปิด · sign-up เปิดไว้ให้ Google สร้าง user ครั้งแรก) · Google OAuth client แยกเฉพาะ ARIA (อยู่ในโปรเจกต์ Google Cloud เดิมของผู้ใช้ · consent screen สถานะ Testing → ต้องเพิ่ม test user ก่อนเพิ่มเจ้าของคนใหม่)
- `owners`: `daiyazwhm@gmail.com` · เพิ่มคน: `insert into public.owners(email) values ('…');` + เพิ่มเป็น test user ใน Google
- Site URL / Redirect `https://aria-th.netlify.app/**`

## ยังไม่ได้ทำ
- บิล/อีเมล (`invoices`, `invoice_delivery_attempts`) — ขั้น 4–5
- งานลบ crop อายุ 12 เดือน (F8) — ครั้งแรกที่ต้องใช้คือ ก.ย. 2027
- มีรูปทดสอบค้างใน bucket `crops/TEST-01/` 4 ไฟล์ (≈ 30 kB) — ลบได้จาก Dashboard › Storage (ลบผ่าน SQL ไม่ได้)

## Deploy ลง Pi (ทำตอน Pi ว่าง · branch `aria-pipeline`)
1. แฟลชไม่ต้อง — ไม่แตะเฟิร์มแวร์/โปรโตคอล UART
2. `scripts/deploy_to_pi.sh` → `sudo systemctl restart mrc-web`
3. token: `sudo install -d -m 700 -o uchida /etc/mrc` แล้ว copy `~/.config/mrc/aria_device_token_MRC-001` ไปเป็น `/etc/mrc/aria_device_token` (chmod 600, owner uchida)
4. `sudo cp ~/mrc/systemd/mrc-sync.{service,timer} /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now mrc-sync.timer`
5. ทะเบียนมิเตอร์: วาง `~/mrc/data/meters.json` (รูปแบบใน สเปก §5) — ไม่มีไฟล์ก็ถ่ายได้ `meter_id` จะเป็น null
6. เช็ค: ถ่ายจาก `/drive` → ป๊อปอัพขึ้น → เก็บ → `python src/sync_supabase.py` → แถวขึ้นตาราง `meter_readings`
