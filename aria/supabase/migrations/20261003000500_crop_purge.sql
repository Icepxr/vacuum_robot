-- ลบรูป crop อัตโนมัติ (ผู้ใช้เลือกแบบ ข 3 ต.ค. 2569 · เสริม F8 ในสเปก)
--   ลบรูปเมื่อ: บิลฉบับปัจจุบันของ รอบ+ห้อง นั้น "รับเงินครบ" (ยอดรับที่ไม่ถูกยกเลิก ≥ ยอดบิล) และวันที่รับเงินล่าสุดผ่านมาแล้ว ≥ 30 วัน (เวลาไทย)
--             เฉพาะค่าที่ตัดสินแล้ว (ยืนยัน/ปฏิเสธ) · ค่าที่ยังรอยืนยันไม่แตะ
--   หรือ:     รูปอายุเกิน 12 เดือน (F8 เดิม · กันห้องที่ค้างจ่ายไม่ให้รูปค้างตลอดไป)
--   ตัวเลขทั้งหมดไม่ลบ — เลขเดือนนี้คือเลขตั้งต้นของบิลเดือนหน้า + หลักฐานกฎค่าห้ามถอยหลัง
-- SQL ลบไฟล์ใน Storage ไม่ได้ (storage.protect_delete) → Edge Function purge-crops ลบไฟล์ผ่าน Storage API แล้วตั้ง
--   crop_path = null + crop_expired_at = now() · pg_cron เรียกวันละครั้ง 03:30 เวลาไทย ผ่าน pg_net
-- ช่วงของรอบ = invoices.detail.range {from, to} ที่ตรึงไว้ตอนอนุมัติ (ไม่คำนวณใหม่) · ห้องของค่า = ห้องของมิเตอร์ที่ผูก ไม่มี = ห้องที่คนขับเลือก

create or replace function public.crops_due_for_purge(p_limit int default 200)
returns table (id bigint, crop_path text, why text)
language sql stable security definer set search_path = '' as $$
  with cur as (
    select i.cycle, i.room_id, i.total_baht,
           (i.detail -> 'range' ->> 'from')::date as d_from, (i.detail -> 'range' ->> 'to')::date as d_to
    from public.invoices i
    where i.state = 'approved' and i.detail ? 'range'
  ), paid as (
    select cur.room_id, cur.d_from, cur.d_to
    from cur join public.invoice_payments p on p.cycle = cur.cycle and p.room_id = cur.room_id and p.voided_at is null
    group by cur.cycle, cur.room_id, cur.total_baht, cur.d_from, cur.d_to
    having sum(p.amount) >= cur.total_baht
       and max(p.paid_on) <= (now() at time zone 'Asia/Bangkok')::date - 30
  )
  select r.id, r.crop_path,
         case when r.captured_at < now() - interval '12 months' then 'age_12m' else 'paid_30d' end
  from public.meter_readings r
  left join public.meters m on m.meter_id = coalesce(r.assigned_meter_id, r.meter_id)
  where r.crop_path is not null
    and (r.captured_at < now() - interval '12 months'
         or (r.status <> 'ocr' and exists (
               select 1 from paid
               where paid.room_id = coalesce(m.room_id, r.room_id)
                 and (r.captured_at at time zone 'Asia/Bangkok')::date > paid.d_from
                 and (r.captured_at at time zone 'Asia/Bangkok')::date <= paid.d_to)))
  order by r.captured_at
  limit greatest(1, least(p_limit, 1000));
$$;
revoke execute on function public.crops_due_for_purge(int) from public, anon, authenticated;
grant execute on function public.crops_due_for_purge(int) to service_role;

create extension if not exists pg_net schema extensions;   -- ไม่ใส่ schema = ลง public → advisor เตือน (0014)
create extension if not exists pg_cron;

-- 20:30 UTC = 03:30 เวลาไทย · ฟังก์ชันไม่รับ input และลบได้เฉพาะรูปที่ถึงเกณฑ์แล้ว → เรียกซ้ำ/คนนอกเรียกก็ไม่ทำให้ลบเกินเกณฑ์
select cron.schedule('purge-crops-daily', '30 20 * * *', $cron$
  select net.http_post(
    url := 'https://brvlfwrmkoyjnrhvfesq.supabase.co/functions/v1/purge-crops',
    headers := jsonb_build_object('Content-Type', 'application/json'),
    body := '{}'::jsonb,
    timeout_milliseconds := 60000);
$cron$);
