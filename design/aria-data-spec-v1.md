# ARIA — สเปกข้อมูลที่จะเก็บ v1

**สร้าง 27 ก.ย. 2569 · ผู้ใช้ตัดสิน F1–F10 วันที่ 28 ก.ย. 2569 (§8)** · ต่อจาก [`aria-backoffice-v1.md`](aria-backoffice-v1.md) §5 และ [`data_flow_หุ่นถึงแดชบอร์ด.md`](../01_เอกสารโครงการ/data_flow_หุ่นถึงแดชบอร์ด.md) · **สถานะ 29 ก.ย.: ตาราง + Edge Function `ingest` ขึ้น `aria-mrc` แล้ว (ทดสอบปลายทางผ่าน) · โค้ดฝั่ง Pi อยู่ branch `aria-pipeline` ยังไม่ deploy ลง Pi** — ดู [`aria/README.md`](../aria/README.md)

ป้ายในเอกสาร: **[มีแล้ว]** = มีในโค้ดวันนี้ · **[ต้องเพิ่ม]** = ออกแบบแล้ว ยังไม่เขียน · **[รอไฟนอล]** = ต้องให้ผู้ใช้เลือก (รวมไว้ที่ §8)

การตัดสินที่เอกสารนี้ยึดตาม (ไม่เปิดใหม่):
- แยก 2 แอป schema เดียว · Pi ควบคุม/ถ่าย · ARIA บนคลาวด์ (C23 · 15 ก.ย.)
- **D6 ตัดสิน 27 ก.ย.:** Pi ส่งผ่าน **Edge Function `ingest` + token ต่ออุปกรณ์** — Pi ไม่ถือ service key
- ARIA ต่อจากต้นแบบ vanilla JS (`design/aria-prototype/`) + supabase-js (27 ก.ย.) · **ฐานหน้าตา = ธีม ARIA Orbit** (`theme.css` แยกชั้นจาก `styles.css`) ที่ผู้ใช้ push 27 ก.ย. บน branch `codex/aria-drive-ui` — ยังไม่ merge เข้า `main`
- จอกลม GC9A01 แบบวงแหวนขอบนอก (`design/ARIA-DISPLAY.md` บน branch เดียวกัน) อ่านทุกอย่างจากเฟรม `$D` เดิม · **สเปกนี้ไม่แตะ `$D` หรือโปรโตคอล UART**
- ลำดับงาน: ท่อ Pi → คลาวด์ก่อน แล้วค่อยทำเว็บ (แบบ v1 §7 · 27 ก.ย.)
- Supabase โปรเจกต์ **`aria-mrc`** (ref `brvlfwrmkoyjnrhvfesq` · ap-southeast-1 · Free $0) สร้าง 27 ก.ย. **ยังว่าง** — แยกจาก MCCMU's Project

---

## 1. ภาพรวม: ข้อมูลอยู่ที่ไหน ใครเป็นเจ้าของ

| ที่เก็บ | เจ้าของ (ผู้เขียน) | เก็บอะไร | ขึ้นคลาวด์ไหม |
|---|---|---|---|
| Pi `data/images/*.jpg` | Pi | ภาพต้นฉบับ 1080p ที่ถ่าย | **ไม่** (ตัดสินแล้ว ไฟล์ 20 §20.2b) |
| Pi `data/crops/*.jpg` | Pi | ภาพ crop หน้าปัด ย่อแล้ว | ขึ้น → Storage `crops` |
| Pi `data/readings.jsonl` | Pi | 1 แถว / 1 ครั้งที่ถ่าย | ขึ้น → `meter_readings` |
| Pi `data/meters.json` | ARIA (copy ลงมาเอง) | ทะเบียนมิเตอร์ให้ dropdown บน `/drive` | เป็นขาลง ไม่ใช่ขาขึ้น |
| Supabase Postgres | แยกตามตาราง §4 | ข้อมูลธุรกิจทั้งหมด + สำเนา reading | — |
| Supabase Storage `crops` (private) | Edge Function เท่านั้น | crop ต่อ `local_id` | — |

**กติกาเดียวที่ห้ามพัง:** หุ่นเขียนได้เฉพาะ "สิ่งที่มันเห็น" · คนเขียน "สิ่งที่ยืนยัน" · ไม่มีช่องไหนที่ทั้งสองฝ่ายเขียนทับกันได้

---

## 2. แถว reading บน Pi (`readings.jsonl`)

### 2.0 ขั้นตอนถ่าย → คนขับตัดสิน (ตัดสิน 28 ก.ย. · F10) [ต้องเพิ่ม]

