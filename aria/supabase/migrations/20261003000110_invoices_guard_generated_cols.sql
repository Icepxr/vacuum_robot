-- ดึงกลับจากคลาวด์ 13 ต.ค. 2026 (supabase_migrations.schema_migrations version 20261002172830 · ชื่อ invoices_guard_generated_cols)
-- ใช้กับ aria-mrc แล้ว — ไฟล์นี้มีไว้ให้ repo สร้างฐานข้อมูลได้ครบ · ลำดับ: หลัง 20261003000100_invoices
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
