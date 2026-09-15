-- โครงตารางสำหรับ Supabase — รันในโปรเจกต์ที่เปิดใหม่สำหรับหุ่นเท่านั้น
-- ⚠ ห้ามรันในโปรเจกต์ MCCMU's Project ซึ่งเป็นเว็บชมรมของงานอื่น
-- ไฟล์นี้รันซ้ำได้ปลอดภัย (idempotent)

create table if not exists meter_readings (
  id          bigserial primary key,
  -- not null สำคัญ: Postgres ยอมให้ค่า NULL ซ้ำกันได้หลายแถวแม้ประกาศ unique
  -- ถ้าปล่อยให้เป็น NULL ได้ record ที่ไม่มี local_id จะถูก insert ซ้ำได้เรื่อยๆ
  local_id    text not null unique,
  captured_at timestamptz not null,
  run_id      text,
  meter_type  text,
  raw_text    text,                        -- ข้อความดิบจาก OCR — เก็บไว้ตรวจย้อนหลัง
  value       numeric,                     -- null = อ่านไม่ออก ไม่ใช่ค่า 0
  confidence  real,
  image_path  text,                        -- ภาพต้นฉบับใน SD ของ Pi (ยังไม่ crop)
  -- schema กลางที่ ARIA ใช้ร่วม (C23 · 15 ก.ย. 2026) — เพิ่มได้ด้วย alter table ถ้าตารางมีอยู่แล้ว
  meter_id        text,                    -- ผูกห้อง/มิเตอร์ (ทะเบียนอยู่ฝั่ง ARIA)
  status          text not null default 'ocr' check (status in ('ocr','confirmed','rejected')),
  confirmed_value numeric,                 -- ค่าที่ผู้ให้เช่ายืนยัน — คนละคอลัมน์กับ value เสมอ
  created_at  timestamptz not null default now()
);
alter table meter_readings add column if not exists meter_id text;
alter table meter_readings add column if not exists status text not null default 'ocr';
alter table meter_readings add column if not exists confirmed_value numeric;

create index if not exists meter_readings_run_idx on meter_readings (run_id, captured_at);

alter table meter_readings enable row level security;

-- ═══════════════════════════════════════════════════════════════
-- ทางเลือกเรื่องสิทธิ์ — เลือกทางใดทางหนึ่ง ไม่ใช่ทั้งสอง
-- ═══════════════════════════════════════════════════════════════
--
-- 🟢 ทางที่แนะนำ: ใช้ **service key** ที่ฝั่ง Pi แล้วไม่ต้องมี policy เลย
--    service key ข้าม RLS ได้อยู่แล้ว และ Pi เป็นอุปกรณ์ที่เราคุมทางกายภาพ
--    วางคีย์ไว้ใน environment variable ได้ปลอดภัย
--    ผลคือ anon ทำอะไรกับตารางนี้ไม่ได้เลยสักอย่าง ← ปลอดภัยที่สุดและไม่มีต้นทุน
--
-- 🟠 ทางที่สอง: ใช้ anon key แล้วเปิด policy ข้างล่าง
--    ⚠ ความเสี่ยงที่แท้จริงไม่ใช่ข้อมูลรั่ว แต่คือ **ตารางถูกถมจนเต็มโควตา**
--       anon key ถูกออกแบบมาให้เปิดเผยต่อสาธารณะ ใครเห็นก็เขียนได้ไม่จำกัด
--       Supabase free tier จำกัด database ที่ 500 MB — สคริปต์ตัวเดียวถมเต็มได้ในไม่กี่นาที
--       แล้วโปรเจกต์เสียที่เก็บข้อมูลไปก่อนถึงเส้นตาย
--
-- ถ้าเลือกทางที่สอง ให้เอาคอมเมนต์ออกจาก 4 บรรทัดนี้:
--
-- drop policy if exists "robot can insert" on meter_readings;
-- create policy "robot can insert" on meter_readings for insert to anon with check (true);
-- drop policy if exists "anyone can read" on meter_readings;
-- create policy "anyone can read"  on meter_readings for select to anon using (true);
--
-- ⚠ ถ้าเปิด RLS แล้วไม่มี policy สำหรับ select เลย จะ **อ่านข้อมูลกลับผ่าน API ไม่ได้**
--    แม้ด้วย anon key — จะได้ [] เปล่าๆ ไม่ error ไม่เตือน
--    (อ่านได้ทางเดียวคือ SQL editor ใน dashboard หรือใช้ service key)
