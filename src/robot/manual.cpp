// manual.cpp — ดู manual.h · ตรรกะการผสม/slew/deadman อยู่ใน manual_core.h (host test: test/host_manual.cpp)
//
// guard ที่บังคับที่นี่ (ที่มา: system_architecture §6.3 · ไฟล์ 18):
//   G2  เสาไม่พับ (เซอร์โวยังจับสัญญาณ) → $V ถูกปฏิเสธ MAST_UP  · ถ้าเสายกขึ้นระหว่างขับ → หยุดล้อทันที
//   G8  deadman 300 ms (ใน core)
//   G14 เพดาน 150 mm/s (ใน core)
//   R2  เปิดดูดแล้วต้องเว้น 1000 ms ก่อนล้อออกตัว → $V ≠ 0 ในช่วงนั้นถูกปฏิเสธ SUCTION_SPINUP
//   R1  แปรง ↔ เซอร์โว: $C ที่เปิดแปรงขณะเซอร์โวจับสัญญาณ → ปฏิเสธ MAST_UP
//   mission กำลังเดิน → $V/$C ถูกปฏิเสธ IN_MISSION (ห้ามสองสมองสั่งล้อพร้อมกัน)
#include "manual.h"

void motorSetLR(int l, int r); void motorStop(const char*);
bool servoAttachedNow();
bool missionRunning();
void blowerCommand(const String&); bool blowerOnNow(); bool brushOnNow();

namespace {
mrc::Manual core;
uint32_t suctionOnMs = 0;                 // เวลาเปิดดูดล่าสุด (R2)
constexpr uint32_t R2_SPINUP_MS = 1000;   // ไฟล์ 18 §18.3
constexpr int      BRUSH_MAX_PCT = 40;    // G7
bool wasActive = false;
}

void manualSetup() { core.configure(mrc::ManualCfg{}); }

const char* manualSetpoint(int v, int w) {
  if (missionRunning())     return "IN_MISSION";
  if (servoAttachedNow())   return "MAST_UP";
  if ((v != 0 || w != 0) && blowerOnNow() && millis() - suctionOnMs < R2_SPINUP_MS) return "SUCTION_SPINUP";
  const bool ok = core.setpoint(v, w, millis());
  if (!ok) Serial.printf("[man] setpoint ถูก clamp: ขอ v=%d w=%d → ใช้ v=%d w=%d (G14)\n", v, w, core.v(), core.w());
  return nullptr;
}

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
  if (brushPct > BRUSH_MAX_PCT) brushPct = BRUSH_MAX_PCT;             // G7
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
  // G2 ระหว่างขับ: ถ้าเสาถูกยก (ใครสั่งก็ตาม) ให้หยุดล้อทันที
  if (core.active() && servoAttachedNow()) manualHalt("เสาไม่ได้พับ (G2)");
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
