import test from 'node:test';
import assert from 'node:assert/strict';
import { modePower, cycleEnergy, simulateDischarge, peakCheck, SCENARIOS, BATTERY_DEFAULTS, withOverrides } from '../js/power.mjs';
const close = (a, e, tol) => assert.ok(Math.abs(a - e) <= tol, `${a} != ${e} ±${tol}`);

test('โหมดเก็บขยะ: กำลังต่อรางตามค่าเริ่มต้น', () => {
  const m = modePower('collect');
  close(m.perRail.r12.watts, 40.8, 1e-9);           // (1.0 + 2.4) × 12 — ตรงกับไฟล์ 02 โหมด A ราง 12 V
  close(m.perRail.r5a.watts, 13.61, 1e-9);          // (2.4 + 0.3 + 0.022) × 5
  close(m.perRail.r6.watts, 4.2, 1e-9);             // (0.5 + 0.1 + 0.1) × 6
  close(m.pIn, 40.8 / 0.92 + (13.61 + 2.5 + 4.2) / 0.85, 1e-9);
});

test('รอบแข่ง 3 นาทีและจำนวนรอบต่อชาร์จ', () => {
  const c = cycleEnergy(SCENARIOS.race.steps);
  const sim = simulateDischarge(SCENARIOS.race.steps);
  close(sim.usableWh, 32.56 * 0.723, 1e-9);
  close(sim.cyclesPerCharge, sim.usableWh / c.wh, 1e-12);
  // รอบสุดท้ายที่ไม่ครบเริ่มด้วยช่วงกินไฟมาก → เวลาวิ่งอยู่ระหว่างรอบเต็มกับรอบถัดไป
  const full = Math.floor(sim.cyclesPerCharge);
  assert.ok(sim.runtimeSec >= full * c.sec && sim.runtimeSec <= (full + 1) * c.sec);
  close(c.wh, 2.80, 0.01);   // เทียบไฟล์ 02 §2.5 = 2.81 Wh
});

test('พีค: ราง 5 V (1) เกินพิกัด 5 A · แบตไม่ถึงฟิวส์', () => {
  const p = peakCheck();
  const r5a = p.rails.find(r => r.rail.id === 'r5a');
  close(r5a.amps, 5.522, 1e-9);
  assert.ok(r5a.ratio > 1);
  assert.ok(p.packA < BATTERY_DEFAULTS.fuseA);
  const ov = peakCheck(withOverrides({ loads: { pi: { peak: 4.0 } } }));
  assert.ok(ov.rails.find(r => r.rail.id === 'r5a').ratio < 1);
});
