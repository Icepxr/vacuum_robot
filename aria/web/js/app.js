// ARIA หลังบ้าน · vanilla JS (ต่อจาก design/aria-prototype) + Supabase
// ขอบเขต: ขั้น 3 ของแบบ v1 §7 (บัญชีเจ้าของ + 5 หน้า + reading_events) · บิลเป็นพรีวิว (ขั้น 4 ยังไม่มีตาราง invoices) · ยังไม่ส่งอีเมล (ขั้น 5)
import * as L from './logic.js?v=w15';
import { createBackdrop, accentNow } from './liquid.js?v=w41';

let gateBg = null, appBg = null;   // วอลเปเปอร์สองโทน (อินสแตนซ์แยก · ตอนเปลี่ยนหน้าทำงานพร้อมกัน)

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
  upload: '<path d="M12 16V4m-5 5 5-5 5 5"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  cloud: '<path d="M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.1 9.1 4.5 4.5 0 0 0 7 18Z"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  sd: '<path d="M8 3h8l3 3v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a3 3 0 0 1 3-3Z"/><path d="M9 7v3m3-3v3m3-3v3"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1"/><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1"/>',
  down: '<path d="M3 7l6 6 4-4 8 8"/><path d="M15 17h6v-6"/>',
  scan: '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M8 12h8"/>',
  baht: '<circle cx="12" cy="12" r="9"/><text x="12" y="16.2" text-anchor="middle" font-size="12" font-weight="600" fill="currentColor" stroke="none">฿</text>',
  alert: '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4"/><path d="M12 17h.01"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="m13.5 6.5 4 4"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  logout: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l-5-5 5-5M5 12h11"/>',
};
// ฟอร์มแก้ข้อมูลที่มีอยู่แล้ว = ดูก่อน → กด "แก้ไข" ถึงมีช่องกรอก + ยกเลิก/บันทึก (ผู้ใช้ขอ 3 ต.ค.: ปุ่มบันทึกไม่ควรลอยอยู่เฉยๆ)
// state.editing = id ของฟอร์มที่เปิดแก้อยู่ (ทีละฟอร์ม) · บันทึกสำเร็จ / เปลี่ยนหน้า / Esc = กลับเป็นโหมดดู
const isEditing = id => state.editing === id;
const editCls = id => `editable${isEditing(id) ? ' editing' : ''}`;
const editBtn = (id, label = 'แก้ไข') => isEditing(id) ? '' : `<button class="btn small ghost set-edit" type="button" data-action="edit" data-form="${id}">${icon('edit')}${label}</button>`;
const editActions = (save = 'บันทึก', lead = '') => `<div class="set-actions">${lead}<button class="btn small" type="button" data-action="edit-cancel">ยกเลิก</button><button class="btn primary small" type="submit">${save}</button></div>`;
const viewVal = (text, empty = 'ยังไม่ตั้ง') => text == null || text === '' ? `<span class="set-val empty">${empty}</span>` : `<span class="set-val">${esc(text)}</span>`;
// แถว ป้าย/ค่า: โหมดดูเห็น view · โหมดแก้เห็น ctl (CSS สลับ ไม่ต้อง render ใหม่ตอนพิมพ์)
const setRow = (label, ctl, hint = '', view = '') => `<label class="set-row"><span class="set-label">${label}${hint ? `<small>${hint}</small>` : ''}</span><span class="set-ctl">${view}${ctl}</span></label>`;

const icon = name => `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.review}</svg>`;
const status = (text, tone = '') => `<span class="status ${tone}">${esc(text)}</span>`;

const FLAG_TEXT = {
  unassigned: ['ยังไม่ผูกมิเตอร์', 'bad'],
  duplicate: ['ถ่ายซ้ำ', 'warn'],
  below_prev: ['ต่ำกว่าค่าก่อน', 'bad'],
  unreadable: ['OCR อ่านไม่ออก', 'warn'],
  low_conf: ['OCR ไม่มั่นใจ', 'warn'],
  clock: ['เวลา Pi ยังไม่ยืนยัน', 'warn'],
};
const EVENT_TEXT = { confirmed: 'ยืนยัน', corrected: 'แก้ค่าแล้วยืนยัน', rejected: 'ปฏิเสธ', assigned: 'ผูกมิเตอร์', reopened: 'ยกเลิกการยืนยัน' };
const PAGE_NAMES = { home: 'หน้าหลัก', review: 'ยืนยันค่ามิเตอร์', bills: 'บิล', rooms: 'ห้องและมิเตอร์', settings: 'ตั้งค่า' };

const state = { guest: false, page: 'home', cycle: null, selectedReading: null, selectedRoom: null, billFilter: 'all', homeRoom: null, roomQuery: '', user: null, data: null, busy: false, editing: null };
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
  if (state.guest) { toast('โหมดผู้ชม · ดูได้อย่างเดียว แก้ไขไม่ได้', true); return false; }
  if (state.busy) return false;
  state.busy = true;
  document.body.classList.add('busy');
  try {
    // หน้าจอยังเป็นข้อมูลเก่า (โหลดใหม่ไม่สำเร็จครั้งก่อน) → ต้องโหลดได้ก่อนถึงเขียนต่อ กันบันทึกซ้ำจากยอดเก่า
    if (state.stale) {
      try { await reload(); state.stale = false; } catch { toast('ยังโหลดข้อมูลล่าสุดไม่ได้ · ตรวจเน็ตแล้วรีเฟรชหน้าก่อนทำต่อ', true); return false; }
    }
    try {
      await fn();
    } catch (e) {
      toast(`บันทึกไม่สำเร็จ: ${friendlyError(e.message)}`, true);
      const typed = keepTyped();
      await reload().catch(() => {});   // บางอย่างอาจสำเร็จไปก่อนพัง (เช่น ส่งอีเมลชุดแรกแล้ว) → ให้หน้าตรงกับฐานข้อมูล
      typed();                          // แต่ไม่ทิ้งสิ่งที่ผู้ใช้พิมพ์ไว้ในฟอร์ม → แก้แล้วกดบันทึกซ้ำได้
      refreshOpenBill();
      return false;
    }
    // ถึงตรงนี้ = บันทึกสำเร็จแล้วแน่นอน (audit WEB-004: เดิมเน็ตหลุดตอนโหลดใหม่ก็ขึ้น "ไม่สำเร็จ" → ผู้ใช้กดซ้ำ ได้รายการรับเงินซ้ำ)
    state.editing = null;
    try {
      await reload();
    } catch {
      state.stale = true;
      closeModal();                     // ไม่เปิดหน้าต่างที่มียอดเก่าค้างไว้ให้กดซ้ำ
      toast(`${okText || 'บันทึกแล้ว'} · แต่โหลดข้อมูลใหม่ไม่สำเร็จ — รีเฟรชหน้าก่อนทำต่อ อย่ากดบันทึกซ้ำ`, true);
      return false;
    }
    if (okText) toast(okText);
    return true;
  } finally {
    state.busy = false;
    document.body.classList.remove('busy');
    document.querySelectorAll('.is-busy').forEach(x => x.classList.remove('is-busy'));
    if (state.data) { const t = keepTyped(); render(); t(); }   // ปุ่มที่ render ตอน busy (ปฏิเสธ/ยกเลิกการยืนยัน) กลับมากดได้ (audit WEB-017) · ไม่ทิ้งค่าที่พิมพ์
  }
}

// หน้าต่างบิลที่เปิดอยู่ = แสดงยอดล่าสุดหลังเขียน (ทั้งสำเร็จและล้มเหลว)
function refreshOpenBill() {
  const room = $('#modal-root .modal-backdrop:not(.closing) [data-bill-modal]')?.dataset.billModal;
  if (room && ctx().bills.some(b => b.room.room_id === room)) showBill(room);
}

// จำค่าที่พิมพ์ในทุกฟอร์มของหน้า (ตาม id ฟอร์ม + name) แล้วคืนให้หลัง render ใหม่
function keepTyped() {
  const saved = [...document.querySelectorAll('#page-content form[id]')].map(f => [f.id, [...f.elements].filter(el => el.name && el.type !== 'radio' && el.type !== 'checkbox').map(el => [el.name, el.value])]);
  return () => saved.forEach(([id, vals]) => { const f = document.getElementById(id); if (f) vals.forEach(([n, v]) => { if (f.elements[n] && 'value' in f.elements[n]) f.elements[n].value = v; }); });
}

