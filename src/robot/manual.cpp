// manual.cpp — ดู manual.h · ตรรกะการผสม/slew/deadman อยู่ใน manual_core.h (host test: test/host_manual.cpp)
//
// หลักโหมดแมนวล (C28 · 16 ก.ย. 2026): "คนขับตัดสินใจเอง" — ESP32 ไม่ปฏิเสธคำสั่งขับด้วยเหตุผลที่คนมองเห็นได้เอง
// สิ่งที่ยังบังคับที่นี่ (เหลือเฉพาะที่คนขับมองไม่เห็น = ไฟฟ้า/ลิงก์):
//   G8  deadman 300 ms (ใน core) — ลิงก์ขาด ไม่ใช่การห้ามคน
//   R2  เปิดดูดแล้วต้องเว้น 1000 ms ก่อนล้อออกตัว (ราง 12 V margin 7.5 % · ไฟล์ 18 §18.2)
//       → ไม่ปฏิเสธแล้ว: รับ $V ไว้ แต่ล้อ = 0 จนพ้นช่วง แล้วออกตัวเองจาก $V ถัดไป · บอก HUD ด้วย flag SPINUP_HOLD
//   R2' ห้ามเปิดดูดขณะล้อหมุน (NOT_STOPPED) — เหตุผลเดียวกัน (inrush ยังไม่วัด)
//   R1  แปรง ↔ เซอร์โว: $C ที่เปิดแปรงขณะเซอร์โวจับสัญญาณ → ปฏิเสธ MAST_UP (ราง 5 V เกิน 33 % · C12)
//       ⚠ กว้างเกินไป — ควรห้ามเฉพาะตอนเซอร์โว*กำลังขยับ* แต่ต้องวัดกระแสค้างสุด (M6) ก่อนแคบลง
//   G7  แปรง: เพดานอยู่ที่ blower_test/config.h (BRUSH_DUTY_MAX_PCT — บนราง 5 V = 100 %) ไม่ clamp ซ้ำที่นี่ (C30: เลข 40 % เดิมมาจากยุคราง 12 V)
//   mission กำลังเดิน → $V/$C ถูกปฏิเสธ IN_MISSION (สองสมองสั่งล้อพร้อมกันไม่ได้ — ไม่เกิดในแมนวล)
// ที่ยกออก (C28): G2 MAST_UP ใน $V และการหยุดล้อเมื่อเสายก (ไฟล์ 08: ห่างขีดพลิก 24 เท่า) ·
//   G14 เปลี่ยนจาก "ห้ามเกิน 150" เป็น "เพดานที่ผู้ใช้ตั้งเอง ($L)" clamp ที่ฮาร์ดแวร์ 716 mm/s เท่านั้น
#include "manual.h"
#include "servo_x.h"

void motorSetLR(int l, int r); void motorStop(const char*);
bool servoAttachedNow();
bool missionRunning();
void blowerCommand(const String&); bool blowerOnNow(); bool brushOnNow();

namespace {
mrc::Manual core;
uint32_t suctionOnMs = 0;                 // เวลาเปิดดูดล่าสุด (R2)
constexpr uint32_t R2_SPINUP_MS = 1000;   // ไฟล์ 18 §18.3
bool wasActive = false;
bool spinupHold = false;                  // R2 กำลังหน่วงล้ออยู่ (โชว์ใน #T)

bool inSpinup() { return blowerOnNow() && millis() - suctionOnMs < R2_SPINUP_MS; }
}

void manualSetup() { core.configure(mrc::ManualCfg{}); }