```
กดถ่าย → ภาพต้นฉบับลง SD + fsync → $K ให้ ESP32 (โปรโตคอลเดิม ไม่แก้)
       → OCR + crop → เขียนลง data/pending/<local_id>.json + fsync       ← ยังไม่อยู่ใน readings.jsonl
       → ป๊อปอัพบน /drive: รูป crop · ค่า OCR · เลือกเลขห้อง · เลือกชนิด (น้ำ/ไฟ)
            ├─ "เก็บ"    → append readings.jsonl (driver_decision = kept) → รอ sync ขึ้นคลาวด์
            ├─ "ไม่เอา"  → ลบภาพต้นฉบับ + crop + pending ทันที · ไม่มีอะไรขึ้นคลาวด์
            └─ ไม่ได้กด (ปิดแอป/เน็ตหลุด/ไฟดับ) → ค้างใน pending/ · ไม่ sync
                           → เปิด /drive ใหม่ขึ้นรายการ "ค้างตัดสิน" ให้กดย้อนหลังได้
                           → ครบ 7 วันลบเอง
```

- **ห้อง + ชนิด ผู้ขับเลือกในป๊อปอัพ ขณะเห็นรูป** → Pi แปลงเป็น `meter_id` จาก `meters.json` (มิเตอร์ที่ติดตั้งอยู่ของห้อง+ชนิดนั้น) · ถ้าหาไม่เจอ (ไม่มีทะเบียน/ห้องไม่อยู่ในทะเบียน) ยังเก็บได้ `meter_id = null` แต่มี `room_id` + `meter_type` ให้ ARIA ผูกทีหลัง
- ค่าที่เลือกล่าสุดเป็นค่าเริ่มของป๊อปอัพถัดไป (เดินห้องเดิมต่อ = กดเก็บได้ทันที)
- **แทน** กติกาเดิมในแบบ v1 §4.2 ที่ให้ตรึง `meter_id` จาก dropdown ณ เวลารับคำสั่งถ่าย — ตอนนี้คนขับเลือกเองโดยเห็นรูปอยู่ตรงหน้า ความเสี่ยง "รูปห้อง 205 ติดชื่อ 204" จึงย้ายจากความผิดพลาดที่มองไม่เห็นมาเป็นการตัดสินใจที่เห็นหลักฐาน
- ลบ `retake_of` ออกจากแบบ — การถ่ายใหม่ = กด "ไม่เอา" แล้วถ่ายอีกครั้ง แถวที่ถูกทิ้งไม่มีอยู่ให้ชี้ถึง
- **ข้อแลก (ผู้ใช้เลือกแล้ว):** รูปที่กด "ไม่เอา" ถูกลบ → ไม่มีตัวอย่างรูปที่ OCR อ่านพลาดไว้จูนทีหลัง

หนึ่งบรรทัดใน `readings.jsonl` = หนึ่งรูปที่คนขับกด "เก็บ" · append-only · fsync ทุกบรรทัด [มีแล้ว]

