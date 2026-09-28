-- ARIA core schema · โปรเจกต์ Supabase aria-mrc (brvlfwrmkoyjnrhvfesq) เท่านั้น
-- ⚠ ห้ามรันใน MCCMU's Project
-- ที่มา: design/aria-data-spec-v1.md (ตัดสิน F1–F10 วันที่ 28 ก.ย. 2569)
-- ขอบเขตรอบนี้: ท่อ Pi → คลาวด์ + ทะเบียน + การยืนยันค่า · บิล/อีเมล (invoices, invoice_delivery_attempts) รอขั้นบิล

create extension if not exists btree_gist with schema extensions;

-- ───────────────────────── สิทธิ์เจ้าของหอ ─────────────────────────
create table public.owners (
  email     text primary key check (email = lower(email) and email like '%@%'),
  added_at  timestamptz not null default now()
);

-- ล็อกอิน Google ได้ไม่พอ ต้องอยู่ใน owners ด้วย (แบบ v1 §6)
create or replace function public.is_owner() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.owners o
    where o.email = lower(coalesce((select auth.jwt()) ->> 'email', ''))
  );
$$;
revoke execute on function public.is_owner() from public, anon;
grant execute on function public.is_owner() to authenticated;

-- ───────────────────────── ฝั่งหุ่น ─────────────────────────
create table public.devices (
  device_id          text primary key check (device_id ~ '^[A-Z0-9][A-Z0-9-]{1,31}$'),
  token_sha256       text not null unique check (token_sha256 ~ '^[0-9a-f]{64}$'),  -- ไม่เก็บ token จริง
  revoked_at         timestamptz,
  created_at         timestamptz not null default now(),
  -- heartbeat ล่าสุด · UI ต้องเขียนว่า "ข้อมูลล่าสุดเมื่อ …" ไม่ใช่ "ออนไลน์"
  last_seen_at       timestamptz,
  pending_rows       integer,
  pending_crops      integer,
  pending_decisions  integer,
  app_version        text,
  disk_free_mb       integer,
  clock_synced       boolean,
  warn               text,     -- รหัสเดียวกับ $D ของจอกลม: NOIP HOT NOCAM DISK NOAIR · '' = ปกติ
  cam_ok             boolean,
  air_available      boolean,
  cpu_temp_c         real
);

-- ───────────────────────── ทะเบียน ─────────────────────────
create table public.rooms (
  room_id  text primary key check (room_id ~ '^[A-Za-z0-9]{1,10}$'),
  floor    text,
  note     text,
  is_demo  boolean not null default false
);

create table public.meters (
  meter_id     text primary key check (meter_id ~ '^[WE]-[A-Za-z0-9]{1,10}-[0-9]{2}$'),  -- W-204-01 · เปลี่ยนตัว = -02
  room_id      text not null references public.rooms on update cascade,
  type         text not null check (type in ('water','electric')),
  digits       smallint not null check (digits between 1 and 9),
  decimals     smallint not null default 0 check (decimals between 0 and 4),
  installed_at date not null,
  retired_at   date,
  start_value  numeric not null default 0 check (start_value >= 0),
  end_value    numeric check (end_value >= 0),
  waypoint     jsonb,
  lift_mm      integer,
  is_demo      boolean not null default false,
  check (retired_at is null or retired_at >= installed_at),
  check (left(meter_id, 1) = case type when 'water' then 'W' else 'E' end),
  -- ห้องเดียวกัน ชนิดเดียวกัน ช่วงติดตั้งห้ามซ้อน
  exclude using gist (room_id with =, type with =, daterange(installed_at, retired_at, '[)') with &&)
);
create index meters_room_idx on public.meters (room_id);

create table public.meter_registry_exports (
  version      integer generated always as identity primary key,
  exported_at  timestamptz not null default now(),
  exported_by  uuid default auth.uid()
);

create table public.tenancies (
  id           bigint generated always as identity primary key,
  room_id      text not null references public.rooms on update cascade,
  tenant_name  text not null check (length(trim(tenant_name)) > 0),
  email        text check (email is null or email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),  -- ไม่มี = ดูบิลได้ ส่งไม่ได้
  start_date   date not null,
  end_date     date,
  rent_baht    numeric(10,2) check (rent_baht is null or rent_baht >= 0),
  is_demo      boolean not null default false,
  created_at   timestamptz not null default now(),
  check (end_date is null or end_date >= start_date),
  exclude using gist (room_id with =, daterange(start_date, end_date, '[]') with &&)
);
create index tenancies_room_idx on public.tenancies (room_id);
-- ไม่มีเบอร์โทร (F5)

create table public.rates (
  id              bigint generated always as identity primary key,
  type            text not null check (type in ('water','electric')),
  baht_per_unit   numeric(10,2) not null check (baht_per_unit > 0),
  effective_from  date not null,
  created_at      timestamptz not null default now(),
  created_by      uuid default auth.uid(),
  unique (type, effective_from)
);  -- append-only: ไม่มี policy update/delete

