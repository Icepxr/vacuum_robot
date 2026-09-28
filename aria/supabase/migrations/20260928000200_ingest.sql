-- ทางรับข้อมูลจาก Pi (D6 · ตัดสิน 27 ก.ย. 2569): Edge Function `ingest` เรียกฟังก์ชันพวกนี้ด้วย service role
-- anon/authenticated เรียกไม่ได้ · ฟังก์ชันรับ device_id ที่ Edge Function ยืนยันจาก token แล้ว ไม่รับจาก payload

-- แถวจากหุ่นเป็นข้อเท็จจริงที่ไม่เปลี่ยน → insert … on conflict do nothing
-- ส่งซ้ำ (Ctrl-C / ไฟดับ / response หาย) = no-op · ไม่มีทางเขียนทับ status/confirmed_value/crop_path
create or replace function public.ingest_readings(p_device text, p_rows jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  allowed constant text[] := array['local_id','captured_at','decided_at','run_id','room_id','meter_type',
    'raw_text','value','confidence','image_path','source','meter_id','registry_version','clock_synced',
    'ocr_engine','air'];
  row_j     jsonb;
  extra     text[];
  lid       text;
  owner_dev text;
  accepted  text[] := '{}';
  rejected  jsonb := '[]';
begin
  if jsonb_typeof(p_rows) <> 'array' then raise exception 'rows must be an array'; end if;
  if jsonb_array_length(p_rows) > 50 then raise exception 'max 50 rows per call'; end if;

  for row_j in select * from jsonb_array_elements(p_rows) loop
    if jsonb_typeof(row_j) <> 'object' then
      rejected := rejected || jsonb_build_object('local_id', null, 'reason', 'row is not an object');
      continue;
    end if;
    lid := row_j ->> 'local_id';
    select array_agg(k) into extra from jsonb_object_keys(row_j) k where k <> all (allowed);
    if extra is not null then
      rejected := rejected || jsonb_build_object('local_id', lid, 'reason', 'unknown fields: ' || array_to_string(extra, ','));
      continue;
    end if;
    begin
      insert into public.meter_readings (local_id, device_id, captured_at, decided_at, run_id, room_id, meter_type,
        raw_text, value, confidence, image_path, source, meter_id, registry_version, clock_synced, ocr_engine, air)
      values (lid, p_device, (row_j ->> 'captured_at')::timestamptz, (row_j ->> 'decided_at')::timestamptz,
        row_j ->> 'run_id', row_j ->> 'room_id', row_j ->> 'meter_type', row_j ->> 'raw_text',
        (row_j ->> 'value')::numeric, (row_j ->> 'confidence')::real, row_j ->> 'image_path', row_j ->> 'source',
        row_j ->> 'meter_id', (row_j ->> 'registry_version')::integer, (row_j ->> 'clock_synced')::boolean,
        row_j ->> 'ocr_engine', case when jsonb_typeof(row_j -> 'air') = 'object' then row_j -> 'air' end)
      on conflict (local_id) do nothing;
      if not found then
        select device_id into owner_dev from public.meter_readings where local_id = lid;
        if owner_dev is distinct from p_device then
          rejected := rejected || jsonb_build_object('local_id', lid, 'reason', 'local_id belongs to another device');
          continue;
        end if;
      end if;
      accepted := accepted || lid;
    exception when others then
      -- แถวเสียแถวเดียวไม่ทำให้ทั้ง batch ล้ม
      rejected := rejected || jsonb_build_object('local_id', lid, 'reason', sqlerrm);
    end;
  end loop;
  return jsonb_build_object('accepted', to_jsonb(accepted), 'rejected', rejected);
end $$;

create or replace function public.ingest_heartbeat(p_device text, p_hb jsonb) returns void
language plpgsql security definer set search_path = '' as $$
begin
  update public.devices set
    last_seen_at      = now(),
    pending_rows      = (p_hb ->> 'pending_rows')::integer,
    pending_crops     = (p_hb ->> 'pending_crops')::integer,
    pending_decisions = (p_hb ->> 'pending_decisions')::integer,
    app_version       = left(p_hb ->> 'app_version', 64),
    disk_free_mb      = (p_hb ->> 'disk_free_mb')::integer,
    clock_synced      = (p_hb ->> 'clock_synced')::boolean,
    warn              = left(p_hb ->> 'warn', 8),
    cam_ok            = (p_hb ->> 'cam_ok')::boolean,
    air_available     = (p_hb ->> 'air_available')::boolean,
    cpu_temp_c        = (p_hb ->> 'cpu_temp_c')::real
  where device_id = p_device;
end $$;

-- เรียกหลังอัปโหลด crop ลง Storage สำเร็จ · คืน false ถ้าแถวไม่ใช่ของอุปกรณ์นี้ (หรือยังไม่มี)
create or replace function public.ingest_crop_attach(p_device text, p_local_id text, p_path text) returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  update public.meter_readings set crop_path = p_path
  where local_id = p_local_id and device_id = p_device and crop_expired_at is null;
  return found;
end $$;

revoke execute on function public.ingest_readings(text, jsonb)          from public, anon, authenticated;
revoke execute on function public.ingest_heartbeat(text, jsonb)         from public, anon, authenticated;
revoke execute on function public.ingest_crop_attach(text, text, text)  from public, anon, authenticated;
grant  execute on function public.ingest_readings(text, jsonb)          to service_role;
grant  execute on function public.ingest_heartbeat(text, jsonb)         to service_role;
grant  execute on function public.ingest_crop_attach(text, text, text)  to service_role;

-- ───────────── Storage: crops (private) ─────────────
-- จำกัด 1 MB ต่อไฟล์เป็นแค่เพดานกันพลาด · crop ที่คาดไว้ ≈ 30 kB [ประมาณการ V9 ไฟล์ 20]
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('crops', 'crops', false, 1048576, array['image/jpeg'])
on conflict (id) do nothing;

-- เจ้าของอ่านได้ (สร้าง signed URL) · เขียนได้เฉพาะ service role ผ่าน ingest
create policy crops_owner_read on storage.objects for select to authenticated
  using (bucket_id = 'crops' and (select public.is_owner()));
