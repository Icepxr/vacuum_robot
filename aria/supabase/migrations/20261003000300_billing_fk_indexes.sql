-- index ให้ foreign key ของตารางบิล/รับเงิน (Supabase performance advisor: unindexed_foreign_keys · 3 ต.ค. 2569)
create index if not exists invoices_room_idx on public.invoices (room_id);
create index if not exists invoices_tenancy_idx on public.invoices (tenancy_id);
create index if not exists invoice_payments_invoice_idx on public.invoice_payments (invoice_id);
create index if not exists invoice_payments_room_idx on public.invoice_payments (room_id);
