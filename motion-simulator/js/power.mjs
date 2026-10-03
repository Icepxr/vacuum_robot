// แบบจำลองงบพลังงาน ผัง 4 buck (ผู้ใช้ 3 ต.ค. 2026) — คำนวณบันทึกที่ 08_การคำนวณ/23_งบพลังงาน_ผัง4buck.md
// แบต → ฟิวส์ → buck 5 V-A (Pi 5 + กล้อง + ENS160) · buck 5 V-B (ESP32) · buck 6 V (เซอร์โว ×2 + แปรง) · buck 12 V (ขับ + ดูด)

export const BATTERY_DEFAULTS = Object.freeze({
  capacityWh: 32.56,   // [สเปก] GNB22004S100A 4S1P 2200 mAh (ไฟล์ 02 §2.7)
  usableFactor: 0.723, // [ประมาณการ] f = 0.82 × 0.98 × 0.90 (ไฟล์ 02 §2.4)
  vFull: 16.8,         // [สเปก] 4.20 V/เซลล์
  vCutoff: 14.0,       // [ตั้งไว้] FAULT 3.50 V/เซลล์ (ไฟล์ 02 §2.0)
  vLow: 15.2,          // [ตั้งไว้] LOW_BATTERY (ไฟล์ 02 §2.6)
  fuseA: 15,           // [ตั้งไว้] ไฟล์ 02 §2.3
});

export const RAILS = Object.freeze([
  { id: 'r5a', name: 'Buck 5 V (1)', v: 5, ratingA: 5, eff: 0.85, note: 'Pi 5 + กล้อง + ENS160' },   // พิกัด 5 A [ผู้ใช้] · η [ประมาณการ ไฟล์ 02]
  { id: 'r5b', name: 'Buck 5 V (2)', v: 5, ratingA: 5, eff: 0.85, note: 'ESP32-S3 + จอ' },
  { id: 'r6', name: 'Buck 6 V', v: 6, ratingA: 5, eff: 0.85, note: 'เซอร์โว ×2 + แปรงปัด' },          // พิกัด 5 A [ผู้ใช้ยืนยัน 3 ต.ค.]
  { id: 'r12', name: 'Buck 12 V', v: 12, ratingA: 8, eff: 0.92, note: 'ขับเคลื่อน + ดูดฝุ่น' },       // 8 A [ไฟล์ 02 §2.3]
]);

// กระแส (A) ที่แรงดันราง ต่อระดับการทำงาน · src = ป้ายที่มา
export const LOADS = Object.freeze([
  { id: 'pi', name: 'Raspberry Pi 5', rail: 'r5a', levels: { run: 2.4, high: 4.0, peak: 5.0 }, src: 'ประมาณการ · ไฟล์ 02 (12/20/25 W)' },
  { id: 'cam', name: 'กล้อง BRIO (USB จาก Pi)', rail: 'r5a', levels: { run: 0.3, peak: 0.5 }, src: 'ประมาณการ · ไม่มีในไฟล์ 02' },
  { id: 'ens', name: 'ENS160 + AHT21', rail: 'r5a', levels: { run: 0.022, peak: 0.022 }, src: 'datasheet · ไฟล์ 21 (0.11 W)' },
  { id: 'esp', name: 'ESP32-S3 + จอ GC9A01', rail: 'r5b', levels: { run: 0.5, peak: 0.6 }, src: 'ประมาณการ · ไฟล์ 02 (2.5/3 W)' },
  { id: 'servoY', name: 'MG996R เสายก', rail: 'r6', levels: { hold: 0.1, run: 0.7, peak: 2.5 }, src: 'datasheet 6 V: วิ่ง 0.5–0.9 A · stall 2.5 A · ค้าง [ประมาณการ]' },
  { id: 'servoX', name: 'MG996R กล้องแกน X', rail: 'r6', levels: { hold: 0.1, run: 0.7, peak: 2.5 }, src: 'datasheet เหมือนตัวแรก' },
  { id: 'brush', name: 'แปรง JGB37-520 6 V', rail: 'r6', levels: { run: 0.5, peak: 3.0 }, src: 'ประมาณการ · ยังไม่วัด (C30)' },
  { id: 'drive', name: 'มอเตอร์ขับ JGB37-520 ×2', rail: 'r12', levels: { run: 1.0, peak: 5.0 }, src: 'ไฟล์ 02: ปกติ 12 W · พีค = ลิมิต DRV8871 2.5 A × 2' },
  { id: 'blower', name: 'Blower BA10033B12U', rail: 'r12', levels: { run: 2.4, peak: 2.4 }, src: 'สเปกร้าน 2.4 A (CWC: ปกติ 1.55 A)' },
]);

const base = { pi: 'run', cam: 'run', ens: 'run', esp: 'run', servoY: 'hold', servoX: 'hold' };
export const MODES = Object.freeze({
  standby: { name: 'จอดรอ', color: '#6f8792', loads: { ...base } },
  drive: { name: 'วิ่งเฉยๆ', color: '#5b8fd6', loads: { ...base, drive: 'run' } },
  collect: { name: 'เก็บขยะ', color: '#30d5e8', loads: { ...base, drive: 'run', blower: 'run', brush: 'run' } },
  lift: { name: 'ยก/ลดเสา', color: '#ffb454', loads: { ...base, pi: 'high', servoY: 'run' } },
  read: { name: 'อ่านมิเตอร์ (OCR)', color: '#78e0aa', loads: { ...base, pi: 'high' } },
  push: { name: 'ดันสิ่งกีดขวาง (พีค)', color: '#ff6e6e', loads: { ...base, pi: 'peak', esp: 'peak', drive: 'peak', blower: 'run', brush: 'peak' } },
});

