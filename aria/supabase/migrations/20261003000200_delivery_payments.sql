-- ส่งบิลทางอีเมล + บันทึกรับเงิน (ผู้ใช้ตัดสิน 3 ต.ค. 2569: Gmail ของหอ + App Password · QR พร้อมเพย์ + เจ้าของกดรับเงินเอง)
-- invoice_delivery_attempts ตาม spec §4.2: ทุกครั้งที่พยายามส่ง = 1 แถว · เขียนโดย Edge Function send-invoices (service role) เท่านั้น
-- invoice_payments: ผูกกับ รอบ + ห้อง (ไม่ใช่ฉบับบิล) → ออกฉบับแก้ไขหลังจ่ายแล้ว เงินที่รับไว้ยังนับอยู่
--   append-only · บันทึกผิด = ยกเลิก (voided_at + เหตุผล) ห้ามลบ/แก้ยอด

-- เลขพร้อมเพย์อยู่ตารางแยก อ่านได้เฉพาะเจ้าของ (settings เปิดให้ guest อ่าน → ไม่ใส่เบอร์/เลขบัตรไว้ที่นั่น)
create table public.payout_settings (
  id           boolean primary key default true check (id),
  promptpay_id text check (promptpay_id is null or promptpay_id ~ '^(0[0-9]{9}|[0-9]{13})$'),   -- มือถือ 10 หลัก หรือเลขบัตร/ผู้เสียภาษี 13 หลัก
  updated_at   timestamptz not null default now()
);
insert into public.payout_settings (id) values (true);
alter table public.payout_settings enable row level security;
create policy payout_read   on public.payout_settings for select to authenticated using ((select public.is_owner()));
create policy payout_update on public.payout_settings for update to authenticated using ((select public.is_owner())) with check ((select public.is_owner()));

create table public.invoice_delivery_attempts (
  id           bigint generated always as identity primary key,
  invoice_id   bigint not null references public.invoices(id),
  to_email     text   not null,
  attempted_at timestamptz not null default now(),
  result       text   not null check (result in ('sent', 'failed')),
  message_id   text,
  error        text,
  requested_by text
);
create index on public.invoice_delivery_attempts (invoice_id);
alter table public.invoice_delivery_attempts enable row level security;
create policy delivery_read on public.invoice_delivery_attempts for select to authenticated using ((select public.is_owner()));
create policy guest_read    on public.invoice_delivery_attempts for select to authenticated using ((select public.is_guest()));

create table public.invoice_payments (
  id          bigint generated always as identity primary key,
  cycle       text   not null references public.billing_cycles(cycle),
  room_id     text   not null references public.rooms(room_id) on update cascade,
  invoice_id  bigint not null references public.invoices(id),
  amount      numeric(12,2) not null check (amount > 0),
  paid_on     date   not null,
  method      text   not null check (method in ('promptpay', 'transfer', 'cash', 'other')),
  note        text,
  recorded_by text   not null,                          -- ใส่โดย trigger payments_stamp จาก JWT
  recorded_at timestamptz not null default now(),
  voided_at   timestamptz,
  void_reason text,
  check ((voided_at is null) = (void_reason is null))
);
create index on public.invoice_payments (cycle, room_id);

create or replace function public.payments_guard() returns trigger language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then raise exception 'ลบรายการรับเงินไม่ได้ · ใช้ยกเลิกแทน'; end if;
  if old.voided_at is not null then raise exception 'รายการนี้ยกเลิกไปแล้ว'; end if;
  if new.voided_at is null or (to_jsonb(new) - 'voided_at' - 'void_reason') <> (to_jsonb(old) - 'voided_at' - 'void_reason') then
    raise exception 'แก้รายการรับเงินไม่ได้ · ยกเลิกแล้วบันทึกใหม่';
  end if;
  return new;
end $$;
create trigger payments_guard before update or delete on public.invoice_payments for each row execute function public.payments_guard();
-- recorded_by มาจาก JWT เสมอ (กันส่งชื่อคนอื่นมา)
create or replace function public.payments_stamp() returns trigger language plpgsql set search_path = '' as $$
begin new.recorded_by := lower(coalesce((select auth.jwt()) ->> 'email', '')); new.recorded_at := now(); return new; end $$;
create trigger payments_stamp before insert on public.invoice_payments for each row execute function public.payments_stamp();

alter table public.invoice_payments enable row level security;
create policy payments_read   on public.invoice_payments for select to authenticated using ((select public.is_owner()));
create policy guest_read      on public.invoice_payments for select to authenticated using ((select public.is_guest()));
create policy payments_insert on public.invoice_payments for insert to authenticated with check ((select public.is_owner()));
create policy payments_void   on public.invoice_payments for update to authenticated using ((select public.is_owner())) with check ((select public.is_owner()));
