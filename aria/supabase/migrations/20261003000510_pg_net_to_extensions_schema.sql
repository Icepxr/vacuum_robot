-- ดึงกลับจากคลาวด์ 13 ต.ค. 2026 (supabase_migrations.schema_migrations version 20261002190118 · ชื่อ pg_net_to_extensions_schema)
-- ใช้กับ aria-mrc แล้ว — ไฟล์นี้มีไว้ให้ repo สร้างฐานข้อมูลได้ครบ · ลำดับ: หลัง 20261003000500_crop_purge
drop extension if exists pg_net;
create extension pg_net schema extensions;