export const SCENARIOS = Object.freeze({
  race: { name: 'แข่ง 3 นาที', src: 'ไฟล์ 02 §2.2 [ประมาณการ]', steps: [['collect', 120], ['lift', 24], ['read', 36]] },
  practice: { name: 'ซ้อมเก็บขยะต่อเนื่อง', src: 'ขอบบนอนุรักษ์นิยม ไฟล์ 02 §2.5', steps: [['collect', 180]] },
  meters: { name: 'อ่านมิเตอร์ 4 จุด', src: 'วิ่ง 10 s/จุด [ประมาณการ]', steps: Array.from({ length: 4 }, () => [['drive', 10], ['lift', 6], ['read', 9]]).flat() },
  manual: { name: 'ขับมือ ไม่ดูด', src: '[ประมาณการ]', steps: [['drive', 50], ['standby', 10]] },
  standby: { name: 'จอดรอ', src: '[ประมาณการ]', steps: [['standby', 60]] },
  bump: { name: 'ชนแล้วดัน', src: 'พีคชั่วขณะ ไฟล์ 02 §2.3', steps: [['collect', 27], ['push', 3]] },
});

export function current(load, level) { return level && level !== 'off' ? (load.levels[level] ?? load.levels.run ?? 0) : 0; }

/** กำลังต่อรางและที่ดึงจากแบต ของโหมดหนึ่ง */
export function modePower(modeId, { loads = LOADS, rails = RAILS } = {}) {
  const mode = MODES[modeId];
  const perRail = Object.fromEntries(rails.map(r => [r.id, { rail: r, amps: 0, watts: 0, items: [] }]));
  for (const ld of loads) {
    const a = current(ld, mode.loads[ld.id]);
    const r = perRail[ld.rail]; if (!r) continue;
    r.amps += a; r.watts += a * r.rail.v; if (a > 0) r.items.push({ load: ld, level: mode.loads[ld.id], amps: a });
  }
  let pOut = 0, pIn = 0;
  for (const r of Object.values(perRail)) { r.pIn = r.watts / r.rail.eff; pOut += r.watts; pIn += r.pIn; }
  return { modeId, perRail, pOut, pIn, effTotal: pOut > 0 ? pOut / pIn : 1 };
}

export function packVoltage(eRemWh, battery) {
  const usable = battery.capacityWh * battery.usableFactor;
  const frac = Math.max(0, Math.min(1, eRemWh / usable));
  return battery.vCutoff + (battery.vFull - battery.vCutoff) * frac; // [ประมาณการ] เชิงเส้นระหว่างเต็มกับจุดตัด
}

/** พลังงานต่อรอบสถานการณ์ */
export function cycleEnergy(steps, opts) {
  let wh = 0, sec = 0;
  for (const [m, s] of steps) { wh += modePower(m, opts).pIn * s / 3600; sec += s; }
  return { wh, sec, avgW: sec > 0 ? wh * 3600 / sec : 0 };
}

/** วนสถานการณ์ซ้ำจนพลังงานที่ใช้ได้หมด · dt 1 s · เก็บจุดทุก sampleSec */
export function simulateDischarge(steps, { battery = BATTERY_DEFAULTS, maxHours = 12, sampleSec = 5, ...opts } = {}) {
  const usable = battery.capacityWh * battery.usableFactor;
  const cyc = cycleEnergy(steps, opts);
  if (!(cyc.wh > 0) || !(cyc.sec > 0)) throw new Error('สถานการณ์ต้องมีเวลาและกินไฟมากกว่า 0');
  const powers = Object.fromEntries(Object.keys(MODES).map(m => [m, modePower(m, opts)]));
  let eRem = usable, t = 0, lowAt = null, maxI = 0; const pts = [];
  const tl = steps.flatMap(([m, s]) => Array.from({ length: Math.round(s) }, () => m));
  while (eRem > 0 && t < maxHours * 3600) {
    const m = tl[t % tl.length], p = powers[m].pIn, v = packVoltage(eRem, battery), i = p / v;
    if (t % sampleSec === 0) pts.push({ t, eRem, soc: eRem / usable, v, p, i, mode: m });
    maxI = Math.max(maxI, i);
    if (lowAt === null && v <= battery.vLow) lowAt = t;
    eRem -= p / 3600; t++;
  }
  return { usableWh: usable, cycle: cyc, cyclesPerCharge: usable / cyc.wh, runtimeSec: t, lowAt, maxPackA: maxI, points: pts };
}

/** ตรวจพีค: ทุกโหลดบนรางอยู่ที่ระดับ peak พร้อมกัน (ถ้ามี) · กระแสแบตคิดที่ V จุดตัด */
export function peakCheck({ battery = BATTERY_DEFAULTS, loads = LOADS, rails = RAILS } = {}) {
  const res = rails.map(r => {
    const amps = loads.filter(l => l.rail === r.id).reduce((s, l) => s + (l.levels.peak ?? l.levels.run ?? 0), 0);
    return { rail: r, amps, ratio: amps / r.ratingA, pIn: amps * r.v / r.eff };
  });
  const pIn = res.reduce((s, x) => s + x.pIn, 0);
  return { rails: res, pIn, packA: pIn / battery.vCutoff, fuseRatio: pIn / battery.vCutoff / battery.fuseA };
}

export function withOverrides({ rails: railOv = {}, loads: loadOv = {} } = {}) {
  return {
    rails: RAILS.map(r => ({ ...r, ...(railOv[r.id] || {}) })),
    loads: LOADS.map(l => ({ ...l, levels: { ...l.levels, ...(loadOv[l.id] || {}) } })),
  };
}
