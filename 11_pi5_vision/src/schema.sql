-- โครงตารางสำหรับ Supabase — รันในโปรเจกต์ที่เปิดใหม่สำหรับหุ่นเท่านั้น
-- ⚠ ห้ามรันในโปรเจกต์ MCCMU's Project ซึ่งเป็นเว็บชมรมของงานอื่น

create table if not exists meter_readings (
  id          bigserial primary key,
  local_id    text unique,                 -- กันส่งซ้ำเวลา sync รอบใหม่
  captured_at timestamptz not null,
  run_id      text,
  meter_type  text,
  raw_text    text,                        -- ข้อความดิบจาก OCR — เก็บไว้ตรวจย้อนหลัง
  value       numeric,                     -- null = อ่านไม่ออก ไม่ใช่ค่า 0
  confidence  real,
  image_path  text,                        -- ภาพต้นฉบับใน SD ของ Pi
  created_at  timestamptz not null default now()
);

create index if not exists meter_readings_run_idx on meter_readings (run_id, captured_at);

-- เปิด RLS ไว้ก่อนตามค่าเริ่มต้นของ Supabase
alter table meter_readings enable row level security;

-- ตัวอย่าง policy สำหรับให้หุ่นเขียนได้ด้วย anon key
-- ⚠ อนุญาตให้ใครก็ได้ที่มี anon key เขียนลงตารางนี้ — ยอมรับได้สำหรับโครงงาน
--   ถ้าอยากรัดกุมกว่านี้ ให้ใช้ service key ที่ฝั่ง Pi แล้วไม่ต้องมี policy นี้
create policy "robot can insert" on meter_readings
  for insert to anon with check (true);