| ฟิลด์ | ชนิด | สถานะ | ความหมาย / กติกา |
|---|---|---|---|
| `local_id` | text 12 hex | [มีแล้ว] | คีย์กันซ้ำตลอดเส้นทาง Pi → คลาวด์ |
| `captured_at` | ISO-8601 UTC | [มีแล้ว] | เวลานาฬิกา Pi ตอนเซฟภาพ · **ใช้ตัดสินว่าค่านี้เป็นของรอบบิลเดือนไหน** (§4.2 `billing_cycles`) |
| `run_id` | text / null | [มีแล้ว] | รอบวิ่ง |
| `meter_type` | `water` / `electric` | [มีแล้ว · เปลี่ยนที่มา] | คนขับเลือกในป๊อปอัพ (เดิมมาจาก flag `--meter-type` ค่าเดียวทั้งรอบ) |
| `room_id` | text | [ต้องเพิ่ม] | คนขับเลือกในป๊อปอัพ |
| `raw_text` | text | [มีแล้ว] | ข้อความดิบจาก OCR |
| `value` | number / null | [มีแล้ว] | ค่าที่ OCR อ่านได้ · `null` = อ่านไม่ออก (ไม่ใช่ 0) · ห้ามแก้ |
| `confidence` | 0–1 | [มีแล้ว] | |
| `image_path` | text | [มีแล้ว] | `images/<ไฟล์>.jpg` — path บน Pi ไม่ใช่ URL |
| `source` | text | [มีแล้ว] | `usb` / `image-stub` |
| `synced_at` | ISO / null | [มีแล้ว] | ฝั่ง Pi ใช้เอง · **ไม่ส่งขึ้น** |
| `meter_id` | text / null | [มีแล้ว แต่ null ทุกแถว → ต้องเพิ่มการใส่ค่า] | Pi แปลงจาก `room_id` + `meter_type` ด้วย `meters.json` ตอนคนขับกด "เก็บ" · หาไม่เจอ = `null` |
| `driver_decision` | `kept` | [ต้องเพิ่ม] | มีค่าเดียวใน jsonl เพราะแถวที่ไม่เก็บไม่ถูกเขียน · เก็บไว้ให้ชัดว่าผ่านการตัดสินของคนขับ |
| `decided_at` | ISO / | [ต้องเพิ่ม] | เวลาที่กด "เก็บ" · ถ้ากดย้อนหลังจากรายการค้าง จะห่างจาก `captured_at` ได้หลายวัน |
| `status` | `ocr` | [มีแล้ว] | หุ่นใส่ `ocr` เสมอ · **ไม่ส่งขึ้น** (§3) |
| `confirmed_value` | null | [มีแล้ว] | หุ่นใส่ `null` เสมอ · **ไม่ส่งขึ้น** |
| `crop_path` | text / null | [ต้องเพิ่ม] | `crops/<local_id>.jpg` · สร้างใน thread OCR |
| `registry_version` | int / null | [ต้องเพิ่ม] | เลขรุ่นของ `meters.json` ที่ใช้ตอนถ่าย |
| `device_id` | text | [ต้องเพิ่ม] | `MRC-001` |
| `clock_synced` | bool / null | [ต้องเพิ่ม · ตัดสิน F1] | Pi ซิงก์เวลาแล้วหรือยัง ณ ตอนถ่าย (`timedatectl show -p NTPSynchronized`) · ARIA ใช้ติดป้าย "เวลาจาก Pi ยังไม่ยืนยัน" (แบบ v1 §8 D5) |
| `ocr_engine` | text | [ต้องเพิ่ม] | `sevenseg` / `tesseract` / … · ต้องรู้ตอนย้อนดูว่าค่าไหนอ่านด้วยวิธีไหน |
| `air` | object / null | [ต้องเพิ่ม · ตัดสิน F3 = ขึ้นคลาวด์] | `{eco2_ppm, tvoc_ppb, aqi, temp_c, rh_pct, validity}` ณ เวลาถ่าย · วันนี้มีแค่ใน event ของ WebSocket ([mrc_web.py:168](../11_pi5_vision/src/mrc_web.py:168)) ไม่ลงไฟล์ · `null` เมื่อไม่มีเซนเซอร์ (`NOAIR`) · **ต้องเก็บ `validity` ด้วย** ไม่งั้นค่าช่วง warm-up ดูเหมือนปกติ |

**ตั้งใจไม่เก็บ (F2 · 28 ก.ย.):** ค่ากล้อง `zoom/pan/tilt/focus` ตอนถ่าย · ผลที่ยอมรับ: ถ้าต้องรัน OCR ซ้ำจากภาพต้นฉบับ จะไม่รู้ว่าถ่ายด้วยซูมเท่าไร

---

## 3. สัญญาการส่งขึ้น: Pi → Edge Function `ingest` [ต้องเพิ่ม]

แทนการ POST เข้า PostgREST ตรงของ `sync_supabase.py` วันนี้ · ตรรกะเดิมที่ดีอยู่แล้วเก็บไว้ทั้งหมด: ส่งเฉพาะแถว `synced_at` ว่าง · batch · เขียน `synced_at` ทุก chunk · เน็ตล้ม = หยุด ข้อมูลในเครื่องครบ

**ยืนยันตัวตน:** header `Authorization: Bearer <device token>` · token สุ่ม 32 ไบต์ อยู่ใน env ของ Pi (ไม่ commit) · ฝั่งคลาวด์เก็บเฉพาะ **SHA-256 ของ token** ในตาราง `devices` · ยกเลิกได้ด้วย `revoked_at`

**สองคำสั่ง:**

| คำสั่ง | ส่งอะไร | ฟังก์ชันทำอะไร |
|---|---|---|
| `POST /ingest/readings` | array ≤ 50 แถว (เฉพาะฟิลด์ที่อนุญาต ↓) + `heartbeat` | upsert บน `local_id` แบบ **ไม่แตะ** คอลัมน์ฝั่งคน · อัปเดต `devices.last_seen_at` + ตัวนับค้าง · ตอบรายชื่อ `local_id` ที่รับแล้ว |
| `PUT /ingest/crops/<local_id>` | JPEG ≤ 200 kB [ประมาณการ — ขอบเขตจริงต้องเทียบขนาด crop ที่วัดได้ ไฟล์ 20 §20.6] | เช็คว่า `local_id` เป็นของอุปกรณ์นี้ → เขียน `crops/<device_id>/<local_id>.jpg` → เติม `crop_path` |

