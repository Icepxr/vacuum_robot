-- กรอกเลขมิเตอร์เอง + ยกเลิกการยืนยัน (ผู้ใช้ตัดสิน 3 ต.ค. 2569)
-- 1) add_manual_reading(): เจ้าของกรอกเลขเองเมื่อหุ่นถ่ายไม่ได้ · สร้างแถว meter_readings (source = 'manual', ไม่มีรูป)
--    แล้วยืนยันทันทีในธุรกรรมเดียว · ต้องมีเหตุผล (ไม่มีรูปเป็นหลักฐาน) · กฎค่าห้ามถอยหลังใน trigger เดิมยังบังคับ
--    meter_readings.device_id เป็น not null → ผูกกับอุปกรณ์เสมือน 'MANUAL' ที่ถูก revoke ตั้งแต่สร้าง (ingest ปฏิเสธ · หน้าเว็บไม่นับเป็นหุ่น)
-- 2) event 'reopened': ค่าที่ยืนยัน/ปฏิเสธแล้ว กลับเป็น "รอยืนยัน" · ประวัติเดิมอยู่ครบ (reading_events append-only)
--    บิลที่อนุมัติแล้วไม่เปลี่ยนตาม → หน้าบิลขึ้น "ค่าเปลี่ยน" ให้ออกฉบับแก้ไขเอง

-- token_sha256 ต้องไม่ซ้ำและเป็น hex 64 ตัว → ใช้ sha256 ของข้อความสุ่มที่ไม่มีใครรู้ · revoked ตั้งแต่ต้น
insert into public.devices (device_id, token_sha256, revoked_at)
values ('MANUAL', encode(extensions.digest(gen_random_uuid()::text || clock_timestamp()::text, 'sha256'), 'hex'), now())
on conflict (device_id) do nothing;

alter table public.reading_events drop constraint reading_events_event_check;
alter table public.reading_events add constraint reading_events_event_check
  check (event in ('confirmed', 'corrected', 'rejected', 'assigned', 'reopened'));

create or replace function public.reading_events_before_insert() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  r      public.meter_readings;
  m_id   text;
  lo     numeric;
  hi     numeric;
begin
  new.actor := (select auth.uid());
  new.at := now();
  select * into r from public.meter_readings where id = new.reading_id for update;
  if r.id is null then raise exception 'reading % not found', new.reading_id; end if;

  if new.event = 'reopened' and r.status = 'ocr' then
    raise exception 'ค่านี้ยังรอยืนยันอยู่แล้ว (reading %)', new.reading_id;
  end if;

  if new.event in ('confirmed','corrected') then
    m_id := coalesce(r.assigned_meter_id, r.meter_id);
    if m_id is null then
      raise exception 'ต้องผูกมิเตอร์ก่อนยืนยันค่า (reading %)', new.reading_id;
    end if;
    select max(x.confirmed_value) into lo from public.meter_readings x
      where coalesce(x.assigned_meter_id, x.meter_id) = m_id and x.status = 'confirmed'
        and x.id <> r.id and x.captured_at < r.captured_at;
    if lo is null then select start_value into lo from public.meters where meter_id = m_id; end if;
    select min(x.confirmed_value) into hi from public.meter_readings x
      where coalesce(x.assigned_meter_id, x.meter_id) = m_id and x.status = 'confirmed'
        and x.id <> r.id and x.captured_at > r.captured_at;
    if lo is not null and new.confirmed_value < lo then
      raise exception 'ค่า % ต่ำกว่าค่ายืนยันก่อนหน้า % ของมิเตอร์ %', new.confirmed_value, lo, m_id;
    end if;
    if hi is not null and new.confirmed_value > hi then
      raise exception 'ค่า % สูงกว่าค่ายืนยันครั้งถัดไป % ของมิเตอร์ %', new.confirmed_value, hi, m_id;
    end if;
  end if;
  return new;
end $$;

create or replace function public.reading_events_after_insert() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.event in ('confirmed','corrected') then
    update public.meter_readings set status = 'confirmed', confirmed_value = new.confirmed_value where id = new.reading_id;
  elsif new.event = 'rejected' then
    update public.meter_readings set status = 'rejected', confirmed_value = null where id = new.reading_id;
  elsif new.event = 'assigned' then
    -- ผูกมิเตอร์ใหม่ = ค่าที่เคยยืนยันกับมิเตอร์เดิมใช้ไม่ได้แล้ว
    update public.meter_readings set assigned_meter_id = new.meter_id, status = 'ocr', confirmed_value = null where id = new.reading_id;
  elsif new.event = 'reopened' then
    update public.meter_readings set status = 'ocr', confirmed_value = null where id = new.reading_id;
  end if;
  return null;
end $$;
revoke execute on function public.reading_events_before_insert() from public, anon, authenticated;
revoke execute on function public.reading_events_after_insert() from public, anon, authenticated;

-- p_at = เวลาที่อ่านหน้าปัดจริง (ตัดสินรอบบิลเหมือน captured_at ของหุ่น) · คืน id ของแถวใหม่
create or replace function public.add_manual_reading(p_meter_id text, p_value numeric, p_at timestamptz, p_reason text) returns bigint
language plpgsql security definer set search_path = '' as $$
declare m public.meters; d date; rid bigint;
begin
  if not public.is_owner() then raise exception 'เฉพาะเจ้าของหอ'; end if;
  if length(trim(coalesce(p_reason, ''))) = 0 then raise exception 'ต้องใส่เหตุผลที่กรอกเอง (ไม่มีรูปเป็นหลักฐาน)'; end if;
  if p_value is null or p_value < 0 then raise exception 'ค่าต้องเป็นตัวเลขไม่ติดลบ'; end if;
  if p_at is null or p_at > now() + interval '5 minutes' then raise exception 'เวลาที่อ่านต้องไม่อยู่ในอนาคต'; end if;
  select * into m from public.meters where meter_id = p_meter_id;
  if m.meter_id is null then raise exception 'ไม่พบมิเตอร์ %', p_meter_id; end if;
  d := (p_at at time zone 'Asia/Bangkok')::date;
  if d < m.installed_at or (m.retired_at is not null and d > m.retired_at) then
    raise exception 'วันที่ % อยู่นอกช่วงที่ติดตั้ง % ', d, p_meter_id;
  end if;
  insert into public.meter_readings (local_id, device_id, captured_at, decided_at, clock_synced, room_id, meter_type, meter_id, value, source)
    values (substr(md5(gen_random_uuid()::text), 1, 12), 'MANUAL', p_at, now(), true, m.room_id, m.type, m.meter_id, p_value, 'manual')
    returning id into rid;
  insert into public.reading_events (reading_id, event, confirmed_value, reason) values (rid, 'confirmed', p_value, trim(p_reason));
  return rid;
end $$;
revoke execute on function public.add_manual_reading(text, numeric, timestamptz, text) from public, anon;
grant execute on function public.add_manual_reading(text, numeric, timestamptz, text) to authenticated;
