import { BATTERY_DEFAULTS, RAILS, LOADS, MODES, SCENARIOS, modePower, cycleEnergy, simulateDischarge, peakCheck, packVoltage } from './power.mjs?v=20261003b';

const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const f = (v, d = 1) => Number(v).toFixed(d);
const LEVEL_NAME = { run: 'ปกติ', high: 'OCR', hold: 'ค้าง', peak: 'พีค' };
function el(tag, attrs = {}, parent, text) { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; }
function tex(src) {
  if (!window.katex) return `<code class="tex-fallback">${src.replace(/</g, '&lt;')}</code>`;
  try { return window.katex.renderToString(src, { displayMode: true, throwOnError: false, strict: 'ignore' }); } catch { return `<code class="tex-fallback">${src}</code>`; }
}
const T = s => `\\text{${s}}`;

// ---------- อินพุต ----------
const batIn = { capacityWh: $('pw-cap'), usableFactor: $('pw-f'), vFull: $('pw-vfull'), vCutoff: $('pw-vcut'), vLow: $('pw-vlow'), fuseA: $('pw-fuse') };
function buildInputs() {
  $('pw-rails').innerHTML = `<div class="pw-row head"><span>ราง</span><span>พิกัด A</span><span>η %</span></div>` +
    RAILS.map(r => `<div class="pw-row"><span title="${r.note}">${r.name}<small>${r.note}</small></span>
      <input type="number" min="0.1" step="0.5" value="${r.ratingA}" data-rail="${r.id}" data-k="ratingA" aria-label="พิกัด ${r.name}">
      <input type="number" min="50" max="100" step="1" value="${Math.round(r.eff * 100)}" data-rail="${r.id}" data-k="eff" aria-label="ประสิทธิภาพ ${r.name}"></div>`).join('');
  $('pw-loads').innerHTML = LOADS.map(l => `<div class="pw-load"><div class="pw-load-name">${l.name}<small>${RAILS.find(r => r.id === l.rail).name} · ${l.src}</small></div>
      <div class="pw-levels">${Object.entries(l.levels).map(([k, v]) => `<label>${LEVEL_NAME[k] || k}<input type="number" min="0" step="0.05" value="${v}" data-load="${l.id}" data-k="${k}"></label>`).join('')}</div></div>`).join('');
}
function readOpts() {
  const battery = {}; for (const [k, e] of Object.entries(batIn)) battery[k] = Number(e.value);
  const rails = RAILS.map(r => ({ ...r }));
  document.querySelectorAll('[data-rail]').forEach(i => { const r = rails.find(x => x.id === i.dataset.rail); const v = Number(i.value); r[i.dataset.k] = i.dataset.k === 'eff' ? v / 100 : v; });
  const loads = LOADS.map(l => ({ ...l, levels: { ...l.levels } }));
  document.querySelectorAll('[data-load]').forEach(i => { loads.find(x => x.id === i.dataset.load).levels[i.dataset.k] = Number(i.value); });
  for (const [k, v] of Object.entries(battery)) if (!(v > 0)) throw new Error(`ค่าแบต ${k} ต้องมากกว่า 0`);
  if (battery.vFull <= battery.vCutoff) throw new Error('แรงดันเต็มต้องสูงกว่าจุดตัด');
  for (const r of rails) if (!(r.ratingA > 0) || !(r.eff > 0 && r.eff <= 1)) throw new Error(`ตรวจพิกัด/η ของ ${r.name}`);
  return { battery, rails, loads };
}

