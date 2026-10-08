// ingest — ทางเดียวที่ Pi เขียนข้อมูลขึ้นคลาวด์ (D6 · design/aria-data-spec-v1.md §3)
//   POST /ingest/readings            {rows: [...≤50], heartbeat?: {...}}
//   PUT  /ingest/crops/<local_id>    body = JPEG
//   GET  /ingest/registry?have_sha=… ทะเบียนห้อง+มิเตอร์ให้ Pi (8 ต.ค. · แทนการ export meters.json แล้ว scp)
//        POST /readings แนบ registry_sha กลับไปด้วย → Pi เรียก GET เฉพาะตอน sha เปลี่ยน (ไม่เพิ่มจำนวนครั้งที่เรียกฟังก์ชัน)
// ยืนยันตัวตนด้วย header x-device-token (ไม่ใช่ JWT → deploy ด้วย verify_jwt=false)
// ฝั่งคลาวด์เก็บแค่ SHA-256 ของ token ในตาราง devices · device_id มาจาก token เท่านั้น ไม่รับจาก payload
import { createClient } from "npm:@supabase/supabase-js@2";

const MAX_CROP_BYTES = 1_048_576; // เพดานกันพลาด = file_size_limit ของ bucket · crop จริงคาด ≈ 30 kB [ประมาณการ V9]
const LOCAL_ID = /^[0-9a-f]{12}$/;

function serviceKey(): string {
  const keys = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (keys) {
    try { const k = JSON.parse(keys)["default"]; if (k) return k; } catch { /* ใช้ legacy ต่อ */ }
  }
  return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
}
const db = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey(), { auth: { persistSession: false } });

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function authDevice(req: Request): Promise<string | null> {
  const token = req.headers.get("x-device-token") ?? "";
  if (token.length < 32) return null;
  const { data, error } = await db.from("devices").select("device_id, revoked_at")
    .eq("token_sha256", await sha256Hex(token)).maybeSingle();
  if (error || !data || data.revoked_at) return null;
  return data.device_id;
}

// ── ทะเบียนลง Pi ──
// ห้องทั้งหมด (รวมห้องที่ยังไม่มีมิเตอร์ — ผู้ใช้ 8 ต.ค.) + มิเตอร์ที่ใช้งานอยู่วันนี้ตามเวลาไทย
// กติกา "ใช้งานอยู่" = meterActiveOn ใน aria/web/js/logic.js: installed_at <= วันนี้ < retired_at
type Registry = { rooms: { room_id: string; floor: string | null }[]; meters: Record<string, unknown>[] };

const todayBkk = () => new Date(Date.now() + 7 * 3600_000).toISOString().slice(0, 10);
const natural = (a: string, b: string) => a.localeCompare(b, "en", { numeric: true });

async function buildRegistry(): Promise<{ reg: Registry; sha: string }> {
  const [rooms, meters] = await Promise.all([
    db.from("rooms").select("room_id, floor"),
    db.from("meters").select("meter_id, room_id, type, digits, decimals, waypoint, lift_mm, installed_at, retired_at"),
  ]);
  if (rooms.error) throw rooms.error;
  if (meters.error) throw meters.error;
  const d = todayBkk();
  const reg: Registry = {
    rooms: rooms.data.map((r) => ({ room_id: r.room_id, floor: r.floor ?? null })).sort((a, b) => natural(a.room_id, b.room_id)),
    meters: meters.data.filter((m) => m.installed_at <= d && (!m.retired_at || d < m.retired_at))
      .sort((a, b) => natural(a.room_id, b.room_id) || a.type.localeCompare(b.type))
      .map((m) => ({ meter_id: m.meter_id, room: m.room_id, type: m.type, digits: m.digits, decimals: m.decimals,
                     waypoint: m.waypoint ?? null, lift_mm: m.lift_mm ?? null })),
  };
  return { reg, sha: await sha256Hex(JSON.stringify(reg)) };
}

async function getRegistry(req: Request, device: string): Promise<Response> {
  const { reg, sha } = await buildRegistry();
  if (new URL(req.url).searchParams.get("have_sha") === sha) return json(200, { unchanged: true, sha });
  // เลขรุ่นต่อเนื่องกับปุ่มส่งออกบนเว็บ (ตารางเดียวกัน) · เนื้อหาเดิม = รุ่นเดิม · เปลี่ยน = ออกรุ่นใหม่
  const last = await db.from("meter_registry_exports").select("version, exported_at, content_sha256")
    .order("version", { ascending: false }).limit(1).maybeSingle();
  if (last.error) return json(500, { error: last.error.message });
  let row = last.data;
  if (!row || row.content_sha256 !== sha) {
    const ins = await db.from("meter_registry_exports").insert({ content_sha256: sha, exported_via: `device:${device}` })
      .select("version, exported_at, content_sha256").single();
    if (ins.error) return json(500, { error: ins.error.message });
    row = ins.data;
  }
  return json(200, { registry_version: row.version, exported_at: row.exported_at, sha, ...reg });
}