**ฟิลด์ที่ Pi ส่งได้ (whitelist):** `local_id` `captured_at` `decided_at` `run_id` `room_id` `meter_type` `raw_text` `value` `confidence` `image_path` `source` `meter_id` `crop_path` `registry_version` `clock_synced` `ocr_engine` `air` · Pi **ส่งเฉพาะแถวใน `readings.jsonl`** (= กด "เก็บ" แล้ว) · ไม่มีช่องทางส่งแถวใน `pending/`

**ฟิลด์ที่ฟังก์ชันใส่เอง:** `device_id` (จาก token ไม่ใช่จาก payload — กันอุปกรณ์หนึ่งแอบอ้างเป็นอีกตัว) · `received_at = now()`

**ปฏิเสธทั้งแถว (ไม่ใช่ทั้ง batch):** ไม่มี `local_id`/`captured_at` · มีฟิลด์นอก whitelist · `meter_type` นอก `water/electric` · ตอบกลับเป็นรายการแถวที่ถูกปฏิเสธพร้อมเหตุผล → Pi ทำเครื่องหมาย `sync_error` ไว้ ไม่ส่งวนซ้ำไม่รู้จบ

**`heartbeat` ที่แนบมากับทุกครั้งที่ส่ง** → ใช้ทำแผง "จากหุ่น" ในหน้าหลัก (แบบ v1 §4.1) และการ์ด `MRC-001` ใน sidebar ของธีม Orbit: `pending_rows` · `pending_crops` · `app_version` · `disk_free_mb` · `clock_synced` · `pending_decisions` (จำนวนรูปค้างตัดสินบน Pi) · `warn` · `cam_ok` · `air_available` · `cpu_temp_c`

`warn` คือรหัสเดียวกับที่ Pi ส่งให้จอกลมทาง `$D` (`display_warn()` ใน [mrc_web.py:105](../11_pi5_vision/src/mrc_web.py:105): `NOIP` > `HOT` > `NOCAM` > `DISK` > `NOAIR`) เพื่อให้หุ่นกับ ARIA พูดคำเดียวกัน · **แต่ส่งค่ารายระบบแยกด้วย** (`cam_ok` `air_available` `disk_free_mb` `cpu_temp_c`) เพราะ `warn` เป็นรหัสเดียวตามลำดับความสำคัญ ถ้า `DISK` กับ `NOAIR` เกิดพร้อมกัน `warn` จะโชว์แค่ `DISK` (ข้อจำกัดเดียวกับที่ `ARIA-DISPLAY.md` §Icon truthfulness เขียนไว้) · จอกลมมีพื้นที่แค่รหัสเดียว แต่คลาวด์ไม่มีข้อจำกัดนั้น

---

## 4. ตารางบนคลาวด์ (Postgres ใน `aria-mrc`) [ต้องเพิ่มทั้งหมด]

ผู้เขียน: **ingest** = Edge Function ด้วย service role ภายในฟังก์ชัน · **owner** = ผู้ให้เช่าที่ล็อกอิน (ผ่าน RLS) · **trigger** = ฐานข้อมูลคำนวณเอง

### 4.1 ฝั่งหุ่น

**`devices`** — ingest อ่าน · owner ดู

| คอลัมน์ | ชนิด | หมายเหตุ |
|---|---|---|
| `device_id` | text PK | `MRC-001` |
| `token_sha256` | text not null | ไม่เก็บ token จริง |
| `revoked_at` | timestamptz | ไม่ null = ปฏิเสธทุกคำขอ |
| `last_seen_at` `pending_rows` `pending_crops` `app_version` `disk_free_mb` `clock_synced` `warn` `cam_ok` `air_available` `cpu_temp_c` | | จาก heartbeat ล่าสุด · **ป้ายบน UI ต้องเป็น "ข้อมูลล่าสุดเมื่อ …" ไม่ใช่ "ออนไลน์"** — หลักเดียวกับจอกลมที่ห้ามอ้างว่าพร้อมเมื่อข้อมูลเก่า |

**`meter_readings`** — ingest เขียน · owner อ่านอย่างเดียว