// ---------- สถานการณ์ ----------
const custom = { name: 'กำหนดเอง', src: 'ผู้ใช้ตั้ง', steps: [['collect', 60], ['lift', 6], ['read', 9], ['drive', 20], ['standby', 0]] };
let scenId = 'race';
function steps() { return (scenId === 'custom' ? custom : SCENARIOS[scenId]).steps.filter(([, s]) => s > 0); }
function buildScenarios() {
  const all = { ...SCENARIOS, custom };
  $('pw-scenarios').innerHTML = Object.entries(all).map(([k, s]) => `<button type="button" data-scen="${k}" aria-pressed="${k === scenId}" title="${s.src}">${s.name}</button>`).join('') +
    `<div class="pw-custom" id="pw-custom" ${scenId === 'custom' ? '' : 'hidden'}>${custom.steps.map(([m, s], i) => `<label><i style="background:${MODES[m].color}"></i>${MODES[m].name}<div class="input-unit"><input type="number" min="0" step="1" value="${s}" data-custom="${i}"><span>s</span></div></label>`).join('')}</div>`;
  document.querySelectorAll('[data-scen]').forEach(b => b.addEventListener('click', () => { scenId = b.dataset.scen; buildScenarios(); restart(); recompute(); }));
  document.querySelectorAll('[data-custom]').forEach(i => i.addEventListener('input', () => { custom.steps[+i.dataset.custom][1] = Math.max(0, Number(i.value) || 0); restart(); recompute(); }));
}

// ---------- ผังไฟ ----------
const flow = $('pw-flow');
let flowParts = null;
function buildFlow(opts) {
  flow.replaceChildren();
  const g = el('g', {}, flow);
  const railY = { r5a: 70, r5b: 185, r6: 290, r12: 400 };
  const loadPos = {}; const groups = {};
  for (const l of opts.loads) (groups[l.rail] ||= []).push(l);
  for (const [rid, ls] of Object.entries(groups)) ls.forEach((l, i) => { loadPos[l.id] = { x: 760, y: railY[rid] + (i - (ls.length - 1) / 2) * 38 }; });
  // แบต + ฟิวส์ + บัส
  el('rect', { x: 30, y: 180, width: 120, height: 120, rx: 14, class: 'pw-bat' }, g);
  const batFill = el('rect', { x: 38, y: 188, width: 104, height: 104, rx: 9, class: 'pw-bat-fill' }, g);
  el('text', { x: 90, y: 168, class: 'pw-label', 'text-anchor': 'middle' }, g, 'แบต 4S');
  const batTxt = el('text', { x: 90, y: 248, class: 'pw-big', 'text-anchor': 'middle' }, g, '');
  el('rect', { x: 176, y: 232, width: 34, height: 16, rx: 3, class: 'pw-fuse' }, g);
  el('text', { x: 193, y: 225, class: 'pw-small', 'text-anchor': 'middle' }, g, 'ฟิวส์');
  const fuseTxt = el('text', { x: 193, y: 270, class: 'pw-small', 'text-anchor': 'middle' }, g, '');
  el('path', { d: 'M150 240 H176', class: 'pw-wire' }, g);
  el('path', { d: `M210 240 H250 M250 ${railY.r5a} V${railY.r12}`, class: 'pw-wire' }, g);
  const parts = { batFill, batTxt, fuseTxt, rails: {}, loads: {}, wires: [] };
  for (const r of opts.rails) {
    const y = railY[r.id];
    const w1 = el('path', { d: `M250 ${y} H330`, class: 'pw-flowline' }, g);
    el('rect', { x: 330, y: y - 30, width: 170, height: 60, rx: 10, class: 'pw-buck' }, g);
    el('text', { x: 415, y: y - 8, class: 'pw-label', 'text-anchor': 'middle' }, g, `${r.name}`);
    const txt = el('text', { x: 415, y: y + 13, class: 'pw-small', 'text-anchor': 'middle' }, g, '');
    el('rect', { x: 340, y: y + 21, width: 150, height: 5, rx: 2.5, class: 'pw-barbg' }, g);
    const bar = el('rect', { x: 340, y: y + 21, width: 0, height: 5, rx: 2.5, class: 'pw-bar' }, g);
    const inTxt = el('text', { x: 290, y: y - 6, class: 'pw-amp', 'text-anchor': 'middle' }, g, '');
    parts.rails[r.id] = { txt, bar, inTxt, w1 }; parts.wires.push(w1);
  }
  for (const l of opts.loads) {
    const { x, y } = loadPos[l.id], ry = railY[l.rail];
    const w = el('path', { d: `M500 ${ry} C 600 ${ry}, 620 ${y}, ${x - 10} ${y}`, class: 'pw-flowline' }, g);
    el('rect', { x: x - 10, y: y - 15, width: 320, height: 30, rx: 8, class: 'pw-loadbox' }, g);
    const name = el('text', { x: x + 2, y: y + 5, class: 'pw-small' }, g, l.name);
    const amp = el('text', { x: x + 300, y: y + 5, class: 'pw-amp', 'text-anchor': 'end' }, g, '');
    parts.loads[l.id] = { w, amp, name }; parts.wires.push(w);
  }
  flowParts = parts;
}
function updateFlow(opts, modeId, eRem) {
  if (!flowParts) return;
  const mp = modePower(modeId, opts), b = opts.battery;
  const usable = b.capacityWh * b.usableFactor, soc = Math.max(0, eRem / usable), v = packVoltage(eRem, b), iPack = mp.pIn / v;
  flowParts.batFill.setAttribute('height', 104 * soc); flowParts.batFill.setAttribute('y', 188 + 104 * (1 - soc));
  flowParts.batFill.setAttribute('class', `pw-bat-fill ${v <= b.vLow ? 'low' : ''}`);
  flowParts.batTxt.textContent = `${f(v, 2)} V`;
  flowParts.fuseTxt.textContent = `${f(iPack, 2)} / ${b.fuseA} A`;
  for (const r of opts.rails) {
    const pr = mp.perRail[r.id], p = flowParts.rails[r.id], ratio = pr.amps / r.ratingA;
    p.txt.textContent = `${f(pr.amps, 2)} / ${r.ratingA} A · ${f(pr.watts, 1)} W`;
    p.bar.setAttribute('width', Math.min(150, 150 * ratio)); p.bar.setAttribute('class', `pw-bar ${ratio > 1 ? 'over' : ratio > 0.8 ? 'warn' : ''}`);
    const iin = pr.pIn / v; p.inTxt.textContent = `${f(iin, 2)} A`; p.w1.dataset.amps = iin;
  }
  const mode = MODES[modeId];
  for (const l of opts.loads) {
    const lvl = mode.loads[l.id], a = lvl ? (l.levels[lvl] ?? l.levels.run ?? 0) : 0, p = flowParts.loads[l.id];
    p.amp.textContent = a > 0 ? `${f(a, a < 0.1 ? 3 : 2)} A · ${LEVEL_NAME[lvl] || lvl}` : 'ปิด';
    p.w.dataset.amps = a; p.name.setAttribute('class', `pw-small ${a > 0 ? '' : 'off'}`);
  }
}
let dash = 0;
function animateWires(dt) {
  if (!flowParts) return; dash += dt;
  for (const w of flowParts.wires) {
    const a = Number(w.dataset.amps || 0);
    w.style.strokeDashoffset = String(-(dash * 40 * Math.min(a, 6)) % 1000);
    w.style.opacity = a > 0 ? String(0.35 + Math.min(0.65, a / 3)) : '0.12';
    w.style.strokeWidth = String(1.5 + Math.min(4, a));
  }
}

