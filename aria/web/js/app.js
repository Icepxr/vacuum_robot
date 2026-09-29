// ARIA หลังบ้าน · vanilla JS (ต่อจาก design/aria-prototype) + Supabase
// ขอบเขต: ขั้น 3 ของแบบ v1 §7 (บัญชีเจ้าของ + 5 หน้า + reading_events) · บิลเป็นพรีวิว (ขั้น 4 ยังไม่มีตาราง invoices) · ยังไม่ส่งอีเมล (ขั้น 5)
import * as L from './logic.js';

const $ = sel => document.querySelector(sel);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = (n, d = 3) => n == null ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: d }).format(n);
const baht = n => n == null ? '—' : '฿' + new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
const pct = c => c == null ? '—' : `${Math.round(c * 100)}%`;

const iconPaths = {
  home: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  review: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m8 12 3 3 5-6"/>',
  bills: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6"/>',
  rooms: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h1m4 0h1M9 11h1m4 0h1M10 21v-5h4v5"/>',
  settings: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
  robot: '<rect x="4" y="7" width="16" height="13" rx="4"/><path d="M12 7V3m-3 0h6M1 12v4m22-4v4M8 13h8M9 17h6"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18"/>',
  camera: '<path d="m8 5 1-2h6l1 2h3a2 2 0 0 1 2 2v12H3V7a2 2 0 0 1 2-2Z"/><circle cx="12" cy="12" r="4"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  water: '<path d="M12 3S5 11 5 15a7 7 0 0 0 14 0c0-4-7-12-7-12Z"/>',
  electric: '<path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z"/>',
};
const icon = name => `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.review}</svg>`;
const status = (text, tone = '') => `<span class="status ${tone}">${esc(text)}</span>`;

const FLAG_TEXT = {
  unassigned: ['ยังไม่ผูกมิเตอร์', 'bad'],
  below_prev: ['ต่ำกว่าค่าก่อน', 'bad'],
  unreadable: ['OCR อ่านไม่ออก', 'warn'],
  low_conf: ['OCR ไม่มั่นใจ', 'warn'],
  clock: ['เวลา Pi ยังไม่ยืนยัน', 'warn'],
};
const EVENT_TEXT = { confirmed: 'ยืนยัน', corrected: 'แก้ค่าแล้วยืนยัน', rejected: 'ปฏิเสธ', assigned: 'ผูกมิเตอร์' };
const PAGE_NAMES = { home: 'หน้าหลัก', review: 'ยืนยันค่ามิเตอร์', bills: 'บิล', rooms: 'ห้องและมิเตอร์', settings: 'ตั้งค่า' };

const state = { page: 'home', cycle: null, selectedReading: null, selectedRoom: null, billFilter: 'all', roomQuery: '', user: null, data: null, busy: false };
let api;
let mIdx = new Map();

// ───────── ข้อมูล ─────────
async function reload() {
  state.data = await api.loadAll();
  mIdx = L.meterIndex(state.data.meters);
  if (!state.cycle) state.cycle = L.cycleOfDate(L.todayBkk(), state.data.cycles, state.data.settings);
  render();
}

// ทุกปุ่มที่เขียนข้อมูลผ่านตรงนี้: กันกดซ้ำระหว่างรอ + โชว์ข้อความจากฐานข้อมูล (trigger เขียนเป็นภาษาไทยไว้แล้ว)
async function write(fn, okText) {
  if (state.busy) return false;
  state.busy = true;
  document.body.classList.add('busy');
  try {
    await fn();
    await reload();
    if (okText) toast(okText);
    return true;
  } catch (e) {
    toast(`บันทึกไม่สำเร็จ: ${friendlyError(e.message)}`, true);
    return false;
  } finally {
    state.busy = false;
    document.body.classList.remove('busy');
  }
}

// ข้อความจาก constraint ของ Postgres เป็นภาษาอังกฤษ · trigger ของเราเขียนไทยอยู่แล้ว ปล่อยผ่าน
function friendlyError(msg) {
  if (/duplicate key/.test(msg)) return 'ซ้ำกับรายการที่มีอยู่แล้ว';
  if (/exclusion constraint/.test(msg)) return 'ช่วงวันที่ทับกับรายการเดิมของห้องนี้ (ผู้เช่า/มิเตอร์ต้องไม่ซ้อนกัน)';
  if (/violates check constraint/.test(msg)) return `ค่าไม่ผ่านเงื่อนไขของฐานข้อมูล (${msg.match(/"([^"]+)"/)?.[1] ?? 'check'})`;
  if (/violates foreign key/.test(msg)) return 'อ้างถึงรายการที่ไม่มีอยู่ หรือยังมีรายการอื่นใช้อยู่';
  if (/row-level security|permission denied/.test(msg)) return 'บัญชีนี้ไม่มีสิทธิ์เขียนข้อมูลนี้';
  if (/Failed to fetch|NetworkError/.test(msg)) return 'ต่อเน็ตไม่ได้ ลองใหม่';
  return msg;
}

function toast(message, bad = false) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.toggle('bad', bad);
  node.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove('show'), bad ? 6000 : 3400);
}

// ───────── ค่าที่ใช้หลายหน้า ─────────
function ctx() {
  const d = state.data;
  const range = L.cycleRange(state.cycle, d.cycles, d.settings);
  const inCycle = L.readingsInCycle(d.readings, range);
  const queue = L.reviewQueue(d.readings, mIdx);
  const rooms = [...d.rooms].sort((a, b) => a.room_id.localeCompare(b.room_id, 'en', { numeric: true }));
  const capture = new Map(rooms.map(r => [r.room_id, L.roomCaptureState(r, range, d, mIdx, inCycle)]));
  const bills = rooms.map(r => L.billPreview(r, state.cycle, d, mIdx));
  return { d, range, inCycle, queue, rooms, capture, bills };
}
const meterLabel = id => { const m = mIdx.get(id); return m ? `${L.TYPE_TH[m.type]} ห้อง ${m.room_id}` : 'ยังไม่ผูก'; };
const eventsOf = readingId => state.data.events.filter(e => e.reading_id === readingId).sort((a, b) => a.id - b.id);
const actorText = a => a == null ? 'ระบบ (ข้อมูลตัวอย่าง)' : a === state.user?.id ? 'คุณ' : 'เจ้าของหออีกบัญชี';
const hasDemo = () => ['rooms', 'meters', 'tenancies', 'readings'].some(k => state.data[k].some(x => x.is_demo));

function pageHead(kicker, title, subtitle, action = '') {
  return `<div class="page-head"><div><span class="eyebrow">${kicker}</span><h1>${title}</h1><p class="page-subtitle">${subtitle}</p></div><div class="page-actions">${action}</div></div>`;
}