| คอลัมน์ | ชนิด | หมายเหตุ |
|---|---|---|
| `id` | bigint identity PK | |
| `local_id` | text **unique not null** | (คอมเมนต์เดิมใน `schema.sql` เรื่อง NULL ซ้ำยังใช้ได้) |
| `device_id` | text FK → devices | |
| `captured_at` | timestamptz not null | เวลา Pi |
| `received_at` | timestamptz not null default now() | เวลาเซิร์ฟเวอร์ — เวลาที่สองเผื่อนาฬิกา Pi เพี้ยน |
| `clock_synced` | boolean | |
| `decided_at` | timestamptz | เวลาที่คนขับกด "เก็บ" |
| `room_id` | text | ที่คนขับเลือก · ไม่บังคับ FK (ห้องอาจยังไม่อยู่ในทะเบียน) |
| `run_id` `meter_type` `raw_text` `source` `ocr_engine` | text | `meter_type` check in (`water`,`electric`) |
| `value` | numeric | null = อ่านไม่ออก |
| `confidence` | real | |
| `meter_id` | text FK → meters · **nullable** | null = เข้าคิว "ยังไม่ผูก" |
| `registry_version` | int | |
| `image_path` | text | path บน Pi |
| `crop_path` | text | null + `crop_expired_at` null = "รูปกำลังซิงก์" · null + มีวันที่ = "รูปหมดอายุ" |
| `crop_expired_at` | timestamptz | งานลบรูปอายุ 12 เดือนใส่ (F8) |
| `air` | jsonb | ตัดสิน F3 · ขนาด ≈ 120 B/แถว [ประมาณการ — ไฟล์ 20 §20.8] |
| `status` | text default `ocr` | **cache** ของ event ล่าสุด · trigger เขียน · ไม่มีใครเขียนตรง |
| `confirmed_value` | numeric | **cache** เหมือนกัน |
| `assigned_meter_id` | text | **cache** ผูกมิเตอร์ทีหลัง (event `assigned`) · แยกจาก `meter_id` ที่หุ่นส่ง เพื่อไม่เขียนทับข้อเท็จจริงจากหุ่น |

**`reading_events`** — owner insert อย่างเดียว · ห้าม update/delete (บังคับด้วย RLS + ไม่มี policy แก้)

| คอลัมน์ | ชนิด | หมายเหตุ |
|---|---|---|
| `id` | bigint identity PK | |
| `reading_id` | FK → meter_readings | |
| `event` | text check in (`confirmed`,`corrected`,`rejected`,`assigned`) | |
| `confirmed_value` | numeric | จำเป็นเมื่อ `confirmed`/`corrected` |
| `meter_id` | text | จำเป็นเมื่อ `assigned` |
| `reason` | text | **จำเป็น**เมื่อ `corrected` หรือค่าผิดปกติ (แบบ v1 §4.2) |
| `actor` | uuid → auth.users | ใส่จาก `auth.uid()` ไม่รับจาก client |
| `at` | timestamptz default now() | |

กติกาที่บังคับในฐานข้อมูล (ไม่ใช่แค่ UI): `confirmed_value` ต้อง ≥ ค่ายืนยันล่าสุดของ **มิเตอร์ตัวเดียวกัน** (ยกเว้นแถวแรกหลังติดตั้ง ใช้ `meters.start_value` เป็นฐาน)

### 4.2 ฝั่งธุรกิจ (owner เขียนผ่าน ARIA)

| ตาราง | คอลัมน์หลัก | กติกา |
|---|---|---|
| `rooms` | `room_id` text PK (`204`) · `floor` · `note` | ห้องว่างยังมีมิเตอร์และ reading ได้ |
| `tenancies` | `id` · `room_id` · `tenant_name` · `email` (nullable) · `start_date` · `end_date` · `rent_baht` (nullable) · **ไม่มีเบอร์โทร (F5)** | ช่วงของห้องเดียวกันห้ามซ้อน · ผู้เช่าเก่าอยู่ในประวัติ · ไม่มีอีเมล = ดูบิลได้ ส่งไม่ได้ |
| `meters` | `meter_id` PK (`W-204-01`) · `room_id` · `type` · `digits` · `decimals` · `installed_at` · `retired_at` · `start_value` · `end_value` · `waypoint` · `lift_mm` | เปลี่ยนตัว = ID ใหม่ (`-02`) · ช่วงติดตั้งของห้อง+ชนิดเดียวกันห้ามซ้อน |
| `meter_registry_exports` | `version` · `exported_at` · `by` | ทุกครั้งที่ export `meters.json` ให้ Pi = 1 แถว · เอาไว้เทียบกับ `registry_version` ของ reading |
| `rates` | `id` · `type` · `baht_per_unit` numeric(10,2) · `effective_from` date | append-only · เปลี่ยนอัตรา = แถวใหม่ |
| `billing_cycles` | `cycle` (`2026-09`) PK · `cutoff_date` · `state` (`open`/`closed`) · `include_rent` bool default false | หนึ่งรอบต่ออาคาร · **reading อยู่รอบไหน = `captured_at` (เวลาไทย) อยู่หลัง `cutoff_date` ของรอบก่อน และไม่เกิน `cutoff_date` ของรอบนี้** · แถวที่ `clock_synced = false` ติดป้ายให้เจ้าของตรวจว่าเข้ารอบถูก (F1) |
| `invoices` | `id` · `cycle` · `room_id` · `revision` · `tenancy_id` · `state` (`draft`/`approved`/`superseded`) · **snapshot:** `water_prev` `water_curr` `water_units` `water_rate` `electric_prev` `electric_curr` `electric_units` `electric_rate` `rent_baht` `total_baht` `recipient_email` · `approved_by` · `approved_at` | unique (`cycle`,`room_id`,`revision`) · แถวที่ `approved` ห้ามแก้ — แก้ = revision ใหม่ + ของเดิมเป็น `superseded` |
| `invoice_delivery_attempts` | `id` · `invoice_id` · `to_email` · `attempted_at` · `result` (`sent`/`failed`) · `message_id` · `error` | ทุกครั้งที่พยายามส่ง = 1 แถว · retry เฉพาะที่ยังไม่มี `sent` |
| `settings` | `dorm_name` · `timezone` (`Asia/Bangkok`) · `sender_email` · `default_cutoff_day` (null = สิ้นเดือน · F6) | แถวเดียว · รอบใหม่ใช้ค่านี้สร้าง `cutoff_date` แล้วแก้รายรอบได้ |
| `owners` | `email` PK · `added_at` | **allowlist** — ล็อกอิน Google ได้ แต่ไม่อยู่ในนี้ = ไม่เห็นข้อมูลอะไรเลย (แบบ v1 §6) |

