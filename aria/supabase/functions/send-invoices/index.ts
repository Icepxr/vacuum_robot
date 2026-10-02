// send-invoices — ส่งบิลที่อนุมัติแล้วทางอีเมลจาก Gmail ของหอ (ผู้ใช้ตัดสิน 3 ต.ค. 2569 · spec §4.2 invoice_delivery_attempts)
//   GET  /send-invoices                       → { configured, sender } (เช็คว่าตั้ง secret แล้วหรือยัง · ไม่คืนรหัส)
//   POST /send-invoices {invoice_ids, resend?} → ส่งทีละฉบับ · ทุกครั้งบันทึก 1 แถวใน invoice_delivery_attempts
//   POST /send-invoices {test: true}           → ส่งตัวอย่างถึงอีเมลของเจ้าของที่กดเอง (เช็คการตั้งค่า)
// ยืนยันตัวตน: JWT ของผู้ใช้ (verify_jwt) + ต้องเป็นเจ้าของ (rpc is_owner ด้วยสิทธิ์ของผู้ใช้เอง)
// SMTP: smtp.gmail.com พอร์ต 465 (TLS) ด้วย smtp.ts + mime.ts ที่เขียนเอง (denomailer พับหัวข้อไทยพัง) — Edge Functions ห้ามพอร์ต 25/587 (supabase.com/docs/guides/functions/limits)
// secrets (ผู้ใช้ตั้งเองใน Dashboard → Edge Functions → Secrets): GMAIL_USER, GMAIL_APP_PASSWORD
import { createClient } from "npm:@supabase/supabase-js@2";
import { smtpSend } from "./smtp.ts";
import { buildMessage } from "./mime.ts";
import { render } from "./template.ts";
import QRCode from "npm:qrcode@1.5.4";
import { promptpayPayload } from "./promptpay.ts";

const URL_ = Deno.env.get("SUPABASE_URL")!;
function serviceKey(): string {
  const keys = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (keys) { try { const k = JSON.parse(keys)["default"]; if (k) return k; } catch { /* legacy */ } }
  return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
}
function anonKey(): string {
  const keys = Deno.env.get("SUPABASE_PUBLISHABLE_KEYS");
  if (keys) { try { const k = JSON.parse(keys)["default"]; if (k) return k; } catch { /* legacy */ } }
  return Deno.env.get("SUPABASE_ANON_KEY")!;
}
const db = createClient(URL_, serviceKey(), { auth: { persistSession: false } });
const GMAIL_USER = Deno.env.get("GMAIL_USER") ?? "";
const GMAIL_PASS = (Deno.env.get("GMAIL_APP_PASSWORD") ?? "").replace(/\s+/g, "");   // Google แสดงเป็น 4 กลุ่มมีช่องว่าง
// โลโก้ ARIA สีขาว: ดึงจากเว็บครั้งเดียวต่อการปลุกฟังก์ชัน แล้วแนบเป็นรูปในอีเมล (cid) · ดึงไม่ได้ = ส่งไม่มีโลโก้
let logoP: Promise<Uint8Array | null> | null = null;
const logo = () => logoP ??= fetch("https://aria-th.netlify.app/img/aria-mark-light.png").then(async (r) => r.ok ? new Uint8Array(await r.arrayBuffer()) : null).catch(() => null);
const GAP_MS = 2000;   // หน่วงระหว่างฉบับ กันโดนจัดเป็นสแปม (ไฟล์ 20: 2–5 s/ฉบับ)

const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info", "Access-Control-Allow-Methods": "GET, POST, OPTIONS" };
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

type Inv = Record<string, any>;