// ---------- จำลองตามเวลา ----------
let opts = null, sim = null, tSim = 0, eRem = 0, playing = false, last = performance.now(), acc = 0, tl = [];
function restart() {
  if (!opts) return;
  tSim = 0; eRem = opts.battery.capacityWh * opts.battery.usableFactor;
  tl = steps().flatMap(([m, s]) => Array.from({ length: Math.round(s) }, () => m));
  playing = false; $('pw-play').textContent = '▶ เล่น';
  updateNow();
}
function modeAt(t) { return tl.length ? tl[Math.floor(t) % tl.length] : 'standby'; }
function updateNow() {
  if (!opts || !tl.length) return;
  const m = modeAt(tSim), mp = modePower(m, opts), v = packVoltage(eRem, opts.battery), usable = opts.battery.capacityWh * opts.battery.usableFactor;
  $('pw-mode-now').textContent = MODES[m].name;
  const mm = Math.floor(tSim / 60), ss = Math.floor(tSim % 60); $('pw-time').textContent = `${mm}:${String(ss).padStart(2, '0')}`;
  $('pw-p').textContent = f(mp.pIn, 1); $('pw-i').textContent = f(mp.pIn / v, 2); $('pw-v').textContent = f(v, 2);
  $('pw-soc').textContent = f(Math.max(0, eRem / usable) * 100, 0);
  const pos = (Math.floor(tSim) % tl.length) / tl.length * 100;
  const cur = $('pw-tl-cursor'); if (cur) cur.style.left = `${pos}%`;
  drawCursor();
  updateFlow(opts, m, eRem);
}
function tick(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  if (!$('tab-power').hidden) {
    animateWires(dt);
    if (playing && opts && tl.length) {
      acc += dt * Number($('pw-speed').value);
      while (acc >= 1) {
        acc -= 1;
        const p = modePower(modeAt(tSim), opts).pIn; eRem -= p / 3600; tSim += 1;
        if (eRem <= 0) { eRem = 0; playing = false; $('pw-play').textContent = '▶ เล่น'; break; }
      }
      updateNow();
    }
  }
  requestAnimationFrame(tick);
}
$('pw-play').addEventListener('click', () => { if (eRem <= 0) restart(); playing = !playing; $('pw-play').textContent = playing ? '⏸ หยุด' : '▶ เล่น'; last = performance.now(); });
$('pw-restart').addEventListener('click', restart);

