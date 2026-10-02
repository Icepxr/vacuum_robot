// purge-crops — ลบรูป crop ที่ถึงเกณฑ์ (ผู้ใช้เลือกแบบ ข 3 ต.ค. 2569 · migration 20261003000500_crop_purge.sql)
//   เกณฑ์อยู่ในฐานข้อมูล (crops_due_for_purge): รับเงินครบ + 30 วัน หรือรูปอายุ > 12 เดือน · ตัวเลขไม่ลบ
//   pg_cron เรียกวันละครั้ง · verify_jwt = false: ไม่รับ input ลบได้เฉพาะรูปที่ถึงเกณฑ์แล้ว → คนนอกเรียกได้แค่ทำให้ลบเร็วขึ้นไม่เกิน 1 วัน
import { createClient } from "npm:@supabase/supabase-js@2";

function serviceKey(): string {
  const keys = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (keys) { try { const k = JSON.parse(keys)["default"]; if (k) return k; } catch { /* legacy */ } }
  return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
}
const db = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey(), { auth: { persistSession: false } });
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method !== "POST") return json(405, { error: "method" });
  const { data: due, error } = await db.rpc("crops_due_for_purge", { p_limit: 500 });
  if (error) return json(500, { error: error.message });
  if (!due?.length) return json(200, { purged: 0 });
  const paths = [...new Set(due.map((r: { crop_path: string }) => r.crop_path))];
  // ไฟล์ที่ไม่มีอยู่แล้วไม่ทำให้ remove ล้ม → ถือว่าลบแล้วเช่นกัน
  const rm = await db.storage.from("crops").remove(paths);
  if (rm.error) return json(502, { error: `storage: ${rm.error.message}` });
  const ids = due.map((r: { id: number }) => r.id);
  const up = await db.from("meter_readings").update({ crop_path: null, crop_expired_at: new Date().toISOString() }).in("id", ids);
  if (up.error) return json(500, { error: up.error.message, removed_files: rm.data?.length ?? 0 });
  const why: Record<string, number> = {};
  for (const r of due as { why: string }[]) why[r.why] = (why[r.why] ?? 0) + 1;
  return json(200, { purged: ids.length, removed_files: rm.data?.length ?? 0, why });
});