async function sendOne(to: string, inv: Inv, dorm: string, promptpay: string | null): Promise<string> {
  const inline: { cid: string; contentType: string; filename: string; bytes: Uint8Array }[] = [];
  const lg = await logo();
  if (lg) inline.push({ cid: "aria-logo", contentType: "image/png", filename: "aria.png", bytes: lg });
  if (promptpay) {
    const png: Uint8Array = await QRCode.toBuffer(promptpayPayload(promptpay, Number(inv.total_baht)), { type: "png", width: 400, margin: 2, errorCorrectionLevel: "M" });
    inline.push({ cid: "promptpay-qr", contentType: "image/png", filename: "promptpay.png", bytes: new Uint8Array(png) });
  }
  const m = render(inv, dorm, promptpay, lg ? "cid:aria-logo" : null);
  const msg = buildMessage({ fromName: dorm, fromAddr: GMAIL_USER, to, subject: m.subject, text: m.text, html: m.html, inline, domain: "aria-th.netlify.app" });
  await smtpSend({ host: "smtp.gmail.com", port: 465, user: GMAIL_USER, pass: GMAIL_PASS, from: GMAIL_USER, to, raw: msg.raw });
  return msg.messageId;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  // เจ้าของเท่านั้น: เรียก is_owner ด้วย JWT ของผู้ใช้เอง (RLS ตัดสิน ไม่ใช่โค้ดนี้)
  const auth = req.headers.get("Authorization") ?? "";
  const asUser = createClient(URL_, anonKey(), { global: { headers: { Authorization: auth } }, auth: { persistSession: false } });
  const { data: owner } = await asUser.rpc("is_owner");
  if (owner !== true) return json(403, { error: "เฉพาะเจ้าของหอ" });
  const { data: u } = await asUser.auth.getUser();
  const who = (u?.user?.email ?? "").toLowerCase();

  const configured = !!(GMAIL_USER && GMAIL_PASS);
  if (req.method === "GET") return json(200, { configured, sender: GMAIL_USER || null });
  if (req.method !== "POST") return json(405, { error: "method" });
  if (!configured) return json(400, { error: "ยังไม่ได้ตั้ง GMAIL_USER / GMAIL_APP_PASSWORD ใน Edge Function secrets" });

  let body: { invoice_ids?: number[]; resend?: boolean; test?: boolean };
  try { body = await req.json(); } catch { return json(400, { error: "body must be JSON" }); }
  const [{ data: st }, { data: pay }] = await Promise.all([
    db.from("settings").select("dorm_name").maybeSingle(),
    db.from("payout_settings").select("promptpay_id").maybeSingle(),
  ]);
  const dorm = st?.dorm_name || "หอพัก";
  const promptpay = pay?.promptpay_id ?? null;
  try {
    if (body.test) {   // ตัวอย่างถึงตัวเอง · ไม่บันทึกลงตาราง
      const sample: Inv = { approved_at: new Date().toISOString(), recipient_email: who, room_id: "A101", cycle: new Date().toISOString().slice(0, 7), revision: 1, tenant_name: "ผู้เช่าตัวอย่าง",
        water_prev: 1231, water_curr: 1244, water_units: 13, water_rate: 18, water_amount: 234, electric_prev: 3502, electric_curr: 3611,
        electric_units: 109, electric_rate: 7, electric_amount: 763, rent_baht: 0, total_baht: 997 };
      await sendOne(who, sample, dorm, promptpay);
      return json(200, { test: true, to: who, qr: !!promptpay });
    }
    const ids = (body.invoice_ids ?? []).filter((x) => Number.isInteger(x)).slice(0, 40);
    if (!ids.length) return json(400, { error: "invoice_ids ว่าง" });
    const { data: invs, error } = await db.from("invoices").select("*").in("id", ids);
    if (error) return json(500, { error: error.message });
    const { data: done } = await db.from("invoice_delivery_attempts").select("invoice_id").in("invoice_id", ids).eq("result", "sent");
    const sentAlready = new Set((done ?? []).map((r) => r.invoice_id));
    const results: unknown[] = [];
    for (const inv of invs ?? []) {
      if (inv.state !== "approved") { results.push({ id: inv.id, skipped: "ไม่ใช่ฉบับปัจจุบัน" }); continue; }
      if (!inv.recipient_email) { results.push({ id: inv.id, skipped: "ไม่มีอีเมล" }); continue; }
      if (sentAlready.has(inv.id) && !body.resend) { results.push({ id: inv.id, skipped: "ส่งแล้ว" }); continue; }
      if (results.length) await new Promise((r) => setTimeout(r, GAP_MS));
      let result = "sent", err: string | null = null, mid: string | null = null;
      try { mid = await sendOne(inv.recipient_email, inv, dorm, promptpay); } catch (e) { result = "failed"; err = String((e as Error)?.message ?? e).slice(0, 500); }
      await db.from("invoice_delivery_attempts").insert({ invoice_id: inv.id, to_email: inv.recipient_email, result, message_id: mid, error: err, requested_by: who });
      results.push({ id: inv.id, result, error: err });
    }
    return json(200, { results });
  } catch (e) {
    return json(502, { error: String((e as Error)?.message ?? e).slice(0, 500) });
  }
});