// ───────── โครงหน้า ─────────
function render() {
  if (!state.data) return;
  $('#top-page-name').textContent = PAGE_NAMES[state.page];
  $('#cycle-name').textContent = `รอบ${L.cycleLabel(state.cycle)}`;
  document.querySelectorAll('#side-nav button').forEach(b => {
    const on = b.dataset.page === state.page;
    b.classList.toggle('active', on);
    if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  const c = ctx();
  $('#nav-review-count').textContent = c.queue.length || '';
  renderChrome(c);
  const pages = { home: renderHome, review: renderReview, bills: renderBills, rooms: renderRooms, settings: renderSettings };
  $('#page-content').innerHTML = pages[state.page](c);
  if (state.page === 'review') loadCrop();
}

function renderChrome(c) {
  const d = c.d;
  $('#ws-name').textContent = d.settings.dorm_name || 'หอพัก (ยังไม่ตั้งชื่อ)';
  $('#ws-meta').textContent = `${d.rooms.length} ห้อง · ${d.meters.filter(m => L.meterActiveOn(m, L.todayBkk())).length} มิเตอร์`;
  const demo = hasDemo();
  $('#ws-demo').hidden = !demo;
  $('#demo-badge').hidden = !demo;
  const email = state.user?.email || '';
  $('#avatar').textContent = (email[0] || '?').toUpperCase();
  $('#avatar').title = email;
  const dev = realDevices()[0];
  $('#dev-name').textContent = dev ? dev.device_id : 'ยังไม่มีหุ่น';
  $('#dev-seen').textContent = dev?.last_seen_at ? `ข้อมูลล่าสุดเมื่อ ${L.dateTimeTh(dev.last_seen_at)}` : 'ยังไม่เคยส่งข้อมูล';
  $('#dev-dot').className = `device-dot ${dev?.warn ? 'warn' : ''}`;
}
const realDevices = () => state.data.devices.filter(x => !x.revoked_at).sort((a, b) => (b.last_seen_at || '').localeCompare(a.last_seen_at || ''));

// ───────── หน้าหลัก ─────────
function attentionItems(c) {
  const list = [];
  const by = f => c.queue.filter(q => q.flags.includes(f));
  const push = (tone, mark, title, desc, attrs) => list.push({ tone, mark, title, desc, attrs });
  const firstAttr = q => `data-page="review" data-reading="${q.r.id}"`;
  const un = by('unassigned');
  if (un.length) push('red', '!', `ยังไม่ผูกมิเตอร์ ${un.length} ค่า`, 'คนขับไม่ได้เลือกห้อง หรือรหัสมิเตอร์ไม่อยู่ในทะเบียน · ผูกก่อนยืนยัน', firstAttr(un[0]));
  for (const q of by('below_prev')) push('red', '!', `${esc(meterLabel(q.meterId))} ต่ำกว่าค่าก่อน`, `OCR ${num(q.value)} < ค่ายืนยันก่อน ${num(q.prev.value)} · ต้องดูรูป`, firstAttr(q));
  const ur = by('unreadable');
  if (ur.length) push('amber', '?', `OCR อ่านไม่ออก ${ur.length} ค่า`, 'ต้องกรอกค่าเองจากรูป', firstAttr(ur[0]));
  const lc = by('low_conf');
  if (lc.length) push('amber', '?', `OCR ไม่มั่นใจ ${lc.length} ค่า`, `ความมั่นใจต่ำกว่า ${pct(L.LOW_CONFIDENCE)} · ดูรูปเทียบ`, firstAttr(lc[0]));
  const ck = by('clock');
  if (ck.length) push('amber', '⏱', `เวลาจาก Pi ยังไม่ยืนยัน ${ck.length} ค่า`, 'ตรวจว่าเข้ารอบบิลถูกเดือนก่อนยืนยัน (F1)', firstAttr(ck[0]));
  const missing = c.rooms.filter(r => c.capture.get(r.room_id).meters.length && !c.capture.get(r.room_id).captured);
  if (missing.length) push('amber', '◌', `ยังไม่มีค่าในรอบนี้ ${missing.length} ห้อง`, `ห้อง ${missing.slice(0, 8).map(r => esc(r.room_id)).join(', ')}${missing.length > 8 ? ' …' : ''}`, `data-page="rooms" data-room="${esc(missing[0].room_id)}"`);
  const noMeter = c.rooms.filter(r => !c.capture.get(r.room_id).meters.length);
  if (noMeter.length) push('amber', '▦', `ห้องไม่มีมิเตอร์ติดตั้ง ${noMeter.length} ห้อง`, `ห้อง ${noMeter.slice(0, 8).map(r => esc(r.room_id)).join(', ')}`, `data-page="rooms" data-room="${esc(noMeter[0].room_id)}"`);
  const noEmail = c.bills.filter(b => b.noEmail);
  if (noEmail.length) push('amber', '@', `ผู้เช่า ${noEmail.length} ห้องยังไม่มีอีเมล`, `ห้อง ${noEmail.map(b => esc(b.room.room_id)).join(', ')} · ดูบิลได้ แต่ส่งไม่ได้`, `data-page="rooms" data-room="${esc(noEmail[0].room.room_id)}"`);
  const noRate = L.TYPES.filter(t => !L.rateOn(c.d.rates, t, c.range.to));
  if (noRate.length) push('amber', '฿', `ยังไม่ตั้งอัตรา${noRate.map(t => L.TYPE_TH[t]).join('และ')}`, `ต้องมีอัตราที่มีผล ณ ${L.dateTh(c.range.to)} ถึงจะคิดบิลได้`, 'data-page="settings"');
  return list;
}

function devicePanel() {
  const devs = realDevices();
  if (!devs.length) return `<div class="empty">ยังไม่มีหุ่นที่ลงทะเบียน</div>`;
  return devs.map(v => {
    const warn = v.warn ? status(`เตือน ${v.warn}`, 'warn') : '';
    const kv = [
      ['ข้อมูลล่าสุดเมื่อ', v.last_seen_at ? L.dateTimeTh(v.last_seen_at) : 'ยังไม่เคยส่ง'],
      ['แถวรอส่งบน Pi', v.pending_rows ?? '—'],
      ['รูป crop รอส่ง', v.pending_crops ?? '—'],
      ['รูปรอคนขับตัดสิน', v.pending_decisions ?? '—'],
      ['นาฬิกา Pi', v.clock_synced == null ? '—' : v.clock_synced ? 'ซิงก์แล้ว' : 'ยังไม่ซิงก์'],
      ['พื้นที่ว่าง SD', v.disk_free_mb == null ? '—' : `${num(v.disk_free_mb / 1024, 1)} GB`],
    ];
    return `<div class="device-block"><div class="device-title"><b>${esc(v.device_id)}</b>${warn}</div><div class="kv-grid">${kv.map(([k, val]) => `<div><small>${k}</small><b>${esc(val)}</b></div>`).join('')}</div></div>`;
  }).join('') + `<p class="fine">ตัวเลขเหล่านี้คือสิ่งที่ Pi รายงานครั้งล่าสุดตอนซิงก์ ไม่ใช่สถานะสด</p>`;
}

function renderHome(c) {
  const withMeters = c.rooms.filter(r => c.capture.get(r.room_id).meters.length);
  const captured = withMeters.filter(r => c.capture.get(r.room_id).captured).length;
  const pendingInCycle = c.queue.filter(q => { const dd = L.bkkDate(q.r.captured_at); return dd > c.range.from && dd <= c.range.to; }).length;
  const ready = c.bills.filter(b => b.state === 'ready').length;
  const blocked = c.bills.filter(b => b.state === 'blocked').length;
  const total = withMeters.length || 0;
  const ratio = total ? captured / total * 100 : 0;
  const items = attentionItems(c);
  return `<section class="page">
  ${pageHead('YOUR METERING WORKSPACE', 'ภาพรวม', `รอบ${L.cycleLabel(state.cycle)} · ค่าที่ถ่าย ${L.dateTh(L.shiftDay(c.range.from, 1))} – ${L.dateTh(c.range.to)} (เวลาไทย)`)}
  <div class="orbit-hero">
    <div class="hero-orbits" aria-hidden="true"><i></i><i></i><i></i><span>✦</span></div>
    <div class="hero-copy"><span class="hero-kicker"><span></span> ARIA · INTELLIGENT METERING</span><h2>จากภาพที่หุ่นอ่าน<br>สู่บิลที่คุณมั่นใจ</h2><p>รอบนี้อ่านครบ ${captured} จาก ${total} ห้อง<br>${c.queue.length ? `มีค่ารอยืนยัน ${c.queue.length} ค่า` : 'ไม่มีค่าค้างยืนยัน'}</p><div class="hero-actions"><button class="btn primary" data-page="review">ตรวจค่าที่ค้าง ${c.queue.length} ค่า ${icon('arrow')}</button><button class="btn hero-secondary" data-page="rooms">ดูห้องทั้งหมด</button></div></div>
    <div class="hero-progress"><svg viewBox="0 0 180 180" aria-hidden="true"><circle class="progress-track" cx="90" cy="90" r="74"/><circle class="progress-value" cx="90" cy="90" r="74" pathLength="100" stroke-dasharray="${ratio} 100"/></svg><div class="progress-copy"><span>อ่านครบแล้ว</span><strong>${captured}<small> / ${total}</small></strong><span>ห้อง</span></div><span class="progress-caption">METER CAPTURE / THIS CYCLE</span></div>
  </div>
  ${hasDemo() ? `<div class="demo-note">${icon('review')}<span>ฐานข้อมูลนี้มีข้อมูลตัวอย่าง (ห้อง 101–110 · หุ่น DEMO-01) ปนอยู่ · ลบได้ก่อนใช้กับหอจริง ดูหน้าตั้งค่า</span></div>` : ''}
  <div class="grid stat-grid">
    <div class="card stat-card"><span class="stat-icon mint">${icon('camera')}</span><div class="label">อ่านมิเตอร์ครบ</div><div class="number">${captured}<small> / ${total} ห้อง</small></div><div class="hint">ทุกมิเตอร์ของห้องมีค่าในรอบนี้</div></div>
    <div class="card stat-card"><span class="stat-icon amber">${icon('review')}</span><div class="label">ค่ารอยืนยัน</div><div class="number warn">${c.queue.length}<small> ค่า</small></div><div class="hint">ในรอบนี้ ${pendingInCycle} · ทุกรอบรวมกัน ${c.queue.length}</div></div>
    <div class="card stat-card"><span class="stat-icon violet">${icon('bills')}</span><div class="label">บิลคำนวณได้</div><div class="number accent">${ready}<small> ห้อง</small></div><div class="hint">ข้อมูลไม่ครบ ${blocked} ห้อง</div></div>
    <div class="card stat-card"><span class="stat-icon mint">${icon('mail')}</span><div class="label">ส่งอีเมล</div><div class="number">—</div><div class="hint">ยังไม่เปิด (ขั้น 5)</div></div>
  </div>
  <div class="grid two-col">
    <div class="card card-pad"><div class="card-head"><div><h2>ต้องดูก่อน</h2><p>รายการที่อาจทำให้บิลคลาดเคลื่อน</p></div><button class="text-link" data-page="review">ไปหน้ายืนยัน →</button></div>
      <div class="attention-list">${items.map(x => `<button class="attention-item" ${x.attrs}><span class="attention-icon ${x.tone}">${x.mark}</span><span class="attention-copy"><strong>${x.title}</strong><span>${x.desc}</span></span><span class="attention-chevron">›</span></button>`).join('') || '<div class="empty">ไม่มีรายการเร่งด่วน</div>'}</div></div>
    <div class="card card-pad"><div class="card-head"><div><h2>จากหุ่น</h2><p>heartbeat ที่แนบมากับการซิงก์ครั้งล่าสุด</p></div></div>${devicePanel()}</div>
  </div>
  <div class="card"><div class="card-head card-pad" style="margin-bottom:0"><div><h2>ห้องในรอบนี้</h2><p>ค่าล่าสุดในรอบของมิเตอร์แต่ละตัว</p></div><button class="text-link" data-page="rooms">ดูทะเบียนทั้งหมด →</button></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>ห้อง</th><th>มิเตอร์น้ำ</th><th>มิเตอร์ไฟ</th><th>บิล</th></tr></thead><tbody>${c.rooms.map((r, i) => {
      const cap = c.capture.get(r.room_id);
      const cell = t => { const p = cap.meters.find(x => x.meter.type === t); if (!p) return '<span class="muted">ไม่มีมิเตอร์</span>'; if (!p.latest) return '<span class="muted">ยังไม่อ่าน</span>'; const l = p.latest; return `<span class="meter-mini ${t}"><span class="type">${icon(t)}</span><strong>${num(l.confirmed_value ?? l.value)}</strong></span> ${l.status === 'confirmed' ? status('ยืนยันแล้ว', 'good') : status('รอยืนยัน', 'warn')}`; };
      return `<tr class="room-row" data-page="rooms" data-room="${esc(r.room_id)}" tabindex="0"><td><span class="room-label">ห้อง ${esc(r.room_id)}</span></td><td>${cell('water')}</td><td>${cell('electric')}</td><td>${billBadge(c.bills[i])}</td></tr>`;
    }).join('') || '<tr><td colspan="4" class="empty">ยังไม่มีห้องในทะเบียน · เพิ่มที่หน้า “ห้องและมิเตอร์”</td></tr>'}</tbody></table></div></div>
  </section>`;
}

function billBadge(b) {
  if (b.state === 'vacant') return status('ห้องว่าง', 'purple');
  if (b.state === 'blocked') return status('ข้อมูลไม่ครบ', 'warn');
  if (b.noEmail) return status('คำนวณได้ · ไม่มีอีเมล', 'bad');
  return status('คำนวณได้', 'good');
}

// ───────── ยืนยันค่ามิเตอร์ ─────────
function renderReview(c) {
  const d = c.d;
  const q = c.queue;
  let sel = d.readings.find(r => r.id === state.selectedReading);
  if (!sel && q.length) { sel = q[0].r; state.selectedReading = sel.id; }
  const head = pageHead('METER REVIEW', 'ยืนยันค่ามิเตอร์', q.length ? `รอยืนยัน ${q.length} ค่า · เรียง ยังไม่ผูก → ต่ำกว่าค่าก่อน → อ่านไม่ออก → ไม่มั่นใจ → เวลาไม่ยืนยัน → ปกติ` : 'ไม่มีค่าที่รอยืนยัน');
  const queueHtml = q.map(x => {
    const f = x.flags[0];
    const cyc = L.cycleOfDate(L.bkkDate(x.r.captured_at), d.cycles, d.settings);
    return `<button class="queue-item ${x.r.id === state.selectedReading ? 'active' : ''}" data-reading="${x.r.id}"><span class="queue-type">${icon(x.r.meter_type || 'review')}</span><span class="queue-copy"><strong>${x.meterId ? esc(meterLabel(x.meterId)) : `${x.r.room_id ? `ห้อง ${esc(x.r.room_id)}` : 'ไม่ระบุห้อง'} · ${L.TYPE_TH[x.r.meter_type] ?? '?'}`}</strong><small>OCR ${num(x.value)} · มั่นใจ ${pct(x.r.confidence)}${cyc !== state.cycle ? ` · รอบ${L.cycleLabel(cyc)}` : ''}</small></span>${f ? status(FLAG_TEXT[f][0], FLAG_TEXT[f][1]) : ''}</button>`;
  }).join('');
  if (!sel) return `<section class="page">${head}<div class="card card-pad"><div class="empty">ไม่มีค่าที่ต้องตรวจ · ค่าที่ยืนยันแล้วเปิดดู/แก้ได้จากหน้า “ห้องและมิเตอร์”</div></div></section>`;
  return `<section class="page">${head}<div class="review-layout">
    <div class="card queue-card"><div class="queue-top"><h2>คิวรอยืนยัน</h2><p>${q.length} ค่า · กดเพื่อตรวจ</p></div><div class="queue-list">${queueHtml || '<div class="empty">คิวว่าง</div>'}</div></div>
    ${reviewDetail(sel, c)}
  </div></section>`;
}

function reviewDetail(r, c) {
  const { meterId, prev, value, flags } = L.readingFlags(r, c.d.readings, mIdx);
  const meter = meterId ? mIdx.get(meterId) : null;
  const decided = r.status !== 'ocr';
  const tone = r.status === 'confirmed' ? ['ยืนยันแล้ว', 'good'] : r.status === 'rejected' ? ['ปฏิเสธแล้ว', 'bad'] : flags[0] ? FLAG_TEXT[flags[0]] : ['รอยืนยัน', 'purple'];
  const units = value != null && prev ? value - prev.value : null;
  const needReason = flags.some(f => ['below_prev', 'low_conf', 'unreadable', 'clock'].includes(f));
  const cropHtml = r.crop_path
    ? `<img id="crop-img" class="crop-img" alt="รูป crop หน้าปัดมิเตอร์" data-path="${esc(r.crop_path)}"><p class="image-caption" id="crop-cap">กำลังโหลดรูป…</p>`
    : `<div class="crop-missing">${r.crop_expired_at ? `รูปหมดอายุแล้ว (ลบหลัง 12 เดือน · ${L.dateTh(L.bkkDate(r.crop_expired_at))})` : r.is_demo ? 'ข้อมูลตัวอย่าง — ไม่มีรูป' : 'รูปกำลังซิงก์จาก Pi · ยังยืนยันไม่ได้จนกว่ารูปจะขึ้น'}</div>`;
  const cropBlocks = !r.crop_path && !r.crop_expired_at && !r.is_demo; // แบบ v1 §4.2 พักการยืนยันที่ต้องอาศัยรูป
  const candidates = c.d.meters.filter(m => (!r.meter_type || m.type === r.meter_type) && L.meterActiveOn(m, L.bkkDate(r.captured_at)))
    .sort((a, b) => (a.room_id === r.room_id ? -1 : 0) - (b.room_id === r.room_id ? -1 : 0) || a.meter_id.localeCompare(b.meter_id, 'en', { numeric: true }));
  const air = r.air ? `<div class="kv-grid air"><div><small>eCO₂</small><b>${esc(r.air.eco2_ppm)} ppm</b></div><div><small>TVOC</small><b>${esc(r.air.tvoc_ppb)} ppb</b></div><div><small>AQI</small><b>${esc(r.air.aqi)}</b></div><div><small>อุณหภูมิ / ชื้น</small><b>${esc(r.air.temp_c)} °C · ${esc(r.air.rh_pct)} %</b></div></div>${r.air.validity ? '<p class="fine">เซนเซอร์ยังไม่พร้อม (validity ≠ 0) ค่าอาจยังไม่นิ่ง</p>' : ''}` : '<p class="fine">ไม่มีค่าอากาศตอนถ่าย</p>';
  const hist = eventsOf(r.id);
  return `<div class="card review-detail">
    <div class="review-header"><div><h2>${meter ? esc(meterLabel(meterId)) : `${r.room_id ? `ห้อง ${esc(r.room_id)}` : 'ไม่ระบุห้อง'} · ${L.TYPE_TH[r.meter_type] ?? '?'}`}</h2><p>${meterId ? `<code>${esc(meterId)}</code>` : 'ยังไม่ผูกมิเตอร์'} · ถ่าย ${L.dateTimeTh(r.captured_at)} · ${esc(r.device_id)}</p></div>${status(tone[0], tone[1])}</div>
    <div class="image-stage">${cropHtml}</div>
    <div class="reading-comparison">
      <div class="comparison-box"><small>ค่ายืนยันก่อนหน้า</small><strong>${prev ? num(prev.value) : '—'}</strong><small>${prev ? (prev.source === 'start' ? 'ค่าเริ่มตอนติดตั้ง' : L.dateTh(L.bkkDate(prev.at))) : 'ผูกมิเตอร์ก่อน'}</small></div>
      <div class="comparison-box"><small>OCR (${esc(r.ocr_engine || '—')})</small><strong>${num(value)}</strong><small>ข้อความดิบ “${esc(r.raw_text ?? '')}” · มั่นใจ ${pct(r.confidence)}</small></div>
      <div class="comparison-box"><small>หน่วยถ้ารับ OCR</small><strong class="${units != null && units < 0 ? 'neg' : ''}">${num(units)}</strong><small>${meter ? `${meter.digits} หลัก · ทศนิยม ${meter.decimals}` : ''}</small></div>
    </div>
    ${flags.length ? `<div class="alert ${flags.some(f => FLAG_TEXT[f][1] === 'bad') ? 'bad' : 'warn'}">${flags.map(f => `<strong>${FLAG_TEXT[f][0]}</strong>`).join(' · ')}${flags.includes('clock') ? ' — นาฬิกา Pi ยังไม่ซิงก์ตอนถ่าย ตรวจว่ารูปนี้เป็นของรอบนี้จริง' : ''}${flags.includes('below_prev') ? ' — ถ้ามิเตอร์ถูกเปลี่ยนตัว ให้ปลดตัวเก่าและเพิ่มตัวใหม่ที่หน้า “ห้องและมิเตอร์” แล้วผูกค่านี้กับตัวใหม่' : ''}</div>` : ''}
    <div class="detail-grid"><div class="detail-kv"><small>คนขับเลือก</small><strong>ห้อง ${esc(r.room_id ?? '—')} · ${L.TYPE_TH[r.meter_type] ?? '—'}</strong></div><div class="detail-kv"><small>ขึ้นคลาวด์เมื่อ</small><strong>${L.dateTimeTh(r.received_at)}</strong></div></div>

    <form id="assign-form" class="inline-form"><label>ผูกกับมิเตอร์<select name="meter_id" required><option value="">— เลือก —</option>${candidates.map(m => `<option value="${esc(m.meter_id)}" ${m.meter_id === meterId ? 'selected' : ''}>${esc(m.meter_id)} · ${esc(meterLabel(m.meter_id))}</option>`).join('')}</select></label><button class="btn small" type="submit">${meterId ? 'เปลี่ยนมิเตอร์' : 'ผูก'}</button></form>

    ${r.status === 'rejected' ? '<div class="alert bad">ค่านี้ถูกปฏิเสธแล้ว · ให้คนขับถ่ายใหม่ในรอบถัดไป (ผูกมิเตอร์ใหม่จะเปิดให้ยืนยันได้อีกครั้ง)</div>' : `
    <form id="confirm-form" class="confirm-form" data-ocr="${value ?? ''}" data-need-reason="${needReason ? 1 : 0}" data-decided="${decided ? 1 : 0}">
      <label>${decided ? 'แก้เป็นค่า' : 'ค่าที่จะยืนยัน'}<input name="value" type="number" inputmode="decimal" step="any" min="0" value="${esc(decided ? r.confirmed_value : value ?? '')}" required ${!meterId || cropBlocks ? 'disabled' : ''}></label>
      <label>เหตุผล ${decided || needReason ? '(จำเป็น)' : '(จำเป็นเมื่อแก้จาก OCR)'}<input name="reason" type="text" maxlength="200" placeholder="เช่น ดูรูปแล้วหลักสุดท้ายเป็น 7" ${!meterId || cropBlocks ? 'disabled' : ''}></label>
      <button class="btn primary" type="submit" ${!meterId || cropBlocks ? 'disabled' : ''}>${decided ? 'บันทึกค่าที่แก้' : 'ยืนยันค่า'}</button>
      ${decided ? '' : `<button class="btn danger" type="button" data-action="reject" ${state.busy ? 'disabled' : ''}>ปฏิเสธ</button>`}
    </form>
    ${!meterId ? '<p class="fine">ต้องผูกมิเตอร์ก่อน ถึงจะยืนยันได้ (ฐานข้อมูลบังคับ)</p>' : ''}`}

    <details class="more"><summary>ค่าอากาศตอนถ่าย</summary>${air}</details>
    <div class="history"><strong>ประวัติ</strong><br>หุ่นอ่าน OCR ${num(value)} · ${L.dateTimeTh(r.captured_at)}${r.decided_at ? ` · คนขับกด “เก็บ” ${L.dateTimeTh(r.decided_at)}` : ''}
      ${hist.map(e => `<br>${EVENT_TEXT[e.event]}${e.confirmed_value != null ? ` ${num(Number(e.confirmed_value))}` : ''}${e.meter_id ? ` → ${esc(e.meter_id)}` : ''}${e.reason ? ` · “${esc(e.reason)}”` : ''} · ${actorText(e.actor)} · ${L.dateTimeTh(e.at)}`).join('')}</div>
  </div>`;
}

// signed URL อายุ 5 นาที · สร้างใหม่ทุกครั้งที่เปิดรายการ (bucket crops เป็น private)
async function loadCrop() {
  const img = $('#crop-img');
  if (!img) return;
  const path = img.dataset.path;
  try {
    const url = await api.cropUrl(path);
    if ($('#crop-img')?.dataset.path !== path) return; // ผู้ใช้เปลี่ยนรายการไปแล้ว
    img.src = url;
    $('#crop-cap').textContent = 'รูป crop จาก Pi · ลิงก์ใช้ได้ 5 นาที';
  } catch (e) {
    $('#crop-cap').textContent = `โหลดรูปไม่ได้: ${e.message}`;
  }
}

async function submitConfirm(form) {
  const r = state.data.readings.find(x => x.id === state.selectedReading);
  const f = new FormData(form);
  const raw = String(f.get('value') ?? '').trim();
  const v = Number(raw);
  const reason = String(f.get('reason') || '').trim();
  if (!raw || !Number.isFinite(v) || v < 0) return toast('ใส่ค่าเป็นตัวเลขไม่ติดลบ', true);
  const ocr = form.dataset.ocr === '' ? null : Number(form.dataset.ocr);
  const decided = form.dataset.decided === '1';
  const changed = decided || ocr == null || v !== ocr;
  if ((changed || form.dataset.needReason === '1') && !reason) return toast('ต้องใส่เหตุผลเมื่อแก้ค่าจาก OCR หรือค่ามีธงเตือน', true);
  const ev = { reading_id: r.id, event: changed ? 'corrected' : 'confirmed', confirmed_value: v, reason: reason || null };
  const next = L.reviewQueue(state.data.readings, mIdx).map(x => x.r.id).find(id => id !== r.id);
  if (await write(() => api.addEvent(ev), `${changed ? 'แก้และยืนยัน' : 'ยืนยัน'} ${num(v)} แล้ว`) && !decided && next) { state.selectedReading = next; render(); }
}

async function rejectReading() {
  const r = state.data.readings.find(x => x.id === state.selectedReading);
  const reason = prompt('เหตุผลที่ปฏิเสธ (เช่น รูปเบลอ / ถ่ายผิดห้อง) — เว้นว่างได้');
  if (reason === null) return;
  const next = L.reviewQueue(state.data.readings, mIdx).map(x => x.r.id).find(id => id !== r.id);
  if (await write(() => api.addEvent({ reading_id: r.id, event: 'rejected', reason: reason.trim() || null }), 'ปฏิเสธแล้ว · รอถ่ายใหม่') && next) { state.selectedReading = next; render(); }
}

async function submitAssign(form) {
  const meterId = new FormData(form).get('meter_id');
  if (!meterId) return;
  const r = state.data.readings.find(x => x.id === state.selectedReading);
  if (r.status === 'confirmed' && !confirm('ค่านี้ยืนยันแล้ว · ผูกมิเตอร์ใหม่จะล้างค่าที่ยืนยันและต้องยืนยันใหม่ ตกลงไหม')) return;
  await write(() => api.addEvent({ reading_id: r.id, event: 'assigned', meter_id: meterId }), `ผูกกับ ${meterId} แล้ว`);
}

// ───────── บิล (พรีวิว) ─────────
const BILL_FILTERS = [['all', 'ทั้งหมด'], ['ready', 'คำนวณได้'], ['blocked', 'ข้อมูลไม่ครบ'], ['noemail', 'ไม่มีอีเมล'], ['vacant', 'ห้องว่าง']];
const billMatch = (b, f) => f === 'all' || (f === 'noemail' ? b.noEmail : b.state === f);

function renderBills(c) {
  const row = c.d.cycles.find(x => x.cycle === state.cycle);
  const list = c.bills.filter(b => billMatch(b, state.billFilter));
  const sum = c.bills.filter(b => b.state === 'ready').reduce((s, b) => s + b.total, 0);
  const rate = t => { const x = L.rateOn(c.d.rates, t, c.range.to); return x ? `${baht(Number(x.baht_per_unit))}/หน่วย (มีผล ${L.dateTh(x.effective_from)})` : 'ยังไม่ตั้ง'; };
  const cell = (b, t) => { const l = b.lines[t]; return l.ok ? `${num(l.units)} หน่วย<br><strong>${l.amount != null ? baht(l.amount) : '—'}</strong>` : '<span class="muted">—</span>'; };
  return `<section class="page">
  ${pageHead('BILLING', 'บิลค่าน้ำและค่าไฟ', `รอบ${L.cycleLabel(state.cycle)} · ตัดรอบ ${L.dateTh(c.range.to)} · คำนวณจากค่าที่ยืนยันแล้วเท่านั้น`)}
  <div class="info-banner"><span class="spark">✦</span><div><strong>พรีวิว</strong> ตัวเลขคำนวณสดทุกครั้งที่เปิดหน้า · การอนุมัติและตรึงยอดบิล (ขั้น 4) และการส่งอีเมล (ขั้น 5) ยังไม่เปิด จึงยังไม่มีบิลฉบับจริง</div></div>
  <label class="switch-row"><input id="include-rent" type="checkbox" ${row?.include_rent ? 'checked' : ''} ${row?.state === 'closed' ? 'disabled' : ''}><span><strong>รวมค่าเช่าในบิลรอบนี้</strong><small>ค่าเช่ากำหนดต่อผู้เช่า · ค่าเริ่มต้นปิด (F7) · ตั้งแยกรายรอบ</small></span></label>
  <div class="filter-bar">${BILL_FILTERS.map(([k, t]) => `<button class="filter ${state.billFilter === k ? 'active' : ''}" data-filter="${k}">${t} <small>${c.bills.filter(b => billMatch(b, k)).length}</small></button>`).join('')}</div>
  <div class="card"><div class="table-wrap"><table class="data-table"><thead><tr><th>ห้อง / ผู้เช่า</th><th>น้ำ</th><th>ไฟ</th><th>ค่าเช่า</th><th class="num">รวม</th><th>สถานะ</th><th></th></tr></thead><tbody>${list.map(b => `<tr>
    <td><span class="room-label">ห้อง ${esc(b.room.room_id)}</span><br><small class="muted">${b.tenancy ? esc(b.tenancy.tenant_name) : 'ห้องว่าง'}${b.tenancy && !b.tenancy.email ? ' · ไม่มีอีเมล' : ''}</small></td>
    <td>${cell(b, 'water')}</td><td>${cell(b, 'electric')}</td>
    <td>${b.includeRent && b.tenancy ? baht(b.rent) : '—'}</td>
    <td class="num bill-total">${baht(b.total)}</td>
    <td>${billBadge(b)}${b.reasons.length && b.state !== 'vacant' ? `<br><small class="muted">${esc(b.reasons[0])}${b.reasons.length > 1 ? ` (+${b.reasons.length - 1})` : ''}</small>` : ''}</td>
    <td><button class="btn small" data-bill="${esc(b.room.room_id)}">ดูรายละเอียด</button></td></tr>`).join('') || '<tr><td colspan="7" class="empty">ไม่มีห้องในตัวกรองนี้</td></tr>'}</tbody></table></div>
    <div class="bill-footer"><p>อัตราที่มีผล ณ วันตัดรอบ · น้ำ ${rate('water')} · ไฟ ${rate('electric')}</p><p><strong>รวมห้องที่คำนวณได้ ${baht(sum)}</strong></p></div></div>
  </section>`;
}

function showBill(roomId) {
  const c = ctx();
  const b = c.bills.find(x => x.room.room_id === roomId);
  const seg = t => b.lines[t].segments.map(s => `<div class="invoice-sub">${esc(s.meter_id)} · ${num(s.base)} → ${num(s.curr)} = ${num(s.units)} หน่วย${s.baseSource === 'start' ? ' (ฐาน = ค่าเริ่มตอนติดตั้ง)' : ''}</div>`).join('');
  const line = t => { const l = b.lines[t]; return `<div class="invoice-line"><span>ค่า${L.TYPE_TH[t]} ${l.ok ? `${num(l.units)} หน่วย × ${l.rate != null ? baht(l.rate) : '?'}` : '—'}</span><strong>${baht(l.amount)}</strong></div>${seg(t)}`; };
  openModal(`<div class="modal-head"><div><span class="eyebrow">INVOICE PREVIEW</span><h2 id="modal-title">ห้อง ${esc(roomId)} · รอบ${L.cycleLabel(state.cycle)}</h2><p class="muted" style="font-size:12px;margin:0">${b.tenancy ? `${esc(b.tenancy.tenant_name)} · ${b.tenancy.email ? esc(b.tenancy.email) : 'ยังไม่มีอีเมล'}` : 'ห้องว่าง · ไม่ออกบิลผู้เช่า'}</p></div><button type="button" aria-label="ปิด" data-action="close-modal">×</button></div>
    <div class="invoice-paper"><h3>${esc(state.data.settings.dorm_name || 'ARIA')} · บิล${L.cycleLabel(state.cycle)}</h3><small>ค่าที่ถ่ายหลัง ${L.dateTh(b.range.from)} ถึง ${L.dateTh(b.range.to)} · พรีวิว ยังไม่ใช่เอกสารเรียกเก็บเงิน</small>
      ${line('water')}${line('electric')}${b.includeRent && b.tenancy ? `<div class="invoice-line"><span>ค่าเช่า (รายการเสริม)</span><strong>${baht(b.rent)}</strong></div>` : ''}
      <div class="invoice-line total"><span>รวม</span><span>${baht(b.total)}</span></div></div>
    ${b.reasons.length ? `<div class="alert warn">${b.reasons.map(esc).join('<br>')}</div>` : ''}
    <div class="modal-actions"><button class="btn" data-action="close-modal">ปิด</button></div>`);
}

async function toggleRent(on) {
  const c = ctx();
  const row = c.d.cycles.find(x => x.cycle === state.cycle);
  // สร้างแถวรอบด้วยวันตัดรอบที่ใช้อยู่ตอนนี้ (ตรึงไว้ ไม่ขยับตามค่าตั้งภายหลัง)
  await write(() => api.upsertCycle({ cycle: state.cycle, cutoff_date: row?.cutoff_date ?? c.range.to, include_rent: on }), on ? 'เปิดรวมค่าเช่ารอบนี้' : 'ปิดรวมค่าเช่ารอบนี้');
}

// ───────── ห้องและมิเตอร์ ─────────
function renderRooms(c) {
  const d = c.d;
  const today = L.todayBkk();
  const qy = state.roomQuery.trim().toLowerCase();
  const tenantNow = id => L.tenancyOn(d.tenancies, id, today);
  const rooms = c.rooms.filter(r => {
    if (!qy) return true;
    const t = tenantNow(r.room_id);
    const hay = [r.room_id, t?.tenant_name, t?.email, ...d.meters.filter(m => m.room_id === r.room_id).map(m => m.meter_id)].join(' ').toLowerCase();
    return hay.includes(qy);
  });
  if (!state.selectedRoom || !d.rooms.some(r => r.room_id === state.selectedRoom)) state.selectedRoom = rooms[0]?.room_id ?? null;
  const exp = d.lastExport ? `ส่งออกล่าสุด v${d.lastExport.version} · ${L.dateTimeTh(d.lastExport.exported_at)}` : 'ยังไม่เคยส่งออก';
  return `<section class="page">
  ${pageHead('REGISTRY', 'ห้องและมิเตอร์', `${d.rooms.length} ห้อง · มิเตอร์ที่ติดตั้งอยู่ ${d.meters.filter(m => L.meterActiveOn(m, today)).length} ตัว · ${exp}`, `<button class="btn" data-action="export">ส่งออก meters.json ให้ Pi</button>`)}
  <div class="room-layout"><div class="card">
    <div class="card-pad room-tools"><input id="room-search" type="search" placeholder="ค้นห้อง ชื่อผู้เช่า อีเมล หรือรหัสมิเตอร์" value="${esc(state.roomQuery)}"><form id="room-add" class="inline-form"><input name="room_id" placeholder="เลขห้องใหม่" maxlength="10" pattern="[A-Za-z0-9]{1,10}" required><input name="floor" placeholder="ชั้น" maxlength="4"><button class="btn small" type="submit">เพิ่มห้อง</button></form></div>
    <div class="table-wrap"><table class="data-table" style="min-width:520px"><thead><tr><th>ห้อง</th><th>ผู้เช่าปัจจุบัน</th><th>มิเตอร์ที่ติดตั้ง</th></tr></thead><tbody>${rooms.map(r => {
      const t = tenantNow(r.room_id);
      const ms = d.meters.filter(m => m.room_id === r.room_id && L.meterActiveOn(m, today));
      return `<tr class="room-row ${r.room_id === state.selectedRoom ? 'selected' : ''}" data-room="${esc(r.room_id)}" tabindex="0"><td class="room-label">${esc(r.room_id)}${r.is_demo ? ' <small class="muted">demo</small>' : ''}</td><td>${t ? esc(t.tenant_name) : '— ว่าง'}<br><small class="muted">${t ? (t.email ? esc(t.email) : 'ไม่มีอีเมล') : ''}</small></td><td><small>${ms.map(m => esc(m.meter_id)).join('<br>') || 'ไม่มี'}</small></td></tr>`;
    }).join('') || '<tr><td colspan="3" class="empty">ไม่พบห้อง</td></tr>'}</tbody></table></div></div>
    ${state.selectedRoom ? roomDetail(state.selectedRoom, c) : '<div class="card room-detail"><div class="empty">เพิ่มห้องแรกทางซ้าย</div></div>'}
  </div></section>`;
}

function roomDetail(roomId, c) {
  const d = c.d;
  const today = L.todayBkk();
  const room = d.rooms.find(r => r.room_id === roomId);
  const ts = d.tenancies.filter(t => t.room_id === roomId).sort((a, b) => b.start_date.localeCompare(a.start_date));
  const cur = L.tenancyOn(d.tenancies, roomId, today);
  const ms = d.meters.filter(m => m.room_id === roomId).sort((a, b) => a.type.localeCompare(b.type) || b.installed_at.localeCompare(a.installed_at));
  const readingsOf = id => d.readings.filter(r => L.readingMeterId(r, mIdx) === id).sort((a, b) => b.captured_at.localeCompare(a.captured_at));
  const unbound = d.readings.filter(r => r.room_id === roomId && !L.readingMeterId(r, mIdx));
  const meterCard = m => {
    const active = L.meterActiveOn(m, today);
    const rs = readingsOf(m.meter_id);
    const lastConf = rs.find(r => r.status === 'confirmed');
    return `<div class="meter-card ${active ? '' : 'retired'}"><div><b>${icon(m.type)} ${L.TYPE_TH[m.type]} · ${esc(m.meter_id)}</b>
      <small>ติดตั้ง ${L.dateTh(m.installed_at)} · ค่าเริ่ม ${num(Number(m.start_value))}${m.retired_at ? ` · ปลด ${L.dateTh(m.retired_at)} ค่าสุดท้าย ${num(m.end_value == null ? null : Number(m.end_value))}` : ''} · ${m.digits} หลัก ทศนิยม ${m.decimals}</small>
      <small>ยืนยันล่าสุด ${lastConf ? `${num(Number(lastConf.confirmed_value))} (${L.dateTh(L.bkkDate(lastConf.captured_at))})` : '—'}</small>
      ${rs.length ? `<div class="reading-chips">${rs.slice(0, 6).map(r => `<button class="chip ${r.status}" data-page="review" data-reading="${r.id}" title="${esc(r.status)}">${L.dateTh(L.bkkDate(r.captured_at))} · ${num(r.confirmed_value ?? r.value)}</button>`).join('')}</div>` : ''}
    </div>${active ? `<button class="btn small ghost" data-action="retire" data-meter="${esc(m.meter_id)}">ปลด/เปลี่ยน</button>` : status('ปลดแล้ว', '')}</div>`;
  };
  const nextW = L.nextMeterId(d.meters, roomId, 'water');
  return `<div class="card room-detail">
    <div class="card-head"><div><h2>ห้อง ${esc(roomId)}</h2><p>ชั้น ${esc(room.floor || '—')}${room.is_demo ? ' · ข้อมูลตัวอย่าง' : ''}</p></div>${status(cur ? 'มีผู้เช่า' : 'ห้องว่าง', cur ? 'good' : 'purple')}</div>

    <h3>ผู้เช่าปัจจุบัน</h3>
    ${cur ? `<form id="tenancy-edit" class="stack-form" data-id="${cur.id}">
      <label class="field">ชื่อผู้เช่า<input name="tenant_name" value="${esc(cur.tenant_name)}" required maxlength="120"></label>
      <label class="field">อีเมลรับบิล<input name="email" type="email" value="${esc(cur.email)}" placeholder="ไม่มี = ดูบิลได้ ส่งไม่ได้"></label>
      <label class="field">ค่าเช่า (บาท/เดือน · ใช้เมื่อเปิดรวมค่าเช่า)<input name="rent_baht" type="number" min="0" step="0.01" value="${esc(cur.rent_baht)}"></label>
      <div class="form-row"><button class="btn primary small" type="submit">บันทึก</button><button class="btn small danger" type="button" data-action="move-out" data-id="${cur.id}">ย้ายออก</button></div>
      <p class="fine">เข้าอยู่ ${L.dateTh(cur.start_date)}${cur.end_date ? ` · ถึง ${L.dateTh(cur.end_date)}` : ''}</p></form>`
    : `<form id="tenancy-add" class="stack-form">
      <label class="field">ชื่อผู้เช่า<input name="tenant_name" required maxlength="120"></label>
      <label class="field">อีเมลรับบิล<input name="email" type="email" placeholder="เว้นว่างได้"></label>
      <div class="form-row"><label class="field">วันเข้าอยู่<input name="start_date" type="date" value="${today}" required></label><label class="field">ค่าเช่า (บาท)<input name="rent_baht" type="number" min="0" step="0.01"></label></div>
      <button class="btn primary small" type="submit">เพิ่มผู้เช่า</button></form>`}
    ${ts.filter(t => t !== cur).length ? `<details class="more"><summary>ประวัติผู้เช่า (${ts.filter(t => t !== cur).length})</summary>${ts.filter(t => t !== cur).map(t => `<div class="setting-line"><span>${esc(t.tenant_name)}</span><small>${L.dateTh(t.start_date)} – ${t.end_date ? L.dateTh(t.end_date) : 'ยังอยู่ (เริ่มในอนาคต)'}</small></div>`).join('')}</details>` : ''}

    <div class="divider"></div><h3>มิเตอร์</h3>
    ${ms.map(meterCard).join('') || '<div class="empty">ยังไม่มีมิเตอร์</div>'}
    ${unbound.length ? `<div class="alert warn">มี ${unbound.length} ค่าที่คนขับเลือกห้องนี้แต่ยังไม่ผูกมิเตอร์ · <button class="text-link" data-page="review" data-reading="${unbound[0].id}">ไปผูก →</button></div>` : ''}
    <details class="more"><summary>เพิ่มมิเตอร์</summary><form id="meter-add" class="stack-form">
      <div class="form-row"><label class="field">ชนิด<select name="type"><option value="water">น้ำ</option><option value="electric">ไฟ</option></select></label><label class="field">รหัส (อัตโนมัติ)<input name="meter_id" value="${esc(nextW)}" readonly></label></div>
      <div class="form-row"><label class="field">จำนวนหลัก<input name="digits" type="number" min="1" max="9" value="5" required></label><label class="field">ทศนิยม<input name="decimals" type="number" min="0" max="4" value="0" required></label></div>
      <div class="form-row"><label class="field">วันติดตั้ง<input name="installed_at" type="date" value="${today}" required></label><label class="field">ค่าเริ่ม (ตัวเลขบนหน้าปัดวันติดตั้ง)<input name="start_value" type="number" min="0" step="any" value="0" required></label></div>
      <button class="btn primary small" type="submit">เพิ่มมิเตอร์</button>
      <p class="fine">เปลี่ยนตัวมิเตอร์ = ปลดตัวเก่า (ใส่ค่าสุดท้าย) แล้วเพิ่มตัวใหม่วันเดียวกัน · รหัสใหม่ต่อเลขเสมอ ไม่ใช้ซ้ำ · อย่าลืมส่งออก meters.json ให้ Pi</p></form></details>
  </div>`;
}

async function addRoom(form) {
  const f = new FormData(form);
  const id = String(f.get('room_id')).trim();
  const floor = String(f.get('floor') || '').trim() || null;
  if (await write(() => api.addRoom({ room_id: id, floor }), `เพิ่มห้อง ${id} แล้ว`)) { state.selectedRoom = id; render(); }
}

const blankToNull = v => { const s = String(v ?? '').trim(); return s === '' ? null : s; };

async function saveTenancy(form, isNew) {
  const f = new FormData(form);
  const row = { tenant_name: String(f.get('tenant_name')).trim(), email: blankToNull(f.get('email'))?.toLowerCase() ?? null, rent_baht: blankToNull(f.get('rent_baht')) };
  if (row.rent_baht != null) row.rent_baht = Number(row.rent_baht);
  if (isNew) await write(() => api.addTenancy({ ...row, room_id: state.selectedRoom, start_date: f.get('start_date') }), 'เพิ่มผู้เช่าแล้ว');
  else await write(() => api.updateTenancy(Number(form.dataset.id), row), 'บันทึกผู้เช่าแล้ว');
}

async function moveOut(id) {
  const t = state.data.tenancies.find(x => x.id === id);
  const end = prompt(`วันสุดท้ายที่ ${t.tenant_name} อยู่ (YYYY-MM-DD)`, L.todayBkk());
  if (!end) return;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(end) || end < t.start_date) return toast('วันที่ไม่ถูกต้อง หรือก่อนวันเข้าอยู่', true);
  await write(() => api.updateTenancy(id, { end_date: end }), 'บันทึกย้ายออกแล้ว · ผู้เช่าอยู่ในประวัติ');
}

async function addMeter(form) {
  const f = new FormData(form);
  const type = f.get('type');
  const row = { meter_id: L.nextMeterId(state.data.meters, state.selectedRoom, type), room_id: state.selectedRoom, type,
    digits: Number(f.get('digits')), decimals: Number(f.get('decimals')), installed_at: f.get('installed_at'), start_value: Number(f.get('start_value')) };
  await write(() => api.addMeter(row), `เพิ่ม ${row.meter_id} แล้ว · อย่าลืมส่งออก meters.json`);
}

async function retireMeter(id) {
  const m = mIdx.get(id);
  const date = prompt(`วันที่ปลด ${id} (YYYY-MM-DD) · ตัวใหม่ติดตั้งวันเดียวกันได้`, L.todayBkk());
  if (!date) return;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date < m.installed_at) return toast('วันที่ไม่ถูกต้อง หรือก่อนวันติดตั้ง', true);
  const endRaw = prompt(`ค่าสุดท้ายบนหน้าปัด ${id} ตอนถอด (ใช้คิดหน่วยช่วงสุดท้าย · เว้นว่างถ้าไม่รู้)`, '');
  if (endRaw === null) return;
  const end = endRaw.trim() === '' ? null : Number(endRaw);
  if (end != null && (!Number.isFinite(end) || end < 0)) return toast('ค่าสุดท้ายต้องเป็นตัวเลขไม่ติดลบ', true);
  await write(() => api.updateMeter(id, { retired_at: date, end_value: end }), `ปลด ${id} แล้ว · เพิ่มตัวใหม่ได้ที่ “เพิ่มมิเตอร์”`);
}