const char* manualSetpoint(int v, int w) {
  if (missionRunning())     return "IN_MISSION";
  // R2: อยู่ในช่วงไต่รอบ blower → รับคำสั่ง (ต่อลมหายใจ deadman) แต่ล้อ 0 · Pi ส่ง $V ซ้ำทุก 100 ms อยู่แล้ว
  // พอพ้น 1000 ms คำสั่งถัดไปจะออกตัวเอง คนขับแค่กดจอยค้างไว้
  const bool hold = (v != 0 || w != 0) && inSpinup();
  if (hold != spinupHold) Serial.printf("[man] R2 spin-up hold %s\n", hold ? "เริ่ม (ล้อรอ 1 s)" : "จบ → ออกตัว");
  spinupHold = hold;
  const bool ok = core.setpoint(hold ? 0 : v, hold ? 0 : w, millis());
  if (!ok) Serial.printf("[man] setpoint ถูก clamp: ขอ v=%d w=%d → ใช้ v=%d w=%d (เพดาน %d/%d)\n",
                         v, w, core.v(), core.w(), core.vMax(), core.wMax());
  return nullptr;
}

bool manualSetLimits(int vMax, int wMax) {
  const bool exact = core.setLimits(vMax, wMax);
  Serial.printf("[man] $L เพดาน v=%d mm/s ω=%d mrad/s → duty สูงสุด %d ‰%s\n",
                core.vMax(), core.wMax(), core.permilleMax(), exact ? "" : " (ถูก clamp ที่เพดานฮาร์ดแวร์)");
  return exact;
}
int  manualVMax() { return core.vMax(); }
int  manualWMax() { return core.wMax(); }
bool manualSpinupHold() { return spinupHold; }

void manualStop(const char* why) {
  if (core.active()) Serial.printf("[man] stop: %s\n", why);
  core.stop();
}

void manualHalt(const char* why) {
  if (core.active() || core.out().l || core.out().r) Serial.printf("[man] halt: %s\n", why);
  core.halt();
  motorSetLR(0, 0);
}

const char* manualSetCleaning(int suctionPct, int brushPct) {
  if (missionRunning()) return "IN_MISSION";
  if (brushPct > 0 && servoAttachedNow()) return "MAST_UP";          // R1
  if (brushPct > 0 && !brushOnNow() && servoXMoving()) return "SERVO_MOVING";   // R1 กับเซอร์โว X (C30) — เฉพาะตอนเริ่มแปรงขณะ X เดินอยู่
  if (brushPct > 100) brushPct = 100;                                 // เพดานจริงอยู่ใน brushSet() ตาม BRUSH_DUTY_MAX_PCT
  const bool suctionOn = suctionPct > 0;
  if (suctionOn && !blowerOnNow()) {
    if (core.out().l || core.out().r) return "NOT_STOPPED";           // R2: ห้ามเปิดดูดขณะล้อหมุน
    suctionOnMs = millis();
    blowerCommand("on");
  } else if (!suctionOn && blowerOnNow()) {
    blowerCommand("off");                                             // off ปิดแปรงด้วย (stopAll ของ M3)
    if (brushPct > 0) blowerCommand(String("b ") + brushPct);
    return nullptr;
  }
  blowerCommand(brushPct > 0 ? String("b ") + brushPct : String("bs"));
  return nullptr;
}

void manualTick() {
  if (spinupHold && !inSpinup() && !core.active()) spinupHold = false;   // deadman ตัดระหว่างรอ → เคลียร์ flag
  const mrc::WheelCmd w = core.tick(millis());
  if (core.tripped()) { core.ackTrip(); Serial.println("[man] deadman: ไม่ได้ $V ใน 300 ms → หยุด (G8)"); }
  const bool nowActive = core.active() || w.l || w.r;
  if (nowActive || wasActive) motorSetLR(w.l, w.r);   // เขียนต่อจนถึง 0 แล้วหยุดเขียน (ไม่แย่งกับคำสั่ง m ในคอนโซล)
  if (wasActive && !nowActive) motorStop("manual จบ");
  wasActive = nowActive;
}

bool manualActive()  { return core.active(); }
bool manualTripped() { return core.tripped(); }
mrc::WheelCmd manualOut() { return core.out(); }
int manualV() { return core.v(); }
int manualW() { return core.w(); }
