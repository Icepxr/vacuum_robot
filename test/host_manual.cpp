// clang++ -std=c++17 -I src/robot test/host_manual.cpp -o /tmp/manual && /tmp/manual
#include <cstdio>
#include "manual_core.h"
using namespace mrc;
static int fails = 0;
#define CHECK(c) do { if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

int main() {
  Manual m; ManualCfg c; m.configure(c);
  uint32_t t = 0;
  // 1. เดินหน้า 150 mm/s → 210 ‰ · C51: ออกตัวขึ้นไป kick 250 ก่อน ค้าง 150 ms แล้วลงมาที่ 210 ตามคำสั่ง (เดิม C31 ค้าง 250 ตลอด)
  CHECK(m.setpoint(150, 0, t));
  WheelCmd w{};
  for (int i = 0; i < 20; ++i) { t += 10; if (i % 5 == 0) m.setpoint(150, 0, t); w = m.tick(t); }
  CHECK(w.l == 250 && w.r == 250);                                   // 200 ms: ยังอยู่ช่วง kick
  for (int i = 0; i < 40; ++i) { t += 10; if (i % 5 == 0) m.setpoint(150, 0, t); w = m.tick(t); }
  CHECK(w.l == 210 && w.r == 210);                                   // พ้น kick → ตามคำสั่งจริง
  // slew: tick แรกจาก 0 ต้องได้แค่ 15
  Manual m1; m1.configure(c); m1.setpoint(150, 0, 0); w = m1.tick(10); CHECK(w.l == 15 && w.r == 15);
  // 2. เพดานเริ่มต้น 150: ขอ 300 mm/s → คืน false และได้เท่า 150
  Manual m2; m2.configure(c); CHECK(!m2.setpoint(300, 0, 0)); CHECK(m2.v() == 150);
  // 2b. ผู้ใช้ยกเพดาน ($L) เป็น 300 → รับ 300 ได้ · permille_max = 300×1.4×1.25 = 525
  CHECK(m2.setLimits(300, 3000)); CHECK(m2.vMax() == 300 && m2.permilleMax() == 525);   // v 300 > v_turn 270 → 300×1.4×1.25
  CHECK(m2.setpoint(300, 0, 10)); CHECK(m2.v() == 300);
  for (int i = 2; i <= 40; ++i) { m2.setpoint(300, 0, i * 10); w = m2.tick(i * 10); }
  CHECK(w.l == 420 && w.r == 420);
  // 2c. ขอเกินฮาร์ดแวร์ 716 → clamp ที่ 716 คืน false · permille_max ไม่เกิน 1000
  CHECK(!m2.setLimits(2000, 99999)); CHECK(m2.vMax() == 716 && m2.wMax() == 7950 && m2.permilleMax() == 1000);
  // 2d. ลดเพดานขณะขับ → setpoint ปัจจุบันถูกกดลงทันที
  m2.setpoint(600, 0, 500); CHECK(m2.v() == 600);
  m2.setLimits(100, 3000); CHECK(m2.v() == 100 && m2.permilleMax() == 472);   // v_turn 270 ชนะ v 100
  // 3. หมุนอยู่กับที่: v=0 ω=+1500 → ซ้ายถอย ขวาเดิน สมมาตร
  Manual m3; m3.configure(c); m3.setpoint(0, 1500, 0);
  for (int i = 0; i < 40; ++i) { m3.setpoint(0, 1500, i * 10); w = m3.tick(i * 10); }
  CHECK(w.l < 0 && w.r > 0 && w.l == -w.r);
  // half = 1500*180/2000 = 135 mm/s → 189 ‰ · C51: หลัง kick ลงมาที่ 189 (≥ hold 100)
  CHECK(w.r == 189);
  // 3b. หมุนแรงกว่า: ω=3000 (ค่าเริ่มต้น) → half 270 mm/s → 378 ‰ · permille_max คิดจาก max(v_max 150, v_turn 270) = 270×1.4×1.25 = 472 → ไม่ถูกตัด
  Manual m3b; m3b.configure(c); CHECK(m3b.permilleMax() == 472);
  for (int i = 0; i < 60; ++i) { m3b.setpoint(0, 3000, i * 10); w = m3b.tick(i * 10); }
  CHECK(w.r == 378 && w.l == -378);
  // 3c. เดินช้า 50 mm/s → 70 ‰ · C51: ออกตัว 250 แล้วประคองที่ hold 100 (ไม่ใช่ 0 เพราะเกิน deadband 40)
  Manual m3c; m3c.configure(c); for (int i = 0; i < 60; ++i) { m3c.setpoint(50, 0, i * 10); w = m3c.tick(i * 10); }
  CHECK(w.l == 100 && w.r == 100);
  // 4. deadman: ไม่มี $V 300 ms → ล้อไล่ลง 0 และ tripped
  Manual m4; m4.configure(c); m4.setpoint(150, 0, 0);
  for (int i = 1; i <= 17; ++i) m4.tick(i * 10);
  CHECK(m4.out().l == 250);
  for (int i = 15; i <= 60; ++i) w = m4.tick(i * 10);           // 600 ms ไม่มีคำสั่ง
  CHECK(w.l == 0 && w.r == 0 && m4.tripped() && !m4.active());
  // หลัง trip ถ้า Pi กลับมา ต้องรับคำสั่งใหม่ได้
  CHECK(m4.setpoint(100, 0, 700)); CHECK(m4.active() && !m4.tripped());
  // 5. halt (E-STOP) ตัดเป็น 0 ทันทีไม่ slew
  Manual m5; m5.configure(c); m5.setpoint(150, 0, 0); for (int i = 1; i <= 14; ++i) m5.tick(i * 10);
  m5.halt(); CHECK(m5.out().l == 0 && m5.out().r == 0);
  // 6. deadband: ขอ 20 mm/s → 28 ‰ < 40 → 0
  Manual m6; m6.configure(c); m6.setpoint(20, 0, 0); for (int i = 1; i <= 5; ++i) w = m6.tick(i * 10);
  CHECK(w.l == 0 && w.r == 0);
  // 7. เพดาน permille_max ค่าเริ่มต้น = 472 (จาก ω 3000): v=150 + ω=1500 → ขวา 210+189=399 (ไม่ถูกตัด) · ซ้าย 21 ‰ < deadband → 0
  Manual m7; m7.configure(c); CHECK(m7.permilleMax() == 472);
  for (int i = 0; i < 60; ++i) { m7.setpoint(150, 1500, i * 10); w = m7.tick(i * 10); }
  CHECK(w.r == 399 && w.l == 0);
  // 8. C51 desaturate: เพดาน 716/7950 · v 716 ω −1988 → ตั้งใจ ซ้าย 1253 ขวา 751 ‰ → ลดตามสัดส่วนเป็น 1000/601 (เดิมตัดข้างเดียว 1000/749)
  Manual m8; m8.configure(c); m8.setLimits(716, 7950);
  for (int i = 0; i < 150; ++i) { m8.setpoint(716, -1988, i * 10); w = m8.tick(i * 10); }
  CHECK(w.l == 1000 && w.r == 601);                  // half = 178 mm/s (ปัดจำนวนเต็ม) → ตั้งใจ 1246/749 → ×1000/1246
  // 8b. ไม่ชนเพดาน → ไม่แตะ
  Manual m8b; m8b.configure(c); m8b.setLimits(716, 7950);
  for (int i = 0; i < 150; ++i) { m8b.setpoint(358, -596, i * 10); w = m8b.tick(i * 10); }
  CHECK(w.l == 575 && w.r == 427);
  // 9. C51 กลับทิศ = ออกตัวใหม่: จากเดินหน้า 70 ‰ (hold 100) → ถอยช้า −50 mm/s → ต้องผ่าน kick −250 ก่อนประคอง −100
  Manual m9; m9.configure(c); int minL = 0; uint32_t tt = 0;
  for (int i = 0; i < 60; ++i) { m9.setpoint(50, 0, tt); w = m9.tick(tt); tt += 10; }
  CHECK(w.l == 100);
  for (int i = 0; i < 80; ++i) { m9.setpoint(-50, 0, tt); w = m9.tick(tt); if (w.l < minL) minL = w.l; tt += 10; }
  CHECK(minL == -250 && w.l == -100);
  // 10. หยุดแล้วออกใหม่ → kick อีกรอบ
  for (int i = 0; i < 60; ++i) { m9.setpoint(0, 0, tt); w = m9.tick(tt); tt += 10; }
  CHECK(w.l == 0);
  int maxL = 0; for (int i = 0; i < 20; ++i) { m9.setpoint(50, 0, tt); w = m9.tick(tt); if (w.l > maxL) maxL = w.l; tt += 10; }
  CHECK(maxL == 250);
  printf(fails ? "%d FAILED\n" : "all ok\n", fails);
  return fails ? 1 : 0;
}