// meters.json → ดาวน์โหลดแล้ว scp ไป ~/mrc/data/meters.json บน Pi (aria/README.md)
async function exportRegistry() {
  let exp;
  const ok = await write(async () => { exp = await api.newExport(); }, null);
  if (!ok) return;
  const json = L.registryJson(state.data.meters, exp.version, exp.exported_at, L.todayBkk());
  const url = URL.createObjectURL(new Blob([JSON.stringify(json, null, 2) + '\n'], { type: 'application/json' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: 'meters.json' });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  toast(`ส่งออก meters.json v${exp.version} · ${json.meters.length} มิเตอร์ · นำไปวางที่ ~/mrc/data/ บน Pi`);
}

// ───────── ตั้งค่า ─────────
function renderSettings(c) {
  const d = c.d;
  const s = d.settings;
  const today = L.todayBkk();
  const rateRows = t => d.rates.filter(x => x.type === t).sort((a, b) => b.effective_from.localeCompare(a.effective_from))
    .map(x => `<div class="setting-line"><span>${L.TYPE_TH[t]} · มีผล ${L.dateTh(x.effective_from)}${L.rateOn(d.rates, t, today) === x ? ' ' + status('ใช้อยู่', 'good') : ''}</span><strong>${baht(Number(x.baht_per_unit))} / หน่วย</strong></div>`).join('') || `<div class="setting-line"><span>${L.TYPE_TH[t]}</span><strong class="muted">ยังไม่ตั้ง</strong></div>`;
  const cycles = [...d.cycles].sort((a, b) => b.cycle.localeCompare(a.cycle));
  const demoCount = ['rooms', 'meters', 'tenancies', 'readings'].reduce((n, k) => n + d[k].filter(x => x.is_demo).length, 0);
  return `<section class="page">${pageHead('PREFERENCES', 'ตั้งค่า', 'ค่าที่เปลี่ยนตรงนี้มีผลกับการคำนวณบิลรอบที่ยังไม่ตรึง')}
  <div class="settings-grid">
    <div class="card settings-box"><h2>ข้อมูลหอพัก</h2>
      <form id="settings-form" class="stack-form">
        <label class="field">ชื่อหอ<input name="dorm_name" value="${esc(s.dorm_name)}" maxlength="120" placeholder="เช่น หอพักสุขใจ"></label>
        <label class="field">วันตัดรอบเริ่มต้น<select name="default_cutoff_day"><option value="">สิ้นเดือน (ค่าเริ่ม)</option>${Array.from({ length: 28 }, (_, i) => i + 1).map(n => `<option value="${n}" ${s.default_cutoff_day === n ? 'selected' : ''}>วันที่ ${n}</option>`).join('')}</select></label>
        <label class="field">Gmail ผู้ส่งบิล (ยังไม่เชื่อม · ขั้น 5)<input name="sender_email" type="email" value="${esc(s.sender_email)}" placeholder="billing.dorm@gmail.com"></label>
        <button class="btn primary small" type="submit">บันทึก</button>
        <p class="fine">โซนเวลา ${esc(s.timezone || 'Asia/Bangkok')} · รอบที่ตั้งวันตัดรอบเฉพาะไว้แล้วด้านล่างไม่เปลี่ยนตามค่านี้</p></form></div>

    <div class="card settings-box"><h2>อัตราค่าน้ำและไฟ</h2><p>เพิ่มแถวใหม่แทนการแก้ของเดิม (append-only) · บิลใช้อัตราที่มีผล ณ วันตัดรอบ</p>
      ${rateRows('water')}${rateRows('electric')}
      <form id="rate-form" class="stack-form"><div class="form-row"><label class="field">ชนิด<select name="type"><option value="water">น้ำ</option><option value="electric">ไฟ</option></select></label><label class="field">บาท/หน่วย<input name="baht_per_unit" type="number" min="0.01" step="0.01" required></label><label class="field">มีผลตั้งแต่<input name="effective_from" type="date" value="${today}" required></label></div><button class="btn primary small" type="submit">เพิ่มอัตรา</button></form></div>

    <div class="card settings-box"><h2>รอบบิล</h2><p>ตรึงวันตัดรอบรายรอบ (เช่น ถ่ายช้ากว่ากำหนด) · รอบที่ไม่มีแถวใช้วันตัดรอบเริ่มต้น</p>
      ${cycles.map(x => `<div class="setting-line"><span>${L.cycleLabel(x.cycle)} · ตัดรอบ ${L.dateTh(x.cutoff_date)}${x.include_rent ? ' · รวมค่าเช่า' : ''}</span>${status(x.state === 'closed' ? 'ปิดแล้ว' : 'เปิด', x.state === 'closed' ? '' : 'purple')}</div>`).join('') || '<div class="setting-line"><span class="muted">ยังไม่มีรอบที่ตั้งเฉพาะ</span></div>'}
      <form id="cycle-form" class="stack-form"><div class="form-row"><label class="field">รอบ<input name="cycle" type="month" value="${esc(state.cycle)}" required></label><label class="field">วันตัดรอบ<input name="cutoff_date" type="date" value="${esc(L.cutoffFor(state.cycle, d.cycles, s))}" required></label></div><button class="btn small" type="submit">บันทึกวันตัดรอบ</button></form></div>

    <div class="card settings-box"><h2>บัญชี</h2><p>เข้าด้วย Google · ต้องอยู่ในรายชื่อเจ้าของหอ (ตาราง owners) ถึงเห็นข้อมูล</p>
      <div class="setting-line"><span>ล็อกอินเป็น</span><strong>${esc(state.user?.email || '—')}</strong></div>
      ${api.mock ? `<div class="setting-line"><span>โหมด</span>${status('จำลองบน localhost', 'warn')}</div>` : ''}
      <button class="btn small" data-action="sign-out">ออกจากระบบ</button></div>

    <div class="card settings-box"><h2>ข้อมูลตัวอย่าง</h2>
      ${demoCount ? `<p>มี ${demoCount} แถวที่ติดป้าย <code>is_demo</code> (ห้อง 101–110 · หุ่น DEMO-01) · ลบได้ครั้งเดียวทั้งหมดก่อนใช้กับหอจริง โดยรัน <code>select public.delete_demo_data();</code> ใน SQL Editor ของ Supabase (ตั้งใจไม่ใส่ปุ่มในเว็บ กันกดพลาด)</p>` : '<p>ไม่มีข้อมูลตัวอย่างแล้ว</p>'}</div>

    <div class="card settings-box"><h2>เกณฑ์ที่ยังไม่ตัดสิน</h2>
      <div class="setting-line"><span>OCR “ไม่มั่นใจ” เมื่อต่ำกว่า</span><strong>${pct(L.LOW_CONFIDENCE)}</strong></div>
      <p class="fine">ค่าจากต้นแบบ ใช้แค่เรียงคิวและติดป้าย · ต้องเก็บจากการถ่ายมิเตอร์จริงก่อนตั้งค่าจริง (สเปก §7a J3)</p></div>
  </div></section>`;
}

async function saveSettings(form) {
  const f = new FormData(form);
  const day = blankToNull(f.get('default_cutoff_day'));
  await write(() => api.updateSettings({ dorm_name: blankToNull(f.get('dorm_name')), sender_email: blankToNull(f.get('sender_email'))?.toLowerCase() ?? null, default_cutoff_day: day == null ? null : Number(day) }), 'บันทึกการตั้งค่าแล้ว');
}

async function addRate(form) {
  const f = new FormData(form);
  const row = { type: f.get('type'), baht_per_unit: Number(f.get('baht_per_unit')), effective_from: f.get('effective_from') };
  if (!(row.baht_per_unit > 0)) return toast('อัตราต้องมากกว่า 0', true);
  if (!confirm(`เพิ่มอัตรา${L.TYPE_TH[row.type]} ${baht(row.baht_per_unit)}/หน่วย มีผล ${L.dateTh(row.effective_from)}?\nแก้/ลบภายหลังไม่ได้ (append-only) ต้องเพิ่มแถวใหม่แทน`)) return;
  await write(() => api.addRate(row), 'เพิ่มอัตราแล้ว');
}

async function saveCycle(form) {
  const f = new FormData(form);
  const cycle = String(f.get('cycle'));
  const cutoff = String(f.get('cutoff_date'));
  const row = state.data.cycles.find(x => x.cycle === cycle);
  if (cutoff <= L.cutoffFor(L.shiftCycle(cycle, -1), state.data.cycles, state.data.settings)) return toast('วันตัดรอบต้องหลังวันตัดรอบของรอบก่อน', true);
  if (cutoff > L.cutoffFor(L.shiftCycle(cycle, 1), state.data.cycles, state.data.settings)) return toast('วันตัดรอบต้องก่อนวันตัดรอบของรอบถัดไป', true);
  await write(() => api.upsertCycle({ cycle, cutoff_date: cutoff, include_rent: row?.include_rent ?? false }), `ตั้งวันตัดรอบ${L.cycleLabel(cycle)} = ${L.dateTh(cutoff)}`);
}

// ───────── modal ─────────
function openModal(html) {
  $('#modal-root').innerHTML = `<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">${html}</div></div>`;
  $('.modal [aria-label="ปิด"]')?.focus();
}
const closeModal = () => { $('#modal-root').innerHTML = ''; };

// ───────── event ─────────
function setPage(page) {
  state.page = page;
  render();
  $('#page-content').focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: 'instant' });
}

