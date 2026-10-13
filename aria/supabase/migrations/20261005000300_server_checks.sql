-- ดึงกลับจากคลาวด์ 13 ต.ค. 2026 (supabase_migrations.schema_migrations version 20261005164204 · ชื่อ server_checks)
-- ใช้กับ aria-mrc แล้ว — ไฟล์นี้มีไว้ให้ repo สร้างฐานข้อมูลได้ครบ · ลำดับ: หลัง 20261005000200_meter_changes
create table public.client_errors (
  id       bigint generated always as identity primary key,
  at       timestamptz not null default now(),
  actor    text not null default lower(coalesce(auth.jwt() ->> 'email', case when (auth.jwt() ->> 'is_anonymous')::boolean then 'guest' else 'unknown' end)),
  page     text check (length(page) <= 200),
  message  text not null check (length(message) <= 1000),
  stack    text check (length(stack) <= 4000),
  ua       text check (length(ua) <= 300)
);
alter table public.client_errors enable row level security;
create policy client_errors_insert on public.client_errors for insert to authenticated with check (true);
create policy client_errors_read   on public.client_errors for select to authenticated using ((select public.is_owner()));

create or replace function public.approve_invoices(p_cycle text, p_cutoff date, p_items jsonb) returns setof public.invoices
language plpgsql set search_path = '' as $$
declare it jsonb; cur public.invoices; rev int; who text := lower(coalesce((select auth.jwt()) ->> 'email', ''));
        t text; rate_db numeric; segs jsonb; s jsonb; seg_sum numeric; bc date;
begin
  if not public.is_owner() then raise exception 'เฉพาะเจ้าของหอ'; end if;
  insert into public.billing_cycles (cycle, cutoff_date) values (p_cycle, p_cutoff) on conflict (cycle) do nothing;
  select cutoff_date into bc from public.billing_cycles where cycle = p_cycle;
  if bc <> p_cutoff then raise exception 'วันตัดรอบ % ไม่ตรงกับที่ตั้งไว้ % · โหลดหน้าใหม่แล้วลองอีกครั้ง', p_cutoff, bc; end if;
  for it in select * from jsonb_array_elements(p_items) loop
    if (it ->> 'tenancy_id') is not null and not exists (select 1 from public.tenancies x where x.id = (it ->> 'tenancy_id')::bigint and x.room_id = it ->> 'room_id') then
      raise exception 'ผู้เช่าไม่ตรงกับห้อง %', it ->> 'room_id';
    end if;
    foreach t in array array['water', 'electric'] loop
      select r.baht_per_unit into rate_db from public.rates r where r.type = t and r.effective_from <= p_cutoff order by r.effective_from desc limit 1;
      if rate_db is null or abs(rate_db - (it ->> (t || '_rate'))::numeric) > 0.0001 then
        raise exception 'อัตรา% ของห้อง % ไม่ตรงกับอัตราที่มีผล ณ % (%) · โหลดหน้าใหม่', t, it ->> 'room_id', p_cutoff, rate_db;
      end if;
      if (it ->> (t || '_units'))::numeric < 0 then raise exception 'หน่วย% ของห้อง % ติดลบ', t, it ->> 'room_id'; end if;
      segs := it -> 'detail' -> 'segments' -> t;
      if segs is not null and jsonb_typeof(segs) = 'array' and jsonb_array_length(segs) > 0 then
        seg_sum := 0;
        for s in select * from jsonb_array_elements(segs) loop
          if abs(((s ->> 'curr')::numeric - (s ->> 'base')::numeric) - (s ->> 'units')::numeric) > 0.0001 then
            raise exception 'หน่วยของมิเตอร์ % ไม่เท่ากับเลขสุดท้าย − เลขฐาน', s ->> 'meter_id';
          end if;
          seg_sum := seg_sum + (s ->> 'units')::numeric;
        end loop;
        if abs(seg_sum - (it ->> (t || '_units'))::numeric) > 0.0001 then
          raise exception 'หน่วย% รวมของห้อง % ไม่เท่ากับผลรวมต่อมิเตอร์', t, it ->> 'room_id';
        end if;
      end if;
    end loop;
    select * into cur from public.invoices where cycle = p_cycle and room_id = it ->> 'room_id' and state = 'approved' for update;
    if found then
      if not coalesce((it ->> 'revise')::boolean, false) then raise exception 'ห้อง % อนุมัติแล้ว', it ->> 'room_id'; end if;
      update public.invoices set state = 'superseded' where id = cur.id;
    end if;
    select coalesce(max(revision), 0) + 1 into rev from public.invoices where cycle = p_cycle and room_id = it ->> 'room_id';
    return query insert into public.invoices (cycle, room_id, revision, tenancy_id, tenant_name, recipient_email,
        water_prev, water_curr, water_units, water_rate, electric_prev, electric_curr, electric_units, electric_rate, rent_baht, detail, approved_by)
      values (p_cycle, it ->> 'room_id', rev, (it ->> 'tenancy_id')::bigint, it ->> 'tenant_name', nullif(it ->> 'recipient_email', ''),
        (it ->> 'water_prev')::numeric, (it ->> 'water_curr')::numeric, (it ->> 'water_units')::numeric, (it ->> 'water_rate')::numeric,
        (it ->> 'electric_prev')::numeric, (it ->> 'electric_curr')::numeric, (it ->> 'electric_units')::numeric, (it ->> 'electric_rate')::numeric,
        coalesce((it ->> 'rent_baht')::numeric, 0), coalesce(it -> 'detail', '{}'::jsonb), who)
      returning *;
  end loop;
end $$;
revoke execute on function public.approve_invoices(text, date, jsonb) from public, anon;
grant execute on function public.approve_invoices(text, date, jsonb) to authenticated;

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
       and (max(p.recorded_at) at time zone 'Asia/Bangkok')::date <= (now() at time zone 'Asia/Bangkok')::date - 30
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
