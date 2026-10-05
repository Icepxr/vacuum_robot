// ตรรกะล้วน (ไม่แตะ DOM / เครือข่าย) ของเว็บหลังบ้าน ARIA · เทสต์ด้วย `node --test aria/web/test/*.test.mjs`
// กติกามาจาก design/aria-data-spec-v1.md §4 และ design/aria-backoffice-v1.md §4–5

// เกณฑ์ "OCR ไม่มั่นใจ" ใช้แค่เรียงคิว/ติดป้าย ไม่ได้กันการยืนยัน
// 0.7 มาจากต้นแบบ · [ยังไม่ตัดสินใจ] ต้องเก็บจากมิเตอร์จริงก่อน (สเปก §7a J3)
export const LOW_CONFIDENCE = 0.7;
export const TYPES = ['water', 'electric'];
export const TYPE_TH = { water: 'น้ำ', electric: 'ไฟ' };

const BKK_OFFSET_MS = 7 * 3600 * 1000; // Asia/Bangkok ไม่มี DST

// ── วันที่ (สตริง YYYY-MM-DD เทียบกันด้วย < > ได้ตรงๆ) ──
export const bkkDate = iso => new Date(new Date(iso).getTime() + BKK_OFFSET_MS).toISOString().slice(0, 10);
export const todayBkk = (now = new Date()) => bkkDate(now.toISOString());
const pad = n => String(n).padStart(2, '0');
export const shiftDay = (date, n) => new Date(Date.parse(date + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);
const lastDay = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate(); // m = 1..12
export const shiftCycle = (cycle, d) => {
  const [y, m] = cycle.split('-').map(Number);
  const t = y * 12 + (m - 1) + d;
  return `${Math.floor(t / 12)}-${pad((t % 12) + 1)}`;
};

// วันตัดรอบ: แถวใน billing_cycles ชนะ · ไม่มีแถว = คำนวณจาก settings.default_cutoff_day (null = สิ้นเดือน · F6)
export function cutoffFor(cycle, cycles, settings) {
  const row = cycles.find(c => c.cycle === cycle);
  if (row) return row.cutoff_date;
  const [y, m] = cycle.split('-').map(Number);
  const day = settings?.default_cutoff_day ?? lastDay(y, m);
  return `${y}-${pad(m)}-${pad(Math.min(day, lastDay(y, m)))}`;
}

// ช่วงของรอบ = (cutoff รอบก่อน, cutoff รอบนี้] ตามวันที่เวลาไทยของ captured_at (สเปก §4.2 billing_cycles)
export function cycleRange(cycle, cycles, settings) {
  return { from: cutoffFor(shiftCycle(cycle, -1), cycles, settings), to: cutoffFor(cycle, cycles, settings) };
}

export function cycleOfDate(date, cycles, settings) {
  let c = date.slice(0, 7);
  for (let i = 0; i < 3; i++) {
    const r = cycleRange(c, cycles, settings);
    if (date <= r.from) c = shiftCycle(c, -1);
    else if (date > r.to) c = shiftCycle(c, 1);
    else return c;
  }
  return c;
}

const TH_MONTHS = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'];
const TH_MON = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
export const cycleLabel = cycle => { const [y, m] = cycle.split('-').map(Number); return `${TH_MONTHS[m - 1]} ${y + 543}`; };
export const dateTh = date => { if (!date) return '—'; const [y, m, d] = date.split('-').map(Number); return `${d} ${TH_MON[m - 1]} ${y + 543}`; };
export const dateTimeTh = iso => {
  if (!iso) return '—';
  const t = new Date(new Date(iso).getTime() + BKK_OFFSET_MS).toISOString();
  return `${dateTh(t.slice(0, 10))} · ${t.slice(11, 16)}`;
};

// ── มิเตอร์และค่าที่อ่าน ──
export const meterIndex = meters => new Map(meters.map(m => [m.meter_id, m]));

// มิเตอร์ที่ reading นี้ผูกอยู่: ผูกทีหลัง (assigned) ชนะ · meter_id จากหุ่นที่ไม่มีในทะเบียน = ยังไม่ผูก
export function readingMeterId(r, mIdx) {
  if (r.assigned_meter_id) return r.assigned_meter_id;
  return r.meter_id && mIdx.has(r.meter_id) ? r.meter_id : null;
}

export const meterOverlaps = (m, from, to) => m.installed_at <= to && (!m.retired_at || m.retired_at > from);
export const meterActiveOn = (m, date) => m.installed_at <= date && (!m.retired_at || date < m.retired_at);

// ค่ายืนยันก่อนหน้าของมิเตอร์เดียวกัน (ก่อน captured_at ของ reading นี้) · ไม่มี = start_value
// ตรงกับ trigger reading_events_before_insert — ฐานข้อมูลเป็นตัวบังคับจริง ที่นี่แค่โชว์ล่วงหน้า
export function previousConfirmed(reading, meterId, readings, mIdx) {
  let best = null;
  for (const x of readings) {
    if (x.id === reading.id || x.status !== 'confirmed') continue;
    if (readingMeterId(x, mIdx) !== meterId || !(x.captured_at < reading.captured_at)) continue;
    if (!best || x.captured_at > best.captured_at) best = x;
  }
  if (best) return { value: Number(best.confirmed_value), source: 'reading', at: best.captured_at };
  const m = mIdx.get(meterId);
  return m ? { value: Number(m.start_value), source: 'start', at: null } : null;
}

// ธงความเสี่ยงของค่าที่รอยืนยัน · ลำดับตามแบบ v1 §4.1 "ต้องดูก่อน"
export function readingFlags(r, readings, mIdx) {
  const meterId = readingMeterId(r, mIdx);
  const prev = meterId ? previousConfirmed(r, meterId, readings, mIdx) : null;
  const value = r.value == null ? null : Number(r.value);
  const flags = [];
  if (!meterId) flags.push('unassigned');
  if (value == null) flags.push('unreadable');
  else if (prev && value < prev.value) flags.push('below_prev');
  if (r.confidence != null && r.confidence < LOW_CONFIDENCE) flags.push('low_conf');
  if (r.clock_synced === false) flags.push('clock');
  return { meterId, prev, value, flags };
}

const FLAG_RANK = { unassigned: 0, below_prev: 1, unreadable: 2, low_conf: 3, clock: 4 };
const rankOf = flags => Math.min(9, ...flags.map(f => FLAG_RANK[f]));

export function reviewQueue(readings, mIdx) {
  return readings
    .filter(r => r.status === 'ocr')
    .map(r => ({ r, ...readingFlags(r, readings, mIdx) }))
    .sort((a, b) => rankOf(a.flags) - rankOf(b.flags) || a.r.captured_at.localeCompare(b.r.captured_at));
}

// ── บิล (พรีวิว · ยังไม่มีตาราง invoices = ขั้น 4) ──
export const rateOn = (rates, type, date) =>
  rates.filter(x => x.type === type && x.effective_from <= date)
    .sort((a, b) => b.effective_from.localeCompare(a.effective_from))[0] || null;

export const tenancyOn = (tenancies, roomId, date) =>
  tenancies.find(t => t.room_id === roomId && t.start_date <= date && (!t.end_date || t.end_date >= date)) || null;

const round = (x, d) => Math.round(x * 10 ** d) / 10 ** d;

function lastConfirmed(readings, meterId, mIdx, pred) {
  let best = null;
  for (const x of readings) {
    if (x.status !== 'confirmed' || readingMeterId(x, mIdx) !== meterId) continue;
    if (!pred(bkkDate(x.captured_at))) continue;
    if (!best || x.captured_at > best.captured_at) best = x;
  }
  return best;
}

// หน่วยของห้อง×ชนิด ในรอบ = Σ ต่อมิเตอร์ (ค่าสุดท้ายในรอบ − ค่าฐาน) · เปลี่ยนมิเตอร์กลางรอบ = รวมสองช่วง (แบบ v1 §5)
// prevSegs = segments ของบิลรอบก่อนที่อนุมัติแล้ว → ใช้ curr ของบิลนั้นเป็นฐาน (ตรึง) ไม่คำนวณใหม่จากข้อมูลตอนนี้
//   กันคิดเงินซ้ำ/ตกหล่นเมื่อแก้วันตัดรอบหรือแก้ค่ารอบก่อนหลังอนุมัติ (audit WEB-003) · ถ้าไม่ตรงกับข้อมูลตอนนี้ → warning ให้ไปออกฉบับแก้ไขรอบก่อน
export function typeUsage(roomId, type, range, data, mIdx, prevSegs = null) {
  const meters = data.meters.filter(m => m.room_id === roomId && m.type === type && meterOverlaps(m, range.from, range.to));
  if (!meters.length) return { ok: false, reason: `ไม่มีมิเตอร์${TYPE_TH[type]}ในรอบนี้`, segments: [], warnings: [] };
  const segments = [], warnings = [];
  for (const m of meters.sort((a, b) => a.installed_at.localeCompare(b.installed_at))) {
    const before = lastConfirmed(data.readings, m.meter_id, mIdx, d => d <= range.from);
    const live = before ? { value: Number(before.confirmed_value), source: 'reading' } : { value: Number(m.start_value), source: 'start' };
    const pinned = (prevSegs || []).find(x => x.meter_id === m.meter_id && x.curr != null);
    const base = pinned ? { value: Number(pinned.curr), source: 'invoice' } : live;
    if (pinned && Math.abs(base.value - live.value) > 1e-9) warnings.push(`ฐาน${TYPE_TH[type]} ${m.meter_id} ใช้ตามบิลรอบก่อน ${base.value} แต่ข้อมูลตอนนี้เป็น ${live.value} · ถ้าค่ารอบก่อนผิด ให้ออกฉบับแก้ไขรอบก่อน`);
    const inCycle = lastConfirmed(data.readings, m.meter_id, mIdx, d => d > range.from && d <= range.to);
    let curr = inCycle ? Number(inCycle.confirmed_value) : null;
    // ถอดมิเตอร์ในรอบนี้: ค่าตอนถอดคือค่าสุดท้ายจริง แม้หุ่นอ่านไว้ก่อนหน้าในรอบ (audit WEB-002 · เดิมใช้แค่เมื่อไม่มีค่าในรอบ → หน่วยหาย)
    if (m.retired_at && m.retired_at <= range.to && m.end_value != null) {
      const end = Number(m.end_value);
      if (curr != null && end < curr) return { ok: false, reason: `ค่าตอนถอด ${m.meter_id} (${end}) ต่ำกว่าค่าที่ยืนยันล่าสุด (${curr})`, segments, warnings };
      curr = end;
    }
    if (curr == null) return { ok: false, reason: `ยังไม่ยืนยันค่า${TYPE_TH[type]} (${m.meter_id})`, segments, warnings };
    const units = round(curr - base.value, 4);
    if (units < 0) return { ok: false, reason: `หน่วย${TYPE_TH[type]}ติดลบ (${m.meter_id})`, segments, warnings };
    segments.push({ meter_id: m.meter_id, base: base.value, baseSource: base.source, curr, units });
  }
  return { ok: true, units: round(segments.reduce((s, x) => s + x.units, 0), 4), segments, warnings };
}

export function billPreview(room, cycle, data, mIdx) {
  const range = cycleRange(cycle, data.cycles, data.settings);
  const cycleRow = data.cycles.find(c => c.cycle === cycle);
  const tenancy = tenancyOn(data.tenancies, room.room_id, range.to);
  const prevInv = (data.invoices || []).find(v => v.room_id === room.room_id && v.cycle === shiftCycle(cycle, -1) && v.state === 'approved');
  const reasons = [], warnings = [];
  const lines = {};
  for (const type of TYPES) {
    const u = typeUsage(room.room_id, type, range, data, mIdx, prevInv?.detail?.segments?.[type] || null);
    warnings.push(...(u.warnings || []));
    const rate = rateOn(data.rates, type, range.to);
    if (!u.ok) reasons.push(u.reason);
    if (!rate) reasons.push(`ยังไม่ตั้งอัตรา${TYPE_TH[type]}ที่มีผล ณ ${dateTh(range.to)}`);
    lines[type] = {
      ...u,
      rate: rate ? Number(rate.baht_per_unit) : null,
      amount: u.ok && rate ? round(u.units * Number(rate.baht_per_unit), 2) : null,
    };
  }
  const includeRent = !!cycleRow?.include_rent;
  const rent = includeRent && tenancy?.rent_baht != null ? Number(tenancy.rent_baht) : 0;
  if (includeRent && tenancy && tenancy.rent_baht == null) reasons.push('เปิดรวมค่าเช่า แต่ห้องนี้ยังไม่ตั้งค่าเช่า');
  const complete = !reasons.length;
  const total = complete ? round(lines.water.amount + lines.electric.amount + rent, 2) : null;
  let state = 'ready';
  if (!tenancy) state = 'vacant';
  else if (!complete) state = 'blocked';
  return { room, range, tenancy, lines, includeRent, rent, total, reasons, warnings, state, noEmail: !!tenancy && !tenancy.email };
}

// ── หน้าหลัก ──
export function readingsInCycle(readings, range) {
  return readings.filter(r => { const d = bkkDate(r.captured_at); return d > range.from && d <= range.to; });
}

// ห้องที่ "อ่านครบ" = มิเตอร์ทุกตัวที่ติดตั้งอยู่ ณ วันตัดรอบมีค่าในรอบที่ไม่ถูกปฏิเสธ
export function roomCaptureState(room, range, data, mIdx, inCycle) {
  const meters = data.meters.filter(m => m.room_id === room.room_id && meterActiveOn(m, range.to));
  const per = meters.map(m => {
    const rs = inCycle.filter(r => readingMeterId(r, mIdx) === m.meter_id && r.status !== 'rejected');
    const latest = rs.sort((a, b) => b.captured_at.localeCompare(a.captured_at))[0] || null;
    return { meter: m, latest };
  });
  return {
    meters: per,
    captured: per.length > 0 && per.every(p => p.latest),
    confirmed: per.length > 0 && per.every(p => p.latest?.status === 'confirmed'),
  };
}

// meters.json ให้ Pi (สเปก §5) · ไม่มีข้อมูลผู้เช่า
export function registryJson(meters, version, exportedAt, today) {
  return {
    registry_version: version,
    exported_at: exportedAt,
    meters: meters.filter(m => meterActiveOn(m, today))
      .sort((a, b) => a.room_id.localeCompare(b.room_id, 'en', { numeric: true }) || a.type.localeCompare(b.type))
      .map(m => ({ meter_id: m.meter_id, room: m.room_id, type: m.type, digits: m.digits, decimals: m.decimals, waypoint: m.waypoint ?? null, lift_mm: m.lift_mm ?? null })),
  };
}

// รหัสมิเตอร์ตัวถัดไปของห้อง+ชนิด (เปลี่ยนตัว = -02 · ห้ามใช้ ID ซ้ำ)
export function nextMeterId(meters, roomId, type) {
  const p = type === 'water' ? 'W' : 'E';
  const used = meters.filter(m => m.room_id === roomId && m.type === type)
    .map(m => Number(m.meter_id.split('-').pop())).filter(Number.isFinite);
  return `${p}-${roomId}-${pad((used.length ? Math.max(...used) : 0) + 1)}`;
}
