-- ขั้นอนุมัติและตรึงยอดบิล (spec aria-data-spec-v1 §4.2 `invoices` · แบบ backoffice v1 §บิล) · 3 ต.ค. 2569
-- ต่างจาก spec: ไม่เก็บ state 'draft' — ร่าง = หน้าพรีวิวที่คำนวณสด · ตารางนี้มีแค่ approved / superseded
-- กติกา: แถว approved ห้ามแก้/ลบ · แก้ = ออกฉบับใหม่ (revision + 1) และฉบับเดิมเปลี่ยนเป็น superseded ในธุรกรรมเดียว
-- ยอดเงินคำนวณในฐานข้อมูล (generated) จากหน่วย × อัตรา + ค่าเช่า → ไม่พึ่งการปัดเศษของเบราว์เซอร์

create table public.invoices (
  id              bigint generated always as identity primary key,
  cycle           text   not null references public.billing_cycles(cycle),
  room_id         text   not null references public.rooms(room_id) on update cascade,
  revision        int    not null check (revision >= 1),
  tenancy_id      bigint references public.tenancies(id),
  tenant_name     text   not null,
  recipient_email text,
  state           text   not null default 'approved' check (state in ('approved', 'superseded')),
  water_prev      numeric(14,4), water_curr numeric(14,4),
  water_units     numeric(14,4) not null check (water_units >= 0),
  water_rate      numeric(10,2) not null check (water_rate > 0),
  electric_prev   numeric(14,4), electric_curr numeric(14,4),
  electric_units  numeric(14,4) not null check (electric_units >= 0),
  electric_rate   numeric(10,2) not null check (electric_rate > 0),
  rent_baht       numeric(10,2) not null default 0 check (rent_baht >= 0),
  water_amount    numeric(12,2) generated always as (round(water_units * water_rate, 2)) stored,
  electric_amount numeric(12,2) generated always as (round(electric_units * electric_rate, 2)) stored,
  total_baht      numeric(12,2) generated always as (round(water_units * water_rate, 2) + round(electric_units * electric_rate, 2) + rent_baht) stored,
  detail          jsonb  not null default '{}'::jsonb,   -- ช่วงมิเตอร์ (เปลี่ยนมิเตอร์กลางรอบ) · reading ids ที่ใช้
  approved_by     text   not null,
  approved_at     timestamptz not null default now(),
  superseded_at   timestamptz,
  unique (cycle, room_id, revision)
);
create unique index invoices_one_current on public.invoices (cycle, room_id) where state = 'approved';

-- แถวที่อนุมัติแล้วห้ามแก้ ยกเว้นเปลี่ยนเป็น superseded (คอลัมน์อื่นต้องเท่าเดิม) · ห้ามลบ: ไม่มี policy DELETE (RLS กรองทิ้ง) + trigger กันอีกชั้น
-- ทดสอบใน transaction ที่ย้อนกลับ 3 ต.ค.: อนุมัติ 4,491.38 · อนุมัติซ้ำถูกปฏิเสธ · revise → rev1 superseded/rev2 approved · แก้/ฟื้น/ลบ ไม่ได้ · guest อ่านได้ อนุมัติไม่ได้
create or replace function public.invoices_guard() returns trigger language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then raise exception 'ลบบิลไม่ได้ (เก็บประวัติ) · ออกฉบับแก้ไขแทน'; end if;
  if old.state = 'superseded' then raise exception 'บิลฉบับที่ถูกแทนแล้วแก้ไม่ได้'; end if;
  -- คอลัมน์ generated (ยอดเงิน) ยังเป็น null ใน NEW ตอน BEFORE trigger → ตัดออกจากการเทียบ (คำนวณจากคอลัมน์ที่เทียบอยู่แล้ว)
  if new.state <> 'superseded' or (to_jsonb(new) - 'state' - 'superseded_at' - 'water_amount' - 'electric_amount' - 'total_baht')
       <> (to_jsonb(old) - 'state' - 'superseded_at' - 'water_amount' - 'electric_amount' - 'total_baht') then
    raise exception 'บิลที่อนุมัติแล้วแก้ไม่ได้ · ออกฉบับแก้ไขแทน';
  end if;
  new.superseded_at := now();
  return new;
end $$;
create trigger invoices_guard before update or delete on public.invoices for each row execute function public.invoices_guard();

alter table public.invoices enable row level security;
create policy invoices_read  on public.invoices for select to authenticated using ((select public.is_owner()));
create policy guest_read     on public.invoices for select to authenticated using ((select public.is_guest()));
create policy invoices_write on public.invoices for insert to authenticated with check ((select public.is_owner()));
create policy invoices_super on public.invoices for update to authenticated using ((select public.is_owner())) with check ((select public.is_owner()));

-- อนุมัติหลายห้องในธุรกรรมเดียว (ทั้งหมดหรือไม่เลย) · items = [{room_id, tenancy_id, tenant_name, recipient_email,
--   water_prev, water_curr, water_units, water_rate, electric_*, rent_baht, detail, revise}]
-- revise = true → ฉบับเดิมของห้องนั้นกลายเป็น superseded แล้วออก revision ใหม่ · ไม่ส่ง revise แต่มีฉบับเดิม = error
-- ถ้ารอบยังไม่มีแถวใน billing_cycles สร้างให้ด้วยวันตัดรอบที่ใช้คำนวณ (ตรึงไว้ ไม่ขยับตามค่าตั้งภายหลัง)
create or replace function public.approve_invoices(p_cycle text, p_cutoff date, p_items jsonb) returns setof public.invoices
language plpgsql set search_path = '' as $$
declare it jsonb; cur public.invoices; rev int; who text := lower(coalesce((select auth.jwt()) ->> 'email', ''));
begin
  if not public.is_owner() then raise exception 'เฉพาะเจ้าของหอ'; end if;
  insert into public.billing_cycles (cycle, cutoff_date) values (p_cycle, p_cutoff) on conflict (cycle) do nothing;
  for it in select * from jsonb_array_elements(p_items) loop
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
