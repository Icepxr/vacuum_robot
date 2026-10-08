-- 8 ต.ค. 2026: Pi ดึงทะเบียนห้อง+มิเตอร์เองผ่าน Edge Function ingest (GET /registry) แทนการ export meters.json แล้ว scp
-- content_sha256 = SHA-256 ของเนื้อหาทะเบียน → เนื้อหาเดิมใช้รุ่นเดิม · เปลี่ยนเมื่อไรออกรุ่นใหม่ (เลขรุ่นต่อจากปุ่มส่งออกบนเว็บ)
-- exported_via = 'device:<id>' (Pi ดึง) · null = ปุ่มส่งออกบนเว็บ (exported_by = ผู้ใช้)
alter table public.meter_registry_exports
  add column content_sha256 text,
  add column exported_via   text;