create table public.billing_cycles (
  cycle         text primary key check (cycle ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  cutoff_date   date not null unique,
  state         text not null default 'open' check (state in ('open','closed')),
  include_rent  boolean not null default false   -- F7 ค่าเช่าเป็น option ปิดเป็นค่าเริ่ม
);

create table public.settings (
  id                  boolean primary key default true check (id),   -- แถวเดียว
  dorm_name           text,
  timezone            text not null default 'Asia/Bangkok',
  sender_email        text,
  default_cutoff_day  smallint check (default_cutoff_day between 1 and 28)  -- null = สิ้นเดือน (F6)
);
insert into public.settings (id) values (true);

-- ───────────────────────── ค่าที่หุ่นอ่าน ─────────────────────────
create table public.meter_readings (
  id                 bigint generated always as identity primary key,
  local_id           text not null unique check (local_id ~ '^[0-9a-f]{12}$'),
  device_id          text not null references public.devices,
  captured_at        timestamptz not null,           -- นาฬิกา Pi · ใช้ตัดสินรอบบิล
  decided_at         timestamptz,                    -- คนขับกด "เก็บ" (F10)
  received_at        timestamptz not null default now(),
  clock_synced       boolean,                        -- F1
  run_id             text,
  room_id            text,                           -- ที่คนขับเลือก · ไม่ FK: ห้องอาจยังไม่อยู่ในทะเบียน
  meter_type         text check (meter_type in ('water','electric')),
  meter_id           text,                           -- ข้อเท็จจริงจากหุ่น · ไม่ FK: ทะเบียนบน Pi อาจเก่ากว่าคลาวด์
  registry_version   integer,
  raw_text           text,
  value              numeric,                        -- null = อ่านไม่ออก ไม่ใช่ 0
  confidence         real check (confidence is null or confidence between 0 and 1),
  ocr_engine         text,
  source             text,
  image_path         text,                           -- path บน Pi ไม่ใช่ URL
  air                jsonb,                          -- F3
  crop_path          text,                           -- ใส่โดย ingest หลังอัปโหลด crop เท่านั้น
  crop_expired_at    timestamptz,                    -- F8 งานลบรูปอายุ 12 เดือนใส่
  -- cache ของ reading_events ล่าสุด · trigger เขียน ไม่มีใครเขียนตรง
  status             text not null default 'ocr' check (status in ('ocr','confirmed','rejected')),
  confirmed_value    numeric,
  assigned_meter_id  text references public.meters,
  is_demo            boolean not null default false
);
create index meter_readings_captured_idx on public.meter_readings (captured_at);
create index meter_readings_meter_idx on public.meter_readings (coalesce(assigned_meter_id, meter_id), captured_at);
create index meter_readings_device_idx on public.meter_readings (device_id);
create index meter_readings_assigned_idx on public.meter_readings (assigned_meter_id);

create table public.reading_events (
  id               bigint generated always as identity primary key,
  reading_id       bigint not null references public.meter_readings on delete cascade,
  event            text not null check (event in ('confirmed','corrected','rejected','assigned')),
  confirmed_value  numeric check (confirmed_value is null or confirmed_value >= 0),
  meter_id         text references public.meters,
  reason           text,
  actor            uuid,
  at               timestamptz not null default now(),
  check (event not in ('confirmed','corrected') or confirmed_value is not null),
  check (event <> 'corrected' or length(trim(coalesce(reason, ''))) > 0),
  check (event <> 'assigned' or meter_id is not null)
);
create index reading_events_reading_idx on public.reading_events (reading_id);
create index reading_events_meter_idx on public.reading_events (meter_id);

-- ก่อน insert: ตั้ง actor/at เอง + บังคับค่ายืนยันไม่ถอยหลังในมิเตอร์ตัวเดียวกัน
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
  end if;
  return null;
end $$;

create trigger reading_events_bi before insert on public.reading_events
  for each row execute function public.reading_events_before_insert();
create trigger reading_events_ai after insert on public.reading_events
  for each row execute function public.reading_events_after_insert();
revoke execute on function public.reading_events_before_insert() from public, anon, authenticated;
revoke execute on function public.reading_events_after_insert() from public, anon, authenticated;

-- ───────────────────────── RLS ─────────────────────────
alter table public.owners                 enable row level security;
alter table public.devices                enable row level security;
alter table public.rooms                  enable row level security;
alter table public.meters                 enable row level security;
alter table public.meter_registry_exports enable row level security;
alter table public.tenancies              enable row level security;
alter table public.rates                  enable row level security;
alter table public.billing_cycles         enable row level security;
alter table public.settings               enable row level security;
alter table public.meter_readings         enable row level security;
alter table public.reading_events         enable row level security;

-- anon ไม่มี policy ใดเลย = ทำอะไรไม่ได้ · เจ้าของหอผ่าน is_owner()
create policy owners_read   on public.owners   for select to authenticated using ((select public.is_owner()));
create policy devices_read  on public.devices  for select to authenticated using ((select public.is_owner()));

create policy rooms_all     on public.rooms     for all to authenticated using ((select public.is_owner())) with check ((select public.is_owner()));
create policy meters_all    on public.meters    for all to authenticated using ((select public.is_owner())) with check ((select public.is_owner()));
create policy tenancies_all on public.tenancies for all to authenticated using ((select public.is_owner())) with check ((select public.is_owner()));
create policy cycles_all    on public.billing_cycles for all to authenticated using ((select public.is_owner())) with check ((select public.is_owner()));

create policy settings_read   on public.settings for select to authenticated using ((select public.is_owner()));
create policy settings_update on public.settings for update to authenticated using ((select public.is_owner())) with check ((select public.is_owner()));

-- append-only: อ่าน + เพิ่มได้ ไม่มี update/delete
create policy rates_read    on public.rates for select to authenticated using ((select public.is_owner()));
create policy rates_insert  on public.rates for insert to authenticated with check ((select public.is_owner()));
create policy exports_read   on public.meter_registry_exports for select to authenticated using ((select public.is_owner()));
create policy exports_insert on public.meter_registry_exports for insert to authenticated with check ((select public.is_owner()));
create policy events_read   on public.reading_events for select to authenticated using ((select public.is_owner()));
create policy events_insert on public.reading_events for insert to authenticated with check ((select public.is_owner()));

-- ค่าที่หุ่นอ่าน: เจ้าของอ่านได้อย่างเดียว · หุ่นเขียนผ่าน ingest_* (service role)
create policy readings_read on public.meter_readings for select to authenticated using ((select public.is_owner()));