### 4.3 Storage

- bucket **`crops`** — private · path `<device_id>/<local_id>.jpg` · owner อ่านผ่าน signed URL อายุสั้น · anon อ่านไม่ได้
- **ลบ crop ที่ `captured_at` เก่ากว่า 12 เดือน (F8)** ด้วยงานตามเวลาฝั่งเซิร์ฟเวอร์ · ตั้ง `crop_path = null` + `crop_expired_at` ให้ UI บอก "รูปหมดอายุ" แทน "รูปกำลังซิงก์" · ตัวเลขในบิลอยู่ใน snapshot ไม่หาย · พื้นที่รูปหยุดโตที่ ≈ 40.5 MB ที่ 48 ห้อง [คำนวณ ไฟล์ 20 §20.8]
- ไม่มี bucket สำหรับภาพต้นฉบับ

---

## 5. ทะเบียนลง Pi (`meters.json`) [ต้องเพิ่ม]

ARIA export → copy ลง `~/mrc/data/meters.json` ตอนอยู่แล็บ (scp) · รูปแบบเดียวกับผังเดิม §1 ช่วง 0 แต่ใช้ `meter_id` แบบ `W-204-01`:

```json
{ "registry_version": 1, "exported_at": "2026-09-27T10:00:00+07:00",
  "meters": [
    { "meter_id": "W-204-01", "room": "204", "type": "water",    "digits": 5, "decimals": 3, "waypoint": null, "lift_mm": null },
    { "meter_id": "E-204-01", "room": "204", "type": "electric", "digits": 5, "decimals": 1, "waypoint": null, "lift_mm": null } ] }
```

**ไม่มีข้อมูลผู้เช่าในไฟล์นี้** — Pi ไม่ต้องรู้ว่าใครอยู่ห้องไหน

---

## 6. สิ่งที่ตั้งใจ **ไม่** เก็บบนคลาวด์ใน v1

| ข้อมูล | เหตุผล |
|---|---|
| ภาพต้นฉบับ 1080p | ตัดสินแล้ว (ไฟล์ 20 §20.2b) |
| รูปที่คนขับกด "ไม่เอา" / ยังไม่ตัดสิน | ลบ / ค้างบน Pi ≤ 7 วัน (F10) |
| ค่ากล้องตอนถ่าย | F2 · ไม่เก็บทั้งบน Pi และคลาวด์ |
| เบอร์โทรผู้เช่า | F5 |
| telemetry การขับ (ความเร็ว ล้อ เซอร์โว แบต) | เป็นข้อมูลวิศวกรรม ไม่ใช่ข้อมูลเจ้าของหอ · อยู่หน้าวินิจฉัย `/` บน Pi |
| ภาพสดจากกล้อง | ARIA ไม่ควบคุมหุ่นผ่านคลาวด์ (แบบ v1 §2) |
| ข้อมูลผู้เช่าบน Pi | Pi ไม่ต้องใช้ · ลดความเสียหายถ้า Pi หาย |

---

## 7. ขนาดข้อมูล

ใช้ตัวเลขใน [ไฟล์ 20 §20.7](../08_การคำนวณ/20_ระบบจัดการข้อมูลหอพัก_ความจุและอีเมล.md) (48 ห้อง): crop ขึ้นคลาวด์ ≈ 3.4 MB/รอบ · แถว ≈ 35 kB/รอบ [คำนวณ] · ชุดทดสอบ 10 ห้อง/20 มิเตอร์เล็กกว่านั้น · ผลของ F3 (อากาศขึ้นคลาวด์) และ F8 (ลบ crop หลัง 12 เดือน) คำนวณไว้ที่ **ไฟล์ 20 §20.8**: แถว 35 → 48 kB/รอบ · รูปหยุดโตที่ ≈ 40.5 MB [คำนวณ จากประมาณการ]