// ข้อความจาก constraint ของ Postgres เป็นภาษาอังกฤษ · trigger ของเราเขียนไทยอยู่แล้ว ปล่อยผ่าน
function friendlyError(msg) {
  if (/duplicate key/.test(msg) && /client_key/.test(msg)) return 'รายการรับเงินนี้บันทึกไปแล้ว (กันบันทึกซ้ำ) · รีเฟรชหน้าเพื่อดูยอดล่าสุด';
  if (/duplicate key/.test(msg)) return 'ซ้ำกับรายการที่มีอยู่แล้ว';
  if (/cutoff_locked/.test(msg)) return 'เปลี่ยนวันตัดรอบไม่ได้ · รอบนี้หรือรอบถัดไปอนุมัติบิลแล้ว';
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
const cycCtx = d => ({ cycles: d.cycles, settings: d.settings });   // ให้ logic รู้รอบบิล (ตรวจถ่ายซ้ำ)
function ctx() {
  const d = state.data;
  const range = L.cycleRange(state.cycle, d.cycles, d.settings);
  const inCycle = L.readingsInCycle(d.readings, range);
  const queue = L.reviewQueue(d.readings, mIdx, cycCtx(d));
  const rooms = [...d.rooms].sort((a, b) => a.room_id.localeCompare(b.room_id, 'en', { numeric: true }));
  const capture = new Map(rooms.map(r => [r.room_id, L.roomCaptureState(r, range, d, mIdx, inCycle)]));
  const bills = rooms.map(r => L.billPreview(r, state.cycle, d, mIdx));
  // บิลที่อนุมัติแล้ว (ฉบับปัจจุบัน) ของรอบนี้ · view = สถานะที่หน้าบิลแสดง (อนุมัติแล้วชนะสถานะพรีวิว)
  for (const b of bills) {
    b.inv = (d.invoices || []).find(v => v.cycle === state.cycle && v.room_id === b.room.room_id && v.state === 'approved') || null;
    b.changed = b.inv ? invoiceDiff(b.inv, b) : [];
    b.view = b.inv ? 'approved' : b.state;
    // การส่ง: ครั้งล่าสุดของฉบับปัจจุบัน · การรับเงิน: รวมทุกรายการที่ไม่ยกเลิกของ รอบ+ห้อง เทียบยอดฉบับปัจจุบัน
    const att = b.inv ? (d.deliveries || []).filter(a => a.invoice_id === b.inv.id).sort((x, y) => y.id - x.id) : [];
    b.sent = att.some(a => a.result === 'sent') ? 'sent' : att.length ? 'failed' : null;
    b.attempts = att;
    b.payments = (d.payments || []).filter(p => p.cycle === state.cycle && p.room_id === b.room.room_id).sort((x, y) => y.id - x.id);
    b.paid = b.payments.filter(p => !p.voided_at).reduce((sum, p) => sum + Number(p.amount), 0);
    b.pay = !b.inv ? null : b.paid >= Number(b.inv.total_baht) - 0.004 ? 'paid' : b.paid > 0 ? 'partial' : 'unpaid';
  }
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
const shown = { page: null, sel: null };
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
  // เปลี่ยนหน้า = เลื่อนขึ้นจางเข้า · เปลี่ยนรายการที่เลือก = เฉพาะแผงรายละเอียดจางเข้า · render จากการบันทึก = ไม่ขยับ (ไม่กระพริบ)
  const sel = `${state.selectedRoom}|${state.selectedReading}|${state.homeRoom}`;
  if (state.page !== shown.page) $('#page-content > .page')?.classList.add('enter');
  else if (sel !== shown.sel) document.querySelectorAll('.rm-detail, .review-detail, .map-detail').forEach(el => el.classList.add('enter'));
  shown.page = state.page; shown.sel = sel;
  if (state.guest) lockForGuest();
  if (state.page === 'review') loadCrop();
  if (state.page === 'settings') { (window.requestIdleCallback || setTimeout)(() => prepStyles(accentNow() === 'teal' ? 'purple' : 'teal')); if (!state.guest) loadMailStatus(); }
}

// ธีมสี (ผู้ใช้ขอ 2 ต.ค. · ม่วงเก็บไว้สลับกลับ) · จำต่อเบราว์เซอร์ · ไฟล์ .teal.css สร้างจาก tools/make_accent.py
const ACCENTS = { purple: { name: 'ม่วง', meta: '#1a0d38', logo: 'img/aria-logo-plum.png', sw: 'linear-gradient(135deg, #8b5cf6, #d946ef)' }, teal: { name: 'เขียวฟ้า', meta: '#071918', logo: 'img/aria-logo-teal.png', sw: 'linear-gradient(135deg, #388782, #3c94b2)' } };
function applyAccentAssets() {
  const a = ACCENTS[accentNow()];
  const g = $('.gate-logo'); if (g) g.src = a.logo;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', a.meta);
}
// สลับไฟล์ CSS แบบไม่ค้าง: โหลดชุดของอีกธีมไว้ก่อนเป็น media="not all" (ไม่มีผลกับหน้า) → ตอนกดแค่สลับ media ทันที
// ไฟล์ /css ตั้ง no-cache (netlify.toml) → ถ้าไม่โหลดไว้ก่อน ทุกครั้งที่กดต้องรอเซิร์ฟเวอร์
const cssHref = (h, name) => name === 'teal' ? h.replace(/css\/(\w+)\.css/, 'css/$1.teal.css') : h.replace(/\.teal\.css/, '.css');
const prepared = {};
function prepStyles(name) {
  if (prepared[name]) return prepared[name];
  const live = [...document.querySelectorAll('link[data-css]:not([media])')];
  const want = live.map(l => cssHref(l.getAttribute('href'), name));
  if (live.every((l, i) => l.getAttribute('href') === want[i])) return Promise.resolve([]);
  prepared[name] = Promise.all(live.map((old, i) => new Promise(res => {
    const n = old.cloneNode(); n.setAttribute('href', want[i]); n.setAttribute('media', 'not all'); n.dataset.accentFor = name;
    n.onload = n.onerror = () => res(n);
    old.after(n);
  })));
  return prepared[name];
}
function commitStyles(name, links) {
  const olds = [...document.querySelectorAll('link[data-css]:not([media])')];
  links.forEach(n => n.removeAttribute('media'));
  // ชุดเก่ากลายเป็นชุดสำรอง (media="not all") ไว้สลับกลับได้ทันที
  const prev = accentNow();
  olds.forEach(o => { o.setAttribute('media', 'not all'); o.dataset.accentFor = prev; });
  prepared[prev] = Promise.resolve(olds);
  delete prepared[name];
}
function applyAccentNow(name, links) {
  try { localStorage.setItem('aria.accent', name); } catch {}
  commitStyles(name, links);
  if (name === 'teal') document.documentElement.dataset.accent = 'teal'; else delete document.documentElement.dataset.accent;
  applyAccentAssets();
  render();
  appBg?.drawNow();   // พื้นหลังเดิม แค่เปลี่ยนจานสี
}
async function setAccent(name) {
  if (!ACCENTS[name] || name === accentNow() || setAccent.busy) return;
  setAccent.busy = true;
  try {
    const links = await prepStyles(name);   // ปกติโหลดไว้แล้วตั้งแต่เปิดหน้าตั้งค่า
    const smooth = document.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (smooth) await document.startViewTransition(() => applyAccentNow(name, links)).finished;
    else applyAccentNow(name, links);
  } finally { setAccent.busy = false; }
}

// โหมดผู้ชม: ปิดทุกช่องกรอก/ปุ่มบันทึก (ช่องค้นหา ตัวกรอง และการเลือกดูยังใช้ได้) · ฐานข้อมูลกันซ้ำด้วย RLS
function lockForGuest() {
  $('#page-content').querySelectorAll('form input, form select, form textarea, form button, #include-rent').forEach(el => { el.disabled = true; });
}
function renderChrome(c) {
  const d = c.d;
  $('#ws-name').textContent = d.settings.dorm_name || 'หอพัก (ยังไม่ตั้งชื่อ)';
  $('#ws-meta').textContent = `${d.rooms.length} ห้อง · ${d.meters.filter(m => L.meterActiveOn(m, L.todayBkk())).length} มิเตอร์`;
  const demo = hasDemo();
  $('#ws-demo').hidden = !demo;
  $('#demo-badge').hidden = !demo || state.guest;
  const email = state.guest ? 'ผู้ชม (Guest)' : state.user?.email || '';
  $('#guest-badge').hidden = !state.guest;
  $('.account-head small').textContent = state.guest ? 'ดูได้อย่างเดียว · แก้ไขไม่ได้' : 'เจ้าของหอ · เข้าด้วย Google';
  $('#avatar').textContent = state.guest ? 'G' : (email[0] || '?').toUpperCase();
  $('#avatar').title = email;
  $('#account-email').textContent = email || '—';
  $('#side-email').textContent = email || '—';
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
  const push = (tone, mark, title, desc, attrs, act) => list.push({ tone, mark, title, desc, attrs, act });
  const firstAttr = q => `data-page="review" data-reading="${q.r.id}"`;
  const un = by('unassigned');
  if (un.length) push('red', 'link', `ยังไม่ผูกมิเตอร์ ${un.length} ค่า`, 'คนขับไม่ได้เลือกห้อง หรือรหัสไม่อยู่ในทะเบียน', firstAttr(un[0]), 'ผูกมิเตอร์');
  for (const q of by('below_prev')) push('red', 'down', `${esc(meterLabel(q.meterId))} ต่ำกว่าค่าก่อน`, `OCR ${num(q.value)} · ค่าก่อน ${num(q.prev.value)}`, firstAttr(q), 'ดูรูป');
  const ur = by('unreadable');
  if (ur.length) push('amber', 'scan', `OCR อ่านไม่ออก ${ur.length} ค่า`, 'ต้องกรอกค่าเองจากรูป', firstAttr(ur[0]), 'กรอกค่า');
  const lc = by('low_conf');
  if (lc.length) push('amber', 'scan', `OCR ไม่มั่นใจ ${lc.length} ค่า`, `ความมั่นใจต่ำกว่า ${pct(L.LOW_CONFIDENCE)}`, firstAttr(lc[0]), 'ดูรูป');
  const ck = by('clock');
  if (ck.length) push('amber', 'clock', `เวลาจาก Pi ยังไม่ยืนยัน ${ck.length} ค่า`, 'ตรวจว่าเข้ารอบบิลถูกเดือน', firstAttr(ck[0]), 'ตรวจ');
  if (!c.rooms.length) push('red', 'rooms', 'ยังไม่มีห้องในทะเบียน', 'เพิ่มห้อง ผู้เช่า และมิเตอร์ก่อน หุ่นถึงผูกค่าได้', 'data-page="rooms"', 'เพิ่มห้อง');
  const missing = c.rooms.filter(r => c.capture.get(r.room_id).meters.length && !c.capture.get(r.room_id).captured);
  if (missing.length) push('amber', 'camera', `ยังไม่มีค่าในรอบนี้ ${missing.length} ห้อง`, `ห้อง ${missing.slice(0, 8).map(r => esc(r.room_id)).join(', ')}${missing.length > 8 ? ' …' : ''}`, `data-page="rooms" data-room="${esc(missing[0].room_id)}"`, 'ดูห้อง');
  const noMeter = c.rooms.filter(r => !c.capture.get(r.room_id).meters.length);
  if (noMeter.length) push('amber', 'rooms', `ห้องไม่มีมิเตอร์ติดตั้ง ${noMeter.length} ห้อง`, `ห้อง ${noMeter.slice(0, 8).map(r => esc(r.room_id)).join(', ')}`, `data-page="rooms" data-room="${esc(noMeter[0].room_id)}"`, 'เพิ่มมิเตอร์');
  const noEmail = c.bills.filter(b => b.noEmail);
  if (noEmail.length) push('amber', 'mail', `ผู้เช่า ${noEmail.length} ห้องยังไม่มีอีเมล`, `ห้อง ${noEmail.map(b => esc(b.room.room_id)).join(', ')} · ดูบิลได้ แต่ส่งไม่ได้`, `data-page="rooms" data-room="${esc(noEmail[0].room.room_id)}"`, 'เพิ่มอีเมล');
  const noRate = L.TYPES.filter(t => !L.rateOn(c.d.rates, t, c.range.to));
  if (noRate.length) push('amber', 'baht', `ยังไม่ตั้งอัตรา${noRate.map(t => L.TYPE_TH[t]).join('และ')}`, `ต้องมีอัตราที่มีผล ณ ${L.dateTh(c.range.to)} ถึงจะคิดบิลได้`, 'data-page="settings"', 'ตั้งอัตรา');
  return list;
}

// การ์ด "จากหุ่น": ตัวตน + อายุข้อมูล → เส้นทางรูปจากหุ่นถึงคลาวด์ → สุขภาพเครื่อง (ทุกค่าคือที่ Pi รายงานตอนซิงก์ ไม่ใช่สถานะสด)
function ageText(iso) {
  const min = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  const text = min < 1 ? 'เมื่อสักครู่' : min < 60 ? `${min} นาทีก่อน` : min < 1440 ? `${Math.round(min / 60)} ชม. ก่อน` : `${Math.round(min / 1440)} วันก่อน`;
  return [text, min <= 120 ? 'good' : min <= 1440 ? 'purple' : 'warn'];
}
// "ต้องดูก่อน": สรุปจำนวน → กลุ่มเร่งด่วน (แดง) / ควรดู (เหลือง) · แต่ละแถวบอกสิ่งที่ต้องทำเป็นคำกริยา
function attentionPanel(items) {
  if (!items.length) return `<div class="attn-clear"><span>${icon('check')}</span><div><b>ไม่มีอะไรค้าง</b><small>ค่าทุกตัวพร้อมคิดบิล</small></div></div>`;
  const groups = [['red', 'เร่งด่วน'], ['amber', 'ควรดู']].map(([t, name]) => [t, name, items.filter(x => x.tone === t)]).filter(g => g[2].length);
  const row = x => `<button class="attn" ${x.attrs}><span class="attn-ic">${icon(x.mark)}</span><span class="attn-copy"><b>${x.title}</b><small>${x.desc}</small></span><span class="attn-act">${x.act || 'ดู'}${icon('arrow')}</span></button>`;
  return `<div class="attn-summary">${groups.map(([t, name, xs]) => `<span class="g-${t}"><b>${xs.length}</b>${name}</span>`).join('')}</div>`
    + groups.map(([t, name, xs]) => `<div class="attn-group g-${t}"><div class="attn-label">${name}</div>${xs.map(row).join('')}</div>`).join('');
}
function devicePanel() {
  const devs = realDevices();
  if (!devs.length) return `<div class="empty">ยังไม่มีหุ่นที่ลงทะเบียน</div>`;
  return devs.map(v => {
    const [age, ageTone] = v.last_seen_at ? ageText(v.last_seen_at) : ['ยังไม่เคยซิงก์', 'warn'];
    const n = x => x ?? '—';
    const rows = v.pending_rows ?? 0, crops = v.pending_crops ?? 0;
    const queued = v.pending_rows == null && v.pending_crops == null ? null : rows + crops;
    const step = (ic, big, label, sub, hot) => `<div class="bf ${hot ? 'hot' : ''}"><span class="bf-ic">${icon(ic)}</span><b>${big}</b><span class="bf-label">${label}</span>${sub ? `<small>${sub}</small>` : ''}</div>`;
    const arrow = '<span class="bf-arrow" aria-hidden="true"><i></i></span>';
    const clean = queued === 0;
    const sd = v.disk_free_mb == null ? null : v.disk_free_mb / 1024;
    const chip = (ic, text, tone) => `<span class="bot-chip ${tone}">${icon(ic)}${text}</span>`;
    return `<div class="bot">
      <div class="bot-head"><span class="bot-avatar">${icon('robot')}</span>
        <div class="bot-id"><b>${esc(v.device_id)}</b><small>${v.last_seen_at ? `ซิงก์ล่าสุด ${L.dateTimeTh(v.last_seen_at)}` : 'ยังไม่เคยส่งข้อมูล'}</small></div>
        ${status(age, ageTone)}</div>
      ${v.warn ? `<div class="bot-warn">${icon('alert')}หุ่นแจ้งเตือน: ${esc(v.warn)}</div>` : ''}
      <div class="bot-flow">
        ${step('camera', n(v.pending_decisions), 'รอคนขับตัดสิน', 'รูปบนหุ่น', v.pending_decisions > 0)}${arrow}
        ${step('upload', n(queued), 'รอส่งขึ้นคลาวด์', queued == null ? '' : `${rows} แถว · ${crops} รูป`, queued > 0)}${arrow}
        ${step('cloud', clean ? icon('check') : '…', 'คลาวด์', clean ? 'ส่งครบแล้ว' : queued == null ? 'ไม่ทราบ' : 'รอซิงก์รอบถัดไป', false)}
      </div>
      <div class="bot-chips">
        ${chip('clock', v.clock_synced == null ? 'นาฬิกา —' : v.clock_synced ? 'นาฬิกาซิงก์แล้ว' : 'นาฬิกายังไม่ซิงก์', v.clock_synced === false ? 'warn' : v.clock_synced ? 'good' : '')}
        ${chip('sd', sd == null ? 'SD —' : `SD ว่าง ${num(sd, 1)} GB`, sd != null && sd < 2 ? 'warn' : '')}
      </div>
    </div>`;
  }).join('') + `<p class="bot-note">ค่าที่หุ่นรายงานตอนซิงก์ ไม่ใช่สถานะสด</p>`;
}

// แถบขั้นของรอบบิล: อ่าน → ยืนยัน → คิดบิล → ส่ง · แต่ละขั้นมีเศษส่วน + แถบความคืบหน้า
function cycleSteps(c, { total, captured, pendingInCycle, ready, blocked }) {
  const withMeters = c.rooms.filter(r => c.capture.get(r.room_id).meters.length);
  const confirmedRooms = withMeters.filter(r => c.capture.get(r.room_id).confirmed).length;
  const billable = c.bills.filter(b => b.state !== 'vacant' || b.inv).length;
  const approved = c.bills.filter(b => b.inv).length, readyNow = c.bills.filter(b => b.view === 'ready').length;
  const sentN = c.bills.filter(b => b.sent === 'sent').length, paidN = c.bills.filter(b => b.pay === 'paid').length;
  const steps = [
    { ic: 'camera', name: 'อ่านมิเตอร์', n: captured, d: total, unit: 'ห้อง', hint: !total ? 'ยังไม่มีห้องที่ติดมิเตอร์' : total - captured ? `ยังขาด ${total - captured} ห้อง` : 'ครบทุกห้อง', page: 'rooms' },
    { ic: 'review', name: 'ยืนยันค่า', n: confirmedRooms, d: total, unit: 'ห้อง', hint: c.queue.length ? `รอยืนยัน ${c.queue.length} ค่า${pendingInCycle !== c.queue.length ? ` (รอบนี้ ${pendingInCycle})` : ''}` : 'ไม่มีค่าค้าง', page: 'review', hot: c.queue.length > 0 },
    { ic: 'lock', name: 'อนุมัติบิล', n: approved, d: billable, unit: 'ห้อง', hint: !billable ? 'ยังไม่มีห้องที่มีผู้เช่า' : readyNow ? `พร้อมอนุมัติ ${readyNow} ห้อง` : blocked ? `ข้อมูลไม่ครบ ${blocked} ห้อง` : 'อนุมัติครบ', page: 'bills', hot: readyNow > 0 },
    { ic: 'mail', name: 'ส่งบิล', n: sentN, d: approved, unit: 'ห้อง', hint: !approved ? 'รออนุมัติบิลก่อน' : `รับเงินแล้ว ${paidN} / ${approved} ห้อง`, page: 'bills', hot: approved > sentN },
  ];
  const html = steps.map((x, i) => {
    const ratio = x.off || !x.d ? 0 : x.n / x.d;
    const st = x.off ? 'off' : ratio >= 1 ? 'done' : ratio > 0 ? 'doing' : 'todo';
    const tag = x.page ? 'button' : 'div';
    return `<${tag} class="cs ${st} ${x.hot && st !== 'done' ? 'hot' : ''}" ${x.page ? `data-page="${x.page}"` : ''} style="--p:${Math.round(ratio * 100)}%">
      <span class="cs-node">${st === 'done' ? icon('check') : icon(x.ic)}</span>
      <span class="cs-step">ขั้น ${i + 1}</span>
      <span class="cs-name">${x.name}</span>
      <span class="cs-num">${x.off ? 'ยังไม่เปิด' : `<b>${x.n}</b><small>/ ${x.d} ${x.unit}</small>`}</span>
      <span class="cs-bar"><i></i></span>
      <span class="cs-hint">${x.hint}</span></${tag}>`;
  }).join('<span class="cs-link" aria-hidden="true"></span>');
  return `<div class="cycle-steps" aria-label="ความคืบหน้ารอบบิล">${html}</div>`;
}
// เริ่มต้นใช้งาน (เปิดใช้จริง 30 ก.ย. · ลบข้อมูลเดโมแล้ว): โชว์จนกว่าจะครบ 5 ขั้น · แต่ละขั้นเช็คจากข้อมูลจริง
const REGISTRY_RESET = '2026-09-29T17:00:00Z'; // = 30 ก.ย. 00:00 เวลาไทย · ลบข้อมูลเดโม · meters.json ที่ส่งออกก่อนหน้านี้มีแต่มิเตอร์เดโม
const markMetersChanged = () => { try { localStorage.setItem('aria.metersChangedAt', new Date().toISOString()); } catch {} render(); };
function onboarding(c) {
  const d = c.d, today = L.todayBkk();
  const live = d.meters.filter(m => L.meterActiveOn(m, today));
  // ตาราง meters ไม่มีเวลาสร้าง → นับว่าส่งออกแล้วเมื่อส่งออกหลังการลบเดโม (REGISTRY_RESET) และหลังแก้มิเตอร์ครั้งล่าสุดในเบราว์เซอร์นี้
  let changed = REGISTRY_RESET;
  try { changed = [changed, localStorage.getItem('aria.metersChangedAt') || ''].sort().pop(); } catch {}
  const exported = !!d.lastExport && live.length > 0 && d.lastExport.exported_at > changed;
  const steps = [
    ['ตั้งชื่อหอ', !!d.settings.dorm_name, 'settings'],
    ['ตั้งอัตราค่าน้ำค่าไฟ', L.TYPES.every(t => L.rateOn(d.rates, t, c.range.to)), 'settings'],
    ['เพิ่มห้อง', d.rooms.length > 0, 'rooms'],
    ['เพิ่มผู้เช่าและมิเตอร์', d.tenancies.length > 0 && live.length > 0, 'rooms'],
    ['ส่งออกให้หุ่น', !!exported, 'rooms'],
  ];
  if (steps.every(x => x[1])) return '';
  const next = steps.findIndex(x => !x[1]);
  return `<section class="onb"><div class="onb-head"><b>เริ่มต้นใช้งาน</b><span>${steps.filter(x => x[1]).length} / ${steps.length}</span></div>
    <div class="onb-steps">${steps.map(([t, ok, page], i) => `<button class="onb-step ${ok ? 'ok' : i === next ? 'next' : ''}" data-page="${page}"${i === 0 && !ok ? ' data-edit="settings-form"' : ''}><span class="onb-dot">${ok ? icon('check') : i + 1}</span>${t}</button>`).join('')}</div></section>`;
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
  ${hasDemo() ? `<div class="demo-note">${icon('alert')}<span>ฐานข้อมูลนี้มีข้อมูลตัวอย่าง (ห้อง 101–110 · หุ่น DEMO-01) ปนอยู่ · ลบได้ก่อนใช้กับหอจริง ดูหน้าตั้งค่า</span></div>` : ''}
  ${onboarding(c)}
  ${cycleSteps(c, { total, captured, pendingInCycle, ready, blocked })}
  <div class="grid two-col">
    <div class="card card-pad"><div class="card-head"><div><h2>ต้องดูก่อน</h2><p>สิ่งที่อาจทำให้บิลคลาดเคลื่อน</p></div><button class="text-link" data-page="review">ไปหน้ายืนยัน →</button></div>
      ${attentionPanel(items)}</div>
    <div class="card card-pad"><div class="card-head"><div><h2>จากหุ่น</h2><p>สถานะที่ส่งมากับการซิงก์ครั้งล่าสุด</p></div></div>${devicePanel()}</div>
  </div>
  ${roomBoard(c)}
  </section>`;
}

// ห้องในรอบนี้ · แผนผังอาคาร (ผู้ใช้เลือกแบบ A 29 ก.ย.) · ช่องละห้อง ไอคอนน้ำ/ไฟ:
// เขียว = ยืนยันแล้ว · เหลือง = มีค่าแต่รอยืนยัน/อ่านไม่ออก · แดง = ยังไม่มีค่า · เทา = ห้องว่าง หรือไม่ได้ติดมิเตอร์ชนิดนั้น
// วาดเป็นผังหอ: แยกชั้นจากเลขห้อง (101 → ชั้น 1) · ห้องครึ่งแรกอยู่ฝั่งบน ครึ่งหลังฝั่งล่าง มีทางเดินคั่น (มือถือ: หมุนเป็นแนวตั้ง)
const METER_STATE = { ok: ['ยืนยันแล้ว', 'good'], wait: ['รอยืนยัน', 'warn'], bad: ['อ่านไม่ออก', 'warn'], unread: ['ยังไม่มีค่า', 'bad'], none: ['ไม่มีมิเตอร์', ''] };
function roomSummary(r, c, i) {
  const cap = c.capture.get(r.room_id);
  const bill = c.bills[i];
  const vacant = bill.state === 'vacant';
  const ms = L.TYPES.map(t => {
    const p = cap.meters.find(x => x.meter.type === t);
    const l = p?.latest;
    const kind = !p ? 'none' : !l ? 'unread' : l.status === 'confirmed' ? 'ok' : (l.confirmed_value ?? l.value) == null ? 'bad' : 'wait';
    const dot = vacant || kind === 'none' ? 'off' : kind === 'unread' ? 'miss' : kind === 'ok' ? 'have' : 'wait';
    return { t, kind, dot, v: l ? l.confirmed_value ?? l.value : null, id: l?.id };
  });
  return { r, bill, vacant, ms };
}
// เลขห้อง 3–4 หลัก → ชั้น = ตัวเลขหน้าสองหลักท้าย (101 → 1, 1203 → 12) · รูปแบบอื่นรวมเป็นกลุ่มเดียว
function floorsOf(list) {
  const m = new Map();
  for (const x of list) { const k = /^\d{3,4}$/.test(x.r.room_id) ? String(Number(x.r.room_id.slice(0, -2))) : ''; if (!m.has(k)) m.set(k, []); m.get(k).push(x); }
  return [...m];
}
function roomBoard(c) {
  const all = c.rooms.map((r, i) => roomSummary(r, c, i));
  if (!all.length) return `<div class="card card-pad"><div class="card-head"><div><h2>ห้องในรอบนี้</h2></div></div><div class="empty">ยังไม่มีห้องในทะเบียน · เพิ่มที่หน้า “ห้องและมิเตอร์”</div></div>`;
  const sel = all.find(x => x.r.room_id === state.homeRoom) || all.find(x => x.ms.some(m => m.dot === 'miss')) || all[0];
  const DOT_TH = { have: 'ยืนยันแล้ว', wait: 'รอยืนยัน', miss: 'ยังไม่มีค่า', off: 'ไม่ต้องอ่าน' };
  const tile = (x, side, i) => `<button class="map-room ${side} ${x.vacant ? 'vacant' : ''} ${x === sel ? 'active' : ''}" style="--i:${i + 1}" data-home-room="${esc(x.r.room_id)}" aria-pressed="${x === sel}"
      aria-label="ห้อง ${esc(x.r.room_id)}${x.vacant ? ' ห้องว่าง' : ''} · ${x.ms.map(m => `${L.TYPE_TH[m.t]}${DOT_TH[m.dot]}`).join(' · ')}">
      <span class="mr-no">${esc(x.r.room_id)}</span><span class="mr-icons">${x.ms.map(m => `<span class="mr-ic ${m.t} ${m.dot}">${icon(m.t)}</span>`).join('')}</span></button>`;
  const line = m => { const [txt, tone] = METER_STATE[m.kind];
    return `<div class="md-line"><span class="mr-ic ${m.t} ${sel.vacant ? 'off' : m.dot}">${icon(m.t)}</span><span class="md-type">${L.TYPE_TH[m.t]}</span><b>${m.kind === 'ok' || m.kind === 'wait' ? num(m.v) : '—'}</b>${status(txt, tone)}</div>`; };
  const pendingM = sel.ms.find(m => m.kind === 'wait' || m.kind === 'bad');
  const pending = !!pendingM;
  const noMeters = sel.ms.every(m => m.kind === 'none');
  const missing = sel.ms.filter(m => !sel.vacant && m.dot === 'miss').length;
  return `<div class="card card-pad room-board"><div class="card-head"><div><h2>ห้องในรอบนี้</h2><p>กดห้องเพื่อดูค่าล่าสุด</p></div>
      <div class="map-legend"><span><i class="have"></i>ยืนยันแล้ว</span><span><i class="wait"></i>รอยืนยัน</span><span><i class="miss"></i>ยังไม่มีค่า</span><span><i class="off"></i>ห้องว่าง</span></div></div>
    <div class="map-layout"><div class="floors">${floorsOf(all).map(([fl, rs]) => {
      const half = Math.ceil(rs.length / 2);
      return `<div class="floor"><div class="floor-label">${fl ? `ชั้น ${esc(fl)}` : 'ผังห้อง'}</div><div class="floor-plan" style="--n:${half}">
        ${rs.slice(0, half).map((x, i) => tile(x, 'side-a', i)).join('')}
        <div class="corridor" aria-hidden="true"><span>ทางเดิน</span></div>
        ${rs.slice(half).map((x, i) => tile(x, 'side-b', i)).join('')}</div></div>`;
    }).join('')}</div>
    <aside class="map-detail" aria-live="polite"><div class="md-head"><span class="md-no">ห้อง ${esc(sel.r.room_id)}</span>${billBadge(sel.bill)}</div>
      ${sel.ms.map(line).join('')}
      <p class="md-note">${sel.vacant ? 'ห้องว่าง · ไม่คิดบิลรอบนี้' : noMeters ? 'ห้องนี้ยังไม่มีมิเตอร์ในทะเบียน' : missing ? `ยังขาด ${missing} มิเตอร์ในรอบนี้ · ให้หุ่นถ่ายเพิ่ม` : pending ? 'มีค่ารอยืนยัน · ตรวจที่หน้ายืนยันค่า' : 'ค่าครบและยืนยันแล้ว'}</p>
      <div class="md-actions">${pending ? `<button class="btn small primary" data-page="review" data-reading="${pendingM.id}">ไปยืนยันค่า</button>` : ''}<button class="btn small" data-page="rooms" data-room="${esc(sel.r.room_id)}">เปิดห้องนี้ ›</button></div>
    </aside></div></div>`;
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
  const head = pageHead('METER REVIEW', 'ยืนยันค่ามิเตอร์', q.length ? `รอยืนยัน ${q.length} ค่า · เรียง ยังไม่ผูก → ถ่ายซ้ำ → ต่ำกว่าค่าก่อน → อ่านไม่ออก → ไม่มั่นใจ → เวลาไม่ยืนยัน → ปกติ` : 'ไม่มีค่าที่รอยืนยัน');
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
  const { meterId, prev, value, flags, dups } = L.readingFlags(r, c.d.readings, mIdx, cycCtx(c.d));
  const meter = meterId ? mIdx.get(meterId) : null;
  const decided = r.status !== 'ocr';
  const manual = r.source === 'manual';   // เจ้าของกรอกเอง ไม่มีรูป (add_manual_reading)
  const tone = r.status === 'confirmed' ? ['ยืนยันแล้ว', 'good'] : r.status === 'rejected' ? ['ปฏิเสธแล้ว', 'bad'] : flags[0] ? FLAG_TEXT[flags[0]] : ['รอยืนยัน', 'purple'];
  const units = value != null && prev ? value - prev.value : null;
  const needReason = flags.some(f => ['below_prev', 'low_conf', 'unreadable', 'clock'].includes(f));
  const cropHtml = r.crop_path
    ? `<img id="crop-img" class="crop-img" alt="รูป crop หน้าปัดมิเตอร์" data-path="${esc(r.crop_path)}"><p class="image-caption" id="crop-cap">กำลังโหลดรูป…</p>`
    : `<div class="crop-missing">${manual ? 'กรอกเองโดยเจ้าของหอ · ไม่มีรูป' : r.crop_expired_at ? `ลบรูปแล้ว ${L.dateTh(L.bkkDate(r.crop_expired_at))} · ตัวเลขยังอยู่ครบ (ลบเมื่อรับเงินครบ 30 วัน หรือรูปอายุ 12 เดือน)` : r.is_demo ? 'ข้อมูลตัวอย่าง — ไม่มีรูป' : 'รูปกำลังซิงก์จาก Pi · ยังยืนยันไม่ได้จนกว่ารูปจะขึ้น'}</div>`;
  const cropBlocks = !r.crop_path && !r.crop_expired_at && !r.is_demo && !manual; // แบบ v1 §4.2 พักการยืนยันที่ต้องอาศัยรูป
  const candidates = c.d.meters.filter(m => (!r.meter_type || m.type === r.meter_type) && L.meterActiveOn(m, L.bkkDate(r.captured_at)))
    .sort((a, b) => (a.room_id === r.room_id ? -1 : 0) - (b.room_id === r.room_id ? -1 : 0) || a.meter_id.localeCompare(b.meter_id, 'en', { numeric: true }));
  const air = r.air ? `<div class="kv-grid air"><div><small>eCO₂</small><b>${esc(r.air.eco2_ppm)} ppm</b></div><div><small>TVOC</small><b>${esc(r.air.tvoc_ppb)} ppb</b></div><div><small>AQI</small><b>${esc(r.air.aqi)}</b></div><div><small>อุณหภูมิ / ชื้น</small><b>${esc(r.air.temp_c)} °C · ${esc(r.air.rh_pct)} %</b></div></div>${r.air.validity ? '<p class="fine">เซนเซอร์ยังไม่พร้อม (validity ≠ 0) ค่าอาจยังไม่นิ่ง</p>' : ''}` : '<p class="fine">ไม่มีค่าอากาศตอนถ่าย</p>';
  const hist = eventsOf(r.id);
  return `<div class="card review-detail">
    <div class="review-header"><div><h2>${meter ? esc(meterLabel(meterId)) : `${r.room_id ? `ห้อง ${esc(r.room_id)}` : 'ไม่ระบุห้อง'} · ${L.TYPE_TH[r.meter_type] ?? '?'}`}</h2><p>${meterId ? `<code>${esc(meterId)}</code>` : 'ยังไม่ผูกมิเตอร์'} · ${manual ? 'อ่าน' : 'ถ่าย'} ${L.dateTimeTh(r.captured_at)} · ${manual ? 'กรอกเอง' : esc(r.device_id)}</p></div>${status(tone[0], tone[1])}</div>
    <div class="image-stage">${cropHtml}</div>
    <div class="reading-comparison">
      <div class="comparison-box"><small>ค่ายืนยันก่อนหน้า</small><strong>${prev ? num(prev.value) : '—'}</strong><small>${prev ? (prev.source === 'start' ? 'ค่าเริ่มตอนติดตั้ง' : L.dateTh(L.bkkDate(prev.at))) : 'ผูกมิเตอร์ก่อน'}</small></div>
      ${manual ? `<div class="comparison-box"><small>กรอกเอง</small><strong>${num(value)}</strong><small>ไม่มีรูป · เหตุผลอยู่ในประวัติ</small></div>` : `<div class="comparison-box"><small>OCR (${esc(r.ocr_engine || '—')})</small><strong>${num(value)}</strong><small>ข้อความดิบ “${esc(r.raw_text ?? '')}” · มั่นใจ ${pct(r.confidence)}</small></div>`}
      <div class="comparison-box"><small>${manual ? 'หน่วยจากค่าที่กรอก' : 'หน่วยถ้ารับ OCR'}</small><strong class="${units != null && units < 0 ? 'neg' : ''}">${num(units)}</strong><small>${meter ? `${meter.digits} หลัก · ทศนิยม ${meter.decimals}` : ''}</small></div>
    </div>
    ${flags.length ? `<div class="alert ${flags.some(f => FLAG_TEXT[f][1] === 'bad') ? 'bad' : 'warn'}">${flags.map(f => `<strong>${FLAG_TEXT[f][0]}</strong>`).join(' · ')}${flags.includes('clock') ? ' — นาฬิกา Pi ยังไม่ซิงก์ตอนถ่าย ตรวจว่ารูปนี้เป็นของรอบนี้จริง' : ''}${flags.includes('duplicate') ? ` — มีรูปของ${meterId ? 'มิเตอร์' : 'ห้อง+ชนิด'}เดียวกันในรอบนี้อีก ${dups.length} รูป เลือกด้านล่างว่าจะใช้รูปไหน` : ''}${flags.includes('below_prev') ? ' — ถ้ามิเตอร์ถูกเปลี่ยนตัว ให้ปลดตัวเก่าและเพิ่มตัวใหม่ที่หน้า “ห้องและมิเตอร์” แล้วผูกค่านี้กับตัวใหม่' : ''}</div>` : ''}
    ${dups.length ? dupPanel(r, dups) : ''}
    <div class="detail-grid"><div class="detail-kv"><small>${manual ? 'กรอกให้' : 'คนขับเลือก'}</small><strong>ห้อง ${esc(r.room_id ?? '—')} · ${L.TYPE_TH[r.meter_type] ?? '—'}</strong></div><div class="detail-kv"><small>${manual ? 'บันทึกเมื่อ' : 'ขึ้นคลาวด์เมื่อ'}</small><strong>${L.dateTimeTh(r.received_at)}</strong></div></div>

    ${meterId && !isEditing('assign-form') ? `<div class="bound-view"><span><small>ผูกกับมิเตอร์</small><b>${esc(meterId)}</b> · ${esc(meterLabel(meterId))}</span><button class="btn small ghost" type="button" data-action="edit" data-form="assign-form">${icon('link')}เปลี่ยน</button></div>`
    : `<form id="assign-form" class="inline-form"><label>ผูกกับมิเตอร์<select name="meter_id" required><option value="">— เลือก —</option>${candidates.map(m => `<option value="${esc(m.meter_id)}" ${m.meter_id === meterId ? 'selected' : ''}>${esc(m.meter_id)} · ${esc(meterLabel(m.meter_id))}</option>`).join('')}</select></label>${meterId ? '<button class="btn small" type="button" data-action="edit-cancel">ยกเลิก</button>' : ''}<button class="btn small primary" type="submit">${meterId ? 'บันทึก' : 'ผูก'}</button></form>`}

    ${r.status === 'rejected' ? `<div class="alert bad reopen-row"><span>ค่านี้ถูกปฏิเสธแล้ว · ให้คนขับถ่ายใหม่ในรอบถัดไป หรือดึงกลับมาตรวจอีกครั้ง</span><button class="btn small" type="button" data-action="reopen" ${state.busy ? 'disabled' : ''}>ดึงกลับมาตรวจ</button></div>` : `
    ${decided && !isEditing('confirm-form') ? `<div class="confirmed-view"><div><small>ค่าที่ยืนยัน</small><b>${num(Number(r.confirmed_value))}</b></div>
      <span class="cv-acts"><button class="btn small" type="button" data-action="edit" data-form="confirm-form" ${!meterId || cropBlocks ? 'disabled' : ''}>${icon('edit')}แก้ค่า</button><button class="btn small" type="button" data-action="reopen" ${state.busy ? 'disabled' : ''} title="กลับเป็นรอยืนยัน · ประวัติเดิมยังอยู่">ยกเลิกการยืนยัน</button></span></div>` : `
    <form id="confirm-form" class="confirm-form${decided ? ' editing-in' : ''}" data-ocr="${value ?? ''}" data-need-reason="${needReason ? 1 : 0}" data-decided="${decided ? 1 : 0}">
      <label>${decided ? 'แก้เป็นค่า' : 'ค่าที่จะยืนยัน'}<input name="value" type="number" inputmode="decimal" step="any" min="0" value="${esc(decided ? r.confirmed_value : value ?? '')}" required ${!meterId || cropBlocks ? 'disabled' : ''}></label>
      <label>เหตุผล ${decided || needReason ? '(จำเป็น)' : '(จำเป็นเมื่อแก้จาก OCR)'}<input name="reason" type="text" maxlength="200" placeholder="เช่น ดูรูปแล้วหลักสุดท้ายเป็น 7" ${!meterId || cropBlocks ? 'disabled' : ''}></label>
      ${decided ? `<button class="btn" type="button" data-action="edit-cancel">ยกเลิก</button><button class="btn primary" type="submit">บันทึกค่าที่แก้</button>` : `<button class="btn primary" type="submit" ${!meterId || cropBlocks ? 'disabled' : ''}>ยืนยันค่า</button><button class="btn danger" type="button" data-action="reject" ${state.busy ? 'disabled' : ''}>ปฏิเสธ</button>`}
    </form>`}
    ${!meterId ? '<p class="fine">ต้องผูกมิเตอร์ก่อน ถึงจะยืนยันได้ (ฐานข้อมูลบังคับ)</p>' : ''}`}

    ${manual ? '' : `<details class="more"><summary>ค่าอากาศตอนถ่าย</summary>${air}</details>`}
    <div class="history"><strong>ประวัติ</strong><br>${manual ? `กรอกเอง ${num(value)} · เวลาที่อ่าน` : `หุ่นอ่าน OCR ${num(value)} ·`} ${L.dateTimeTh(r.captured_at)}${r.decided_at && !manual ? ` · คนขับกด “เก็บ” ${L.dateTimeTh(r.decided_at)}` : ''}
      ${hist.map(e => `<br>${EVENT_TEXT[e.event]}${e.confirmed_value != null ? ` ${num(Number(e.confirmed_value))}` : ''}${e.meter_id ? ` → ${esc(e.meter_id)}` : ''}${e.reason ? ` · “${esc(e.reason)}”` : ''} · ${actorText(e.actor)} · ${L.dateTimeTh(e.at)}`).join('')}</div>
  </div>`;
}

// signed URL อายุ 5 นาที · สร้างใหม่ทุกครั้งที่เปิดรายการ (bucket crops เป็น private)
async function loadCrop() {
  document.querySelectorAll('img.dup-crop:not([src])').forEach(async t => { try { t.src = await api.cropUrl(t.dataset.path); } catch { t.replaceWith(Object.assign(document.createElement('span'), { textContent: 'โหลดรูปไม่ได้' })); } });
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
  if (decided && v === Number(r.confirmed_value)) { toast('ค่าเดิม · ไม่มีอะไรเปลี่ยน'); stopEdit(); return; }   // กันแถว corrected ซ้ำ (เจอบนเว็บจริง 3 ต.ค.: reading 39 สองแถวห่าง 3 วินาที)
  if ((changed || form.dataset.needReason === '1') && !reason) return toast('ต้องใส่เหตุผลเมื่อแก้ค่าจาก OCR หรือค่ามีธงเตือน', true);
  const ev = { reading_id: r.id, event: changed ? 'corrected' : 'confirmed', confirmed_value: v, reason: reason || null };
  const next = L.reviewQueue(state.data.readings, mIdx, cycCtx(state.data)).map(x => x.r.id).find(id => id !== r.id);
  if (await write(() => api.addEvent(ev), `${changed ? 'แก้และยืนยัน' : 'ยืนยัน'} ${num(v)} แล้ว`) && !decided && next) { state.selectedReading = next; render(); }
}

async function rejectReading() {
  const r = state.data.readings.find(x => x.id === state.selectedReading);
  const reason = prompt('เหตุผลที่ปฏิเสธ (เช่น รูปเบลอ / ถ่ายผิดห้อง) — เว้นว่างได้');
  if (reason === null) return;
  const next = L.reviewQueue(state.data.readings, mIdx, cycCtx(state.data)).map(x => x.r.id).find(id => id !== r.id);
  if (await write(() => api.addEvent({ reading_id: r.id, event: 'rejected', reason: reason.trim() || null }), 'ปฏิเสธแล้ว · รอถ่ายใหม่') && next) { state.selectedReading = next; render(); }
}

// ถ่ายซ้ำ: รูปทุกใบของมิเตอร์/ห้องเดียวกันในรอบนี้ (รวมใบที่เปิดอยู่) · เลือก "ใช้รูปนี้" = ปฏิเสธใบที่เหลือ (ดึงกลับได้จากประวัติ)
function dupPanel(r, dups) {
  const all = [r, ...dups].sort((a, b) => a.captured_at.localeCompare(b.captured_at));
  const card = x => {
    const v = x.status === 'confirmed' ? Number(x.confirmed_value) : x.value == null ? null : Number(x.value);
    const img = x.crop_path ? `<img class="dup-crop" alt="" data-path="${esc(x.crop_path)}">` : `<span>${x.source === 'manual' ? 'กรอกเอง' : 'ไม่มีรูป'}</span>`;
    return `<div class="dup-item${x.id === r.id ? ' current' : ''}">
      <button class="dup-thumb" type="button" data-page="review" data-reading="${x.id}" title="เปิดรูปนี้">${img}</button>
      <div class="dup-meta"><b>${num(v)}</b><small>${L.dateTimeTh(x.captured_at)}</small><small>${x.status === 'confirmed' ? 'ยืนยันแล้ว' : x.source === 'manual' ? 'กรอกเอง · รอยืนยัน' : 'รอยืนยัน'}${x.id === r.id ? ' · ใบนี้' : ''}</small></div>
      <button class="btn small${x.id === r.id ? ' primary' : ''}" type="button" data-action="keep-dup" data-keep="${x.id}" ${state.busy ? 'disabled' : ''}>ใช้รูปนี้</button>
    </div>`;
  };
  return `<div class="dup-panel"><div class="dup-head"><strong>ถ่ายซ้ำ ${all.length} รูปในรอบนี้ · เลือกรูปที่จะใช้</strong><small>รูปที่ไม่เลือกจะถูกปฏิเสธ (ดึงกลับมาตรวจได้) · ถ้าตั้งใจอ่านหลายครั้งในรอบ ยืนยันตามปกติได้ — บิลใช้ค่าล่าสุดที่ยืนยัน</small></div><div class="dup-list">${all.map(card).join('')}</div></div>`;
}

async function keepDuplicate(keepId) {
  const r = state.data.readings.find(x => x.id === state.selectedReading);
  const keep = state.data.readings.find(x => x.id === keepId);
  if (!r || !keep) return;
  const { dups } = L.readingFlags(r, state.data.readings, mIdx, cycCtx(state.data));
  const others = [r, ...dups].filter(x => x.id !== keepId && x.status !== 'rejected');
  if (!others.length) return;
  const confirmedN = others.filter(x => x.status === 'confirmed').length;
  const when = L.dateTimeTh(keep.captured_at);
  if (!confirm(`ใช้รูป ${when} แล้วปฏิเสธอีก ${others.length} รูป${confirmedN ? `\n(${confirmedN} รูปในนี้ยืนยันค่าไปแล้ว — ค่านั้นจะไม่ถูกใช้คิดบิล)` : ''}\nดึงกลับมาตรวจได้ภายหลัง`)) return;
  const reason = `ถ่ายซ้ำ — เลือกใช้รูป ${when}`;
  const ok = await write(async () => { for (const x of others) await api.addEvent({ reading_id: x.id, event: 'rejected', reason }); },
    `เลือกรูป ${when} · ปฏิเสธรูปซ้ำ ${others.length} รูป`);
  if (!ok) return;
  // รูปที่เลือกยังรอยืนยัน = อยู่ที่ใบนั้นต่อ (ยืนยันค่า) · ยืนยันไปแล้ว = ไปคิวถัดไป
  const after = state.data.readings.find(x => x.id === keepId);
  state.selectedReading = after?.status === 'ocr' ? keepId : (L.reviewQueue(state.data.readings, mIdx, cycCtx(state.data))[0]?.r.id ?? keepId);
  render();
}

// ยกเลิกการยืนยัน/ปฏิเสธ → กลับเป็นรอยืนยัน (event 'reopened') · บิลที่อนุมัติแล้วไม่เปลี่ยนเอง → หน้าบิลขึ้น "ค่าเปลี่ยน" ให้ออกฉบับแก้ไข
async function reopenReading() {
  const r = state.data.readings.find(x => x.id === state.selectedReading);
  const meterId = L.readingMeterId(r, mIdx);
  const roomId = meterId ? mIdx.get(meterId)?.room_id : r.room_id;
  const cyc = L.cycleOfDate(L.bkkDate(r.captured_at), state.data.cycles, state.data.settings);
  const inv = (state.data.invoices || []).find(v => v.cycle === cyc && v.room_id === roomId && v.state === 'approved');
  const warn = inv && r.status === 'confirmed' ? `\n\nห้อง ${roomId} อนุมัติบิลรอบ${L.cycleLabel(cyc)} ไปแล้ว · บิลเดิมไม่เปลี่ยนเอง ต้องยืนยันค่าใหม่แล้วออกฉบับแก้ไขที่หน้าบิล` : '';
  const reason = prompt(`${r.status === 'confirmed' ? `ยกเลิกการยืนยันค่า ${num(Number(r.confirmed_value))}` : 'ดึงค่าที่ปฏิเสธกลับมาตรวจ'} → กลับเป็น “รอยืนยัน”${warn}\n\nเหตุผล (เว้นว่างได้)`);
  if (reason === null) return;
  await write(() => api.addEvent({ reading_id: r.id, event: 'reopened', reason: reason.trim() || null }), 'กลับเป็นรอยืนยันแล้ว');
}

// กรอกเลขเอง: เวลาที่อ่าน (เวลาไทย) ตัดสินรอบบิลเหมือนเวลาถ่ายของหุ่น
function showManualForm(meterId) {
  const m = mIdx.get(meterId);
  const last = state.data.readings.filter(r => L.readingMeterId(r, mIdx) === meterId && r.status === 'confirmed').sort((a, b) => b.captured_at.localeCompare(a.captured_at))[0];
  const nowBkk = new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 16);
  openModal(`<div class="modal-head"><div><h2 id="modal-title">กรอกเลข ${esc(meterId)}</h2><p class="muted" style="font-size:12px;margin:0">${esc(meterLabel(meterId))} · ล่าสุด ${last ? `${num(Number(last.confirmed_value))} (${L.dateTh(L.bkkDate(last.captured_at))})` : `ค่าเริ่ม ${num(Number(m.start_value))}`}</p></div><button type="button" aria-label="ปิด" data-action="close-modal">×</button></div>
    <form id="manual-form" class="set-inline manual-form" data-meter="${esc(meterId)}">
      <label class="mini-field"><small>เลขบนหน้าปัด</small><input name="value" type="number" inputmode="decimal" min="0" step="any" required autofocus></label>
      <label class="mini-field"><small>เวลาที่อ่าน (เวลาไทย)</small><input name="at" type="datetime-local" value="${nowBkk}" min="${esc(m.installed_at)}T00:00" max="${nowBkk}" required></label>
      <label class="mini-field wide"><small>เหตุผล (จำเป็น · ไม่มีรูปเป็นหลักฐาน)</small><input name="reason" maxlength="200" required placeholder="เช่น หุ่นเข้าห้องนี้ไม่ได้ · จดจากหน้าปัดเอง"></label>
      <button class="btn primary small" type="submit">บันทึกและยืนยัน</button></form>
    <p class="set-hint">ค่าที่กรอกถูกยืนยันทันที · ต้องไม่ต่ำกว่าค่าที่ยืนยันก่อนหน้า · ยกเลิกได้ภายหลังที่หน้ายืนยันค่า</p>`);
  $('#manual-form [name=value]')?.focus();
}

async function submitManual(form) {
  const f = new FormData(form);
  const raw = String(f.get('value') ?? '').trim();
  const v = Number(raw);
  const reason = String(f.get('reason') || '').trim();
  const at = String(f.get('at') || '');
  if (!raw || !Number.isFinite(v) || v < 0) return toast('ใส่ค่าเป็นตัวเลขไม่ติดลบ', true);
  if (!reason) return toast('ต้องใส่เหตุผลที่กรอกเอง', true);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(at)) return toast('เวลาที่อ่านไม่ถูกต้อง', true);
  const iso = new Date(`${at}:00+07:00`).toISOString();
  if (await write(() => api.addManualReading(form.dataset.meter, v, iso, reason), `บันทึก ${form.dataset.meter} = ${num(v)} แล้ว`)) closeModal();
}

async function submitAssign(form) {
  const meterId = new FormData(form).get('meter_id');
  if (!meterId) return;
  const r = state.data.readings.find(x => x.id === state.selectedReading);
  if (r.status === 'confirmed' && !confirm('ค่านี้ยืนยันแล้ว · ผูกมิเตอร์ใหม่จะล้างค่าที่ยืนยันและต้องยืนยันใหม่ ตกลงไหม')) return;
  await write(() => api.addEvent({ reading_id: r.id, event: 'assigned', meter_id: meterId }), `ผูกกับ ${meterId} แล้ว`);
}

// ───────── บิล (พรีวิว) ─────────
const BILL_FILTERS = [['all', 'ทั้งหมด'], ['ready', 'รออนุมัติ'], ['approved', 'อนุมัติแล้ว'], ['unpaid', 'ค้างชำระ'], ['paid', 'ชำระแล้ว'], ['blocked', 'ติดปัญหา'], ['noemail', 'ไม่มีอีเมล'], ['vacant', 'ห้องว่าง']];
const billMatch = (b, f) => f === 'all' || (f === 'noemail' ? b.noEmail : f === 'paid' ? b.pay === 'paid' : f === 'unpaid' ? b.pay === 'unpaid' || b.pay === 'partial' : b.view === f);
const SEND_TH = { sent: ['ส่งแล้ว', 'good'], failed: ['ส่งไม่สำเร็จ', 'bad'] };
const PAY_TH = { paid: ['ชำระแล้ว', 'good'], partial: ['ชำระบางส่วน', 'warn'], unpaid: ['ค้างชำระ', 'idle'] };
const METHOD_TH = { promptpay: 'พร้อมเพย์', transfer: 'โอน', cash: 'เงินสด', other: 'อื่นๆ' };
// เหตุผลแบบสั้นบนการ์ด (ตัดรหัสมิเตอร์/วันที่ออก · ตัวเต็มอยู่ในหน้ารายละเอียด)
const shortReason = r => r.replace(/\s*\([^)]*\)\s*$/, '').replace(/ที่มีผล ณ .*$/, '').trim();
// อัตรายังไม่ตั้ง = ปัญหาระดับหน้า (ชิปแดงบนแถบสรุป) → ไม่ซ้ำบนทุกการ์ด · การ์ดโชว์เหตุผลของห้องนั้นก่อน
function whyLine(reasons) {
  const own = reasons.filter(r => !r.startsWith('ยังไม่ตั้งอัตรา'));
  const text = own.length ? shortReason(own[0]) : 'รอตั้งอัตรา';
  const more = own.length > 1 ? ` <em>+${own.length - 1}</em>` : '';
  return `<span class="bc-why">${icon('alert')}${esc(text)}${more}</span>`;
}
const BILL_STATE = { approved: ['อนุมัติแล้ว', 'good'], ready: ['รออนุมัติ', 'ready'], blocked: ['ติดปัญหา', 'warn'], vacant: ['ห้องว่าง', 'off'] };

// ── อนุมัติบิล (migration 20261003000100): ส่ง snapshot ของพรีวิว · ฐานข้อมูลคำนวณยอดเอง · แก้หลังอนุมัติ = ออกฉบับใหม่ ──
function invoicePayload(b) {
  const side = t => { const l = b.lines[t], sg = l.segments;
    return { [`${t}_prev`]: sg[0]?.base ?? null, [`${t}_curr`]: sg[sg.length - 1]?.curr ?? null, [`${t}_units`]: l.units, [`${t}_rate`]: l.rate }; };
  return { room_id: b.room.room_id, tenancy_id: b.tenancy.id, tenant_name: b.tenancy.tenant_name, recipient_email: b.tenancy.email || null,
    ...side('water'), ...side('electric'), rent_baht: b.includeRent ? b.rent : 0,
    detail: { segments: { water: b.lines.water.segments, electric: b.lines.electric.segments }, range: b.range } };
}
// ค่าที่เปลี่ยนไปหลังอนุมัติ (เทียบหน่วย/อัตรา/ค่าเช่า/ผู้รับ ไม่เทียบยอด → ไม่หลอกเพราะการปัดเศษ)
function invoiceDiff(v, b) {
  if (b.state !== 'ready') return [b.state === 'vacant' ? 'ห้องไม่มีผู้เช่าแล้ว' : 'ข้อมูลตอนนี้ยังไม่ครบ'];
  const p = invoicePayload(b), out = [];
  const same = (x, y) => Math.abs(Number(x) - Number(y)) < 1e-6;
  if (!same(p.water_units, v.water_units) || !same(p.water_rate, v.water_rate)) out.push('ค่าน้ำ');
  if (!same(p.electric_units, v.electric_units) || !same(p.electric_rate, v.electric_rate)) out.push('ค่าไฟ');
  if (!same(p.rent_baht, v.rent_baht)) out.push('ค่าเช่า');
  if (p.tenant_name !== v.tenant_name || (p.recipient_email || null) !== (v.recipient_email || null)) out.push('ผู้เช่า/อีเมล');
  return out;
}
async function approveBills(rooms, revise = false) {
  const c = ctx();
  const items = c.bills.filter(b => rooms.includes(b.room.room_id) && b.state === 'ready').map(b => ({ ...invoicePayload(b), revise }));
  if (!items.length) return;
  const sum = items.reduce((s, it) => s + Math.round(it.water_units * it.water_rate * 100) / 100 + Math.round(it.electric_units * it.electric_rate * 100) / 100 + Number(it.rent_baht), 0);
  const what = items.length === 1 ? `ห้อง ${items[0].room_id}` : `${items.length} ห้อง`;
  const zero = items.filter(it => ['water', 'electric'].some(t => (it.detail.segments[t] || []).some(x => x.baseSource === 'start' && x.base === 0 && x.units > 0))).map(it => it.room_id);
  const warnRooms = c.bills.filter(b => rooms.includes(b.room.room_id) && b.state === 'ready' && (b.warnings || []).length).map(b => b.room.room_id);
  const zeroNote = (warnRooms.length ? `\n\n⚠ ห้อง ${warnRooms.join(', ')} ฐานไม่ตรงกับข้อมูลรอบก่อน · ดูคำเตือนในหน้าต่างบิล` : '') + (zero.length ? `\n\n⚠ ห้อง ${zero.join(', ')} ฐานมิเตอร์ = 0 → คิดทุกหน่วยบนหน้าปัด · ตรวจค่าเริ่มของมิเตอร์ก่อน` : '');
  if (!confirm(`${revise ? 'ออกฉบับแก้ไข' : 'อนุมัติบิล'} ${what} · รอบ${L.cycleLabel(state.cycle)}\nยอดรวม ${baht(sum)}\n\nอนุมัติแล้วยอดจะถูกตรึง แก้ภายหลังต้องออกฉบับแก้ไข (ฉบับเดิมเก็บเป็นประวัติ)${zeroNote}`)) return;
  const row = c.d.cycles.find(x => x.cycle === state.cycle);
  if (await write(() => api.approveInvoices(state.cycle, row?.cutoff_date ?? c.range.to, items), `${revise ? 'ออกฉบับแก้ไข' : 'อนุมัติ'} ${what} แล้ว`)) closeModal();
}

// หน้าบิล (ออกแบบใหม่ 30 ก.ย. · อนุมัติ 3 ต.ค.): แถบสรุป → ตัวกรอง → การ์ดห้องละใบ · รายละเอียดเต็มอยู่ในหน้าต่างบิล
function renderBills(c) {
  const row = c.d.cycles.find(x => x.cycle === state.cycle);
  const list = c.bills.filter(b => billMatch(b, state.billFilter));
  const n = k => c.bills.filter(b => b.view === k).length;
  const approvedSum = c.bills.filter(b => b.inv).reduce((s, b) => s + Number(b.inv.total_baht), 0);
  const ready = c.bills.filter(b => b.view === 'ready');
  const readySum = ready.reduce((s, b) => s + b.total, 0);
  const rateChip = t => { const x = L.rateOn(c.d.rates, t, c.range.to);
    return x ? `<span class="rate-chip ${t}">${icon(t)}<b>${baht(Number(x.baht_per_unit))}</b><small>/หน่วย</small></span>`
      : `<button class="rate-chip missing" data-page="settings">${icon(t)}ยังไม่ตั้งอัตรา</button>`; };
  const seg = k => `<i class="${BILL_STATE[k][1]}" style="flex:${n(k)}"></i>`;
  const locked = c.bills.some(b => b.inv);
  const rent = `<label class="rent-switch" title="${locked ? 'มีบิลที่อนุมัติแล้วในรอบนี้ · เปลี่ยนแล้วบิลเหล่านั้นจะขึ้นว่าข้อมูลเปลี่ยน' : 'ค่าเช่ากำหนดต่อผู้เช่า · ตั้งแยกรายรอบ'}"><input id="include-rent" type="checkbox" ${row?.include_rent ? 'checked' : ''} ${row?.state === 'closed' ? 'disabled' : ''}><span class="sw" aria-hidden="true"></span>รวมค่าเช่า</label>`;
  const line = (b, t) => { const l = b.lines[t];
    return `<span class="bl ${t} ${l.ok ? '' : 'none'}"><span class="bl-ic">${icon(t)}</span><span class="bl-u">${l.ok ? `${num(l.units)} หน่วย` : '—'}</span><b>${l.ok && l.amount != null ? baht(l.amount) : ''}</b></span>`; };
  const invLine = (v, t) => `<span class="bl ${t}"><span class="bl-ic">${icon(t)}</span><span class="bl-u">${num(Number(v[`${t}_units`]))} หน่วย</span><b>${baht(Number(v[`${t}_amount`]))}</b></span>`;
  const card = b => {
    const [label, tone] = BILL_STATE[b.view];
    const v = b.inv;
    const foot = v ? `<span class="bc-total"><small>${b.changed.length ? `<span class="bc-changed" title="เปลี่ยน: ${esc(b.changed.join(', '))}">${icon('alert')}ข้อมูลเปลี่ยน</span>` : `ฉบับ ${v.revision}`}</small>${baht(Number(v.total_baht))}</span>`
      : b.view === 'ready' ? `<span class="bc-total"><small>รวม</small>${baht(b.total)}</span>`
      : b.view === 'vacant' ? `<span class="bc-note">ไม่ออกบิลรอบนี้</span>`
      : whyLine(b.reasons);
    const lines = v ? `${invLine(v, 'water')}${invLine(v, 'electric')}${Number(v.rent_baht) ? `<span class="bl rent"><span class="bl-ic">${icon('rooms')}</span><span class="bl-u">ค่าเช่า</span><b>${baht(Number(v.rent_baht))}</b></span>` : ''}`
      : `${line(b, 'water')}${line(b, 'electric')}${b.includeRent ? `<span class="bl rent"><span class="bl-ic">${icon('rooms')}</span><span class="bl-u">ค่าเช่า</span><b>${baht(b.rent)}</b></span>` : ''}`;
    return `<button class="bill-card ${tone}" data-bill="${esc(b.room.room_id)}">
      <span class="bc-head"><span class="bc-room">${esc(b.room.room_id)}</span><span class="bc-state">${v ? icon('lock') : '<i></i>'}${label}</span></span>
      <span class="bc-tenant">${v ? esc(v.tenant_name) : b.tenancy ? esc(b.tenancy.tenant_name) : 'ไม่มีผู้เช่า'}${b.noEmail ? `<span class="bc-noemail" title="ยังไม่มีอีเมล · ส่งบิลไม่ได้">${icon('mail')}</span>` : ''}</span>
      ${b.view === 'vacant' ? '' : `<span class="bc-lines">${lines}</span>`}
      ${v ? `<span class="bc-chips">${b.sent ? `<span class="mini ${SEND_TH[b.sent][1]}">${icon('mail')}${SEND_TH[b.sent][0]}</span>` : `<span class="mini idle">${icon('mail')}${b.inv.recipient_email ? 'ยังไม่ส่ง' : 'ไม่มีอีเมล'}</span>`}<span class="mini ${PAY_TH[b.pay][1]}">${icon('baht')}${PAY_TH[b.pay][0]}</span></span>` : ''}
      <span class="bc-foot">${foot}</span></button>`;
  };
  const toSend = c.bills.filter(b => b.inv && b.inv.recipient_email && b.sent !== 'sent');   // รวมฉบับที่เคยส่งไม่สำเร็จ
  return `<section class="page">
  ${pageHead('BILLING', 'บิล', `รอบ${L.cycleLabel(state.cycle)} · ตัดรอบ ${L.dateTh(c.range.to)}`, `${ready.length ? `<button class="btn primary" data-action="approve-all">${icon('lock')}อนุมัติ ${ready.length} ห้องที่พร้อม</button>` : ''}${toSend.length ? `<button class="btn" data-action="send-all">${icon('mail')}ส่งอีเมล ${toSend.length} ฉบับ</button>` : ''}${rent}`)}
  <div class="bill-summary">
    <div class="bs-sum"><small>ยอดที่อนุมัติแล้ว</small><b>${baht(approvedSum)}</b><span>รับแล้ว ${baht(c.bills.reduce((t, b) => t + (b.inv ? Math.min(b.paid, Number(b.inv.total_baht)) : 0), 0))}${ready.length ? ` · รออนุมัติอีก ${ready.length} ห้อง` : ''}</span></div>
    <div class="bs-mix"><div class="bs-bar">${seg('approved')}${seg('ready')}${seg('blocked')}${seg('vacant')}</div>
      <div class="bs-legend"><span class="good"><i></i>อนุมัติแล้ว ${n('approved')}</span><span class="ready"><i></i>รออนุมัติ ${n('ready')}</span><span class="warn"><i></i>ติดปัญหา ${n('blocked')}</span><span class="off"><i></i>ว่าง ${n('vacant')}</span></div></div>
    <div class="bs-rates">${rateChip('water')}${rateChip('electric')}</div>
  </div>
  <div class="bill-filters" role="group" aria-label="ตัวกรอง">${BILL_FILTERS.map(([k, t]) => `<button class="${state.billFilter === k ? 'active' : ''}" data-filter="${k}" aria-pressed="${state.billFilter === k}">${t}<em>${c.bills.filter(b => billMatch(b, k)).length}</em></button>`).join('')}</div>
  ${list.length ? `<div class="bill-grid">${list.map(card).join('')}</div>` : '<div class="card card-pad"><div class="empty">ไม่มีห้องในตัวกรองนี้</div></div>'}
  </section>`;
}

function showBill(roomId) {
  const c = ctx();
  const b = c.bills.find(x => x.room.room_id === roomId);
  const v = b.inv;
  const [label, tone] = BILL_STATE[b.view];
  const segsOf = t => v ? v.detail?.segments?.[t] : b.lines[t].segments;
  const zeroBase = ['water', 'electric'].flatMap(t => (segsOf(t) || []).filter(x => x.baseSource === 'start' && Number(x.base) === 0 && Number(x.units) > 0).map(x => x.meter_id));
  const seg = (segs) => (segs || []).map(s => `<small class="inv-meter">${esc(s.meter_id)} · ${num(s.base)} → ${num(s.curr)}${s.baseSource === 'start' ? ' · ฐาน = ค่าตอนติดตั้ง' : s.baseSource === 'invoice' ? ' · ฐาน = บิลรอบก่อน' : ''}</small>`).join('');
  const line = t => { const l = b.lines[t];
    return `<div class="inv-line ${t}"><span class="bl-ic">${icon(t)}</span><div><b>ค่า${L.TYPE_TH[t]}</b><small>${l.ok ? `${num(l.units)} หน่วย × ${l.rate != null ? baht(l.rate) : '?'}` : 'ยังคำนวณไม่ได้'}</small>${seg(l.segments)}</div><strong>${baht(l.amount)}</strong></div>`; };
  const vline = t => `<div class="inv-line ${t}"><span class="bl-ic">${icon(t)}</span><div><b>ค่า${L.TYPE_TH[t]}</b><small>${num(Number(v[`${t}_units`]))} หน่วย × ${baht(Number(v[`${t}_rate`]))}</small>${seg(v.detail?.segments?.[t])}</div><strong>${baht(Number(v[`${t}_amount`]))}</strong></div>`;
  const history = (c.d.invoices || []).filter(x => x.cycle === state.cycle && x.room_id === roomId && x.state === 'superseded').sort((a, b2) => b2.revision - a.revision);
  const body = v ? `${vline('water')}${vline('electric')}${Number(v.rent_baht) ? `<div class="inv-line rent"><span class="bl-ic">${icon('rooms')}</span><div><b>ค่าเช่า</b></div><strong>${baht(Number(v.rent_baht))}</strong></div>` : ''}
      <div class="inv-total"><span>รวม · ฉบับ ${v.revision}</span><b>${baht(Number(v.total_baht))}</b></div>`
    : `${line('water')}${line('electric')}${b.includeRent && b.tenancy ? `<div class="inv-line rent"><span class="bl-ic">${icon('rooms')}</span><div><b>ค่าเช่า</b></div><strong>${baht(b.rent)}</strong></div>` : ''}
      <div class="inv-total"><span>รวม</span><b>${baht(b.total)}</b></div>`;
  const who = v ? (v.tenant_name) : b.tenancy?.tenant_name;
  const mail = v ? (v.recipient_email || 'ยังไม่มีอีเมล') : b.tenancy ? (b.tenancy.email || 'ยังไม่มีอีเมล') : 'ไม่มีผู้เช่า';
  const actions = [];
  if (!v && b.state === 'ready') actions.push(`<button class="btn primary" data-action="approve" data-bill-room="${esc(roomId)}">${icon('lock')}อนุมัติบิลนี้</button>`);
  if (v && b.changed.length && b.state === 'ready') actions.push(`<button class="btn primary" data-action="revise" data-bill-room="${esc(roomId)}">ออกฉบับแก้ไข</button>`);
  if (v && v.recipient_email) actions.push(`<button class="btn ${b.sent ? '' : 'primary'}" data-action="send-one" data-bill-room="${esc(roomId)}">${icon('mail')}${b.sent ? 'ส่งอีเมลซ้ำ' : 'ส่งอีเมล'}</button>`);
  if (!v && b.reasons.some(r => r.startsWith('ยังไม่ยืนยัน'))) actions.push(`<button class="btn primary" data-page="review">ไปยืนยันค่า</button>`);
  if (!v && b.reasons.some(r => r.startsWith('ยังไม่ตั้งอัตรา'))) actions.push(`<button class="btn primary" data-page="settings">ตั้งอัตรา</button>`);
  openModal(`<div class="modal-head"><div><h2 id="modal-title">ห้อง ${esc(roomId)}</h2><p class="muted" style="font-size:12px;margin:0">รอบ${L.cycleLabel(state.cycle)}${who ? ` · ${esc(who)}` : ''}</p></div><button type="button" aria-label="ปิด" data-action="close-modal">×</button></div>
    <div class="inv" data-bill-modal="${esc(roomId)}">
      <div class="inv-top"><span class="bc-state ${tone}">${v ? icon('lock') : '<i></i>'}${label}</span><span class="inv-mail">${icon('mail')}${esc(mail)}</span></div>
      ${body}
    </div>
    ${v && b.changed.length ? `<ul class="inv-why"><li>${icon('alert')}ข้อมูลเปลี่ยนหลังอนุมัติ: ${esc(b.changed.join(', '))}${b.state === 'ready' ? ` · ยอดใหม่ ${baht(b.total)}` : ''}</li></ul>` : ''}
    ${(b.warnings || []).length && b.state === 'ready' ? `<ul class="inv-why">${b.warnings.map(w => `<li>${icon('alert')}${esc(w)}</li>`).join('')}</ul>` : ''}
    ${zeroBase.length ? `<ul class="inv-why"><li>${icon('alert')}ฐานของ ${esc(zeroBase.join(', '))} = 0 (ค่าตอนติดตั้ง) · บิลนี้คิดทุกหน่วยบนหน้าปัด · ถ้าวันติดตั้งหน้าปัดไม่ใช่ 0 ให้แก้ค่าเริ่มของมิเตอร์ก่อนอนุมัติ${v ? ' แล้วออกฉบับแก้ไข' : ''}</li></ul>` : ''}
    ${!v && b.reasons.length ? `<ul class="inv-why">${b.reasons.map(r => `<li>${icon('alert')}${esc(r)}</li>`).join('')}</ul>` : ''}
    ${v ? billFollowUp(b) : ''}
    <p class="inv-note">${v ? `อนุมัติโดย ${esc(v.approved_by)} · ${L.dateTimeTh(v.approved_at)}${history.length ? ` · ฉบับเดิม ${history.map(h => `#${h.revision} ${baht(Number(h.total_baht))}`).join(', ')}` : ''}` : 'พรีวิว · ยังไม่ใช่เอกสารเรียกเก็บเงิน'}</p>
    <div class="modal-actions">${actions.map((h, i) => i ? h.replace('btn primary', 'btn') : h).join('')}<button class="btn" data-action="close-modal">ปิด</button></div>`);   // ปุ่มหลักได้ทีละปุ่ม (HIG)
}

// ส่วนท้ายหน้าต่างบิลที่อนุมัติแล้ว: ผลการส่งอีเมล + การรับเงิน (บันทึก/ยกเลิก)
function billFollowUp(b) {
  const v = b.inv, due = Number(v.total_baht), left = Math.max(0, Math.round((due - b.paid) * 100) / 100);
  const sends = b.attempts.length ? b.attempts.slice(0, 4).map(a => `<li class="${a.result}"><span>${a.result === 'sent' ? 'ส่งแล้ว' : 'ส่งไม่สำเร็จ'} · ${esc(a.to_email)}</span><small>${L.dateTimeTh(a.attempted_at)}${a.error ? ` · ${esc(a.error)}` : ''}</small></li>`).join('')
    : `<li class="none"><span>${v.recipient_email ? 'ยังไม่ได้ส่ง' : 'ผู้เช่าไม่มีอีเมล · ส่งไม่ได้'}</span></li>`;
  const pays = b.payments.map(p => `<li class="${p.voided_at ? 'void' : ''}"><span>${baht(Number(p.amount))} · ${METHOD_TH[p.method]} · ${L.dateTh(p.paid_on)}</span><small>${p.voided_at ? `ยกเลิก: ${esc(p.void_reason)}` : `บันทึกโดย ${esc(p.recorded_by)}`}${p.note ? ` · ${esc(p.note)}` : ''}</small>${p.voided_at ? '' : `<button class="mt-retire" data-action="void-pay" data-pay-id="${p.id}">ยกเลิก</button>`}</li>`).join('');
  const [pt, pc] = PAY_TH[b.pay];
  return `<div class="inv-follow">
    <section><h4>${icon('mail')}อีเมล</h4><ul class="fu-list">${sends}</ul></section>
    <section><h4>${icon('baht')}รับเงิน <span class="mini ${pc}">${pt}</span><small>${left ? `ค้าง ${baht(left)}` : 'ครบแล้ว'}</small></h4>
      ${pays ? `<ul class="fu-list">${pays}</ul>` : ''}
      ${left ? `<form id="pay-form" class="set-inline" data-pay-room="${esc(b.room.room_id)}" data-key="${payKey(b)}">
        <label class="mini-field"><small>ยอด (บาท)</small><input name="amount" type="number" min="0.01" step="0.01" value="${left.toFixed(2)}" required></label>
        <label class="mini-field"><small>วันที่รับ</small><input name="paid_on" type="date" value="${L.todayBkk()}" required></label>
        <label class="mini-field"><small>ช่องทาง</small><select name="method">${Object.entries(METHOD_TH).map(([k, t]) => `<option value="${k}">${t}</option>`).join('')}</select></label>
        <label class="mini-field"><small>หมายเหตุ</small><input name="note" maxlength="120" placeholder="ไม่ใส่ก็ได้"></label>
        <button class="btn primary small" type="submit">บันทึกรับเงิน</button></form>` : ''}
    </section></div>`;
}
// ส่งทีละชุด 8 ฉบับ: Edge Function ฟรีเพลนรันได้ ≤ 150 s ต่อครั้ง · ฉบับละ ~3 s + หน่วง 2 s → 8 ฉบับ ≈ 40 s (เผื่อ 3.7 เท่า)
const SEND_BATCH = 8;
async function sendBills(rooms, resend = false) {
  const bills = ctx().bills.filter(b => rooms.includes(b.room.room_id) && b.inv && b.inv.recipient_email);
  if (!bills.length) return;
  const what = bills.length === 1 ? `ห้อง ${bills[0].room.room_id} ถึง ${bills[0].inv.recipient_email}` : `${bills.length} ฉบับ`;
  if (!confirm(`${resend ? 'ส่งซ้ำ' : 'ส่ง'}อีเมลบิล ${what}\nจาก Gmail ของหอ · ฉบับละประมาณ 5 วินาที`)) return;
  const ids = bills.map(b => b.inv.id), results = [];
  const ok = await write(async () => {
    for (let i = 0; i < ids.length; i += SEND_BATCH) {
      if (ids.length > SEND_BATCH) toast(`กำลังส่ง ${Math.min(i + SEND_BATCH, ids.length)} / ${ids.length} …`);
      const res = await api.sendInvoices(ids.slice(i, i + SEND_BATCH), resend);
      results.push(...(res.results || []));
    }
  }, null);
  const sent = results.filter(x => x.result === 'sent').length, failed = results.filter(x => x.result === 'failed').length, skip = results.filter(x => x.skipped).length;
  if (!ok) return;   // write แสดงสาเหตุแล้ว และโหลดข้อมูลใหม่ → ชิปบนการ์ดบอกว่าฉบับไหนส่งไปแล้ว
  toast(`ส่งแล้ว ${sent}${failed ? ` · ไม่สำเร็จ ${failed}` : ''}${skip ? ` · ข้าม ${skip}` : ''}`, failed > 0);
  closeModal();
  if (bills.length === 1) showBill(bills[0].room.room_id);
}
// คีย์กันบันทึกซ้ำ (unique ในฐานข้อมูล · audit WEB-004): คงที่ต่อ "ยอดคงค้างชุดเดียวกัน" → กดซ้ำจากหน้าต่างเดิม = ถูกปฏิเสธ
// เปลี่ยนเมื่อมีรายการรับเงินใหม่หรือยกเลิกรายการ → รับงวดถัดไปได้ตามปกติ
const payKeys = new Map();
function payKey(b) {
  const k = `${state.cycle}|${b.room.room_id}|${b.payments.map(p => p.id + (p.voided_at ? 'v' : '')).join(',')}`;
  if (!payKeys.has(k)) payKeys.set(k, crypto.randomUUID());
  return payKeys.get(k);
}

async function addPayment(form) {
  const b = ctx().bills.find(x => x.room.room_id === form.dataset.payRoom);
  const f = new FormData(form);
  const amount = Number(f.get('amount'));
  if (!(amount > 0)) return toast('ยอดต้องมากกว่า 0', true);
  if (!confirm(`บันทึกรับเงินห้อง ${b.room.room_id} ${baht(amount)} (${METHOD_TH[f.get('method')]}) วันที่ ${L.dateTh(f.get('paid_on'))}?\nแก้ภายหลังไม่ได้ ต้องยกเลิกแล้วบันทึกใหม่`)) return;
  const row = { cycle: state.cycle, room_id: b.room.room_id, invoice_id: b.inv.id, amount, paid_on: f.get('paid_on'), method: f.get('method'), note: blankToNull(f.get('note')), client_key: form.dataset.key };
  if (await write(() => api.addPayment(row), `บันทึกรับเงินห้อง ${b.room.room_id} แล้ว`)) showBill(b.room.room_id);
}
async function voidPayment(id) {
  const p = state.data.payments.find(x => x.id === id);
  const reason = prompt(`ยกเลิกรายการรับเงิน ${baht(Number(p.amount))} ห้อง ${p.room_id}\nเหตุผล (จำเป็น · เก็บเป็นประวัติ):`, '');
  if (!reason || !reason.trim()) return;
  if (await write(() => api.voidPayment(id, reason.trim()), 'ยกเลิกรายการแล้ว')) showBill(p.room_id);
}

async function loadMailStatus() {
  const el = $('#mail-status'), note = $('#mail-status-note');
  if (!el) return;
  try {
    const m = await api.mailStatus();
    if (!$('#mail-status')) return;
    $('#mail-status').innerHTML = m.configured ? status('พร้อมส่ง', 'good') : status('ยังไม่ตั้ง', 'warn');
    $('#mail-status-note').textContent = m.configured ? m.sender : 'ตั้ง secret ใน Supabase ก่อน (ดูวิธีด้านล่าง)';
  } catch (e) { el.innerHTML = status('ตรวจไม่ได้', 'bad'); note.textContent = e.message; }
}
async function mailTest(btn) {
  btn.disabled = true;
  try { const r = await api.sendTestMail(); toast(`ส่งอีเมลทดสอบถึง ${r.to} แล้ว${r.qr ? ' (มี QR พร้อมเพย์)' : ' · ยังไม่มี QR เพราะยังไม่ตั้งพร้อมเพย์'}`); }
  catch (e) { toast(`ส่งไม่ได้: ${e.message}`, true); }
  finally { btn.disabled = false; }
}
async function savePayout(form) {
  const v = String(new FormData(form).get('promptpay_id') || '').replace(/[\s-]/g, '');
  if (v && !/^(0\d{9}|\d{13})$/.test(v)) return toast('พร้อมเพย์ต้องเป็นเบอร์มือถือ 10 หลัก หรือเลข 13 หลัก', true);
  await write(() => api.setPromptpay(v || null), v ? 'บันทึกพร้อมเพย์แล้ว' : 'ลบพร้อมเพย์แล้ว');
}

async function toggleRent(on) {
  const c = ctx();
  const row = c.d.cycles.find(x => x.cycle === state.cycle);
  // สร้างแถวรอบด้วยวันตัดรอบที่ใช้อยู่ตอนนี้ (ตรึงไว้ ไม่ขยับตามค่าตั้งภายหลัง)
  await write(() => api.upsertCycle({ cycle: state.cycle, cutoff_date: row?.cutoff_date ?? c.range.to, include_rent: on }), on ? 'เปิดรวมค่าเช่ารอบนี้' : 'ปิดรวมค่าเช่ารอบนี้');
}

// ───────── ห้องและมิเตอร์ ─────────
// หน้าห้องและมิเตอร์ (ออกแบบใหม่ 30 ก.ย.): รายการห้องแบบแถวกระชับ (ซ้าย) · รายละเอียดห้องเป็นการ์ดหมวด ผู้เช่า / มิเตอร์ (ขวา)
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
  const activeMeters = d.meters.filter(m => L.meterActiveOn(m, today));
  const exp = d.lastExport ? `ส่งออกล่าสุด v${d.lastExport.version} · ${L.dateTimeTh(d.lastExport.exported_at)}` : 'ยังไม่เคยส่งออก';
  const item = r => {
    const t = tenantNow(r.room_id);
    const has = type => activeMeters.some(m => m.room_id === r.room_id && m.type === type);
    return `<button class="rm-item ${r.room_id === state.selectedRoom ? 'active' : ''}" data-room="${esc(r.room_id)}" aria-current="${r.room_id === state.selectedRoom}">
      <span class="rm-no">${esc(r.room_id)}</span>
      <span class="rm-who"><b>${t ? esc(t.tenant_name) : 'ห้องว่าง'}</b>${t && !t.email ? `<small class="rm-warn">ไม่มีอีเมล</small>` : ''}</span>
      <span class="rm-ms">${L.TYPES.map(type => `<span class="mr-ic ${type} ${has(type) ? 'have' : 'off'}" title="${L.TYPE_TH[type]}${has(type) ? '' : ' · ไม่มีมิเตอร์'}">${icon(type)}</span>`).join('')}</span></button>`;
  };
  return `<section class="page">
  ${pageHead('REGISTRY', 'ห้องและมิเตอร์', `${d.rooms.length} ห้อง · มิเตอร์ ${activeMeters.length} ตัว`, `<button class="btn" data-action="export" title="${esc(exp)} · นำไฟล์ไปวางที่ ~/mrc/data/ บน Pi">${icon('upload')}ส่งออกให้หุ่น</button>`)}
  <div class="rm-layout">
    <aside class="rm-list">
      <div class="rm-search">${icon('scan')}<input id="room-search" type="search" placeholder="ค้นห้อง ผู้เช่า รหัสมิเตอร์" value="${esc(state.roomQuery)}" aria-label="ค้นหา"></div>
      <div class="rm-items">${rooms.map(item).join('') || `<div class="set-empty">${d.rooms.length ? 'ไม่พบห้อง' : 'ยังไม่มีห้อง · เพิ่มห้องแรกด้านล่าง'}</div>`}</div>
      <details class="set-more rm-add" ${d.rooms.length ? '' : 'open'}><summary>${icon('arrow')}เพิ่มห้อง</summary><form id="room-add" class="set-inline">
        <label class="mini-field"><small>เลขห้อง</small><input name="room_id" placeholder="111" maxlength="10" pattern="[A-Za-z0-9]{1,10}" required></label>
        <label class="mini-field"><small>ชั้น</small><input name="floor" placeholder="1" maxlength="4"></label>
        <button class="btn primary small" type="submit">เพิ่ม</button></form></details>
    </aside>
    <div class="rm-detail">${state.selectedRoom ? roomDetail(state.selectedRoom, c) : '<section class="set-card"><p class="set-empty">เลือกหรือเพิ่มห้องทางซ้าย · ห้อง → ผู้เช่า → มิเตอร์ → ส่งออกให้หุ่น</p></section>'}</div>
  </div></section>`;
}

function roomDetail(roomId, c) {
  const d = c.d;
  const today = L.todayBkk();
  const room = d.rooms.find(r => r.room_id === roomId);
  const ts = d.tenancies.filter(t => t.room_id === roomId).sort((a, b) => b.start_date.localeCompare(a.start_date));
  const cur = L.tenancyOn(d.tenancies, roomId, today);
  const past = ts.filter(t => t !== cur);
  const ms = d.meters.filter(m => m.room_id === roomId).sort((a, b) => a.type.localeCompare(b.type) || b.installed_at.localeCompare(a.installed_at));
  const live = ms.filter(m => L.meterActiveOn(m, today));
  const retired = ms.filter(m => !L.meterActiveOn(m, today));
  const readingsOf = id => d.readings.filter(r => L.readingMeterId(r, mIdx) === id).sort((a, b) => b.captured_at.localeCompare(a.captured_at));
  const unbound = d.readings.filter(r => r.room_id === roomId && !L.readingMeterId(r, mIdx));
  const row = (label, ctl, hint = '') => `<label class="set-row"><span class="set-label">${label}${hint ? `<small>${hint}</small>` : ''}</span><span class="set-ctl">${ctl}</span></label>`;
  const CHIP = { confirmed: 'ยืนยันแล้ว', ocr: 'รอยืนยัน', rejected: 'ปฏิเสธ' };
  const meterTile = m => {
    const active = L.meterActiveOn(m, today);
    const rs = readingsOf(m.meter_id);
    const lastConf = rs.find(r => r.status === 'confirmed');
    const pend = rs.find(r => r.status === 'ocr');
    return `<div class="mt ${m.type} ${active ? '' : 'retired'}">
      <div class="mt-head"><span class="bl-ic">${icon(m.type)}</span><span class="mt-id"><b>${esc(m.meter_id)}</b><small>${L.TYPE_TH[m.type]} · ${m.digits} หลัก${m.decimals ? ` ทศนิยม ${m.decimals}` : ''}</small></span>
        ${active ? `<button class="mt-retire mt-manual" data-action="manual-read" data-meter="${esc(m.meter_id)}" title="กรอกเลขเองเมื่อหุ่นถ่ายไม่ได้">กรอกเอง</button><button class="mt-retire" data-action="retire" data-meter="${esc(m.meter_id)}" title="ปลด/เปลี่ยนมิเตอร์">ปลด</button>` : status('ปลดแล้ว', '')}</div>
      <div class="mt-val ${!lastConf && pend ? 'pending' : ''}"><b>${lastConf ? num(Number(lastConf.confirmed_value)) : pend ? num(pend.value) : '—'}</b><small>${lastConf ? `ยืนยัน ${L.dateTh(L.bkkDate(lastConf.captured_at))}` : pend ? `OCR ${L.dateTh(L.bkkDate(pend.captured_at))} · รอยืนยัน` : 'ยังไม่มีค่า'}</small></div>
      ${rs.length ? `<div class="mt-hist">${rs.slice(0, 4).map(r => `<button class="mt-chip ${r.status}${r.source === 'manual' ? ' manual' : ''}" data-page="review" data-reading="${r.id}" title="${CHIP[r.status] || r.status}${r.source === 'manual' ? ' · กรอกเอง' : ''}"><i></i>${num(r.confirmed_value ?? r.value)}<small>${L.dateTh(L.bkkDate(r.captured_at)).replace(/ \d{4}$/, '')}</small></button>`).join('')}</div>` : ''}
      <small class="mt-meta">ติดตั้ง ${L.dateTh(m.installed_at)} · เริ่ม ${num(Number(m.start_value))}${active ? ` <button class="text-link mt-fix" data-action="fix-start" data-meter="${esc(m.meter_id)}">แก้ค่าเริ่ม</button>` : ''}${m.retired_at ? ` · ปลด ${L.dateTh(m.retired_at)} · สุดท้าย ${num(m.end_value == null ? null : Number(m.end_value))}` : ''}</small></div>`;
  };
  const nextW = L.nextMeterId(d.meters, roomId, 'water');

  const head = `<header class="rd-head"><span class="rd-no">${esc(roomId)}</span><div><b>ห้อง ${esc(roomId)}</b><small>ชั้น ${esc(room.floor || '—')}${room.is_demo ? ' · ข้อมูลตัวอย่าง' : ''}</small></div>${status(cur ? 'มีผู้เช่า' : 'ห้องว่าง', cur ? 'good' : 'purple')}</header>`;

  const tenant = `<section class="set-card"><header class="set-head"><span class="set-ic">${icon('user')}</span><h2>ผู้เช่า</h2>${cur ? `<small class="set-sub">เข้าอยู่ ${L.dateTh(cur.start_date)}${cur.end_date ? ` – ${L.dateTh(cur.end_date)}` : ''}</small>${editBtn('tenancy-edit')}` : ''}</header>
    ${cur ? `<form id="tenancy-edit" class="set-form ${editCls('tenancy-edit')}" data-id="${cur.id}">
      ${setRow('ชื่อ', `<input name="tenant_name" value="${esc(cur.tenant_name)}" required maxlength="120">`, '', viewVal(cur.tenant_name))}
      ${setRow('อีเมลรับบิล', `<input name="email" type="email" value="${esc(cur.email)}" placeholder="เว้นว่าง = ส่งบิลไม่ได้">`, '', viewVal(cur.email, 'ไม่มี · ส่งบิลทางอีเมลไม่ได้'))}
      ${setRow('ค่าเช่า / เดือน', `<input name="rent_baht" type="number" min="0" step="0.01" value="${esc(cur.rent_baht)}" placeholder="฿">`, 'ใช้เมื่อเปิดรวมค่าเช่า', viewVal(cur.rent_baht == null ? null : baht(Number(cur.rent_baht))))}
      ${editActions('บันทึก', `<button class="btn small danger set-lead" type="button" data-action="move-out" data-id="${cur.id}">ย้ายออก</button>`)}</form>`
    : `<form id="tenancy-add" class="set-form">
      ${row('ชื่อ', '<input name="tenant_name" required maxlength="120" placeholder="ชื่อผู้เช่า">')}
      ${row('อีเมลรับบิล', '<input name="email" type="email" placeholder="เว้นว่างได้">')}
      ${row('วันเข้าอยู่', `<input name="start_date" type="date" value="${today}" required>`)}
      ${row('ค่าเช่า / เดือน', '<input name="rent_baht" type="number" min="0" step="0.01" placeholder="฿">')}
      <div class="set-actions"><button class="btn primary small" type="submit">เพิ่มผู้เช่า</button></div></form>`}
    ${past.length ? `<details class="rt-hist rd-past"><summary>ผู้เช่าก่อนหน้า ${past.length}</summary>${past.map(t => `<span>${esc(t.tenant_name)} · ${L.dateTh(t.start_date)} – ${t.end_date ? L.dateTh(t.end_date) : 'เริ่มในอนาคต'}</span>`).join('')}</details>` : ''}</section>`;

  const meters = `<section class="set-card"><header class="set-head"><span class="set-ic">${icon('camera')}</span><h2>มิเตอร์</h2></header>
    ${unbound.length ? `<button class="bot-warn rd-unbound" data-page="review" data-reading="${unbound[0].id}">${icon('link')}มี ${unbound.length} ค่าที่ยังไม่ผูกมิเตอร์ · ไปผูก</button>` : ''}
    ${live.length ? `<div class="mt-grid">${live.map(meterTile).join('')}</div>` : '<p class="set-empty">ยังไม่มีมิเตอร์ที่ใช้อยู่</p>'}
    ${retired.length ? `<details class="rt-hist rd-past"><summary>มิเตอร์ที่ปลดแล้ว ${retired.length}</summary><div class="mt-grid">${retired.map(meterTile).join('')}</div></details>` : ''}
    <details class="set-more"><summary>${icon('arrow')}เพิ่มมิเตอร์</summary><form id="meter-add" class="set-inline">
      <span class="seg" role="radiogroup" aria-label="ชนิด"><label><input type="radio" name="type" value="water" checked><span>${icon('water')}น้ำ</span></label><label><input type="radio" name="type" value="electric"><span>${icon('electric')}ไฟ</span></label></span>
      <label class="mini-field"><small>รหัส</small><input name="meter_id" value="${esc(nextW)}" readonly></label>
      <label class="mini-field"><small>จำนวนหลัก</small><input name="digits" type="number" min="1" max="9" value="5" required></label>
      <label class="mini-field"><small>ทศนิยม</small><input name="decimals" type="number" min="0" max="4" value="0" required></label>
      <label class="mini-field"><small>วันติดตั้ง</small><input name="installed_at" type="date" value="${today}" required></label>
      <label class="mini-field"><small>ค่าบนหน้าปัดวันติดตั้ง</small><input name="start_value" type="number" min="0" step="any" placeholder="เลขที่เห็นวันนี้" required></label>
      <button class="btn primary small" type="submit">เพิ่ม</button></form>
      <p class="set-hint">เปลี่ยนมิเตอร์ = ปลดตัวเก่าแล้วเพิ่มตัวใหม่วันเดียวกัน · เพิ่มเสร็จกด “ส่งออกให้หุ่น”</p></details></section>`;

  return `${head}${tenant}${meters}`;
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
  // ฐาน 0 = บิลแรกคิดทุกหน่วยที่หน้าปัดเคยหมุนมา (เจอจริงบนเว็บ 3 ต.ค.: ห้อง A102/A103 บิลแรก 1,234 หน่วย)
  if (row.start_value === 0 && !confirm(`ค่าบนหน้าปัดวันติดตั้ง = 0 ?\n\nบิลแรกจะคิดทุกหน่วยตั้งแต่ 0 ถึงเลขที่อ่านได้ · ใช้ 0 เฉพาะมิเตอร์ใหม่ที่หน้าปัดเป็น 0 จริง`)) return;
  if (await write(() => api.addMeter(row), `เพิ่ม ${row.meter_id} แล้ว · อย่าลืมส่งออกให้หุ่น`)) markMetersChanged();
}

// ค่าเริ่ม = เลขบนหน้าปัดวันติดตั้ง = ฐานของบิลแรก · ต้องไม่เกินค่าที่ยืนยันครั้งแรก (ไม่งั้นหน่วยติดลบ)
async function fixStart(id) {
  const m = mIdx.get(id);
  const first = state.data.readings.filter(r => L.readingMeterId(r, mIdx) === id && r.status === 'confirmed').sort((a, b) => a.captured_at.localeCompare(b.captured_at))[0];
  const raw = prompt(`ค่าบนหน้าปัด ${id} วันติดตั้ง (${L.dateTh(m.installed_at)})\nตอนนี้ = ${num(Number(m.start_value))}${first ? ` · ค่าที่ยืนยันแรก ${num(Number(first.confirmed_value))}` : ''}\n\nบิลที่อนุมัติแล้วไม่เปลี่ยนเอง ต้องออกฉบับแก้ไข`, String(Number(m.start_value)));
  if (raw === null || raw.trim() === '') return;
  const v = Number(raw);
  if (!Number.isFinite(v) || v < 0) return toast('ค่าเริ่มต้องเป็นตัวเลขไม่ติดลบ', true);
  if (first && v > Number(first.confirmed_value)) return toast(`ค่าเริ่มต้องไม่เกินค่าที่ยืนยันครั้งแรก ${num(Number(first.confirmed_value))}`, true);
  await write(() => api.updateMeter(id, { start_value: v }), `ค่าเริ่ม ${id} = ${num(v)} แล้ว`);
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
  const last = state.data.readings.filter(r => L.readingMeterId(r, mIdx) === id && r.status === 'confirmed' && L.bkkDate(r.captured_at) <= date).sort((a, b) => b.captured_at.localeCompare(a.captured_at))[0];
  if (end != null && last && end < Number(last.confirmed_value)) return toast(`ค่าตอนถอดต้องไม่ต่ำกว่าค่าที่ยืนยันล่าสุด ${num(Number(last.confirmed_value))}`, true);
  if (await write(() => api.updateMeter(id, { retired_at: date, end_value: end }), `ปลด ${id} แล้ว · เพิ่มตัวใหม่ได้ที่ “เพิ่มมิเตอร์”`)) markMetersChanged();
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
// หน้าตั้งค่า (ออกแบบใหม่ 30 ก.ย.): หมวดละการ์ด หัวมีไอคอน · แถว "ป้าย ซ้าย / ช่องกรอก ขวา" · คำอธิบายยาวย้ายไป title/ยืนยัน
function renderSettings(c) {
  const d = c.d;
  const s = d.settings;
  const today = L.todayBkk();
  const sec = (ic, title, body, foot = '', act = '') => `<section class="set-card"><header class="set-head"><span class="set-ic">${icon(ic)}</span><h2>${title}</h2>${act}</header>${body}${foot ? `<footer class="set-foot">${foot}</footer>` : ''}</section>`;
  const rateTile = t => {
    const all = d.rates.filter(x => x.type === t).sort((a, b) => b.effective_from.localeCompare(a.effective_from));
    const cur = L.rateOn(d.rates, t, today);
    const future = all.filter(x => x.effective_from > today);
    const past = all.filter(x => x !== cur && x.effective_from <= today);
    return `<div class="rate-tile ${t} ${cur ? '' : 'missing'}"><span class="rt-top"><span class="bl-ic">${icon(t)}</span>ค่า${L.TYPE_TH[t]}</span>
      <b>${cur ? baht(Number(cur.baht_per_unit)) : 'ยังไม่ตั้ง'}${cur ? '<small> / หน่วย</small>' : ''}</b>
      <small>${cur ? `ตั้งแต่ ${L.dateTh(cur.effective_from)}` : 'บิลคิดไม่ได้จนกว่าจะตั้ง'}</small>
      ${future.map(x => `<small class="rt-next">ถัดไป ${baht(Number(x.baht_per_unit))} · ${L.dateTh(x.effective_from)}</small>`).join('')}
      ${past.length ? `<details class="rt-hist"><summary>ประวัติ ${past.length}</summary>${past.map(x => `<span>${baht(Number(x.baht_per_unit))} · ${L.dateTh(x.effective_from)}</span>`).join('')}</details>` : ''}</div>`;
  };
  const cycles = [...d.cycles].sort((a, b) => b.cycle.localeCompare(a.cycle));
  const demoCount = ['rooms', 'meters', 'tenancies', 'readings'].reduce((n, k) => n + d[k].filter(x => x.is_demo).length, 0);
  const email = state.user?.email || '—';

  // Gmail ผู้ส่งจริงมาจาก secret GMAIL_USER (การ์ดอีเมล) → เอาช่อง sender_email ที่ไม่มีผลออกจากหน้านี้
  const dorm = sec('rooms', 'หอพัก', `<form id="settings-form" class="set-form ${editCls('settings-form')}">
      ${setRow('ชื่อหอ', `<input name="dorm_name" value="${esc(s.dorm_name)}" maxlength="120" placeholder="หอพักสุขใจ">`, 'ขึ้นหัวบิลและชื่อผู้ส่งอีเมล', viewVal(s.dorm_name))}
      ${setRow('ตัดรอบทุกวันที่', `<select name="default_cutoff_day"><option value="">สิ้นเดือน</option>${Array.from({ length: 28 }, (_, i) => i + 1).map(n => `<option value="${n}" ${s.default_cutoff_day === n ? 'selected' : ''}>${n}</option>`).join('')}</select>`, 'รอบที่ตั้งเฉพาะไว้ไม่เปลี่ยนตาม', viewVal(s.default_cutoff_day ? `วันที่ ${s.default_cutoff_day}` : 'สิ้นเดือน'))}
      ${editActions()}</form>`, '', editBtn('settings-form'));

  const rates = sec('baht', 'อัตราค่าน้ำค่าไฟ', `<div class="rate-tiles">${rateTile('water')}${rateTile('electric')}</div>
    <details class="set-more"><summary>${icon('arrow')}เพิ่มอัตราใหม่</summary>
      <form id="rate-form" class="set-inline">
        <span class="seg" role="radiogroup" aria-label="ชนิด"><label><input type="radio" name="type" value="water" checked><span>${icon('water')}น้ำ</span></label><label><input type="radio" name="type" value="electric"><span>${icon('electric')}ไฟ</span></label></span>
        <label class="mini-field"><small>บาท/หน่วย</small><input name="baht_per_unit" type="number" min="0.01" step="0.01" placeholder="18.00" required></label>
        <label class="mini-field"><small>มีผลตั้งแต่</small><input name="effective_from" type="date" value="${today}" required></label>
        <button class="btn primary small" type="submit">เพิ่ม</button>
      </form><p class="set-hint">เพิ่มแล้วแก้/ลบไม่ได้ · เปลี่ยนราคา = เพิ่มแถวใหม่ที่มีผลวันใหม่</p></details>`);

  const cyc = sec('calendar', 'รอบบิลที่ตั้งเฉพาะ', `${cycles.length ? `<div class="cycle-list">${cycles.map(x => `<div class="cycle-item"><b>${L.cycleLabel(x.cycle)}</b><span>ตัดรอบ ${L.dateTh(x.cutoff_date)}${x.include_rent ? ' · รวมค่าเช่า' : ''}</span>${status(x.state === 'closed' ? 'ปิดแล้ว' : 'เปิด', x.state === 'closed' ? '' : 'purple')}</div>`).join('')}</div>` : '<p class="set-empty">ยังไม่มี · ทุกรอบใช้วันตัดรอบปกติ</p>'}
    <details class="set-more"><summary>${icon('arrow')}ตั้งวันตัดรอบเฉพาะรอบ</summary><form id="cycle-form" class="set-inline">
      <label class="mini-field"><small>รอบ</small><input name="cycle" type="month" value="${esc(state.cycle)}" required></label>
      <label class="mini-field"><small>วันตัดรอบ</small><input name="cutoff_date" type="date" value="${esc(L.cutoffFor(state.cycle, d.cycles, s))}" required></label>
      <button class="btn primary small" type="submit">ตั้งวันตัดรอบ</button></form><p class="set-hint">ใช้เมื่อรอบนั้นตัดไม่ตรงวันปกติ เช่น เลื่อนเพราะวันหยุด</p></details>`);

  const acct = sec('user', 'บัญชี', `<div class="acct"><span class="acct-av">${state.guest ? 'G' : esc((email[0] || '?').toUpperCase())}</span><div><b>${state.guest ? 'ผู้ชม (Guest)' : esc(email)}</b><small>${state.guest ? 'ผู้ชม · ดูได้อย่างเดียว' : 'Google · เจ้าของหอ'}${api.mock ? ' · โหมดจำลอง' : ''}</small></div></div>`,
    `<button class="btn small" data-action="sign-out">ออกจากระบบ</button><button class="btn small ghost" data-action="sign-out-all" title="ใช้เมื่อลืมออกจากเครื่องอื่น">ทุกอุปกรณ์</button>`);

  const adv = sec('settings', 'ขั้นสูง', `<div class="set-rows">
      <div class="set-row static"><span class="set-label">OCR “ไม่มั่นใจ” ต่ำกว่า<small>ค่าจากต้นแบบ · รอข้อมูลถ่ายจริง</small></span><span class="set-ctl"><b>${pct(L.LOW_CONFIDENCE)}</b></span></div>
      <div class="set-row static"><span class="set-label">ข้อมูลตัวอย่าง<small>${demoCount ? 'ลบด้วย SQL ใน Supabase · ตั้งใจไม่มีปุ่ม' : 'ลบแล้ว'}</small></span><span class="set-ctl">${demoCount ? status(`${demoCount} แถว`, 'warn') : status('ไม่มี', 'good')}</span></div>
      ${demoCount ? `<code class="set-code">select public.delete_demo_data();</code>` : ''}
      <div class="set-row static"><span class="set-label">โซนเวลา</span><span class="set-ctl"><b>${esc(s.timezone || 'Asia/Bangkok')}</b></span></div></div>`);

  const pp = d.payout?.promptpay_id || '';
  const mail = state.guest ? '' : sec('mail', 'อีเมลบิลและการรับเงิน', `<div class="set-rows">
      <div class="set-row static"><span class="set-label">ผู้ส่ง (Gmail ของหอ)<small id="mail-status-note">กำลังตรวจ…</small></span><span class="set-ctl"><span id="mail-status">${status('…', '')}</span></span></div>
      <div class="set-row static"><span class="set-label">ทดสอบการส่ง<small>ส่งบิลตัวอย่างถึงอีเมลที่ล็อกอินอยู่</small></span><span class="set-ctl"><button class="btn small" type="button" data-action="mail-test">${icon('mail')}ส่งทดสอบ</button></span></div></div>
    <form id="payout-form" class="set-form ${editCls('payout-form')}">
      ${setRow('พร้อมเพย์รับเงิน', `<input name="promptpay_id" inputmode="numeric" maxlength="17" value="${esc(pp)}" placeholder="0812345678">`, 'มือถือ 10 หลัก หรือเลขบัตร 13 หลัก · ใส่ QR ในอีเมล', viewVal(pp, 'ยังไม่ตั้ง · อีเมลไม่มี QR'))}
      ${editActions()}</form>
    <details class="rt-hist rd-past"><summary>วิธีตั้ง Gmail ผู้ส่ง</summary><span>1. บัญชี Google ของหอ → Security → เปิด 2-Step Verification</span><span>2. myaccount.google.com/apppasswords → สร้าง App Password (16 ตัว)</span><span>3. Supabase → Edge Functions → Secrets → เพิ่ม GMAIL_USER = อีเมลหอ และ GMAIL_APP_PASSWORD = รหัส 16 ตัว</span><span>4. กลับมากด "ส่งทดสอบ" ด้านบน</span></details>`, '', editBtn('payout-form'));
  const look = sec('settings', 'ธีมสี', `<div class="accent-picks">${Object.entries(ACCENTS).map(([k, v]) => `<button class="accent-pick ${k} ${accentNow() === k ? 'active' : ''}" data-accent-pick="${k}" aria-pressed="${accentNow() === k}"><span class="sw" style="background:${v.sw}" aria-hidden="true"></span>${v.name}</button>`).join('')}</div><p class="set-hint">จำไว้เฉพาะเบราว์เซอร์นี้</p>`);
  return `<section class="page">${pageHead('PREFERENCES', 'ตั้งค่า', 'มีผลกับบิลรอบที่ยังไม่ปิด')}
  <div class="set-layout"><div class="set-col">${dorm}${rates}${cyc}</div><div class="set-col">${acct}${mail}${look}${adv}</div></div></section>`;
}

async function saveSettings(form) {
  const f = new FormData(form);
  const day = blankToNull(f.get('default_cutoff_day'));
  await write(() => api.updateSettings({ dorm_name: blankToNull(f.get('dorm_name')), default_cutoff_day: day == null ? null : Number(day) }), 'บันทึกการตั้งค่าแล้ว');
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
  // รอบนี้หรือรอบถัดไปอนุมัติบิลแล้ว = ห้ามเลื่อนวันตัด (ช่วงของบิลที่ตรึงไว้จะไม่ตรง → คิดซ้ำ/ตกหล่น · audit WEB-003 · ฐานข้อมูลกันซ้ำ)
  const locked = (state.data.invoices || []).filter(v => v.state === 'approved' && (v.cycle === cycle || v.cycle === L.shiftCycle(cycle, 1)));
  if (row && row.cutoff_date !== cutoff && locked.length) return toast(`เปลี่ยนวันตัดรอบ${L.cycleLabel(cycle)}ไม่ได้ · อนุมัติบิลแล้ว ${[...new Set(locked.map(v => v.room_id))].join(', ')} (รอบนี้หรือรอบถัดไป)`, true);
  if (cutoff <= L.cutoffFor(L.shiftCycle(cycle, -1), state.data.cycles, state.data.settings)) return toast('วันตัดรอบต้องหลังวันตัดรอบของรอบก่อน', true);
  if (cutoff > L.cutoffFor(L.shiftCycle(cycle, 1), state.data.cycles, state.data.settings)) return toast('วันตัดรอบต้องก่อนวันตัดรอบของรอบถัดไป', true);
  await write(() => api.upsertCycle({ cycle, cutoff_date: cutoff, include_rent: row?.include_rent ?? false }), `ตั้งวันตัดรอบ${L.cycleLabel(cycle)} = ${L.dateTh(cutoff)}`);
}

// ───────── modal ─────────
function openModal(html) {
  // เปิดซ้ำตอนหน้าต่างยังเปิดอยู่ (เช่น บันทึกรับเงินแล้วแสดงบิลใหม่) = เปลี่ยนเนื้อหาเฉยๆ ไม่เล่นแอนิเมชันเปิดซ้ำ
  const live = $('#modal-root .modal-backdrop:not(.closing) .modal');
  if (live) { live.innerHTML = html; return; }
  $('#modal-root').innerHTML = `<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">${html}</div></div>`;
  $('.modal [aria-label="ปิด"]')?.focus();
}
// ปิดแบบจางออก 160 ms · เปิดใหม่ระหว่างนั้น = แทนที่ทันที (openModal เขียนทับ #modal-root)
function closeModal() {
  const bd = $('#modal-root .modal-backdrop');
  if (!bd || bd.classList.contains('closing')) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { bd.remove(); return; }
  bd.classList.add('closing');
  setTimeout(() => bd.remove(), 170);
}

// โหมดแก้: render ใหม่ด้วย state.editing แล้วโฟกัสช่องแรก · ยกเลิก = render ค่าจากฐานข้อมูลกลับมา (ทิ้งที่พิมพ์)
function startEdit(id) {
  if (state.guest) return;
  state.editing = id;
  render();
  const f = document.getElementById(id);
  f?.querySelector('input:not([type=hidden]):not(:disabled), select')?.focus({ preventScroll: true });
  f?.scrollIntoView({ block: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
}
function stopEdit() {
  const id = state.editing;
  state.editing = null;
  render();
  document.querySelector(`[data-action="edit"][data-form="${id}"]`)?.focus({ preventScroll: true });
}

// ───────── event ─────────
function setPage(page) {
  state.page = page;
  state.editing = null;
  render();
  $('#page-content').focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: 'instant' });
}

// ───────── บัญชี: เมนู + ออกจากระบบ ─────────
function toggleAccountMenu(open) {
  const menu = $('#account-menu'), btn = $('#avatar');
  const on = open ?? menu.hidden;
  menu.hidden = !on;
  btn.setAttribute('aria-expanded', String(on));
  if (on) menu.querySelector('button')?.focus();
}

let signingOut = false;
async function signOut(scope) {
  if (signingOut) return;
  if (scope === 'global' && !confirm('ออกจากระบบทุกอุปกรณ์ที่ล็อกอินบัญชีนี้ไว้?\n(มือถือ/คอมเครื่องอื่นต้องล็อกอินใหม่)')) return;
  signingOut = true;
  document.body.classList.add('busy');
  try {
    await api.signOut(scope);
  } catch (e) {
    // เน็ตหลุดตอนสั่ง global: ฝั่งเครื่องนี้ต้องออกให้ได้เสมอ → ล้าง session ในเครื่องแล้วบอกตามจริง
    if (scope === 'global') { try { await api.signOut('local'); } catch (_) {} sessionStorage.setItem('aria.gate', 'global-failed'); }
  }
  if (!sessionStorage.getItem('aria.gate')) sessionStorage.setItem('aria.gate', scope === 'global' ? 'signed-out-all' : 'signed-out');
  location.replace(location.pathname + (api.mock ? '?mock' : ''));
}

document.addEventListener('click', e => {
  const t = e.target;
  // ปิดเมนูบัญชีเมื่อคลิกที่อื่น (หรือหลังเลือกเมนู)
  if (!$('#account-menu').hidden && !t.closest('.account-head') && !t.closest('#avatar')) toggleAccountMenu(false);
  const ac = t.closest('[data-accent-pick]');
  if (ac) { setAccent(ac.dataset.accentPick); return; }
  const hr = t.closest('[data-home-room]');
  if (hr) {
    state.homeRoom = hr.dataset.homeRoom; render();
    document.querySelector(`[data-home-room="${CSS.escape(state.homeRoom)}"]`)?.focus({ preventScroll: true });
    // จอแคบ: รายละเอียดอยู่ใต้ผัง → เลื่อนให้เห็น
    if (matchMedia('(max-width: 1000px)').matches) $('.map-detail')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    return;
  }
  const step = t.closest('[data-cycle-step]');
  if (step) { state.cycle = L.shiftCycle(state.cycle, Number(step.dataset.cycleStep)); render(); return; }
  const nav = t.closest('[data-page]');
  if (nav) {
    if (nav.closest('.modal')) closeModal();
    if (nav.dataset.reading) state.selectedReading = Number(nav.dataset.reading);
    if (nav.dataset.room) state.selectedRoom = nav.dataset.room;
    setPage(nav.dataset.page);
    if (nav.dataset.edit) startEdit(nav.dataset.edit);   // เช่น "ตั้งชื่อหอ" → เปิดฟอร์มหอพักในโหมดแก้ทันที
    return;
  }
  const rd = t.closest('[data-reading]');
  if (rd) {
    state.selectedReading = Number(rd.dataset.reading);
    state.editing = null;
    render();
    // จอแคบ: รายละเอียดอยู่ใต้คิว → เลื่อนลงให้เห็นทันที
    if (rd.closest('.queue-list') && matchMedia('(max-width: 1000px)').matches) $('.review-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  const room = t.closest('[data-room]');
  if (room) {
    state.selectedRoom = room.dataset.room; state.editing = null; render();
    if (room.classList.contains('rm-item') && matchMedia('(max-width: 1000px)').matches) $('.rm-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  const filter = t.closest('[data-filter]');
  if (filter) { state.billFilter = filter.dataset.filter; render(); return; }
  const bill = t.closest('[data-bill]');
  if (bill) { showBill(bill.dataset.bill); return; }
  const a = t.closest('[data-action]');
  if (!a) return;
  const act = a.dataset.action;
  document.querySelectorAll('.is-busy').forEach(x => x.classList.remove('is-busy'));
  if (a.tagName === 'BUTTON') a.classList.add('is-busy');
  if (act === 'close-modal') { if (t === a || a.tagName === 'BUTTON') closeModal(); return; }
  if (act === 'edit') startEdit(a.dataset.form);
  else if (act === 'edit-cancel') stopEdit();
  else if (act === 'reject') rejectReading();
  else if (act === 'keep-dup') keepDuplicate(Number(a.dataset.keep));
  else if (act === 'reopen') reopenReading();
  else if (act === 'manual-read') showManualForm(a.dataset.meter);
  else if (act === 'export') exportRegistry();
  else if (act === 'approve') approveBills([a.dataset.billRoom]);
  else if (act === 'revise') approveBills([a.dataset.billRoom], true);
  else if (act === 'send-one') sendBills([a.dataset.billRoom], !!ctx().bills.find(b => b.room.room_id === a.dataset.billRoom)?.sent);
  else if (act === 'send-all') sendBills(ctx().bills.filter(b => b.inv && b.inv.recipient_email && b.sent !== 'sent').map(b => b.room.room_id));
  else if (act === 'void-pay') voidPayment(Number(a.dataset.payId));
  else if (act === 'mail-test') mailTest(a);
  else if (act === 'approve-all') approveBills(ctx().bills.filter(b => b.view === 'ready').map(b => b.room.room_id));
  else if (act === 'retire') retireMeter(a.dataset.meter);
  else if (act === 'fix-start') fixStart(a.dataset.meter);
  else if (act === 'move-out') moveOut(Number(a.dataset.id));
  else if (act === 'reload') location.reload();
  else if (act === 'account-menu') toggleAccountMenu();
  else if (act === 'sign-out') signOut('local');
  else if (act === 'sign-out-all') signOut('global');
  else if (act === 'sign-in') startSignIn(a);
  else if (act === 'guest') startGuest(a);
});

const SUBMITS = {
  'confirm-form': submitConfirm, 'assign-form': submitAssign, 'room-add': addRoom,
  'tenancy-edit': f => saveTenancy(f, false), 'tenancy-add': f => saveTenancy(f, true), 'meter-add': addMeter,
  'settings-form': saveSettings, 'rate-form': addRate, 'cycle-form': saveCycle, 'pay-form': addPayment, 'payout-form': savePayout, 'manual-form': submitManual,
};
document.addEventListener('submit', e => {
  const fn = SUBMITS[e.target.id];
  if (!fn) return;
  e.preventDefault();
  e.submitter?.classList.add('is-busy');   // หมุนเฉพาะปุ่มที่กด (CSS body.busy .is-busy)
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
  if (e.key === 'Escape') { if (state.editing && !$('.modal-backdrop:not(.closing)')) stopEdit(); closeModal(); if (!$('#account-menu').hidden) { toggleAccountMenu(false); $('#avatar').focus(); } }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('tr[data-room]')) { e.preventDefault(); e.target.click(); }
});

// ───────── เข้าระบบ ─────────
function showGate(title, text, actions, note = '') {
  $('#app').hidden = true;
  $('#gate').hidden = false;
  if (!gateBg) gateBg = createBackdrop($('#liquid'));
  $('#gate-title').textContent = title;
  if (title.endsWith(' ARIA')) $('#gate-title').innerHTML = `${esc(title.slice(0, -5))} <span class="accent">ARIA</span>`;
  $('#gate-text').textContent = text;
  $('#gate-text').hidden = !text;
  $('#gate-actions').innerHTML = actions;
  const n = $('#gate-note');
  n.textContent = note.text || '';
  n.className = `gate-note ${note.tone || ''}`;
  n.hidden = !note.text;
}

const G_LOGO = '<svg class="g-logo" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>';
const GUEST_BTN = `<button class="gate-guest" data-action="guest" title="ดูได้อย่างเดียว · แก้ไขไม่ได้"><span class="g-mark guest-mark" aria-hidden="true">${icon('user')}</span>Guest</button>`;
const SIGN_IN_BTN_ONLY = `<button class="gate-google" data-action="sign-in"><span class="g-mark">${G_LOGO}</span><span class="g-label">Continue with Google</span><span class="g-arrow" aria-hidden="true">→</span></button>`;
const SIGN_IN_BTN = SIGN_IN_BTN_ONLY + GUEST_BTN;
const GATE_NOTES = {
  'signed-out': { text: 'Signed out', tone: 'good' },
  'signed-out-all': { text: 'Signed out on all devices', tone: 'good' },
  'global-failed': { text: 'Signed out here only — other devices failed', tone: 'warn' },
  expired: { text: 'Session expired', tone: 'warn' },
};

async function startSignIn(btn) {
  sessionStorage.setItem('aria.fly', '1');   // กลับจาก Google แล้วเล่นอะนิเมชันโลโก้ (หน้าโหลดใหม่ทั้งหน้า จึงต้องจำไว้ข้าม reload)
  btn.disabled = true;
  btn.innerHTML = '<span class="g-mark"><span class="spinner" aria-hidden="true"></span></span><span class="g-label">Redirecting…</span>';
  try { await api.signIn(); } catch (e) {
    btn.disabled = false;
    btn.outerHTML = SIGN_IN_BTN_ONLY;
    const n = $('#gate-note'); n.textContent = 'Sign-in failed — try again'; n.className = 'gate-note bad'; n.hidden = false;
  }
}

async function startGuest(btn) {
  btn.disabled = true;
  btn.lastChild.textContent = 'Opening…';
  try { await api.signInGuest(); sessionStorage.setItem('aria.fly', '1'); location.reload(); } catch (e) {
    btn.disabled = false; btn.outerHTML = GUEST_BTN;
    const n = $('#gate-note');
    n.textContent = /disabled/i.test(e.message) ? 'Guest access is turned off' : 'Guest sign-in failed — try again';
    n.className = 'gate-note bad'; n.hidden = false;
  }
}

// Google/Supabase ส่ง error กลับมาทาง URL (?error=… หรือ #error=…) เช่น กดยกเลิก · ต้องอ่านก่อน supabase-js จัดการ URL
function takeAuthError() {
  const q = new URLSearchParams(location.search), h = new URLSearchParams(location.hash.slice(1));
  const code = q.get('error') || h.get('error');
  if (!code) return null;
  const desc = q.get('error_description') || h.get('error_description') || code;
  history.replaceState(null, '', location.pathname + (q.has('mock') ? '?mock' : ''));
  if (code === 'access_denied') return { text: 'Sign-in cancelled', tone: 'warn' };
  return { text: `Sign-in rejected: ${desc}`, tone: 'bad' };
}

async function boot() {
  applyAccentAssets();
  document.querySelectorAll('[data-icon]').forEach(n => { n.innerHTML = icon(n.dataset.icon); });
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
  if (local && new URLSearchParams(location.search).has('mock')) {
    api = (await import('./mock.js?v=w49')).createMockApi();
  } else {
    if (!window.supabase) return showGate('Failed to load', '', '<button class="gate-google plain" data-action="reload"><span>Reload</span></button>');
    api = (await import('./api.js?v=w45')).createApi();
  }
  const urlError = takeAuthError();
  const flag = sessionStorage.getItem('aria.gate');
  sessionStorage.removeItem('aria.gate');
  const note = urlError || GATE_NOTES[flag] || '';
  let session;
  try { session = await api.session(); } catch (e) {
    if (/code verifier|pkce|invalid.*grant|expired/i.test(e.message)) {   // ลิงก์กลับจาก Google ใช้ซ้ำ/หมดอายุ
      history.replaceState(null, '', location.pathname);
      return showGate('Welcome to ARIA', '', SIGN_IN_BTN, { text: 'Link expired — sign in again', tone: 'warn' });
    }
    return showGate('Can’t connect', '', '<button class="gate-google plain" data-action="reload"><span>Try again</span></button>');
  }
  if (!session) {
    api.onAuthChange((_ev, s) => { if (s) location.reload(); });   // ล็อกอินเสร็จในแท็บอื่น
    return showGate('Welcome to ARIA', '', SIGN_IN_BTN, note);
  }
  state.user = session.user;
  state.guest = session.user.is_anonymous === true;
  document.body.classList.toggle('guest', state.guest);
  // ล็อกอินได้ไม่พอ ต้องอยู่ใน owners (RLS บังคับอีกชั้น — ถึงข้ามหน้านี้ไปก็ไม่เห็นข้อมูล) · ผู้ชมข้ามได้ RLS ให้อ่านอย่างเดียว
  if (!state.guest && !(await api.isOwner().catch(() => false))) {
    return showGate('No access', session.user.email || '',
      '<button class="gate-google plain" data-action="sign-out"><span>Use another account</span></button>');
  }
  // ออกจากระบบในแท็บอื่น / token ถูกเพิกถอน (ออกทุกอุปกรณ์จากเครื่องอื่น) → กลับหน้าเข้าสู่ระบบ
  api.onAuthChange(ev => {
    if (ev === 'SIGNED_OUT' && !signingOut) { sessionStorage.setItem('aria.gate', 'expired'); location.replace(location.pathname + (api.mock ? '?mock' : '')); }
  });
  if (location.search.includes('code=')) history.replaceState(null, '', location.pathname + (api.mock ? '?mock' : ''));
  const fly = sessionStorage.getItem('aria.fly') === '1' && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  sessionStorage.removeItem('aria.fly');
  if (fly) showGate('Welcome to ARIA', '', '', { text: 'Signed in', tone: 'good' });   // ฉากเริ่มของอะนิเมชัน = หน้าเข้าสู่ระบบ
  const loading = reload().catch(e => toast(`โหลดข้อมูลไม่ได้: ${e.message}`, true));
  // หลังบ้านใช้วอลเปเปอร์เดียวกับหน้าเข้าสู่ระบบ โทนมืด (ผู้ใช้สั่ง 29 ก.ย.) · ความละเอียดต่ำ + 30 fps เพราะเปิดตลอดเวลาทำงาน
  appBg = createBackdrop($('#app-bg'), { tone: 1, scale: 0.35, fps: 30 });
  if (fly) {
    await loading;
    await new Promise(r => setTimeout(r, 800));   // ให้การ์ดเล่นท่าเข้าจนจบ + เห็นคำว่า Signed in แวบหนึ่ง
    await flyToApp();
  } else {
    $('#gate').hidden = true;
    gateBg?.stop(); gateBg = null;
    $('#app').hidden = false;
    await loading;
  }
}

// ───────── อะนิเมชันเปลี่ยนหน้า: โลโก้บนการ์ดเข้าสู่ระบบ → ที่อยู่ในหลังบ้าน (shared element) ─────────
// 1) ข้อความ/ปุ่มบนการ์ดจางออก  2) โลโก้ลอยไปที่กล่องโลโก้ใน sidebar (จอคอม) หรือแถบบน (มือถือ) พร้อม crossfade เป็นแบบของปลายทาง
// 3) ผ้าสว่างละลายเป็นผ้ามืด · sidebar เลื่อนเข้าจากซ้าย · แถบบนหล่นลง · เนื้อหาลอยขึ้น
// ใช้แค่ transform/opacity/ขนาดของโลโก้ตัวเดียว · ลดการเคลื่อนไหว = ไม่เล่น (เช็คตอนเริ่มใน boot)
async function flyToApp() {
  const gate = $('#gate'), app = $('#app');
  const srcImg = gate.querySelector('.gate-logo');
  const from = srcImg.getBoundingClientRect();
  gate.classList.add('gate-leaving');                      // ลอยเป็นชั้นบนสุด fixed ทับหลังบ้าน
  app.hidden = false;                                      // ต้องแสดงก่อนจึงวัดตำแหน่งปลายทางได้
  const desktop = matchMedia('(min-width: 801px)').matches;
  const target = desktop ? $('.brand-glass img') : $('.mobile-logo img');
  const to = target.getBoundingClientRect();

  // โลโก้บิน: กล่องเดียว มีรูปต้นทาง (โลโก้เต็ม) กับรูปปลายทาง (ตัวมาร์ค) ซ้อนกันแล้ว crossfade
  const flyer = document.createElement('div');
  flyer.className = 'logo-flyer';
  flyer.innerHTML = `<img class="a" src="${srcImg.getAttribute('src')}" alt=""><img class="b" src="${target.getAttribute('src')}" alt="">`;
  Object.assign(flyer.style, { left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px` });
  document.body.appendChild(flyer);
  srcImg.style.visibility = 'hidden';
  target.style.visibility = 'hidden';

  const E = 'cubic-bezier(.65, 0, .35, 1)', OUT = 'cubic-bezier(.16, 1, .3, 1)';
  const mine = [];                                         // เก็บเฉพาะอะนิเมชันที่สร้างเอง (ห้ามไปยกเลิกของ CSS เช่นแสงวาบ)
  const run = (el, kf, o) => { if (!el) return Promise.resolve(); const an = el.animate(kf, { fill: 'both', ...o }); mine.push(an); return an.finished; };
  const card = gate.querySelector('.gate-card');
  const jobs = [];
  // 1) ของบนการ์ด (ยกเว้นโลโก้) จางออก แล้วตัวการ์ดกระจกยุบหาย
  [...card.children].filter(el => el !== srcImg).forEach((el, i) =>
    jobs.push(run(el, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-6px)' }], { duration: 260, delay: i * 30, easing: 'ease-out' })));
  jobs.push(run(card, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(.94)' }], { duration: 420, delay: 180, easing: E }));
  // 2) โลโก้ลอย (ตำแหน่ง/ขนาดของกล่องเดียว) + crossfade ต้นทาง → ปลายทาง
  jobs.push(run(flyer, [
    { left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px` },
    { left: `${to.left}px`, top: `${to.top}px`, width: `${to.width}px`, height: `${to.height}px` },
  ], { duration: 950, delay: 260, easing: E }));
  jobs.push(run(flyer.querySelector('.a'), [{ opacity: 1 }, { opacity: 0 }], { duration: 500, delay: 560, easing: 'ease-in-out' }));
  jobs.push(run(flyer.querySelector('.b'), [{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 560, easing: 'ease-in-out' }));
  // 3) ผ้าสว่างละลายเป็นผ้ามืด (หลังบ้านอยู่ใต้ชั้นนี้อยู่แล้ว)
  jobs.push(run(gate, [{ opacity: 1 }, { opacity: 0 }], { duration: 700, delay: 420, easing: 'ease-in-out' }));
  // หลังบ้านประกอบตัว
  const sidebar = $('.sidebar'), topbar = $('.topbar');
  if (desktop) {
    jobs.push(run(sidebar, [{ opacity: 0, transform: 'translateX(-28px)' }, { opacity: 1, transform: 'none' }], { duration: 700, delay: 520, easing: OUT }));
    jobs.push(run($('.brand-glass'), [{ opacity: 0, transform: 'scale(.9)' }, { opacity: 1, transform: 'none' }], { duration: 600, delay: 700, easing: OUT }));
  } else {
    jobs.push(run($('.side-nav'), [{ opacity: 0, transform: 'translateY(24px)' }, { opacity: 1, transform: 'none' }], { duration: 650, delay: 700, easing: OUT }));
  }
  jobs.push(run(topbar, [{ opacity: 0, transform: 'translateY(-18px)' }, { opacity: 1, transform: 'none' }], { duration: 650, delay: 620, easing: OUT }));
  [...$('#page-content .page').children].slice(0, 6).forEach((el, i) =>
    jobs.push(run(el, [{ opacity: 0, transform: 'translateY(22px)' }, { opacity: 1, transform: 'none' }], { duration: 700, delay: 760 + i * 70, easing: OUT })));

  await Promise.all(jobs);
  // เก็บกวาด: คืนสภาพทุกอย่างให้เหมือนเข้าหน้าปกติ (ไม่ทิ้ง style/animation ค้าง)
  target.style.visibility = '';
  flyer.remove();
  mine.forEach(an => an.cancel());
  srcImg.style.visibility = '';
  gate.classList.remove('gate-leaving');
  gate.hidden = true;
  gateBg?.stop(); gateBg = null;
}

boot();
