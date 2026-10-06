// ข้อมูลจำลองในหน่วยความจำ · เปิดได้เฉพาะ localhost ด้วย ?mock (ดู app.js) · ไม่แตะเครือข่าย
// ชุดเดียวกับ migrations 0300_demo_seed + 20260929000100_demo_readings เพื่อให้พรีวิวหน้าตาตรงกับของจริง
import { readingMeterId, meterIndex, shiftCycle } from './logic.js?v=w15';

export function createMockApi() {
  const prev = { '101': [1231, 3502], '102': [987, 2140], '103': [1518, 2901], '104': [1192, 3271], '105': [1402, 5012], '106': [802, 1320], '107': [1105, 4521], '108': [1351, 3204], '109': [890, 2750], '110': [1120, 2876] };
  const names = { '101': ['วราภรณ์ ใจดี', 'waraporn@example.com', 3500], '102': ['ศักดิ์ชัย แสนสุข', 'sakchai@example.com', 3700], '103': ['ธนพร พรมมา', 'thanaporn@example.com', 3600], '104': ['นิภาพร สุขใจ', 'nipaporn@example.com', 3400], '105': ['กิตติพงษ์ รัตนวงศ์', 'kittipong@example.com', 3800], '107': ['พิมพ์ชนก วงศ์ดี', 'pimchanok@example.com', 3500], '108': ['นรินทร์ คำมา', 'narin@example.com', 3900], '109': ['รัชนี แก้วตา', 'ratchanee@example.com', 3500], '110': ['สุรเชษฐ์ จันทร์ดี', null, 3300] };
  const d = { rooms: [], meters: [], tenancies: [], readings: [], events: [], rates: [], cycles: [], settings: { id: true, dorm_name: null, timezone: 'Asia/Bangkok', sender_email: null, default_cutoff_day: null }, devices: [], lastExport: null, invoices: [], deliveries: [], payments: [], payout: { promptpay_id: null } };
  let tid = 0, rid = 0, eid = 0, ver = 0;
  for (const room of Object.keys(prev)) {
    d.rooms.push({ room_id: room, floor: room[0], note: null, is_demo: true });
    ['water', 'electric'].forEach((type, i) => d.meters.push({ meter_id: `${i ? 'E' : 'W'}-${room}-01`, room_id: room, type, digits: 5, decimals: 0, installed_at: '2026-01-01', retired_at: null, start_value: prev[room][i], end_value: null, waypoint: null, lift_mm: null, is_demo: true }));
    if (names[room]) d.tenancies.push({ id: ++tid, room_id: room, tenant_name: names[room][0], email: names[room][1], start_date: '2026-01-01', end_date: null, rent_baht: names[room][2], is_demo: true });
  }
  const ocr = [[1, '101', 'water', 1244, .97], [2, '101', 'electric', 3611, .96], [3, '102', 'water', 998, .98], [4, '102', 'electric', 2233, .95], [5, '103', 'water', 1532, .95], [6, '103', 'electric', 2977, .94], [7, '104', 'water', 1205, .91], [8, '104', 'electric', 3340, .89], [9, '105', 'water', 1477, .41], [10, '105', 'electric', 5096, .96], [11, '106', 'water', 811, .93], [12, '106', 'electric', 1352, .94], [13, '107', 'water', 1117, .96], [14, '107', 'electric', 4602, .97], [15, '108', 'water', 1362, .94], [16, '108', 'electric', 3184, .83], [19, '110', 'water', 1133, .95], [20, '110', 'electric', 2950, .97]];
  const at = n => new Date(Date.UTC(2026, 8, 20, 3, 0) + n * 180000).toISOString();
  const mk = (n, room, type, value, conf, meter) => ({ id: ++rid, local_id: rid.toString(16).padStart(12, '0'), device_id: 'DEMO-01', captured_at: at(n), decided_at: at(n), received_at: at(n + 60), clock_synced: room !== '107', run_id: null, room_id: room, meter_type: type, meter_id: meter, registry_version: null, raw_text: String(value), value, confidence: conf, ocr_engine: 'sevenseg', source: 'demo', image_path: null, air: n % 3 ? null : { eco2_ppm: 620 + n * 10, tvoc_ppb: 80 + n, aqi: 2, temp_c: 29.5, rh_pct: 58, validity: 0 }, crop_path: null, crop_expired_at: null, status: 'ocr', confirmed_value: null, assigned_meter_id: null, is_demo: true });
  for (const [n, room, type, v, c] of ocr) d.readings.push(mk(n, room, type, v, c, `${type === 'water' ? 'W' : 'E'}-${room}-01`));
  d.readings.push(mk(19, null, 'water', 1188, .88, null));
  // ถ่ายซ้ำ (6 ต.ค.): 104 น้ำ ถ่ายสองรอบ (ยังไม่ยืนยันทั้งคู่) · 101 น้ำ ยืนยันไปแล้วแต่ถ่ายซ้ำอีกใบ → หน้ายืนยันให้เลือกใช้รูปไหน
  d.readings.push(mk(20, '104', 'water', 1201, .92, 'W-104-01'));
  d.devices.push({ device_id: 'ARIA-001', revoked_at: null, last_seen_at: '2026-09-28T13:12:00Z', pending_rows: 0, pending_crops: 2, pending_decisions: 1, app_version: 'c51-f10', disk_free_mb: 41200, clock_synced: true, warn: '', cam_ok: true, air_available: true, cpu_temp_c: 52.1 });
  const done = ['W-101-01', 'E-101-01', 'W-102-01', 'E-102-01', 'W-103-01', 'E-105-01', 'W-106-01', 'E-106-01', 'W-107-01', 'E-107-01', 'W-108-01', 'W-110-01', 'E-110-01'];
  for (const r of d.readings) if (done.includes(r.meter_id)) apply({ reading_id: r.id, event: 'confirmed', confirmed_value: r.value, actor: null });
  d.readings.push(mk(21, '101', 'water', 1245, .93, 'W-101-01'));   // ถ่ายซ้ำหลังยืนยันใบแรกแล้ว

  // ?mock=empty → สภาพหลัง delete_demo_data() (30 ก.ย.): ไม่มีห้อง/มิเตอร์/ผู้เช่า · เหลือค่าจริงจาก ARIA-001 3 แถว (OCR อ่านไม่ออก · ยังไม่ผูก)
  if (new URLSearchParams(location.search).get('mock') === 'empty') {
    d.rooms = []; d.meters = []; d.tenancies = []; d.events = []; d.readings = [];
    [['101', 'water', 'ocr'], ['102', 'electric', 'rejected'], ['103', 'electric', 'ocr']].forEach(([room, type, st], i) =>
      d.readings.push({ ...mk(30 + i, room, type, null, 0, `${type === 'water' ? 'W' : 'E'}-${room}-01`), device_id: 'ARIA-001', raw_text: null, status: st, is_demo: false }));
    d.rates.push({ id: 1, type: 'water', baht_per_unit: 18, effective_from: '2026-09-01' }, { id: 2, type: 'electric', baht_per_unit: 7, effective_from: '2026-09-01' });
    d.settings.dorm_name = 'Aria-Dorm';
  }

  // จำลอง trigger reading_events_before/after_insert
  function apply(ev) {
    const r = d.readings.find(x => x.id === ev.reading_id);
    if (!r) throw new Error(`reading ${ev.reading_id} not found`);
    if (ev.event === 'confirmed' || ev.event === 'corrected') {
      const idx = meterIndex(d.meters), m = readingMeterId(r, idx);
      if (!m) throw new Error(`ต้องผูกมิเตอร์ก่อนยืนยันค่า (reading ${r.id})`);
      const same = d.readings.filter(x => x.id !== r.id && x.status === 'confirmed' && readingMeterId(x, idx) === m);
      const lo = Math.max(...same.filter(x => x.captured_at < r.captured_at).map(x => x.confirmed_value), -Infinity);
      const base = lo === -Infinity ? idx.get(m).start_value : lo;
      const hi = Math.min(...same.filter(x => x.captured_at > r.captured_at).map(x => x.confirmed_value), Infinity);
      if (ev.confirmed_value < base) throw new Error(`ค่า ${ev.confirmed_value} ต่ำกว่าค่ายืนยันก่อนหน้า ${base} ของมิเตอร์ ${m}`);
      if (ev.confirmed_value > hi) throw new Error(`ค่า ${ev.confirmed_value} สูงกว่าค่ายืนยันครั้งถัดไป ${hi} ของมิเตอร์ ${m}`);
      if (ev.event === 'corrected' && !String(ev.reason || '').trim()) throw new Error('corrected ต้องมีเหตุผล');
      Object.assign(r, { status: 'confirmed', confirmed_value: ev.confirmed_value });
    } else if (ev.event === 'rejected') Object.assign(r, { status: 'rejected', confirmed_value: null });
    else if (ev.event === 'assigned') Object.assign(r, { assigned_meter_id: ev.meter_id, status: 'ocr', confirmed_value: null });
    else if (ev.event === 'reopened') {
      if (r.status === 'ocr') throw new Error(`ค่านี้ยังรอยืนยันอยู่แล้ว (reading ${r.id})`);
      Object.assign(r, { status: 'ocr', confirmed_value: null });
    }
    d.events.push({ id: ++eid, reason: null, meter_id: null, confirmed_value: null, ...ev, at: new Date().toISOString() });
  }
  const clone = x => structuredClone(x);
  const USER = 'mock-user';
  return {
    mock: true,
    // จำลองสถานะล็อกอินด้วย sessionStorage ให้ลองหน้าเข้า/ออกระบบบน localhost ได้
    async session() {
      if (sessionStorage.getItem('mock.out')) return null;
      return sessionStorage.getItem('mock.guest') ? { user: { id: 'guest', email: null, is_anonymous: true } } : { user: { id: USER, email: 'owner@example.com' } };
    },
    async signInGuest() { sessionStorage.removeItem('mock.out'); sessionStorage.setItem('mock.guest', '1'); },
    onAuthChange() {},
    async signIn() { sessionStorage.removeItem('mock.out'); sessionStorage.removeItem('mock.guest'); setTimeout(() => location.reload(), 300); },
    async signOut() { sessionStorage.setItem('mock.out', '1'); sessionStorage.removeItem('mock.guest'); },
    async isOwner() { return true; },
    async loadAll() { return clone(d); },
    async addEvent(ev) { apply({ ...ev, actor: USER }); },
    // จำลอง add_manual_reading(): แถวใหม่ไม่มีรูป + ยืนยันทันที · ยืนยันไม่ผ่าน = ไม่มีแถวค้าง (ธุรกรรมเดียว)
    async addManualReading(meterId, value, at, reason) {
      const m = d.meters.find(x => x.meter_id === meterId);
      if (!m) throw new Error(`ไม่พบมิเตอร์ ${meterId}`);
      if (!String(reason || '').trim()) throw new Error('ต้องใส่เหตุผลที่กรอกเอง (ไม่มีรูปเป็นหลักฐาน)');
      if (new Date(at) > new Date(Date.now() + 300000)) throw new Error('เวลาที่อ่านต้องไม่อยู่ในอนาคต');
      const r = { run_id: null, registry_version: null, image_path: null, id: ++rid, local_id: rid.toString(16).padStart(12, '0'), device_id: 'MANUAL', captured_at: at, decided_at: new Date().toISOString(), received_at: new Date().toISOString(), clock_synced: true,
        room_id: m.room_id, meter_type: m.type, meter_id: m.meter_id, raw_text: null, value, confidence: null, ocr_engine: null, source: 'manual', air: null, crop_path: null, crop_expired_at: null, status: 'ocr', confirmed_value: null, assigned_meter_id: null, is_demo: false };
      d.readings.push(r);
      try { apply({ reading_id: r.id, event: 'confirmed', confirmed_value: value, reason: reason.trim(), actor: USER }); }
      catch (e) { d.readings.pop(); throw e; }
      return r.id;
    },
    async cropUrl() { throw new Error('ข้อมูลจำลองไม่มีรูป'); },
    async addRoom(row) { if (d.rooms.some(r => r.room_id === row.room_id)) throw new Error('duplicate key'); d.rooms.push({ floor: null, note: null, is_demo: false, ...row }); },
    async updateRoom(id, patch) { Object.assign(d.rooms.find(r => r.room_id === id), patch); },
    async addTenancy(row) { d.tenancies.push({ id: ++tid, email: null, end_date: null, rent_baht: null, is_demo: false, ...row }); },
    async updateTenancy(id, patch) { Object.assign(d.tenancies.find(t => t.id === id), patch); },
    async addMeter(row) { d.meters.push({ retired_at: null, end_value: null, waypoint: null, lift_mm: null, is_demo: false, ...row }); },
    async updateMeter(id, patch) { Object.assign(d.meters.find(m => m.meter_id === id), patch); },
    async addRate(row) { if (d.rates.some(r => r.type === row.type && r.effective_from === row.effective_from)) throw new Error('duplicate key value violates unique constraint "rates_type_effective_from_key"'); d.rates.push({ id: d.rates.length + 1, ...row }); },
    async updateSettings(patch) { Object.assign(d.settings, patch); },
    async upsertCycle(row) {
      const old = d.cycles.find(x => x.cycle === row.cycle), next = shiftCycle(row.cycle, 1);
      if (old && old.cutoff_date !== row.cutoff_date && d.invoices.some(v => v.state === 'approved' && (v.cycle === row.cycle || v.cycle === next))) throw new Error('cutoff_locked'); const c = d.cycles.find(x => x.cycle === row.cycle); if (c) Object.assign(c, row); else d.cycles.push({ state: 'open', include_rent: false, ...row }); },
    // จำลอง rpc approve_invoices (ยอด = round(หน่วย×อัตรา, 2) ต่อชนิด + ค่าเช่า เหมือนคอลัมน์ generated)
    async approveInvoices(cycle, cutoff, items) {
      const r2 = x => Math.round(x * 100 + 1e-9) / 100;
      if (!d.cycles.some(c => c.cycle === cycle)) d.cycles.push({ cycle, cutoff_date: cutoff, state: 'open', include_rent: false });
      const out = [];
      for (const it of items) {
        const cur = d.invoices.find(v => v.cycle === cycle && v.room_id === it.room_id && v.state === 'approved');
        if (cur && !it.revise) throw new Error(`ห้อง ${it.room_id} อนุมัติแล้ว`);
        if (cur) Object.assign(cur, { state: 'superseded', superseded_at: new Date().toISOString() });
        const rev = Math.max(0, ...d.invoices.filter(v => v.cycle === cycle && v.room_id === it.room_id).map(v => v.revision)) + 1;
        const { revise, ...row } = it;
        const v = { id: d.invoices.length + 1, cycle, revision: rev, state: 'approved', rent_baht: 0, ...row,
          water_amount: r2(it.water_units * it.water_rate), electric_amount: r2(it.electric_units * it.electric_rate),
          approved_by: 'owner@example.com', approved_at: new Date().toISOString(), superseded_at: null };
        v.total_baht = r2(v.water_amount + v.electric_amount + Number(v.rent_baht || 0));
        d.invoices.push(v); out.push(clone(v));
      }
      return out;
    },
    async mailStatus() { return { configured: !!sessionStorage.getItem('mock.mail'), sender: sessionStorage.getItem('mock.mail') ? 'dorm@gmail.com' : null }; },
    async sendTestMail() { if (!sessionStorage.getItem('mock.mail')) throw new Error('ยังไม่ได้ตั้ง GMAIL_USER / GMAIL_APP_PASSWORD ใน Edge Function secrets'); return { test: true, to: 'owner@example.com', qr: !!d.payout.promptpay_id }; },
    async sendInvoices(ids, resend) {
      if (!sessionStorage.getItem('mock.mail')) throw new Error('ยังไม่ได้ตั้ง GMAIL_USER / GMAIL_APP_PASSWORD ใน Edge Function secrets');
      const results = [];
      for (const id of ids) {
        const v = d.invoices.find(x => x.id === id);
        if (!v || v.state !== 'approved') { results.push({ id, skipped: 'ไม่ใช่ฉบับปัจจุบัน' }); continue; }
        if (!v.recipient_email) { results.push({ id, skipped: 'ไม่มีอีเมล' }); continue; }
        if (!resend && d.deliveries.some(a => a.invoice_id === id && a.result === 'sent')) { results.push({ id, skipped: 'ส่งแล้ว' }); continue; }
        const fail = v.recipient_email.includes('fail');
        d.deliveries.push({ id: d.deliveries.length + 1, invoice_id: id, to_email: v.recipient_email, attempted_at: new Date().toISOString(), result: fail ? 'failed' : 'sent', error: fail ? '550 mailbox unavailable' : null, requested_by: 'owner@example.com' });
        results.push({ id, result: fail ? 'failed' : 'sent' });
      }
      return { results };
    },
    async addPayment(row) { if (row.client_key && d.payments.some(p => p.client_key === row.client_key)) throw new Error('duplicate key value violates unique constraint "invoice_payments_client_key_key"'); d.payments.push({ id: d.payments.length + 1, recorded_by: 'owner@example.com', recorded_at: new Date().toISOString(), voided_at: null, void_reason: null, note: null, ...row }); },
    async voidPayment(id, reason) { const p = d.payments.find(x => x.id === id); if (p.voided_at) throw new Error('รายการนี้ยกเลิกไปแล้ว'); Object.assign(p, { voided_at: new Date().toISOString(), void_reason: reason }); },
    async setPromptpay(id) { d.payout.promptpay_id = id; },
    async newExport() { d.lastExport = { version: ++ver, exported_at: new Date().toISOString() }; return clone(d.lastExport); },
  };
}