// ---------- กราฟ ----------
let chartMap = null;
function drawChart() {
  const c = $('pw-chart'); c.replaceChildren();
  const W = 640, H = 360, L = 50, R = 52, Tp = 14, B = 40, pts = sim.points;
  const tMax = Math.max(60, sim.runtimeSec), pMax = Math.max(10, ...pts.map(p => p.p)) * 1.1;
  const X = t => L + t / tMax * (W - L - R), Y = s => H - B - s * (H - Tp - B), YP = p => H - B - p / pMax * (H - Tp - B);
  for (let i = 0; i <= 4; i++) {
    el('line', { x1: L, x2: W - R, y1: Y(i / 4), y2: Y(i / 4), class: 'chart-grid' }, c);
    el('text', { x: L - 6, y: Y(i / 4) + 4, 'text-anchor': 'end', class: 'chart-text' }, c, `${i * 25}%`);
    el('text', { x: W - R + 6, y: Y(i / 4) + 4, class: 'chart-text', fill: '#ffb454' }, c, `${f(pMax * i / 4, 0)} W`);
  }
  const stepMin = tMax > 3600 ? 15 : tMax > 1200 ? 5 : tMax > 300 ? 2 : 1;
  for (let m = 0; m * 60 <= tMax; m += stepMin) el('text', { x: X(m * 60), y: H - B + 16, 'text-anchor': 'middle', class: 'chart-text' }, c, `${m}`);
  el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', class: 'chart-text' }, c, 'เวลา (นาที)');
  el('polyline', { points: pts.map(p => `${X(p.t)},${YP(p.p)}`).join(' '), fill: 'none', stroke: '#ffb454', 'stroke-width': 1.2, opacity: .8 }, c);
  el('polyline', { points: pts.map(p => `${X(p.t)},${Y(p.soc)}`).join(' '), fill: 'none', stroke: '#30d5e8', 'stroke-width': 2.4 }, c);
  if (sim.lowAt != null) { el('line', { x1: X(sim.lowAt), x2: X(sim.lowAt), y1: Tp, y2: H - B, stroke: '#ff6e6e', 'stroke-dasharray': '5 5' }, c); el('text', { x: X(sim.lowAt) + 4, y: Tp + 12, class: 'chart-text', fill: '#ff6e6e' }, c, 'LOW'); }
  chartMap = { X, Y, H, B, Tp, cursor: el('line', { x1: L, x2: L, y1: Tp, y2: H - B, stroke: '#eaf6fa', 'stroke-width': 1, opacity: .7 }, c) };
}
function drawCursor() { if (!chartMap) return; const x = chartMap.X(Math.min(tSim, sim.runtimeSec)); chartMap.cursor.setAttribute('x1', x); chartMap.cursor.setAttribute('x2', x); }