**ข้อควรรู้ของแพ็กเกจฟรี:** Supabase Free หยุดโปรเจกต์ที่ไม่มีการใช้งานนานพอ (ต้องเช็คเงื่อนไขปัจจุบันในเอกสาร Supabase ก่อนพึ่ง) · ถ้าถูกหยุด ingest จะล้มแต่ **ข้อมูลบน Pi ไม่หาย** เพราะส่งเฉพาะแถวที่ `synced_at` ว่าง

---

## 7a. ผลต่อจอกลม GC9A01 (ตรวจ 28 ก.ย. บน branch `codex/aria-drive-ui`)

ไล่ 21 หน้าเทียบกับสิ่งที่คนขับต้องรู้ **ตอนยืนอยู่หน้ามิเตอร์** ตามผังข้อมูลนี้ · **ยังไม่แก้โค้ดจอ** — ทุกข้อเป็นข้อเสนอรอไฟนอล (F10)

> **ตัดสิน 28 ก.ย. (F10): ผู้ใช้เลือกป๊อปอัพบน `/drive` ให้คนขับเลือกห้อง+ชนิดและตัดสินเก็บ/ไม่เอา (§2.0)** → J1–J2 ย้ายไปอยู่บนมือถือแทนจอกลม (superseded) · J3 ไม่ต้องมีเกณฑ์ confidence เพราะคนขับเห็นรูป+ค่า OCR ก่อนตัดสินเอง (superseded) · **ข้อเสนอที่เหลือ J4:** ระหว่างรอตัดสิน จอกลมควรโชว์ "Review on phone" — ต้องเพิ่ม evt ใหม่ (เช่น `REVIEW`) · เฟิร์มแวร์เดิมจะแสดงผ่านหน้า `OtherEvent` เป็นข้อความดิบ `REVIEW` ได้โดยไม่พัง จึงไม่บังคับแฟลชพร้อมกัน · ตาราง J1–J3 ด้านล่างเก็บไว้เป็นประวัติ

| # | หน้า | ช่องว่างเทียบกับงานเรา | ข้อเสนอ | ต้องแก้ |
|---|---|---|---|---|
| J1 | `Reading` ("Meter reading" + ค่า + "Saved") | ไม่บอกว่าแถวนี้ถูกตรึงกับ **มิเตอร์ไหน** · ถ้าคนขับลืมเปลี่ยน dropdown รูปห้อง 205 จะติดชื่อ 204 และมารู้ตอนเจ้าของหอยืนยัน = ต้องส่งหุ่นกลับไปทั้งรอบ | แสดงป้ายสั้น `W-204` ใต้ค่า (ตัด `-01` ออกเพื่อให้พอดีจอ) | ฟิลด์ใหม่ใน `$D` + `tft.cpp` + `mrc_protocol.py` + เทสต์ |
| J2 | `Saved` / `Reading` | ถ่ายโดย **ไม่ได้เลือกมิเตอร์** (`meter_id = null`) ดูเหมือนสำเร็จปกติ | ใช้สีเหลือง + ข้อความ `No meter set` แทน `Saved` · ยังถ่ายได้ตามกติกา "ถ่ายห้ามล้ม" | ใช้ฟิลด์เดียวกับ J1 (ว่าง = ไม่ได้เลือก) |
| J3 | `Reading` | OCR ที่ confidence ต่ำขึ้นเป็นสีเขียวเหมือนค่าที่มั่นใจ · ผังข้อมูล §1 ช่วง 3 บอกว่าจุดที่ถ่ายใหม่ถูกที่สุดคือตอนยังอยู่หน้ามิเตอร์ | ถ้าต่ำกว่าเกณฑ์ ใช้สีเหลือง + `Check photo` | เกณฑ์ **[ยังไม่ตัดสินใจ]** — ยังไม่มีข้อมูลว่า confidence ของ `sevenseg` ต่ำแค่ไหนถึงอ่านผิดจริง ต้องเก็บจากการถ่ายมิเตอร์จริงก่อน · ห้ามใส่ตัวเลขลอยๆ |

**ตั้งใจไม่เพิ่มบนจอกลม:** สถานะ sync/ค้างส่ง, นาฬิกา Pi ไม่ซิงก์, สถานะคลาวด์ — คนขับที่สนามแก้ไม่ได้ (ไม่มีเน็ต) และเสี่ยงทำให้จอดูเหมือนอ้างว่าต่ออินเทอร์เน็ต ซึ่ง `ARIA-DISPLAY.md` ห้ามไว้ · ข้อมูลพวกนี้ไปอยู่ใน heartbeat → ARIA (§3) · ทะเบียน `meters.json` หาย/เก่า ให้เตือนบน `/drive` ตอนเปิดหน้า ไม่ใช่บนจอ

