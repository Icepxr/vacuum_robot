// ชั้นข้อมูลจริง (Supabase) · mock.js มีหน้าตาเดียวกันไว้พรีวิวบน localhost
import { SUPABASE_URL, SUPABASE_KEY } from './config.js?v=w13';

const PAGE = 1000; // เพดานแถวต่อคำขอของ PostgREST บน Supabase

// ข้อความ error จาก Edge Function (supabase-js ห่อไว้ใน context ของ FunctionsHttpError)
async function fnError(e) { try { const b = await e.context.json(); return b.error || e.message; } catch { return e.message; } }

export function createApi() {
  const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
    auth: { flowType: 'pkce', persistSession: true, detectSessionInUrl: true },
  });
  const must = ({ data, error }) => { if (error) throw new Error(error.message); return data; };

  async function all(table, select, order) {
    const out = [];
    for (let from = 0; ; from += PAGE) {
      let q = sb.from(table).select(select).range(from, from + PAGE - 1);
      if (order) q = q.order(order, { ascending: true });
      const rows = must(await q);
      out.push(...rows);
      if (rows.length < PAGE) return out;
    }
  }

  return {
    mock: false,
    async session() { return must(await sb.auth.getSession()).session; },
    onAuthChange(cb) { sb.auth.onAuthStateChange((event, s) => cb(event, s)); },
    async signIn() {
      const redirectTo = location.origin + location.pathname;
      // prompt=select_account: ให้เลือกบัญชีทุกครั้ง (สลับบัญชีได้ ไม่ติดบัญชี Google ที่ค้างในเบราว์เซอร์)
      must(await sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo, queryParams: { prompt: 'select_account' } } }));
    },
    // supabase-js ตั้งค่าเริ่ม scope = 'global' (ออกทุกอุปกรณ์) → ปุ่มปกติใช้ 'local' = เฉพาะเครื่องนี้
    async signOut(scope = 'local') { must(await sb.auth.signOut({ scope })); },
    // ผู้ชม (กรรมการ): anonymous sign-in · RLS ให้อ่านได้อย่างเดียว (migration 20261002000100)
    async signInGuest() { must(await sb.auth.signInAnonymously()); },
    async isOwner() { return must(await sb.rpc('is_owner')) === true; },

    async loadAll() {
      const [rooms, meters, tenancies, readings, events, rates, cycles, settings, devices, exports, invoices, deliveries, payments, payout] = await Promise.all([
        all('rooms', '*', 'room_id'),
        all('meters', '*', 'meter_id'),
        all('tenancies', '*', 'id'),
        all('meter_readings', '*', 'captured_at'),
        all('reading_events', '*', 'id'),
        all('rates', '*', 'effective_from'),
        all('billing_cycles', '*', 'cycle'),
        sb.from('settings').select('*').maybeSingle().then(must),
        all('devices', 'device_id,revoked_at,last_seen_at,pending_rows,pending_crops,pending_decisions,app_version,disk_free_mb,clock_synced,warn,cam_ok,air_available,cpu_temp_c', 'device_id'),
        sb.from('meter_registry_exports').select('*').order('version', { ascending: false }).limit(1).then(must),
        all('invoices', '*', 'id'),
        all('invoice_delivery_attempts', '*', 'id'),
        all('invoice_payments', '*', 'id'),
        sb.from('payout_settings').select('promptpay_id').maybeSingle().then(must),   // guest อ่านไม่ได้ → null
      ]);
      return { rooms, meters, tenancies, readings, events, rates, cycles, settings: settings || {}, devices, lastExport: exports[0] || null, invoices, deliveries, payments, payout: payout || null };
    },

    // ทุกการตัดสินเรื่องค่ามิเตอร์ = แถวใหม่ใน reading_events (append-only) · trigger กันค่าถอยหลังและอัปเดต cache
    async addEvent(ev) { must(await sb.from('reading_events').insert(ev)); },
    // กรอกเลขเอง (ไม่มีรูป) · สร้างแถว + ยืนยันในธุรกรรมเดียว (migration 20261003000400)
    async addManualReading(meterId, value, at, reason) { return must(await sb.rpc('add_manual_reading', { p_meter_id: meterId, p_value: value, p_at: at, p_reason: reason })); },
    async cropUrl(path) {
      const { data, error } = await sb.storage.from('crops').createSignedUrl(path, 300);
      if (error) throw new Error(error.message);
      return data.signedUrl;
    },

    async addRoom(row) { must(await sb.from('rooms').insert(row)); },
    async updateRoom(id, patch) { must(await sb.from('rooms').update(patch).eq('room_id', id)); },
    async addTenancy(row) { must(await sb.from('tenancies').insert(row)); },
    async updateTenancy(id, patch) { must(await sb.from('tenancies').update(patch).eq('id', id)); },
    async addMeter(row) { must(await sb.from('meters').insert(row)); },
    async updateMeter(id, patch) { must(await sb.from('meters').update(patch).eq('meter_id', id)); },
    async addRate(row) { must(await sb.from('rates').insert(row)); },
    async updateSettings(patch) { must(await sb.from('settings').update(patch).eq('id', true)); },
    async upsertCycle(row) { must(await sb.from('billing_cycles').upsert(row, { onConflict: 'cycle' })); },
    // อนุมัติบิล (ธุรกรรมเดียวทั้งชุด · ฐานข้อมูลคำนวณยอดเอง) · migration 20261003000100
    async approveInvoices(cycle, cutoff, items) { return must(await sb.rpc('approve_invoices', { p_cycle: cycle, p_cutoff: cutoff, p_items: items })); },
    // ส่งอีเมล (Edge Function send-invoices) · รับเงิน (invoice_payments · ยกเลิกได้ ลบไม่ได้) · migration 20261003000200
    async mailStatus() { const { data, error } = await sb.functions.invoke('send-invoices', { method: 'GET' }); if (error) throw new Error(await fnError(error)); return data; },
    async sendInvoices(ids, resend = false) { const { data, error } = await sb.functions.invoke('send-invoices', { body: { invoice_ids: ids, resend } }); if (error) throw new Error(await fnError(error)); return data; },
    async sendTestMail() { const { data, error } = await sb.functions.invoke('send-invoices', { body: { test: true } }); if (error) throw new Error(await fnError(error)); return data; },
    async addPayment(row) { must(await sb.from('invoice_payments').insert(row)); },
    async voidPayment(id, reason) { must(await sb.from('invoice_payments').update({ voided_at: new Date().toISOString(), void_reason: reason }).eq('id', id)); },
    async setPromptpay(id) { must(await sb.from('payout_settings').update({ promptpay_id: id, updated_at: new Date().toISOString() }).eq('id', true)); },
    async newExport() { return must(await sb.from('meter_registry_exports').insert({}).select().single()); },
  };
}