// ---------- คำนวณทั้งหมด ----------
function recompute() {
  try { opts = readOpts(); $('pw-validation').textContent = ''; }
  catch (e) { $('pw-validation').textContent = `ตรวจค่าอินพุต: ${e.message}`; return; }
  const st = steps();
  if (!st.length) { $('pw-validation').textContent = 'สถานการณ์ต้องมีอย่างน้อย 1 ช่วงที่เวลามากกว่า 0'; return; }
  try { sim = simulateDischarge(st, opts); } catch (e) { $('pw-validation').textContent = e.message; return; }
  const cyc = sim.cycle, total = cyc.sec;
  $('pw-timeline').innerHTML = st.map(([m, s]) => `<span style="flex:${s};background:${MODES[m].color}" title="${MODES[m].name} ${s} s">${s / total > 0.08 ? `${MODES[m].name} ${s}s` : ''}</span>`).join('') + '<i id="pw-tl-cursor"></i>';
  $('pw-ecyc').textContent = f(cyc.wh, 3);
  $('pw-cycles').textContent = f(sim.cyclesPerCharge, 1);
  $('pw-runtime').textContent = f(sim.runtimeSec / 60, 1);
  $('pw-low').textContent = sim.lowAt != null ? f(sim.lowAt / 60, 1) : '—';
  if (!flowParts || flowParts.loadsCount !== opts.loads.length) { buildFlow(opts); flowParts.loadsCount = opts.loads.length; }
  if (eRem > sim.usableWh || eRem === 0 && tSim === 0) restart();
  drawChart(); updateNow();
  renderBreakdown(st); renderPeak(); renderMatrix(); renderSteps(st); renderConclusions(st);
}

