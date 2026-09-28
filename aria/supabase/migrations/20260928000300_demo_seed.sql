-- ข้อมูลทดสอบ 10 ห้อง / 20 มิเตอร์ (F9 · ตัดสิน 28 ก.ย. 2569) — ชื่อ/อีเมลสมมติชุดเดียวกับ design/aria-prototype/app.js
-- ทุกแถวมี is_demo = true · ลบทั้งหมดก่อนใช้กับหอจริงด้วย public.delete_demo_data()
insert into public.rooms (room_id, floor, is_demo)
select r::text, left(r::text, 1), true from generate_series(101, 110) r;

-- start_value = ค่า prev ในต้นแบบ (ใช้เป็นฐานของการยืนยันครั้งแรก)
insert into public.meters (meter_id, room_id, type, digits, decimals, installed_at, start_value, is_demo)
select format('%s-%s-01', t.p, v.room), v.room, t.type, 5, 0, date '2026-01-01', case t.type when 'water' then v.w else v.e end, true
from (values ('101',1231,3502),('102',987,2140),('103',1518,2901),('104',1192,3271),('105',1402,5012),
             ('106',802,1320),('107',1105,4521),('108',1351,3204),('109',890,2750),('110',1120,2876)) v(room, w, e)
cross join (values ('W','water'),('E','electric')) t(p, type);

-- ห้อง 106 ว่าง · ห้อง 110 ไม่มีอีเมล (ทดสอบ "ดูบิลได้ ส่งไม่ได้")
insert into public.tenancies (room_id, tenant_name, email, start_date, rent_baht, is_demo) values
  ('101','วราภรณ์ ใจดี','waraporn@example.com','2026-01-01',3500,true),
  ('102','ศักดิ์ชัย แสนสุข','sakchai@example.com','2026-01-01',3700,true),
  ('103','ธนพร พรมมา','thanaporn@example.com','2026-01-01',3600,true),
  ('104','นิภาพร สุขใจ','nipaporn@example.com','2026-01-01',3400,true),
  ('105','กิตติพงษ์ รัตนวงศ์','kittipong@example.com','2026-01-01',3800,true),
  ('107','พิมพ์ชนก วงศ์ดี','pimchanok@example.com','2026-01-01',3500,true),
  ('108','นรินทร์ คำมา','narin@example.com','2026-01-01',3900,true),
  ('109','รัชนี แก้วตา','ratchanee@example.com','2026-01-01',3500,true),
  ('110','สุรเชษฐ์ จันทร์ดี',null,'2026-01-01',3300,true);

create or replace function public.delete_demo_data() returns void
language sql security definer set search_path = '' as $$
  delete from public.meter_readings where is_demo or assigned_meter_id in (select meter_id from public.meters where is_demo);
  delete from public.tenancies where is_demo;
  delete from public.meters where is_demo;
  delete from public.rooms where is_demo;
$$;
revoke execute on function public.delete_demo_data() from public, anon, authenticated;
