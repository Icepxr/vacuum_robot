import { AIR_DEFAULTS, CFM_TO_M3S, solveOperatingPoint, terminalVelocity, systemCurve, fanDp, PLA_DENSITY, DEBRIS_SHAPES, DEBRIS_DEFAULTS, debrisFate } from './airflow.mjs?v=20261003b';

const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const SLOWDOWN = 40;
const PMAX_BAND = [300, 486.2];

// ---------- แท็บ ----------
const subtitles = {
  motion: 'จำลองการเคลื่อนที่แบบ differential drive จากมิติจริงและ encoder',
  air: 'ทางเดินฝุ่นและแรงดูดของ blower — แบบจำลองท่อ 1 มิติบนหน้าตัด CAD จริง',
  power: 'งบพลังงาน ผัง 4 buck — กระแสต่อราง แบตลดตามเวลา และรอบต่อการชาร์จในแต่ละสถานการณ์',
};
const TABS = Object.keys(subtitles);
function selectTab(name) {
  document.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
  for (const t of TABS) $(`tab-${t}`).hidden = name !== t;
  $('page-subtitle').textContent = subtitles[name];
  try { localStorage.setItem('mrc-lab-tab', name); } catch {}
  if (name === 'air') render();
  window.dispatchEvent(new CustomEvent('mrc-tab', { detail: name }));
  window.dispatchEvent(new Event('resize'));
}
document.querySelectorAll('[data-tab]').forEach(b => b.addEventListener('click', () => selectTab(b.dataset.tab)));
{ const h = location.hash.slice(1); let saved = null; try { saved = localStorage.getItem('mrc-lab-tab'); } catch {}
  const want = TABS.includes(h) ? h : saved; if (want && want !== 'motion' && TABS.includes(want)) selectTab(want); }

// ---------- อินพุต ----------
const inputs = {
  pMaxPa: $('air-pmax'), qFreeCfm: $('air-qfree'), curve: $('air-curve'),
  edgeFrontMm: $('air-edge-front'), edgeRearMm: $('air-edge-rear'),
  chWidMm: $('air-ch-w'), chHgtMm: $('air-ch-h'), chLenMm: $('air-ch-l'),
  holeDiaMm: $('air-hole'), filterPaAt10: $('air-filter'),
};
const dbx = {
  shape: $('air-shape'), sizeMm: $('air-size'), lenMm: $('air-len'), cd: $('air-cd'), mu: $('air-mu'),
  brushRpm: $('air-brush-rpm'), brushDiaMm: $('air-brush-d'), stepMm: $('air-step'), rampDeg: $('air-ramp'),
};
function readDebris() { const d = {}; for (const [k, e] of Object.entries(dbx)) d[k] = k === 'shape' ? e.value : Number(e.value); return d; }
function setDebris(d) { for (const [k, v] of Object.entries(d)) if (dbx[k]) dbx[k].value = v; syncShape(); }
function syncShape() {
  const sh = dbx.shape.value;
  $('air-size-label').textContent = sh === 'cube' ? 'ด้าน a' : 'Ø d';
  $('air-len-wrap').hidden = sh !== 'rod';
}
dbx.shape.addEventListener('change', () => { dbx.cd.value = DEBRIS_SHAPES[dbx.shape.value].cd; syncShape(); render(); });
$('air-debris-reset').addEventListener('click', () => { setDebris({ ...DEBRIS_DEFAULTS }); render(); });
syncShape();
function readParams() {
  const p = {};
  for (const [k, el] of Object.entries(inputs)) p[k] = k === 'curve' ? el.value : Number(el.value);
  return p;
}
function setParams(p) { for (const [k, v] of Object.entries(p)) if (inputs[k]) inputs[k].value = k === 'curve' ? v : +(+v).toFixed(2); }
const PRESETS = {
  r1: { edgeFrontMm: 8.2, edgeRearMm: 27.2, filterPaAt10: 0 },
  r2: { edgeFrontMm: 3, edgeRearMm: 3, filterPaAt10: 0 },
  filter: { edgeFrontMm: 8.2, edgeRearMm: 27.2, filterPaAt10: 100 },
};
document.querySelectorAll('[data-air-preset]').forEach(b => b.addEventListener('click', () => { setParams(PRESETS[b.dataset.airPreset]); render(); }));
$('air-reset').addEventListener('click', () => {
  setParams({ pMaxPa: AIR_DEFAULTS.pMaxPa, qFreeCfm: AIR_DEFAULTS.qFreeCfm, curve: 'lin', edgeFrontMm: 8.2, edgeRearMm: 27.2,
    chWidMm: 25, chHgtMm: 50, chLenMm: 165, holeDiaMm: 79.9, filterPaAt10: 0 });
  setDebris({ ...DEBRIS_DEFAULTS }); render();
});
for (const el of [...Object.values(inputs), ...Object.values(dbx)]) el.addEventListener('input', render);