function renderBreakdown(st) {
  const share = {}; let loss = 0, total = 0;
  for (const [m, s] of st) {
    const mp = modePower(m, opts);
    for (const r of Object.values(mp.perRail)) {
      for (const it of r.items) share[it.load.name] = (share[it.load.name] || 0) + it.amps * r.rail.v * s / 3600;
      loss += (r.pIn - r.watts) * s / 3600;
    }
    total += mp.pIn * s / 3600;
  }
  const rows = [...Object.entries(share), ['สูญเสียใน buck', loss]].sort((a, b) => b[1] - a[1]);
  const mx = Math.max(...rows.map(r => r[1]), 1e-9);
  $('pw-breakdown').innerHTML = rows.map(([n, v]) => `<div class="row"><span>${n}</span><span class="bar"><i style="width:${(v / mx * 100).toFixed(1)}%"></i></span><b>${f(v / total * 100, 0)} %</b></div>`).join('');
}
function renderPeak() {
  const pk = peakCheck(opts);
  const row = (n, a, rate, extra = '') => { const r = a / rate; return `<div class="pw-pk ${r > 1 ? 'over' : r > 0.8 ? 'warn' : 'ok'}"><span>${n}</span><b>${f(a, 2)} / ${rate} A</b><em>${f(r * 100, 0)} %</em>${extra}</div>`; };
  $('pw-peak').innerHTML = pk.rails.map(r => row(r.rail.name, r.amps, r.rail.ratingA)).join('') + row(`แบต @ ${opts.battery.vCutoff} V เทียบฟิวส์`, pk.packA, opts.battery.fuseA) +
    `<p class="geometry-note">สมมติโหลดทุกตัวบนรางอยู่ที่ "พีค" พร้อมกัน (stall/inrush) = กรณีแย่สุด · ใช้เลือก buck/ฟิวส์/สาย ไม่ใช่คิดพลังงาน</p>`;
}
function renderMatrix() {
  const modes = Object.keys(MODES);
  $('pw-matrix').innerHTML = `<table class="pw-matrix"><thead><tr><th>โหลด</th>${modes.map(m => `<th><i style="background:${MODES[m].color}"></i>${MODES[m].name}</th>`).join('')}</tr></thead><tbody>` +
    opts.loads.map(l => `<tr><td>${l.name}</td>${modes.map(m => { const lv = MODES[m].loads[l.id]; const a = lv ? (l.levels[lv] ?? l.levels.run) : 0; return `<td class="${a ? '' : 'off'}">${a ? f(a, a < 0.1 ? 3 : 2) : '–'}</td>`; }).join('')}</tr>`).join('') +
    `<tr class="sum"><td>ดึงจากแบต (W)</td>${modes.map(m => `<td>${f(modePower(m, opts).pIn, 1)}</td>`).join('')}</tr></tbody></table>`;
}
function renderSteps(st) {
  const b = opts.battery, usable = b.capacityWh * b.usableFactor, mc = modePower('collect', opts);
  const railLine = r => { const pr = mc.perRail[r.id]; const terms = pr.items.map(i => f(i.amps, i.amps < 0.1 ? 3 : 2)).join(' + ') || '0'; return String.raw`P_\text{${r.name.replace(/[()]/g, '')}} &= ${r.v}\times(${terms}) = ${f(pr.watts, 2)}\ \text{W}`; };
  const pinTerms = opts.rails.map(r => `\\frac{${f(mc.perRail[r.id].watts, 2)}}{${r.eff}}`).join(' + ');
  const eTerms = st.map(([m, s]) => `${f(modePower(m, opts).pIn, 2)}\\times${s}`).join(' + ');
  const pk = peakCheck(opts);
  const list = [
    ['กำลังต่อราง (ตัวอย่างโหมดเก็บขยะ)', 'ประมาณการโหลด', [{ tex: String.raw`P_\text{rail} = V_\text{rail}\sum_j I_j` }, { tex: String.raw`\begin{aligned}${opts.rails.map(railLine).join('\\\\')}\end{aligned}` }]],
    ['กำลังที่ดึงจากแบต (หักประสิทธิภาพ buck)', 'ประมาณการ η', [{ tex: String.raw`P_\text{batt} = \sum_k \frac{P_k}{\eta_k} = ${pinTerms} = ${f(mc.pIn, 2)}\ \text{W}` }, { tex: String.raw`\eta_\text{รวม} = \frac{${f(mc.pOut, 2)}}{${f(mc.pIn, 2)}} = ${f(mc.effTotal * 100, 1)}\,\%` }]],
    ['กระแสแบต', 'คำนวณ', [{ tex: String.raw`I_\text{pack} = \frac{P_\text{batt}}{V_\text{pack}} = \frac{${f(mc.pIn, 2)}}{14.8} = ${f(mc.pIn / 14.8, 2)}\ \text{A}\ (\text{nominal}) \qquad \frac{${f(mc.pIn, 2)}}{${b.vCutoff}} = ${f(mc.pIn / b.vCutoff, 2)}\ \text{A}\ (\text{จุดตัด})` }]],
    [`พลังงานต่อรอบ "${(scenId === 'custom' ? custom : SCENARIOS[scenId]).name}"`, 'คำนวณ', [{ tex: String.raw`E_\text{cycle} = \sum_m \frac{P_{\text{batt},m}\,t_m}{3600} = \frac{${eTerms}}{3600} = ${f(sim.cycle.wh, 3)}\ \text{Wh}` }]],
    ['พลังงานที่ใช้ได้และรอบต่อชาร์จ', 'ประมาณการ f', [{ tex: String.raw`E_\text{usable} = C\cdot f = ${b.capacityWh}\times${b.usableFactor} = ${f(usable, 2)}\ \text{Wh}` }, { tex: String.raw`N = \frac{E_\text{usable}}{E_\text{cycle}} = \frac{${f(usable, 2)}}{${f(sim.cycle.wh, 3)}} = ${f(sim.cyclesPerCharge, 2)}\ ${T('รอบ')}, \qquad t_\text{run} = ${f(sim.runtimeSec / 60, 1)}\ \text{min}` }]],
    ['พีคพร้อมกัน → พิกัด buck และฟิวส์', 'คำนวณ', [{ tex: String.raw`I_\text{rail,peak} = \sum_j I_{j,\text{peak}}, \qquad I_\text{pack,peak} = \frac{\sum_k I_{k,\text{peak}}V_k/\eta_k}{V_\text{cut}} = \frac{${f(pk.pIn, 1)}}{${b.vCutoff}} = ${f(pk.packA, 2)}\ \text{A}` }]],
  ];
  $('pw-steps').innerHTML = list.map(([h, tag, lines]) => `<li><span class="t">${h}</span><span class="tag">[${tag}]</span>${lines.map(l => `<div class="math">${tex(l.tex)}</div>`).join('')}</li>`).join('');
}
function renderConclusions(st) {
  const b = opts.battery, pk = peakCheck(opts), r = id => pk.rails.find(x => x.rail.id === id);
  const out = [];
  out.push(['ok', `สถานการณ์นี้กิน ${f(sim.cycle.wh, 2)} Wh/รอบ (เฉลี่ย ${f(sim.cycle.avgW, 1)} W) → ${f(sim.cyclesPerCharge, 1)} รอบต่อชาร์จ · วิ่งต่อเนื่อง ${f(sim.runtimeSec / 60, 1)} นาที [คำนวณ]`]);
  const a = r('r5a'); out.push([a.ratio > 1 ? 'bad' : a.ratio > 0.8 ? 'warn' : 'ok', `Buck 5 V (1) พีค ${f(a.amps, 2)} A = ${f(a.ratio * 100, 0)} % ของพิกัด — Pi 5 ที่ 25 W ตัวเดียวก็ 5 A แล้ว · Pi 5 ต้องการ 5.1 V/5 A ถ้าเจรจา USB-PD ไม่ได้จะจำกัด USB รวม 600 mA ซึ่งกล้อง BRIO ใช้ไฟจากตรงนั้น (system_architecture §4) [คำนวณ]`]);
  const s6 = r('r6'); out.push([s6.ratio > 1 ? 'bad' : 'warn', `Buck 6 V พีคพร้อมกัน ${f(s6.amps, 2)} A = ${f(s6.ratio * 100, 0)} % ของ ${s6.rail.ratingA} A · เซอร์โว stall 2 ตัวอย่างเดียวก็ ${f(2 * (opts.loads.find(l => l.id === 'servoY').levels.peak), 1)} A แล้ว → กติกา R1 (ห้ามแปรงออกตัวขณะเซอร์โวเดิน) ต้องคงไว้ · ใช้งานปกติ (แปรงวิ่ง + เซอร์โวขยับ) ≈ 1.9 A [คำนวณ]`]);
  const s12 = r('r12'); out.push([s12.ratio > 1 ? 'bad' : s12.ratio > 0.8 ? 'warn' : 'ok', `Buck 12 V พีค ${f(s12.amps, 2)} A = ${f(s12.ratio * 100, 0)} % ของ ${s12.rail.ratingA} A (มอเตอร์ขับที่ลิมิต DRV8871 + blower) [คำนวณ]`]);
  out.push([pk.fuseRatio > 1 ? 'bad' : pk.fuseRatio > 0.8 ? 'warn' : 'ok', `กระแสแบตพีคพร้อมกัน ${f(pk.packA, 2)} A ที่ ${b.vCutoff} V = ${f(pk.fuseRatio * 100, 0)} % ของฟิวส์ ${b.fuseA} A · พีคแบบนี้สั้น < 1 s ฟิวส์มีความเฉื่อยความร้อน [คำนวณ]`]);
  out.push(['ok', 'แปรงอยู่ราง 6 V (ผู้ใช้ยืนยัน · C56) → 200 rpm ไร้โหลด · เฟิร์มแวร์ BRUSH_RAIL_V แก้เป็น 6.0 แล้ว (เพดาน duty 100 % เท่าเดิม · ยังไม่แฟลช)']);
  $('pw-conclusions').innerHTML = out.map(([c, s]) => `<li class="${c}">${s}</li>`).join('');
}

// ---------- เริ่ม ----------
buildInputs(); buildScenarios();
$('pw-rails').addEventListener('input', recompute); $('pw-loads').addEventListener('input', recompute);
for (const e of Object.values(batIn)) e.addEventListener('input', recompute);
$('pw-reset').addEventListener('click', () => { for (const [k, e] of Object.entries(batIn)) e.value = BATTERY_DEFAULTS[k]; buildInputs(); scenId = 'race'; buildScenarios(); restart(); recompute(); });
window.addEventListener('mrc-tab', e => { if (e.detail === 'power') recompute(); });
window.addEventListener('load', () => { if (opts) recompute(); });
recompute(); restart();
requestAnimationFrame(tick);
