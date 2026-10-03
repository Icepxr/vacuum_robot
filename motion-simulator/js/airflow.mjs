// แบบจำลองทางลม 1 มิติ v2 — พอร์ตจาก 08_การคำนวณ/scripts_22/airflow_1d_v2.py (ไฟล์ 22 §22.10)
// ทาง: ช่องใต้พื้น+แปรง → กล่องท้าย → ช่องตรง → ถังขยะ (ซ้ายสุด) → รู Ø80 → blower ชั้นบน

export const CFM_TO_M3S = 0.000471947;

export const AIR_DEFAULTS = Object.freeze({
  rho: 1.2, mu: 1.81e-5,                    // [สเปก] อากาศ ~25–30 °C
  qFreeCfm: 38.68,                          // [สเปก-ร้าน]
  pMaxPa: 486.2 * (4200 / 4500) ** 2,       // [ประมาณการ] BFB1012VH 486.2 Pa @4500 → 4200 rpm = 423.5 Pa
  curve: 'lin',                             // 'lin' มองโลกร้าย · 'quad' มองโลกดี
  slotLenMm: 196, slotWidMm: 40,            // [วัดจาก CAD]
  edgeFrontMm: 8.2, edgeRearMm: 27.2,       // [ประมาณการ] พื้นอ้างจากล้อใน Asembly2
  chWidMm: 25, chHgtMm: 50, chLenMm: 165,   // [วัดจาก CAD]
  bayWidMm: 84.9, bayHgtMm: 50,             // [วัดจาก CAD]
  holeDiaMm: 79.9,                          // [วัดจาก CAD]
  filterPaAt10: 0,                          // [ยังไม่ตัดสินใจ]
  kGap: 1.5, kChIn: 0.5, kDump: 1.0, kHole: 1.0, roughMm: 0.05,  // [ประมาณการ] ค่าตำรา
});

export const PLA_DENSITY = 1240;

export function fanDp(qM3s, p) {
  const r = qM3s / (p.qFreeCfm * CFM_TO_M3S);
  return p.curve === 'quad' ? p.pMaxPa * (1 - r * r) : p.pMaxPa * (1 - r);
}

export function frictionFactor(v, dhM, p) {
  const re = p.rho * v * dhM / p.mu;
  if (re < 1e-9) return 0;
  if (re < 2300) return 64 / re;
  return 0.25 / Math.log10(p.roughMm * 1e-3 / (3.7 * dhM) + 5.74 / re ** 0.9) ** 2; // Swamee–Jain
}

export function geometry(p) {
  const chW = p.chWidMm / 1e3, chH = p.chHgtMm / 1e3;
  const edgeLen = 2 * (p.slotLenMm + p.slotWidMm) / 2 / 1e3; // ครึ่งเส้นรอบ = 1 ขอบยาว + 1 ขอบสั้น
  return {
    aSlot: p.slotLenMm * p.slotWidMm * 1e-6,
    aGapFront: edgeLen * p.edgeFrontMm / 1e3,
    aGapRear: edgeLen * p.edgeRearMm / 1e3,
    aGap: edgeLen * (p.edgeFrontMm + p.edgeRearMm) / 1e3,
    aCh: chW * chH, dhCh: 2 * chW * chH / (chW + chH), lCh: p.chLenMm / 1e3,
    aBay: p.bayWidMm * p.bayHgtMm * 1e-6,
    aHole: Math.PI / 4 * (p.holeDiaMm / 1e3) ** 2,
  };
}

export function pressureTerms(q, p, g = geometry(p)) {
  const dyn = v => 0.5 * p.rho * v * v;
  const vGap = q / g.aGap, vCh = q / g.aCh, vHole = q / g.aHole;
  const f = frictionFactor(vCh, g.dhCh, p);
  const kFric = f * g.lCh / g.dhCh;
  return {
    vGap, vCh, vHole, f, kFric,
    inlet: p.kGap * dyn(vGap),
    chEntry: p.kChIn * dyn(vCh),
    chFriction: kFric * dyn(vCh),
    dump: p.kDump * dyn(vCh),
    hole: p.kHole * dyn(vHole),
    filter: p.filterPaAt10 * q / 0.010,
  };
}

export function systemDp(q, p, g = geometry(p)) {
  const t = pressureTerms(q, p, g);
  return t.inlet + t.chEntry + t.chFriction + t.dump + t.hole + t.filter;
}

export function solveOperatingPoint(params = {}) {
  const p = { ...AIR_DEFAULTS, ...params };
  for (const k of ['pMaxPa', 'qFreeCfm', 'chWidMm', 'chHgtMm', 'holeDiaMm', 'slotLenMm', 'slotWidMm'])
    if (!(p[k] > 0)) throw new Error(`${k} ต้องมากกว่า 0`);
  if (p.edgeFrontMm + p.edgeRearMm <= 0) throw new Error('ช่องใต้ขอบรวมต้องมากกว่า 0');
  const g = geometry(p);
  let lo = 0, hi = p.qFreeCfm * CFM_TO_M3S;
  for (let i = 0; i < 100; i++) {
    const q = (lo + hi) / 2;
    if (fanDp(q, p) - systemDp(q, p, g) > 0) lo = q; else hi = q;
  }
  const q = lo, t = pressureTerms(q, p, g);
  return {
    params: p, geometry: g, q, terms: t, dpFan: fanDp(q, p),
    qFront: q * p.edgeFrontMm / (p.edgeFrontMm + p.edgeRearMm),
    v: { gap: t.vGap, slot: q / g.aSlot, channel: t.vCh, bay: q / g.aBay, hole: t.vHole },
  };
}

