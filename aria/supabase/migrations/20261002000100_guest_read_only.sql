-- ผู้ชม (กรรมการ) แบบ guest: ปุ่ม "View as guest" → Supabase anonymous sign-in → อ่านได้อย่างเดียว (ผู้ใช้ตัดสิน 2 ต.ค. 2569)
-- เห็นข้อมูลจริงทั้งหมด (รวมชื่อ/อีเมลผู้เช่า) ตามที่ผู้ใช้เลือก · ไม่เห็นตาราง owners
-- เขียนไม่ได้เลย: นโยบายเขียนทุกตัวยังเป็น is_owner() · policy ด้านล่างเป็น SELECT อย่างเดียว
-- ต้องเปิด Authentication → Sign In / Providers → "Allow anonymous sign-ins" ใน Dashboard ด้วย (ตั้งผ่าน SQL ไม่ได้)

create or replace function public.is_guest() returns boolean
language sql stable set search_path = '' as $$
  select coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false);
$$;

create policy guest_read on public.rooms                  for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.meters                 for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.tenancies              for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.meter_readings         for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.reading_events         for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.rates                  for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.billing_cycles         for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.settings               for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.devices                for select to authenticated using ((select public.is_guest()));
create policy guest_read on public.meter_registry_exports for select to authenticated using ((select public.is_guest()));

-- รูป crop: สร้าง signed URL ได้ (ต้องมีสิทธิ์ SELECT บน storage.objects)
create policy crops_guest_read on storage.objects for select to authenticated
  using (bucket_id = 'crops' and (select public.is_guest()));
