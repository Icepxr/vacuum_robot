-- ค่าที่หุ่นอ่าน "ตัวอย่าง" ให้หน้ายืนยันค่า/บิลของเว็บหลังบ้านมีของให้ลอง (F9 · is_demo)
-- ค่าชุดเดียวกับ design/aria-prototype/app.js · ไม่มีรูป crop (ข้อมูลตัวอย่าง) · ลบด้วย public.delete_demo_data()
-- อุปกรณ์ DEMO-01 ถูก revoke ตั้งแต่สร้าง → ingest ปฏิเสธทุกคำขอ · token_sha256 เป็นค่าสุ่มที่ไม่มีใครถือ token

insert into public.devices (device_id, token_sha256, revoked_at)
values ('DEMO-01', encode(extensions.gen_random_bytes(32), 'hex'), now());

-- (ลำดับ, ห้อง, ชนิด, OCR, confidence) · ถ่าย 20 ก.ย. 2569 ห่างกัน 3 นาที
-- 108 ไฟ: OCR ต่ำกว่าค่าเริ่ม (ผิดปกติ) · 105 น้ำ: OCR ไม่มั่นใจ · 109: ยังไม่อ่าน · 106: ห้องว่าง
insert into public.meter_readings (local_id, device_id, captured_at, decided_at, clock_synced, room_id, meter_type,
  meter_id, raw_text, value, confidence, ocr_engine, source, air, is_demo)
select substr(md5('demo-' || v.room || v.t), 1, 12), 'DEMO-01',
       timestamptz '2026-09-20 10:00+07' + (v.n * interval '3 minutes'),
       timestamptz '2026-09-20 10:00+07' + (v.n * interval '3 minutes') + interval '20 seconds',
       v.room <> '107',                                   -- 107: นาฬิกา Pi ยังไม่ซิงก์ (F1)
       v.room, v.t, format('%s-%s-01', case v.t when 'water' then 'W' else 'E' end, v.room),
       v.ocr::text, v.ocr, v.conf, 'sevenseg', 'demo',
       case when v.n % 3 = 0 then jsonb_build_object('eco2_ppm', 620 + v.n * 10, 'tvoc_ppb', 80 + v.n, 'aqi', 2,
            'temp_c', 29.5, 'rh_pct', 58.0, 'validity', 0) end,
       true
from (values
  (1,'101','water',1244,.97),(2,'101','electric',3611,.96),
  (3,'102','water',998,.98),(4,'102','electric',2233,.95),
  (5,'103','water',1532,.95),(6,'103','electric',2977,.94),
  (7,'104','water',1205,.91),(8,'104','electric',3340,.89),
  (9,'105','water',1477,.41),(10,'105','electric',5096,.96),
  (11,'106','water',811,.93),(12,'106','electric',1352,.94),
  (13,'107','water',1117,.96),(14,'107','electric',4602,.97),
  (15,'108','water',1362,.94),(16,'108','electric',3184,.83),
  (19,'110','water',1133,.95),(20,'110','electric',2950,.97)
) v(n, room, t, ocr, conf);

-- 1 แถวที่คนขับไม่ได้เลือกห้อง (meter_id = null) → คิว "ยังไม่ผูก"
insert into public.meter_readings (local_id, device_id, captured_at, decided_at, clock_synced, room_id, meter_type,
  meter_id, raw_text, value, confidence, ocr_engine, source, is_demo)
values (substr(md5('demo-unassigned'), 1, 12), 'DEMO-01', timestamptz '2026-09-20 10:57+07',
  timestamptz '2026-09-20 10:58+07', true, null, 'water', null, '01188', 1188, .88, 'sevenseg', 'demo', true);

-- ค่าที่ยืนยันแล้วตามต้นแบบ (ผ่าน trigger เดียวกับที่เว็บใช้ · actor = null เพราะเป็น migration)
insert into public.reading_events (reading_id, event, confirmed_value)
select r.id, 'confirmed', r.value from public.meter_readings r
where r.is_demo and r.device_id = 'DEMO-01' and r.meter_id in
  ('W-101-01','E-101-01','W-102-01','E-102-01','W-103-01','E-105-01','W-106-01','E-106-01',
   'W-107-01','E-107-01','W-108-01','W-110-01','E-110-01');

create or replace function public.delete_demo_data() returns void
language sql security definer set search_path = '' as $$
  delete from public.meter_readings where is_demo or assigned_meter_id in (select meter_id from public.meters where is_demo);
  delete from public.devices where device_id = 'DEMO-01';
  delete from public.tenancies where is_demo;
  delete from public.meters where is_demo;
  delete from public.rooms where is_demo;
$$;
revoke execute on function public.delete_demo_data() from public, anon, authenticated;
