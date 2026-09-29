// node --test aria/web/test/*.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import * as L from '../js/logic.js';

const settingsEnd = { default_cutoff_day: null };
const meter = (id, room, type, extra = {}) => ({ meter_id: id, room_id: room, type, digits: 5, decimals: 0, installed_at: '2026-01-01', retired_at: null, start_value: 100, end_value: null, ...extra });
let seq = 0;
const reading = (meterId, at, value, extra = {}) => ({ id: ++seq, local_id: String(seq).padStart(12, '0'), meter_id: meterId, assigned_meter_id: null, captured_at: at, value, confidence: 0.95, status: 'ocr', confirmed_value: null, clock_synced: true, ...extra });
const confirmed = (meterId, at, v) => reading(meterId, at, v, { status: 'confirmed', confirmed_value: v });

test('bkkDate ใช้เวลาไทย: 23:30 UTC = วันถัดไป', () => {
  assert.equal(L.bkkDate('2026-09-30T16:59:59Z'), '2026-09-30');
  assert.equal(L.bkkDate('2026-09-30T17:00:00Z'), '2026-10-01');
});

test('วันตัดรอบค่าเริ่ม = สิ้นเดือน · ก.พ. ปีไม่อธิกสุรทิน', () => {
  assert.equal(L.cutoffFor('2026-02', [], settingsEnd), '2026-02-28');
  assert.deepEqual(L.cycleRange('2026-03', [], settingsEnd), { from: '2026-02-28', to: '2026-03-31' });
});

test('วันตัดรอบ 25 · แถว billing_cycles ชนะค่าตั้ง', () => {
  const s = { default_cutoff_day: 25 };
  assert.deepEqual(L.cycleRange('2026-09', [], s), { from: '2026-08-25', to: '2026-09-25' });
  assert.equal(L.cycleOfDate('2026-09-26', [], s), '2026-10');
  assert.equal(L.cycleOfDate('2026-09-25', [], s), '2026-09');
  const cycles = [{ cycle: '2026-09', cutoff_date: '2026-09-28', include_rent: false }];
  assert.equal(L.cycleOfDate('2026-09-27', cycles, s), '2026-09');
  assert.equal(L.cycleOfDate('2026-01-01', [], settingsEnd), '2026-01');
  assert.equal(L.shiftCycle('2026-01', -1), '2025-12');
  assert.equal(L.shiftCycle('2026-12', 1), '2027-01');
});

test('meter_id จากหุ่นที่ไม่อยู่ในทะเบียน = ยังไม่ผูก · assigned ชนะ', () => {
  const idx = L.meterIndex([meter('W-101-01', '101', 'water')]);
  assert.equal(L.readingMeterId({ meter_id: 'W-999-01' }, idx), null);
  assert.equal(L.readingMeterId({ meter_id: 'W-999-01', assigned_meter_id: 'W-101-01' }, idx), 'W-101-01');
});

test('คิว: ยังไม่ผูก → ต่ำกว่าค่าก่อน → อ่านไม่ออก → ไม่มั่นใจ → นาฬิกา → ปกติ', () => {
  const meters = [meter('W-101-01', '101', 'water'), meter('E-101-01', '101', 'electric')];
  const idx = L.meterIndex(meters);
  const rs = [
    reading('W-101-01', '2026-09-20T03:00:00Z', 150),                          // ปกติ
    reading('W-101-01', '2026-09-20T03:01:00Z', 150, { clock_synced: false }), // นาฬิกา
    reading('E-101-01', '2026-09-20T03:02:00Z', 150, { confidence: 0.4 }),     // ไม่มั่นใจ
    reading('E-101-01', '2026-09-20T03:03:00Z', null),                         // อ่านไม่ออก
    reading('E-101-01', '2026-09-20T03:04:00Z', 50),                           // ต่ำกว่า start 100
    reading(null, '2026-09-20T03:05:00Z', 150),                                // ยังไม่ผูก
  ];
  const q = L.reviewQueue(rs, idx);
  assert.deepEqual(q.map(x => x.flags[0] ?? 'ok'), ['unassigned', 'below_prev', 'unreadable', 'low_conf', 'clock', 'ok']);
  assert.equal(q[1].prev.source, 'start');
});

test('ค่าก่อนหน้า = ค่ายืนยันล่าสุดก่อนเวลาถ่าย ไม่ใช่ค่าล่าสุดทั้งหมด', () => {
  const idx = L.meterIndex([meter('W-101-01', '101', 'water')]);
  const a = confirmed('W-101-01', '2026-08-20T03:00:00Z', 120);
  const later = confirmed('W-101-01', '2026-10-20T03:00:00Z', 200);
  const r = reading('W-101-01', '2026-09-20T03:00:00Z', 130);
  const p = L.previousConfirmed(r, 'W-101-01', [a, later, r], idx);
  assert.deepEqual([p.value, p.source], [120, 'reading']);
});

const baseData = () => {
  const meters = [meter('W-101-01', '101', 'water', { start_value: 1000 }), meter('E-101-01', '101', 'electric', { start_value: 3000 })];
  return {
    meters, settings: settingsEnd, cycles: [],
    rates: [{ type: 'water', baht_per_unit: 18, effective_from: '2026-01-01' }, { type: 'electric', baht_per_unit: 8, effective_from: '2026-01-01' },
            { type: 'electric', baht_per_unit: 9, effective_from: '2026-10-01' }],
    tenancies: [{ id: 1, room_id: '101', tenant_name: 'ก', email: 'a@example.com', start_date: '2026-01-01', end_date: null, rent_baht: 3500 }],
    readings: [confirmed('W-101-01', '2026-09-20T03:00:00Z', 1013), confirmed('E-101-01', '2026-09-20T03:00:00Z', 3109.5)],
  };
};

