-- กันเงินผิดจากรอบบิล (audit 5 ต.ค. 2569 · WEB-003, WEB-004)
-- 1) ห้ามเลื่อนวันตัดรอบของรอบที่อนุมัติบิลแล้ว หรือรอบที่รอบถัดไปอนุมัติแล้ว
--    (ช่วงของรอบ = (cutoff รอบก่อน, cutoff รอบนี้] · เลื่อนแล้วบิลที่ตรึงไว้ไม่ตรงช่วงใหม่ → หน่วยถูกคิดซ้ำ/ตกหล่นข้ามบิล)
--    เว็บกันไว้แล้วใน saveCycle · ที่นี่กันชั้นฐานข้อมูล
-- 2) invoice_payments.client_key: คีย์ที่เว็บสร้างต่อฟอร์มรับเงิน · unique → กดบันทึกซ้ำจากหน้าต่างเดิม (เช่น เน็ตหลุดตอนโหลดใหม่) ถูกปฏิเสธ

create or replace function public.billing_cycles_cutoff_lock() returns trigger language plpgsql set search_path = '' as $$
declare nxt text := to_char((old.cycle || '-01')::date + interval '1 month', 'YYYY-MM');
begin
  if new.cutoff_date is distinct from old.cutoff_date and exists (
       select 1 from public.invoices i where i.state = 'approved' and i.cycle in (old.cycle, nxt)) then
    raise exception 'cutoff_locked: รอบ % หรือรอบถัดไปอนุมัติบิลแล้ว เปลี่ยนวันตัดรอบไม่ได้', old.cycle;
  end if;
  return new;
end $$;
create trigger billing_cycles_cutoff_lock before update on public.billing_cycles
  for each row execute function public.billing_cycles_cutoff_lock();

alter table public.invoice_payments add column client_key uuid unique;