document.addEventListener('click', e => {
  const t = e.target;
  const step = t.closest('[data-cycle-step]');
  if (step) { state.cycle = L.shiftCycle(state.cycle, Number(step.dataset.cycleStep)); render(); return; }
  const nav = t.closest('[data-page]');
  if (nav) {
    if (nav.dataset.reading) state.selectedReading = Number(nav.dataset.reading);
    if (nav.dataset.room) state.selectedRoom = nav.dataset.room;
    setPage(nav.dataset.page);
    return;
  }
  const rd = t.closest('[data-reading]');
  if (rd) {
    state.selectedReading = Number(rd.dataset.reading);
    render();
    // จอแคบ: รายละเอียดอยู่ใต้คิว → เลื่อนลงให้เห็นทันที
    if (rd.closest('.queue-list') && matchMedia('(max-width: 1000px)').matches) $('.review-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  const room = t.closest('[data-room]');
  if (room) { state.selectedRoom = room.dataset.room; render(); return; }
  const filter = t.closest('[data-filter]');
  if (filter) { state.billFilter = filter.dataset.filter; render(); return; }
  const bill = t.closest('[data-bill]');
  if (bill) { showBill(bill.dataset.bill); return; }
  const a = t.closest('[data-action]');
  if (!a) return;
  const act = a.dataset.action;
  if (act === 'close-modal') { if (t === a || a.tagName === 'BUTTON') closeModal(); return; }
  if (act === 'reject') rejectReading();
  else if (act === 'export') exportRegistry();
  else if (act === 'retire') retireMeter(a.dataset.meter);
  else if (act === 'move-out') moveOut(Number(a.dataset.id));
  else if (act === 'reload') location.reload();
  else if (act === 'sign-out') api.signOut().then(() => location.reload());
  else if (act === 'sign-in') api.signIn().catch(err => toast(`เข้าสู่ระบบไม่ได้: ${err.message}`, true));
});

const SUBMITS = {
  'confirm-form': submitConfirm, 'assign-form': submitAssign, 'room-add': addRoom,
  'tenancy-edit': f => saveTenancy(f, false), 'tenancy-add': f => saveTenancy(f, true), 'meter-add': addMeter,
  'settings-form': saveSettings, 'rate-form': addRate, 'cycle-form': saveCycle,
};
document.addEventListener('submit', e => {
  const fn = SUBMITS[e.target.id];
  if (!fn) return;
  e.preventDefault();
  fn(e.target);
});

document.addEventListener('change', e => {
  if (e.target.id === 'include-rent') toggleRent(e.target.checked);
  if (e.target.form?.id === 'meter-add' && e.target.name === 'type') e.target.form.meter_id.value = L.nextMeterId(state.data.meters, state.selectedRoom, e.target.value);
});

let searchTimer;
document.addEventListener('input', e => {
  if (e.target.id !== 'room-search') return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.roomQuery = e.target.value;
    const pos = e.target.selectionStart;
    render();
    const box = $('#room-search');
    box.focus();
    box.setSelectionRange(pos, pos);
  }, 200);
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('tr[data-room]')) { e.preventDefault(); e.target.click(); }
});