// ---------- CAD sections ----------
let sections = null;
fetch('./assets/airpath-sections.json').then(r => r.ok ? r.json() : Promise.reject(r.status))
  .then(j => { sections = j; buildScene(); render(); })
  .catch(e => { $('air-validation').textContent = `โหลดหน้าตัด CAD ไม่ได้ (${e}) — เปิดผ่าน http server`; });

let view = 'side';
document.querySelectorAll('[data-air-view]').forEach(b => b.addEventListener('click', () => {
  view = b.dataset.airView;
  document.querySelectorAll('[data-air-view]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  buildScene(); render();
}));
let playing = !matchMedia('(prefers-reduced-motion: reduce)').matches;
const playBtn = $('air-play');
function syncPlay() { playBtn.textContent = playing ? '⏸ หยุด' : '▶ เล่น'; playBtn.setAttribute('aria-pressed', String(playing)); }
playBtn.addEventListener('click', () => { playing = !playing; syncPlay(); }); syncPlay();

// เส้นทางอนุภาค (mm) และช่วงความเร็ว: 0 ช่องใต้พื้น · 1 กล่องท้าย · 2 ช่องตรง · 3 ถัง · 4 รูขึ้น blower
const PATHS = {
  side: { pts: [[248, -34], [244, -14], [224, 2], [198, 20], [30, 20], [-15, 20], [0, 47], [0, 95]], seg: [0, 1, 1, 2, 3, 4, 4],
          boxDrop: [[200, -19], [222, -24]], chDrop: [[150, -1], [190, -1]], binDrop: [[-35, -1], [20, -1]], extent: [-62, 285, -40, 108], ax: ['x', 'z'] },
  top:  { pts: [[248, -160], [248, -64], [222, -63], [198, -62], [30, -62], [-15, -63], [0, -64], [0, -64.1]], seg: [0, 1, 1, 2, 3, 4, 4],
          boxDrop: [[204, -85], [222, -40]], chDrop: [[150, -72], [190, -52]], binDrop: [[-40, -100], [20, -30]], extent: [-62, 285, -205, 72], ax: ['x', 'y'] },
};
const svg = $('air-view');
let mapX, mapY, layerParticles, labels = {};
function el(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (parent) parent.appendChild(e); return e; }
function polyline(pts, cls, parent) { return el('polyline', { points: pts.map(([a, b]) => `${mapX(a).toFixed(1)},${mapY(b).toFixed(1)}`).join(' '), class: cls, fill: 'none', stroke: '#9fb7c2' }, parent); }
function text(x, y, t, cls, parent, anchor = 'middle') { const e = el('text', { x: mapX(x), y: mapY(y), class: cls, 'text-anchor': anchor }, parent); e.textContent = t; return e; }

function buildScene() {
  svg.replaceChildren();
  if (!sections) return;
  const P = PATHS[view], [x0, x1, y0, y1] = P.extent, W = 1100, H = 520, pad = 28;
  const s = Math.min((W - 2 * pad) / (x1 - x0), (H - 2 * pad) / (y1 - y0));
  const ox = (W - s * (x1 - x0)) / 2, oy = (H - s * (y1 - y0)) / 2;
  mapX = x => ox + (x - x0) * s; mapY = y => H - oy - (y - y0) * s;
  const g = el('g', {}, svg);
  if (view === 'side') {
    const fz = sections.floorZ;
    el('line', { x1: mapX(x0), y1: mapY(fz), x2: mapX(x1), y2: mapY(fz), class: 'floor-line' }, g);
    text(x0 + 4, fz - 5, 'พื้น (ประมาณจากล้อ Asembly2)', 'air-zone-label', g, 'start');
    el('circle', { cx: mapX(242.5), cy: mapY(-5.8), r: 20.5 * s, class: 'brush' }, g);
    text(242.5, -5.8, 'แปรง', 'air-zone-label', g);
    for (const pl of sections.side.lower) polyline(pl, 'cad-line', g);
    for (const pl of sections.side.upper) polyline(pl, 'cad-line upper', g);
    el('rect', { x: mapX(-48.5), y: mapY(100), width: 97 * s, height: 46 * s, class: 'brush', 'stroke-dasharray': '6 5', fill: 'rgba(91,143,214,.12)', stroke: '#5b8fd6' }, g);
    text(0, 80, 'blower (ไม่มีใน CAD)', 'air-zone-label', g);
    text(-10, 8, 'ถังขยะ', 'air-zone-label', g);
    text(115, 34, 'ช่องตรง', 'air-zone-label', g);
    text(237, 60, 'กล่องท้าย', 'air-zone-label', g);
    text(237.6, 82, 'จอ Ø36', 'air-zone-label', g);
  } else {
    for (const pl of sections.top.lower) polyline(pl, 'cad-line', g);
    for (const pl of sections.top.upperFloor) polyline(pl, 'cad-line upper', g);
    el('rect', { x: mapX(228), y: mapY(3), width: 40 * s, height: 196 * s, class: 'brush' }, g);
    text(248, -175, 'ช่องใต้พื้น + แปรง', 'air-zone-label', g);
    text(-10, -118, 'ถังขยะ', 'air-zone-label', g);
    text(0, -20, 'Ø80 → blower', 'air-zone-label', g);
    text(115, -40, 'ช่องตรง', 'air-zone-label', g);
  }
  polyline(P.pts, 'flow-path', g);
  const lp = view === 'side'
    ? { 0: [262, -24], 2: [115, 6], 3: [-30, 32], 4: [26, 60] }
    : { 0: [270, -110], 2: [115, -84], 3: [-30, -80], 4: [30, -100] };
  labels = {};
  for (const [k, [x, y]] of Object.entries(lp)) labels[k] = text(x, y, '', 'air-speed-label', g, 'start');
  layerParticles = el('g', {}, svg);
  particles = []; piles = [];
}

// ---------- อนุภาค ----------
let particles = [], piles = [], spawnAcc = 0, lastT = performance.now(), result = null, lastKey = '';
const segLen = () => { const P = PATHS[view]; return P.pts.slice(1).map((p, i) => Math.hypot(p[0] - P.pts[i][0], p[1] - P.pts[i][1])); };
function pointAt(sMm) {
  const P = PATHS[view], L = segLen(); let s = sMm;
  for (let i = 0; i < L.length; i++) { if (s <= L[i]) { const a = P.pts[i], b = P.pts[i + 1], t = s / L[i]; return { x: a[0] + (b[0] - a[0]) * t, y: a[1] + (b[1] - a[1]) * t, seg: P.seg[i], idx: i }; } s -= L[i]; }
  return null;
}
const rnd = (a, b) => a + Math.random() * (b - a);
let fateNow = null;
function fate(kind) {
  if (kind === 'dust' || !fateNow) return { lift: true, entry: true, carried: true };
  return { lift: fateNow.entryByAir, entry: fateNow.entry, carried: fateNow.channel };
}
function tick(now) {
  const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;
  if (playing && result && layerParticles && !$('tab-air').hidden) {
    spawnAcc += dt * 14;
    while (spawnAcc > 1) { spawnAcc--; const kind = Math.random() < .3 ? 'dust' : 'debris'; const f = fate(kind);
      particles.push({ s: 0, kind, ...f, off: rnd(-4, 4), state: f.lift ? 'green' : 'amber', node: el('circle', { r: kind === 'dust' ? 1.6 : 3.4 }, layerParticles) }); }
    const total = segLen().reduce((a, b) => a + b, 0);
    const vSeg = [result.v.slot, Math.max(result.v.slot, 1.0), result.v.channel, result.v.bay, result.v.hole];
    for (const p of particles) {
      const here = pointAt(p.s); if (!here) { p.dead = true; continue; }
      if (here.seg <= 1 && !p.lift) { p.s += 3.0 * 1000 * dt / SLOWDOWN; } // แปรงดีด (ความเร็วแสดงผล 3 m/s — ไม่ใช่ค่าคำนวณ)
      else p.s += vSeg[here.seg] * 1000 * dt / SLOWDOWN;
      const nxt = pointAt(p.s);
      if (p.kind === 'debris' && nxt && nxt.seg === 2 && !p.entry) { settle(p, PATHS[view].boxDrop, 'red'); continue; }
      if (p.kind === 'debris' && nxt && nxt.seg === 2 && !p.carried) { settle(p, PATHS[view].chDrop, 'purple'); continue; }
      if (p.kind === 'debris' && nxt && nxt.seg === 4) { settle(p, PATHS[view].binDrop, 'green'); continue; }
      if (p.kind === 'debris' && nxt && nxt.seg === 2) p.state = 'green';
      if (!nxt || p.s >= total) { p.dead = true; continue; }
      p.node.setAttribute('cx', mapX(nxt.x) + p.off); p.node.setAttribute('cy', mapY(nxt.y) + p.off * .6);
      p.node.setAttribute('class', `pt ${p.kind === 'dust' ? 'grey' : p.state}`);
    }
    for (const p of particles) if (p.dead) p.node.remove();
    particles = particles.filter(p => !p.dead);
    while (piles.length > 160) piles.shift().remove();
  }
  requestAnimationFrame(tick);
}
function settle(p, box, color) {
  p.dead = true; p.node.remove();
  const [[ax, ay], [bx, by]] = box;
  piles.push(el('circle', { cx: mapX(rnd(Math.min(ax, bx), Math.max(ax, bx))), cy: mapY(rnd(Math.min(ay, by), Math.max(ay, by))), r: 3, class: `pt ${color} settled` }, layerParticles));
}
requestAnimationFrame(tick);

// ---------- กราฟ P–Q ----------
function drawChart(p, r) {
  const c = $('air-chart'); c.replaceChildren();
  const W = 640, H = 400, L = 58, R = 18, T = 16, B = 44;
  const qMax = p.qFreeCfm * CFM_TO_M3S * 1e3 * 1.02, pMax = Math.max(500, p.pMaxPa * 1.1);
  const X = q => L + q / qMax * (W - L - R), Y = v => H - B - v / pMax * (H - T - B);
  for (let i = 0; i <= 5; i++) { const v = pMax * i / 5; el('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), class: 'chart-grid' }, c); const t = el('text', { x: L - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'chart-text' }, c); t.textContent = v.toFixed(0); }
  for (let q = 0; q <= qMax; q += 2.5) { el('line', { x1: X(q), x2: X(q), y1: T, y2: H - B, class: 'chart-grid' }, c); const t = el('text', { x: X(q), y: H - B + 16, 'text-anchor': 'middle', class: 'chart-text' }, c); t.textContent = q.toFixed(1); }
  el('line', { x1: L, x2: W - R, y1: H - B, y2: H - B, class: 'chart-axis' }, c); el('line', { x1: L, x2: L, y1: T, y2: H - B, class: 'chart-axis' }, c);
  const xt = el('text', { x: (L + W - R) / 2, y: H - 8, 'text-anchor': 'middle', class: 'chart-text' }, c); xt.textContent = 'Q (L/s)';
  const yt = el('text', { x: 14, y: (T + H - B) / 2, 'text-anchor': 'middle', class: 'chart-text', transform: `rotate(-90 14 ${(T + H - B) / 2})` }, c); yt.textContent = 'ΔP (Pa)';
  const qf = p.qFreeCfm * CFM_TO_M3S, n = 60, qs = Array.from({ length: n + 1 }, (_, i) => qf * i / n);
  const lo = qs.map(q => [X(q * 1e3), Y(fanDp(q, { ...p, pMaxPa: PMAX_BAND[0] }))]), hi = qs.map(q => [X(q * 1e3), Y(fanDp(q, { ...p, pMaxPa: PMAX_BAND[1] }))]);
  el('polygon', { points: [...lo, ...hi.reverse()].map(a => a.join(',')).join(' '), class: 'chart-band', fill: 'rgba(141,164,175,.14)' }, c);
  const curve = systemCurve(p, n);
  el('polyline', { points: curve.map(k => `${X(k.q * 1e3)},${Y(Math.max(0, k.fan))}`).join(' '), class: 'chart-fan', fill: 'none', stroke: '#eaf6fa' }, c);
  el('polyline', { points: curve.filter(k => k.sys <= pMax).map(k => `${X(k.q * 1e3)},${Y(k.sys)}`).join(' '), class: 'chart-sys', fill: 'none', stroke: '#30d5e8' }, c);
  el('circle', { cx: X(r.q * 1e3), cy: Y(r.dpFan), r: 6, class: 'chart-op' }, c);
  const lab = el('text', { x: X(r.q * 1e3) - 10, y: Y(r.dpFan) - 12, 'text-anchor': 'end', class: 'air-speed-label' }, c);
  lab.textContent = `${(r.q * 1e3).toFixed(2)} L/s · ${r.dpFan.toFixed(0)} Pa`;
}

// ---------- ขั้นคำนวณ ----------
const f1 = (v, d = 1) => Number(v).toFixed(d);
// แต่ละขั้น: [หัวข้อ, ป้าย, [{note?, tex}]] · tex เรนเดอร์ด้วย KaTeX (ถ้าโหลดไม่ได้จะแสดง TeX ดิบ)
const n = (v, d = 2) => Number(v).toFixed(d);
const T = s => `\\text{${s}}`;
function steps(p, r, F) {
  const g = r.geometry, t = r.terms, q = r.q, rho = p.rho;
  const edgeLen = p.slotLenMm + p.slotWidMm;
  const re = rho * t.vCh * g.dhCh / p.mu;
  const sum = t.inlet + t.chEntry + t.chFriction + t.dump + t.hole + t.filter;
  const qL = n(q * 1e3), qf = p.qFreeCfm * CFM_TO_M3S * 1e3;
  const fanTex = p.curve === 'lin'
    ? String.raw`\Delta P_\text{fan}(Q) = \Delta P_\text{max}\left(1 - \frac{Q}{Q_\text{free}}\right)`
    : String.raw`\Delta P_\text{fan}(Q) = \Delta P_\text{max}\left[1 - \left(\frac{Q}{Q_\text{free}}\right)^{2}\right]`;
  const loss = (label, k, v, val) => String.raw`${T(label)} &: & ${k} \times \tfrac12(${rho})(${n(v)})^2 &= ${n(val, 1)}\ \text{Pa}`;
  return [
    ['ลมสูงสุดของ blower (ไม่มีตัวต้าน)', 'สเปกร้าน', [
      { tex: String.raw`Q_\text{free} = ${n(p.qFreeCfm)}\ \text{CFM} \times 4.71947\times10^{-4}\ \frac{\text{m}^3/\text{s}}{\text{CFM}} = ${n(qf)}\ \text{L/s}` }]],
    ['ความดันสูงสุดและ curve ของ blower', 'ประมาณการ', [
      { note: 'เทียบ Delta BFB1012VH ด้วยกฎพัดลม ΔP ∝ n²', tex: String.raw`\Delta P_\text{max} = 486.2 \left(\frac{4200}{4500}\right)^{2} = 423.5\ \text{Pa} \qquad (\text{ใช้อยู่ } ${n(p.pMaxPa, 1)}\ \text{Pa})` },
      { tex: fanTex }]],
    ['หน้าตัดจาก CAD', 'CAD', [
      { tex: String.raw`\begin{aligned}
A_\text{gap} &= (L_\text{slot}+W_\text{slot})(h_\text{f}+h_\text{r}) = ${edgeLen}\times(${n(p.edgeFrontMm, 1)}+${n(p.edgeRearMm, 1)}) = ${n(g.aGap * 1e6, 0)}\ \text{mm}^2\\
A_\text{ch} &= w\,h = ${n(p.chWidMm, 1)}\times${n(p.chHgtMm, 1)} = ${n(g.aCh * 1e6, 0)}\ \text{mm}^2, \qquad D_h = \frac{2wh}{w+h} = ${n(g.dhCh * 1e3, 1)}\ \text{mm}\\
A_\text{slot} &= 40\times196 = 7840\ \text{mm}^2, \qquad A_\text{bin} = 84.9\times50 = 4245\ \text{mm}^2\\
A_\text{hole} &= \frac{\pi}{4}d^{2} = \frac{\pi}{4}(${n(p.holeDiaMm, 1)})^{2} = ${n(g.aHole * 1e6, 0)}\ \text{mm}^2
\end{aligned}` }]],
    ['ความเร็วที่จุดทำงาน', 'คำนวณ', [
      { tex: String.raw`v_i = \frac{Q}{A_i}, \qquad Q = ${qL}\ \text{L/s} = ${n(q * 1e3, 2)}\times10^{-3}\ \text{m}^3/\text{s}` },
      { tex: String.raw`\begin{aligned}
v_\text{gap} &= ${n(r.v.gap)} & v_\text{slot} &= ${n(r.v.slot)} & v_\text{ch} &= ${n(r.v.channel)}\\
v_\text{bin} &= ${n(r.v.bay)} & v_\text{hole} &= ${n(r.v.hole)} & & \quad [\text{m/s}]
\end{aligned}` }]],
    ['แรงเสียดทานในช่องตรง', 'คำนวณ', [
      { tex: String.raw`Re = \frac{\rho\,v_\text{ch}\,D_h}{\mu} = \frac{${rho}\times${n(t.vCh)}\times${n(g.dhCh, 4)}}{1.81\times10^{-5}} = ${Math.round(re).toLocaleString('en-US')}` },
      { note: 'Swamee–Jain · ความหยาบผิว ε = 0.05 mm (ชิ้นพิมพ์ 3D) [ประมาณการ]', tex: String.raw`f = \frac{0.25}{\left[\log_{10}\!\left(\dfrac{\varepsilon}{3.7D_h} + \dfrac{5.74}{Re^{0.9}}\right)\right]^{2}} = ${n(t.f, 4)}, \qquad K_f = f\,\frac{L}{D_h} = ${n(t.f, 4)}\times\frac{${n(p.chLenMm, 0)}}{${n(g.dhCh * 1e3, 1)}} = ${n(t.kFric, 3)}` }]],
    ['การสูญเสียแต่ละจุด', 'ประมาณการ K', [
      { tex: String.raw`\Delta P_i = K_i\cdot\tfrac12\rho v_i^{2}` },
      { tex: String.raw`\begin{aligned}
${loss('ลอดใต้ขอบ', p.kGap, t.vGap, t.inlet)}\\
${loss('เข้าช่องตรง', p.kChIn, t.vCh, t.chEntry)}\\
${loss('เสียดทาน', n(t.kFric, 3), t.vCh, t.chFriction)}\\
${loss('ทิ้งเข้าถัง', p.kDump, t.vCh, t.dump)}\\
${loss('รูขึ้น blower', p.kHole, t.vHole, t.hole)}\\
${T('ไส้กรอง')} &: & ${n(p.filterPaAt10, 0)}\times\frac{Q}{10\ \text{L/s}} &= ${n(t.filter, 1)}\ \text{Pa}
\end{aligned}` }]],
    ['จุดทำงาน: blower = ผลรวมการสูญเสีย', 'คำนวณ', [
      { note: 'หา Q ด้วย bisection', tex: String.raw`\Delta P_\text{fan}(Q) = \sum_i \Delta P_i \;\Rightarrow\; \Delta P_\text{fan}(${qL}) = ${n(r.dpFan, 1)}\ \text{Pa} \approx ${n(sum, 1)}\ \text{Pa}\ \checkmark` }]],
    ...debrisSteps(p, r, F),
  ];
}

function debrisSteps(p, r, F) {
  const d = F.debris, rho = p.rho, a = n(d.sizeMm / 1e3, 4);
  const geo = d.shape === 'sphere'
    ? String.raw`m = \rho_p\frac{\pi d^{3}}{6} = ${d.rhoP}\times\frac{\pi(${a})^{3}}{6}, \qquad A = \frac{\pi d^{2}}{4}`
    : d.shape === 'rod'
      ? String.raw`m = \rho_p\frac{\pi d^{2}L}{4} = ${d.rhoP}\times\frac{\pi(${a})^{2}(${n(d.lenMm / 1e3, 4)})}{4}, \qquad A = d\,L`
      : String.raw`m = \rho_p a^{3} = ${d.rhoP}\times(${a})^{3}, \qquad A = a^{2} = (${a})^{2}`;
  const cmp = (v, need) => v >= need ? '\\ge' : '<';
  return [
    [`เศษ ${DEBRIS_SHAPES[d.shape].label} ${d.sizeMm}${d.shape === 'rod' ? ` × ${d.lenMm}` : ''} mm: มวลและความเร็วปลาย`, 'คำนวณ', [
      { tex: String.raw`${geo} \;\Rightarrow\; m = ${n(d.mass * 1e6, 1)}\ \text{mg}, \quad A = ${n(d.area * 1e6, 2)}\ \text{mm}^2` },
      { note: `C_d = ${d.cd} [ประมาณการ]`, tex: String.raw`v_t = \sqrt{\frac{2\,m\,g}{\rho\,C_d\,A}} = \sqrt{\frac{2\times${n(d.mass, 7)}\times9.81}{${rho}\times${d.cd}\times${n(d.area, 8)}}} = ${n(d.vt)}\ \text{m/s}` }]],
    ['เกณฑ์ลากไถลบนพื้น และขึ้นทางลาด', 'ประมาณการ μ', [
      { tex: String.raw`\tfrac12\rho v^{2}C_dA \ge \mu m g \;\Rightarrow\; v_\text{slide} = v_t\sqrt{\mu} = ${n(d.vt)}\sqrt{${d.mu}} = ${n(F.vSlide)}\ \text{m/s}` },
      { tex: String.raw`v_\text{ramp} = v_t\sqrt{\sin\theta + \mu\cos\theta} = ${n(d.vt)}\sqrt{\sin ${d.rampDeg}^\circ + ${d.mu}\cos ${d.rampDeg}^\circ} = ${n(F.vRamp)}\ \text{m/s}` }]],
    ['แปรงดีดข้ามขั้นได้ไหม (ballistic ในอุดมคติ)', 'JGB37-520 6 V 200 rpm · รอบประมาณการ', [
      { tex: String.raw`v_\text{tip} = \frac{\pi D n}{60} = \frac{\pi\times${n(d.brushDiaMm / 1e3, 3)}\times${d.brushRpm}}{60} = ${n(F.vTip, 3)}\ \text{m/s}, \qquad h = \frac{v_\text{tip}^{2}}{2g} = ${n(F.hThrowMm, 1)}\ \text{mm}` },
      { tex: String.raw`h_\text{step} = ${d.stepMm}\ \text{mm} \;\Rightarrow\; n_\text{min} = \frac{60\sqrt{2 g h_\text{step}}}{\pi D} = ${n(F.rpmNeeded, 0)}\ \text{rpm}` }]],
    ['ตัดสินชะตากรรม', 'คำนวณ', [
      { tex: String.raw`\begin{aligned}
${T('ทางเข้า (ลม)')} &: & v_\text{slot} = ${n(r.v.slot)} &${cmp(r.v.slot, d.vt)} v_t = ${n(d.vt)} & &\Rightarrow ${T(F.entryByAir ? 'ผ่าน' : 'ไม่ผ่าน')}\\
${T('ทางเข้า (แปรง)')} &: & h = ${n(F.hThrowMm, 1)} &${cmp(F.hThrowMm, d.stepMm)} h_\text{step} = ${d.stepMm} & &\Rightarrow ${T(F.entryByBrush ? 'ผ่าน' : 'ไม่ผ่าน')}\\
${T('ช่องตรง')} &: & v_\text{ch} = ${n(r.v.channel)} &${cmp(r.v.channel, F.vSlide)} v_\text{slide} = ${n(F.vSlide)} & &\Rightarrow ${T(F.channel ? 'ลากไปได้' : 'ค้าง')}\\
${T('ถังขยะ')} &: & v_\text{bin} = ${n(r.v.bay)} &${cmp(r.v.bay, d.vt)} v_t & &\Rightarrow ${T(F.settlesInBin ? 'ตกในถัง' : 'ลอยตามไป')}
\end{aligned}` }]],
  ];
}

function tex(src) {
  if (!window.katex) return `<code class="tex-fallback">${src.replace(/</g, '&lt;')}</code>`;
  try { return window.katex.renderToString(src, { displayMode: true, throwOnError: false, strict: 'ignore', trust: false }); }
  catch { return `<code class="tex-fallback">${src.replace(/</g, '&lt;')}</code>`; }
}
function renderSteps(list) {
  $('air-steps').innerHTML = list.map(([h, tag, lines]) =>
    `<li><span class="t">${h}</span><span class="tag ${tag === 'CAD' ? 'cad' : ''}">[${tag}]</span>` +
    lines.map(l => `${l.note ? `<p class="step-note">${l.note}</p>` : ''}<div class="math">${tex(l.tex)}</div>`).join('') + '</li>').join('');
}
let lastSteps = null;
window.addEventListener('load', () => { if (lastSteps) renderSteps(lastSteps); });

function conclusions(p, r, F) {
  const d = F.debris;
  const name = `${DEBRIS_SHAPES[d.shape].label} ${d.sizeMm}${d.shape === 'rod' ? `×${d.lenMm}` : ''} mm`;
  const rearShare = p.edgeRearMm / (p.edgeFrontMm + p.edgeRearMm) * 100;
  const base = solveOperatingPoint({ ...p, filterPaAt10: 0 });
  const out = [
    [F.entry ? 'ok' : 'bad', F.entry
      ? `${name} ผ่านทางเข้าได้ ${F.entryByAir ? 'ด้วยลม' : `ด้วยแปรงดีด (สูง ${f1(F.hThrowMm)} ≥ ขั้น ${d.stepMm} mm)`} [คำนวณ]`
      : `${name} ค้างที่ทางเข้า: ลมยกได้แค่ ${f1(r.v.slot, 2)} m/s < v_t ${f1(d.vt, 2)} m/s และแปรง ${d.brushRpm} rpm ดีดได้สูง ${f1(F.hThrowMm)} mm < ขั้น ${d.stepMm} mm → ต้องให้แปรงหมุน ≥ ${f1(F.rpmNeeded, 0)} rpm แต่ JGB37-520 รุ่นนี้ได้สูงสุด 200 rpm ที่พิกัด 6 V [คำนวณ]`],
    [F.channel ? 'ok' : 'bad', `ในช่องตรงลม ${f1(r.v.channel)} m/s ${F.channel ? '≥' : '<'} เกณฑ์ลากไถล ${f1(F.vSlide, 2)} m/s → ${F.channel ? 'ถ้าเข้าช่องได้ จะถูกลากไปถึงถัง' : 'ค้างในช่องตรง'} ${F.airborne ? '(ลอยได้ด้วย)' : '(ไถลไปตามพื้น ไม่ลอย)'} [คำนวณ]`],
    [rearShare > 50 ? 'warn' : 'ok', `ลม ${f1(rearShare, 0)} % เข้าทางขอบหลัง (สูง ${f1(p.edgeRearMm)} mm) ด้านที่ไม่มีเศษ · ลมใต้ขอบ ${f1(r.v.gap, 2)} m/s [คำนวณ]`],
    [r.v.bay < terminalVelocity(1) ? 'ok' : 'warn', `ในถังลมช้าลงเหลือ ${f1(r.v.bay, 2)} m/s ${r.v.bay < terminalVelocity(1) ? '< v_t เศษ 1 mm (5.5 m/s) → เศษตกในถังได้' : 'ยังเร็ว เศษเล็กอาจลอยตามไป blower'} · ฝุ่นละเอียดยังลอยผ่านรูขึ้น blower [คำนวณ]`],
  ];
  if (p.filterPaAt10 > 0) out.push(['warn', `ไส้กรอง ${f1(p.filterPaAt10, 0)} Pa@10 L/s ลดลมจาก ${f1(base.q * 1e3, 2)} เหลือ ${f1(r.q * 1e3, 2)} L/s (−${f1((1 - r.q / base.q) * 100, 0)} %) [คำนวณ]`]);
  const share = (r.terms.chEntry + r.terms.chFriction + r.terms.dump) / r.dpFan * 100;
  out.push(['warn', `ช่องตรงกิน ${f1(share, 0)} % ของ ΔP ทั้งหมด → ตัวต้านหลักของระบบ ไม่ใช่รูขึ้น blower [คำนวณ]`]);
  return out;
}

function render() {
  let p, r;
  try { p = readParams(); r = solveOperatingPoint(p); $('air-validation').textContent = ''; }
  catch (e) { $('air-validation').textContent = `ตรวจค่าอินพุต: ${e.message}`; return; }
  result = r;
  let F;
  try { F = debrisFate(r, readDebris()); } catch (e) { $('air-validation').textContent = `ตรวจค่าเศษ: ${e.message}`; return; }
  fateNow = F; const vt = F.debris.vt;
  $('air-q').textContent = f1(r.q * 1e3, 2); $('air-dp').textContent = f1(r.dpFan, 0);
  $('air-vch').textContent = f1(r.v.channel, 2); $('air-vslot').textContent = f1(r.v.slot, 2);
  $('air-vbay').textContent = f1(r.v.bay, 2); $('air-vt').textContent = f1(vt, 2);
  $('air-throw').textContent = `${f1(F.hThrowMm)} / ${F.debris.stepMm}`;
  $('air-fate').textContent = !F.entry ? 'ค้างทางเข้า' : !F.channel ? 'ค้างช่องตรง' : F.settlesInBin ? 'ถึงถัง' : 'ลอยเข้า blower';
  $('air-fate').className = !F.entry || !F.channel ? 'bad' : 'ok';
  if (labels[0]) { labels[0].textContent = `${f1(r.v.slot, 2)} m/s`; labels[2].textContent = `${f1(r.v.channel, 1)} m/s`; labels[3].textContent = `${f1(r.v.bay, 2)} m/s`; labels[4].textContent = `${f1(r.v.hole, 2)} m/s`; }
  const key = JSON.stringify([p, readDebris()]); if (key !== lastKey) { for (const x of piles) x.remove(); piles = []; lastKey = key; }
  drawChart(r.params, r);
  const t = r.terms, parts = [['ลอดใต้ขอบ', t.inlet], ['เข้าช่องตรง', t.chEntry], ['เสียดทานช่องตรง', t.chFriction], ['ทิ้งเข้าถัง', t.dump], ['รูขึ้น blower', t.hole], ['ไส้กรอง', t.filter]];
  const mx = Math.max(...parts.map(x => x[1]), 1);
  $('air-breakdown').innerHTML = parts.map(([n, v]) => `<div class="row"><span>${n}</span><span class="bar"><i style="width:${(v / mx * 100).toFixed(1)}%"></i></span><b>${f1(v)} Pa</b></div>`).join('');
  lastSteps = steps(r.params, r, F); renderSteps(lastSteps);
  $('air-conclusions').innerHTML = conclusions(r.params, r, F).map(([c, s]) => `<li class="${c}">${s}</li>`).join('');
}
render();