**🔴 ข้อควรระวังถ้าทำ J1/J2 — ลำดับ deploy:** parser `$D` ใน [comm.cpp:71](../src/robot/comm.cpp:71) รับได้สูงสุด 13 ช่อง (`n < 13`) · ถ้า Pi ส่งช่องที่ 14 ไปหาเฟิร์มแวร์เดิม ส่วนเกินจะติดไปกับ `arg` → จอหน้า Reading จะโชว์ `1234.5,W-204` · **ต้องแฟลช ESP32 ก่อน deploy Pi เสมอ** (เฟิร์มแวร์ใหม่ + Pi เก่า ปลอดภัย เพราะช่องที่ขาดได้ค่าว่าง)

**ความสัมพันธ์กับลำดับงาน:** J1–J2 ใช้ไม่ได้จนกว่าจะมี `meters.json` + dropdown บน `/drive` (แบบ v1 §7 ขั้น 1) → ทำพร้อมขั้นนั้นแล้วแฟลชครั้งเดียว · **เทสพรุ่งนี้ (28 ก.ย.) ให้เทสจอแบบที่ push มาตามเดิม ไม่ต้องรอข้อเสนอนี้**

---

## 8. การตัดสิน (ผู้ใช้ 28 ก.ย. 2569)

| # | เรื่อง | ตัดสิน | ผลต่อแบบ |
|---|---|---|---|
| **F1** | เวลา | ต้องมีเวลากำกับเพื่อรู้ว่าเป็นของเดือนไหน | เก็บ `captured_at` (ตัดสินรอบบิล) + `received_at` + `clock_synced` (ให้เจ้าของเห็นว่าเวลาไหนเชื่อไม่ได้ — ถ้า Pi บูตไม่มีเน็ตและนาฬิกาเพี้ยน ค่าจะตกผิดเดือนโดยไม่มีใครรู้) · D5 (มีแบต RTC ไหม) **ยังไม่ได้วัด** |
| **F2** | ค่ากล้องตอนถ่าย | **ไม่เก็บ** | ตัดฟิลด์ `cam` |
| **F3** | ค่าอากาศตอนถ่าย | **ขึ้นคลาวด์** | `air` jsonb ใน `meter_readings` · +13.8 kB/รอบ (ไฟล์ 20 §20.8) · **ยังไม่มีหน้า ARIA ที่แสดง** — ต้องออกแบบเพิ่มตอนทำเว็บ |
| **F4** | ผู้เช่าย้ายกลางงวด | **ข้ามไปก่อน** | ไม่ทำฟังก์ชันใน v1 · `tenancies` มีช่วงวันอยู่แล้ว ทำทีหลังได้ไม่ต้องแก้ schema |
| **F5** | เบอร์โทรผู้เช่า | **ไม่เก็บ** | |
| **F6** | วันตัดรอบ | **ตั้งได้ในหน้าตั้งค่า ค่าเริ่ม = สิ้นเดือน** | `settings.default_cutoff_day` + `billing_cycles.cutoff_date` |
| **F7** | ค่าเช่า | **option ปิดเป็นค่าเริ่ม** (ยืนยันของ 17 ก.ย.) | |
| **F8** | อายุ crop บนคลาวด์ | **ลบหลัง 12 เดือน** | งานลบตามเวลา + `crop_expired_at` · รูปหยุดโตที่ ≈ 40.5 MB (48 ห้อง) |
| **F9** | ข้อมูลทดสอบ | **ใน `aria-mrc` + `is_demo`** | คอลัมน์ `is_demo` ในตารางที่ใส่ข้อมูลตัวอย่าง · ลบได้ในคำสั่งเดียว |
| **F10** | ยืนยันรูปตอนถ่าย | **ป๊อปอัพบน `/drive`**: รูป crop + ค่า OCR + เลือกเลขห้อง + ชนิดมิเตอร์ · "ไม่เอา" = **ลบ** · ไม่ได้กด = **ไม่ส่งขึ้น เก็บบน Pi 7 วัน** กดย้อนหลังได้ | §2.0 · แทนการตรึง `meter_id` ตอนรับคำสั่งถ่าย (แบบ v1 §4.2) · ตัด `retake_of` |

**ยังไม่อยู่ในรอบนี้:** วิธีให้สิทธิ์ส่ง Gmail (D4) — ไม่กระทบโครงตาราง เพราะผลส่งเก็บใน `invoice_delivery_attempts` ไม่ว่าส่งด้วยวิธีไหน