/** ความเร็วปลายของเศษทรงกลม: v_t = √(4 g d ρp / (3 Cd ρ)) */
export function terminalVelocity(dMm, { rho = 1.2, rhoP = PLA_DENSITY, cd = 0.44 } = {}) {
  return Math.sqrt(4 * 9.81 * (dMm / 1e3) * rhoP / (3 * cd * rho));
}

export function systemCurve(params, n = 60) {
  const p = { ...AIR_DEFAULTS, ...params }, g = geometry(p), qf = p.qFreeCfm * CFM_TO_M3S;
  return Array.from({ length: n + 1 }, (_, i) => { const q = qf * i / n; return { q, fan: fanDp(q, p), sys: systemDp(q, p, g) }; });
}

// ---------- เศษ: รูปทรงปรับได้ (ไฟล์ 22 §22.11) ----------
// C_d [ประมาณการ]: ลูกบาศก์กลิ้ง 0.8–1.05 (ใช้ 0.8 = ฝั่งร้าย v_t สูงกว่า) · ทรงกลม 0.44 (Re > 1,000) · ท่อนเส้นใยขวางลม 1.0
export const DEBRIS_SHAPES = Object.freeze({
  cube: { label: 'ลูกบาศก์', cd: 0.8 },
  sphere: { label: 'ทรงกลม', cd: 0.44 },
  rod: { label: 'ท่อนเส้นใย (ขวางลม)', cd: 1.0 },
});
export const DEBRIS_DEFAULTS = Object.freeze({
  shape: 'cube', sizeMm: 5, lenMm: 5, cd: 0.8, rhoP: PLA_DENSITY,
  mu: 0.35,            // [ประมาณการ] PLA บนพื้นพิมพ์ 3D 0.3–0.4
  rampDeg: 20,         // [วัดจาก CAD] ขึ้น 9 mm ใน 25 mm
  stepMm: 15,          // [วัดจาก CAD] พื้นกล่องท้าย → พื้นช่องตรง
  brushRpm: 200,       // [สเปก-ร้าน ไร้โหลด] JGB37-520 6 V 200 rpm บนราง 6 V (ผู้ใช้ยืนยัน 3 ต.ค. · C56) · วัดจริงด้วย encoder ได้
  brushDiaMm: 41,      // [วัดจาก CAD] swiper ใน Asembly2
});

/** มวล พื้นที่รับลม และความเร็วปลาย v_t = √(2mg / (ρ C_d A)) */
export function debrisProps(debris = {}, rho = 1.2) {
  const d = { ...DEBRIS_DEFAULTS, ...debris };
  if (!(d.sizeMm > 0) || !(d.cd > 0) || (d.shape === 'rod' && !(d.lenMm > 0))) throw new Error('ขนาดและ C_d ของเศษต้องมากกว่า 0');
  const a = d.sizeMm / 1e3, l = d.lenMm / 1e3;
  let volume, area;
  if (d.shape === 'sphere') { volume = Math.PI * a ** 3 / 6; area = Math.PI * a * a / 4; }
  else if (d.shape === 'rod') { volume = Math.PI * a * a * l / 4; area = a * l; }
  else { volume = a ** 3; area = a * a; }
  const mass = d.rhoP * volume;
  const vt = Math.sqrt(2 * mass * 9.81 / (rho * d.cd * area));
  return { ...d, volume, area, mass, vt };
}

/** ชะตากรรมของเศษตามเกณฑ์ §22.11 */
export function debrisFate(op, debris = {}) {
  const d = debrisProps(debris, op.params.rho);
  const th = d.rampDeg * Math.PI / 180;
  const vSlide = d.vt * Math.sqrt(d.mu);
  const vRamp = d.vt * Math.sqrt(Math.sin(th) + d.mu * Math.cos(th));
  const vTip = Math.PI * d.brushDiaMm / 1e3 * d.brushRpm / 60;
  const hThrowMm = vTip ** 2 / (2 * 9.81) * 1e3;
  const vTipNeeded = Math.sqrt(2 * 9.81 * d.stepMm / 1e3);
  const rpmNeeded = vTipNeeded * 60 / (Math.PI * d.brushDiaMm / 1e3);
  const entryByAir = op.v.slot >= d.vt;            // ลมในทางเข้ายกข้ามขั้นได้เอง
  const entryByBrush = hThrowMm >= d.stepMm;       // แปรงดีดข้ามขั้น (ballistic ในอุดมคติ)
  return {
    debris: d, vSlide, vRamp, vTip, hThrowMm, vTipNeeded, rpmNeeded,
    entryByAir, entryByBrush, entry: entryByAir || entryByBrush,
    channel: op.v.channel >= vSlide,                 // ลากไถลไปตามพื้นช่องตรงได้
    airborne: op.v.channel >= d.vt,
    settlesInBin: op.v.bay < d.vt,
  };
}
