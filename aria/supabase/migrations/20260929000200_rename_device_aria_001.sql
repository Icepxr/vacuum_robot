-- เปลี่ยนชื่อหุ่นที่ **แสดง** ใน ARIA จาก MRC-001 → ARIA-001 (ผู้ใช้สั่ง 29 ก.ย. 2569 · "เปลี่ยนแค่ชื่อที่แสดง ไม่ต้องแก้โค้ด")
-- เว็บหลังบ้านแสดง devices.device_id ตรงๆ → เปลี่ยนที่ข้อมูลแทนการเพิ่ม mapping ในโค้ด
-- โค้ดบน Pi/เฟิร์มแวร์ยังใช้ชื่อ MRC-001 ภายใน (DEVICE_ID ใน aria_store.py ไม่ถูกส่งขึ้นคลาวด์ จึงไม่ขัดกัน)
-- token เดิมใช้ต่อได้ (คลาวด์ผูก token_sha256 กับแถว ไม่ได้ผูกกับชื่อ) · Edge Function อ่าน device_id จาก token → ไม่ต้อง deploy ใหม่
-- รูป crop เดิมยังอยู่ที่ crops/MRC-001/… (crop_path เก็บ path เต็มต่อแถว ใช้ได้ตามเดิม) · รูปใหม่จะไปที่ crops/ARIA-001/…
alter table public.meter_readings drop constraint meter_readings_device_id_fkey;
alter table public.meter_readings add constraint meter_readings_device_id_fkey
  foreign key (device_id) references public.devices (device_id) on update cascade;
update public.devices set device_id = 'ARIA-001' where device_id = 'MRC-001';
