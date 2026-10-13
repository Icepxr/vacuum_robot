-- ดึงกลับจากคลาวด์ 13 ต.ค. 2026 (supabase_migrations.schema_migrations version 20261005163256 · ชื่อ meter_changes)
-- ใช้กับ aria-mrc แล้ว — ไฟล์นี้มีไว้ให้ repo สร้างฐานข้อมูลได้ครบ · ลำดับ: หลัง 20261005000100_billing_guards
create table public.meter_changes (
  id         bigint generated always as identity primary key,
  meter_id   text not null references public.meters(meter_id) on update cascade,
  field      text not null,
  old_value  text,
  new_value  text,
  reason     text,
  actor      text not null default lower(coalesce(auth.jwt() ->> 'email', 'system')),
  at         timestamptz not null default now()
);
create index on public.meter_changes (meter_id);
alter table public.meter_changes enable row level security;
create policy meter_changes_read on public.meter_changes for select to authenticated using ((select public.is_owner()));

create or replace function public.meters_guard() returns trigger language plpgsql security definer set search_path = '' as $$
declare first_v numeric; last_v numeric; r text := nullif(current_setting('aria.reason', true), '');
begin
  if new.start_value is distinct from old.start_value then
    select x.confirmed_value into first_v from public.meter_readings x
      where coalesce(x.assigned_meter_id, x.meter_id) = old.meter_id and x.status = 'confirmed' order by x.captured_at limit 1;
    if first_v is not null and new.start_value > first_v then
      raise exception 'เลขเริ่ม % มากกว่าค่าที่ยืนยันครั้งแรก % ของมิเตอร์ %', new.start_value, first_v, old.meter_id;
    end if;
  end if;
  if new.end_value is not null and new.end_value is distinct from old.end_value then
    select x.confirmed_value into last_v from public.meter_readings x
      where coalesce(x.assigned_meter_id, x.meter_id) = old.meter_id and x.status = 'confirmed'
        and (new.retired_at is null or (x.captured_at at time zone 'Asia/Bangkok')::date <= new.retired_at)
      order by x.captured_at desc limit 1;
    if last_v is not null and new.end_value < last_v then
      raise exception 'เลขตอนถอด % ต่ำกว่าค่าที่ยืนยันล่าสุด % ของมิเตอร์ %', new.end_value, last_v, old.meter_id;
    end if;
  end if;
  insert into public.meter_changes (meter_id, field, old_value, new_value, reason)
  select old.meter_id, f, o, n, r from (values
    ('start_value', old.start_value::text, new.start_value::text),
    ('end_value', old.end_value::text, new.end_value::text),
    ('retired_at', old.retired_at::text, new.retired_at::text),
    ('installed_at', old.installed_at::text, new.installed_at::text)) v(f, o, n)
  where o is distinct from n;
  return new;
end $$;
create trigger meters_guard before update on public.meters for each row execute function public.meters_guard();
revoke execute on function public.meters_guard() from public, anon, authenticated;

create or replace function public.set_meter_start(p_meter_id text, p_value numeric, p_reason text) returns void
language plpgsql set search_path = '' as $$
begin
  if not public.is_owner() then raise exception 'เฉพาะเจ้าของหอ'; end if;
  if length(trim(coalesce(p_reason, ''))) = 0 then raise exception 'ต้องใส่เหตุผลที่แก้เลขเริ่ม'; end if;
  perform set_config('aria.reason', trim(p_reason), true);
  update public.meters set start_value = p_value where meter_id = p_meter_id;
  if not found then raise exception 'ไม่พบมิเตอร์ %', p_meter_id; end if;
  perform set_config('aria.reason', '', true);
end $$;
revoke execute on function public.set_meter_start(text, numeric, text) from public, anon;
grant execute on function public.set_meter_start(text, numeric, text) to authenticated;