// ───────── เข้าระบบ ─────────
function showGate(title, text, actions) {
  $('#app').hidden = true;
  $('#gate').hidden = false;
  $('#gate-title').textContent = title;
  $('#gate-text').textContent = text;
  $('#gate-actions').innerHTML = actions;
}

async function boot() {
  document.querySelectorAll('[data-icon]').forEach(n => { n.innerHTML = icon(n.dataset.icon); });
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
  if (local && new URLSearchParams(location.search).has('mock')) {
    api = (await import('./mock.js')).createMockApi();
  } else {
    if (!window.supabase) return showGate('โหลดไม่สำเร็จ', 'ไฟล์ supabase-js ไม่ถูกโหลด ลองรีเฟรชหน้า', '');
    api = (await import('./api.js')).createApi();
  }
  let session;
  try { session = await api.session(); } catch (e) { return showGate('เชื่อมต่อไม่ได้', e.message, '<button class="btn" data-action="reload">ลองใหม่</button>'); }
  if (!session) {
    api.onAuthChange(s => { if (s) location.reload(); });
    return showGate('เข้าสู่ระบบ ARIA', 'หลังบ้านสำหรับเจ้าของหอพัก · ใช้บัญชี Google ที่ได้รับสิทธิ์เท่านั้น', '<button class="btn primary" data-action="sign-in">เข้าสู่ระบบด้วย Google</button>');
  }
  state.user = session.user;
  // ล็อกอินได้ไม่พอ ต้องอยู่ใน owners (RLS บังคับอีกชั้น — ถึงข้ามหน้านี้ไปก็ไม่เห็นข้อมูล)
  if (!(await api.isOwner().catch(() => false))) {
    return showGate('บัญชีนี้ยังไม่ได้รับสิทธิ์', `${session.user.email || 'บัญชีนี้'} ไม่อยู่ในรายชื่อเจ้าของหอ · ให้ผู้ดูแลเพิ่มอีเมลในตาราง owners แล้วเข้าใหม่`, '<button class="btn" data-action="sign-out">ออกจากระบบ</button>');
  }
  $('#gate').hidden = true;
  $('#app').hidden = false;
  if (location.search.includes('code=')) history.replaceState(null, '', location.pathname + (api.mock ? '?mock' : ''));
  try { await reload(); } catch (e) { toast(`โหลดข้อมูลไม่ได้: ${e.message}`, true); }
}

boot();