async function postReadings(req: Request, device: string): Promise<Response> {
  let body: { rows?: unknown; heartbeat?: unknown };
  try { body = await req.json(); } catch { return json(400, { error: "body must be JSON" }); }
  const rows = body.rows ?? [];
  if (!Array.isArray(rows) || rows.length > 50) return json(400, { error: "rows must be an array of ≤ 50" });

  let result = { accepted: [] as string[], rejected: [] as unknown[] };
  if (rows.length) {
    const { data, error } = await db.rpc("ingest_readings", { p_device: device, p_rows: rows });
    if (error) return json(500, { error: error.message });
    result = data;
  }
  // heartbeat พังต้องไม่ทำให้แถวที่รับแล้วถูกนับว่าล้ม — ไม่งั้น Pi ส่งแถวชุดเดิมวนไม่จบถ้า heartbeat เสียถาวร
  let heartbeat_error: string | undefined;
  if (body.heartbeat && typeof body.heartbeat === "object") {
    const { error } = await db.rpc("ingest_heartbeat", { p_device: device, p_hb: body.heartbeat });
    if (error) heartbeat_error = error.message;
  }
  // sha ของทะเบียนตอนนี้ — Pi เทียบกับของตัวเองแล้วค่อย GET /registry ถ้าต่าง · พังก็ไม่กระทบแถวที่รับแล้ว
  let registry_sha: string | undefined;
  try { registry_sha = (await buildRegistry()).sha; } catch { /* ไม่ส่ง sha รอบนี้ */ }
  const out = { ...result, ...(registry_sha ? { registry_sha } : {}) };
  return json(200, heartbeat_error ? { ...out, heartbeat_error } : out);
}

async function putCrop(req: Request, device: string, localId: string): Promise<Response> {
  if (!LOCAL_ID.test(localId)) return json(400, { error: "bad local_id" });
  // แถวต้องขึ้นมาก่อนรูป — ใช้พิสูจน์ว่า local_id เป็นของอุปกรณ์นี้ ก่อนเขียนอะไรลง Storage
  const { data: row, error: qerr } = await db.from("meter_readings")
    .select("device_id, crop_expired_at").eq("local_id", localId).maybeSingle();
  if (qerr) return json(500, { error: qerr.message });
  if (!row) return json(409, { error: "reading not uploaded yet — send the row first" });
  if (row.device_id !== device) return json(403, { error: "local_id belongs to another device" });
  if (row.crop_expired_at) return json(410, { error: "crop expired (F8) — not re-uploading" });

  const declared = Number(req.headers.get("content-length") ?? "0");
  if (declared > MAX_CROP_BYTES) return json(413, { error: `crop must be 1..${MAX_CROP_BYTES} bytes` });   // ไม่อ่านทั้งก้อนเข้าหน่วยความจำก่อนรู้ขนาด
  const bytes = new Uint8Array(await req.arrayBuffer());
  if (bytes.length === 0 || bytes.length > MAX_CROP_BYTES) return json(413, { error: `crop must be 1..${MAX_CROP_BYTES} bytes` });
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) return json(415, { error: "not a JPEG" });

  const path = `${device}/${localId}.jpg`;
  const up = await db.storage.from("crops").upload(path, bytes, { contentType: "image/jpeg", upsert: true });
  if (up.error) return json(500, { error: up.error.message });
  const { data: ok, error } = await db.rpc("ingest_crop_attach", { p_device: device, p_local_id: localId, p_path: path });
  if (error) return json(500, { error: error.message });
  return json(200, { local_id: localId, crop_path: path, attached: ok });
}

Deno.serve(async (req) => {
  const device = await authDevice(req);
  if (!device) return json(401, { error: "unknown or revoked device token" });

  const parts = new URL(req.url).pathname.split("/").filter(Boolean);   // ["ingest", "readings"] | ["ingest","crops","<id>"] | ["ingest","registry"]
  const i = parts.indexOf("ingest");
  const route = parts.slice(i + 1);
  try {
    if (req.method === "POST" && route.length === 1 && route[0] === "readings") return await postReadings(req, device);
    if (req.method === "PUT" && route.length === 2 && route[0] === "crops") return await putCrop(req, device, route[1]);
    if (req.method === "GET" && route.length === 1 && route[0] === "registry") return await getRegistry(req, device);
    return json(404, { error: "not found" });
  } catch (e) {
    return json(500, { error: String(e) });
  }
});
