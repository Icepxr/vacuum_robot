import test from 'node:test';
import assert from 'node:assert/strict';
import { AIR_DEFAULTS, solveOperatingPoint, terminalVelocity, fanDp } from '../js/airflow.mjs';

const close = (a, e, tol) => assert.ok(Math.abs(a - e) <= tol, `${a} != ${e} ±${tol}`);

// ค่าอ้างอิงจาก 08_การคำนวณ/scripts_22/airflow_1d_v2.py (ไฟล์ 22 §22.10)
test('R1 ตาม CAD ตรงกับสคริปต์ Python', () => {
  const r = solveOperatingPoint();
  close(r.q * 1e3, 13.23, 0.01);
  close(r.dpFan, 117, 1);
  close(r.v.channel, 10.6, 0.05);
  close(r.v.slot, 1.69, 0.01);
  close(r.v.hole, 2.6, 0.05);
});

test('R2 ซีลขอบ 3 mm และไส้กรอง', () => {
  close(solveOperatingPoint({ edgeFrontMm: 3, edgeRearMm: 3 }).q * 1e3, 11.72, 0.01);
  close(solveOperatingPoint({ filterPaAt10: 100 }).q * 1e3, 10.52, 0.01);
  close(solveOperatingPoint({ curve: 'quad' }).q * 1e3, 14.79, 0.01);
});

test('ΔP_max เทียบเคียงและความเร็วปลาย', () => {
  close(AIR_DEFAULTS.pMaxPa, 423.5, 0.1);
  close(fanDp(0, AIR_DEFAULTS), AIR_DEFAULTS.pMaxPa, 1e-9);
  close(terminalVelocity(5), 12.4, 0.05);
  close(terminalVelocity(3), 9.6, 0.05);
});

test('จุดทำงานสมดุล: ΔP blower = ผลรวมการสูญเสีย', () => {
  const r = solveOperatingPoint({ pMaxPa: 300, filterPaAt10: 50 });
  const t = r.terms;
  close(r.dpFan, t.inlet + t.chEntry + t.chFriction + t.dump + t.hole + t.filter, 0.01);
});

import { debrisProps, debrisFate } from '../js/airflow.mjs';

test('เศษ: v_t ตรงกับไฟล์ 22 §22.11', () => {
  close(debrisProps({ shape: 'sphere', sizeMm: 5, cd: 0.44 }).vt, 12.39, 0.01);
  close(debrisProps({ shape: 'cube', sizeMm: 5, cd: 0.8 }).vt, 11.26, 0.01);
  close(debrisProps({ shape: 'cube', sizeMm: 5, cd: 1.05 }).vt, 9.83, 0.01);
  close(debrisProps({ shape: 'sphere', sizeMm: 3, cd: 0.44 }).vt, terminalVelocity(3), 1e-9);
});

test('ลูกบาศก์ 5 mm ค่าเริ่มต้น: ค้างที่ทางเข้า (ตรงกับอาการจริง)', () => {
  const f = debrisFate(solveOperatingPoint(), {});
  assert.equal(f.entry, false);
  close(f.hThrowMm, 9.4, 0.1);   // แปรง 200 rpm บนราง 6 V (C56) — ยังต่ำกว่าขั้น 15 mm
  close(f.rpmNeeded, 252, 1);
  assert.equal(f.channel, true);   // ถ้าเข้าได้ ช่องตรงลากไถลไปได้
  const fast = debrisFate(solveOperatingPoint(), { brushRpm: 260 });
  assert.equal(fast.entryByBrush, true);
});