test('บิล: ค่าฐาน = start_value เมื่อไม่มีค่ายืนยันก่อนรอบ · อัตรา ณ วันตัดรอบ', () => {
  const d = baseData(); const idx = L.meterIndex(d.meters);
  const b = L.billPreview({ room_id: '101' }, '2026-09', d, idx);
  assert.equal(b.state, 'ready');
  assert.equal(b.lines.water.units, 13);
  assert.equal(b.lines.water.amount, 234);        // 13 × 18
  assert.equal(b.lines.electric.units, 109.5);
  assert.equal(b.lines.electric.amount, 876);     // 109.5 × 8 (อัตรา 9 เริ่ม 1 ต.ค. ยังไม่มีผล)
  assert.equal(b.total, 1110);                    // ไม่รวมค่าเช่า (F7 ค่าเริ่มปิด)
  assert.equal(b.lines.water.segments[0].baseSource, 'start');
});

test('บิล: เปิดรวมค่าเช่า · รอบถัดไปใช้ค่ายืนยันรอบก่อนเป็นฐาน', () => {
  const d = baseData(); const idx = L.meterIndex(d.meters);
  d.cycles = [{ cycle: '2026-10', cutoff_date: '2026-10-31', include_rent: true }];
  d.readings.push(confirmed('W-101-01', '2026-10-20T03:00:00Z', 1020), confirmed('E-101-01', '2026-10-20T03:00:00Z', 3200));
  const b = L.billPreview({ room_id: '101' }, '2026-10', d, idx);
  assert.equal(b.lines.water.units, 7);
  assert.equal(b.lines.electric.units, 90.5);
  assert.equal(b.lines.electric.rate, 9);
  assert.equal(b.total, 7 * 18 + 90.5 * 9 + 3500);
});

test('บิล: ยังไม่ยืนยัน/ไม่มีอัตรา = blocked · ไม่มีผู้เช่า = vacant', () => {
  const d = baseData(); const idx = L.meterIndex(d.meters);
  d.readings = d.readings.slice(0, 1); d.rates = d.rates.filter(r => r.type === 'water');
  const b = L.billPreview({ room_id: '101' }, '2026-09', d, idx);
  assert.equal(b.state, 'blocked');
  assert.equal(b.total, null);
  assert.ok(b.reasons.some(r => r.includes('ยังไม่ยืนยันค่าไฟ')));
  assert.ok(b.reasons.some(r => r.includes('ยังไม่ตั้งอัตราไฟ')));
  d.tenancies = [];
  assert.equal(L.billPreview({ room_id: '101' }, '2026-09', d, idx).state, 'vacant');
});

test('บิล: เปลี่ยนมิเตอร์กลางรอบ = รวมสองช่วง', () => {
  const d = baseData();
  d.meters[0] = meter('W-101-01', '101', 'water', { start_value: 1000, retired_at: '2026-09-15', end_value: 1008 });
  d.meters.push(meter('W-101-02', '101', 'water', { installed_at: '2026-09-15', start_value: 0 }));
  d.readings[0] = confirmed('W-101-02', '2026-09-20T03:00:00Z', 6);
  const idx = L.meterIndex(d.meters);
  const b = L.billPreview({ room_id: '101' }, '2026-09', d, idx);
  assert.equal(b.lines.water.units, 14);          // (1008 − 1000) + (6 − 0)
  assert.equal(b.lines.water.segments.length, 2);
});

test('ห้องอ่านครบ: ทุกมิเตอร์ที่ติดตั้งมีค่าไม่ถูกปฏิเสธในรอบ', () => {
  const d = baseData(); const idx = L.meterIndex(d.meters);
  const range = L.cycleRange('2026-09', [], settingsEnd);
  d.readings[1] = reading('E-101-01', '2026-09-20T03:00:00Z', 3100, { status: 'rejected' });
  const s = L.roomCaptureState({ room_id: '101' }, range, d, idx, L.readingsInCycle(d.readings, range));
  assert.equal(s.captured, false);
});

test('meters.json: เฉพาะมิเตอร์ที่ติดตั้งอยู่ · ไม่มีข้อมูลผู้เช่า · รหัสถัดไป', () => {
  const ms = [meter('W-2-01', '2', 'water', { retired_at: '2026-05-01' }), meter('W-2-02', '2', 'water', { installed_at: '2026-05-01' }), meter('E-10-01', '10', 'electric')];
  const j = L.registryJson(ms, 3, 'x', '2026-09-29');
  assert.deepEqual(j.meters.map(m => m.meter_id), ['W-2-02', 'E-10-01']);
  assert.deepEqual(Object.keys(j.meters[0]).sort(), ['decimals', 'digits', 'lift_mm', 'meter_id', 'room', 'type', 'waypoint']);
  assert.equal(L.nextMeterId(ms, '2', 'water'), 'W-2-03');
  assert.equal(L.nextMeterId(ms, '3', 'electric'), 'E-3-01');
});
