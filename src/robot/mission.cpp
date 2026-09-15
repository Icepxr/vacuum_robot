// mission.cpp — ดู mission.h · ตรรกะลำดับอยู่ใน mission_core.h (ทดสอบบน host แล้ว: test/host_mission.cpp)
//
// ตำแหน่งเสา (us) **ยังไม่ได้ตั้ง** — ขึ้นกับเรขาคณิตกลไกยกจริง (C8 · ไฟล์ 12) ต้องวัดตอนประกอบ
// จนกว่าจะตั้งด้วย `mis set up <us>` และ `mis set down <us>` คำสั่ง `mis start` จะปฏิเสธ
#include "mission.h"
#include "mission_core.h"
#include "comm.h"

// จุดต่อของโมดูลเดิม (นิยามใน src/<ชุด>/main.cpp)
void motorCommand(const String&); void motorStop(const char*);
void blowerCommand(const String&); void blowerStop(const char*);
bool servoMissionMove(int us, int fromUsIfUnknown); void servoStop(const char*); int servoCurrentUs();

namespace {

mrc::Mission    mission;
mrc::MissionCfg cfg;                  // ค่าตั้งต้นใน mission_core.h · ปรับได้ด้วย `mis set`
int  mastUpUs   = -1;                 // [ยังไม่ตัดสินใจ] — ตั้งด้วย mis set up
int  mastDownUs = -1;                 // [ยังไม่ตัดสินใจ] — ตั้งด้วย mis set down
int  brushPct   = 24;                 // 60 % ของเพดาน 40 % (BRUSH_DUTY_MAX_PCT · G7) เท่าคำสั่ง `both` ของ M3
mrc::MState lastState = mrc::MState::IDLE;

void ioSuction(bool on) { blowerCommand(on ? "on" : "off"); }
void ioBrush(bool on)   { blowerCommand(on ? String("b ") + brushPct : String("bs")); }
void ioDrive(int pm)    { motorCommand(String("d ") + pm); }     // rampTo 300 ms อยู่ในโมดูลล้อ
void ioStop()           { motorStop("mission: หยุดล้อ"); }
bool ioMastUp()         { return servoMissionMove(mastUpUs, mastDownUs); }
bool ioMastDown()       { return servoMissionMove(mastDownUs, mastUpUs); }
void ioMastRelease()    { servoStop("mission: พับสุดแล้ว ปล่อย PWM"); }
bool ioRequestCapture() { return commRequestCapture(); }
mrc::CapState ioCaptureState() { return (mrc::CapState)(uint8_t)commCaptureState(); }   // enum ตรงกันตามลำดับ
void ioLog(const char* m) { Serial.printf("[mis] %s\n", m); }
uint32_t ioNow()        { return millis(); }

const mrc::MissionIO io = { ioSuction, ioBrush, ioDrive, ioStop, ioMastUp, ioMastDown, ioMastRelease,
                            ioRequestCapture, ioCaptureState, ioLog, ioNow };

void printStatus() {
  Serial.printf("[mis] state=%s จุดที่ %u/%u · ถ่ายได้ %u · ล้ม %u · เสา up=%d down=%d us (ตอนนี้ %d) · "
                "drive %d‰ %lu ms · settle %lu ms · แปรง %d %%\n",
                mrc::mstateName(mission.state()), mission.stopIndex(), cfg.stops, mission.captured(), mission.failed(),
                mastUpUs, mastDownUs, servoCurrentUs(), cfg.drive_permille, (unsigned long)cfg.drive_ms,
                (unsigned long)cfg.settle_ms, brushPct);
}

}  // namespace

static_assert((int)mrc::CapState::TIMEOUT == (int)CaptureState::TIMEOUT, "enum CapState ต้องตรงกับ CaptureState");

void missionSetup() { mission.bind(io); }

void missionTick() {
  mission.tick(millis());
  if (mission.state() != lastState) {
    lastState = mission.state();
    Serial.printf("[mis] → %s (จุด %u)\n", mrc::mstateName(lastState), mission.stopIndex());
  }
}

void missionAbort(const char* why) { mission.abort(why, millis()); }
bool missionRunning()               { return mission.running(); }

void missionHelp() {
  Serial.println("  mis start [n]      เดินภารกิจ n จุด (ค่าตั้งต้น 3) — ต้องตั้ง up/down ก่อน · ล้อควรลอยรอบแรก");
  Serial.println("  mis abort          หยุดล้อ/ดูด/แปรง · เสาคงที่ (ไม่ปล่อย PWM กลางทาง)");
  Serial.println("  mis st             สถานะ");
  Serial.println("  mis set up <us>    ตำแหน่งเสายก   · mis set down <us>  ตำแหน่งพับ  (500–2500)");
  Serial.println("  mis set drive <‰>  duty ล้อ · mis set ms <ms> เวลาวิ่งต่อจุด · mis set settle <ms> · mis set brush <%>");
  Serial.println("  ⚠ ห้ามพิมพ์อะไรระหว่างเสากำลังยก/พับ — โมดูลเซอร์โวถือว่าเป็นการสั่งหยุด (แล้วภารกิจจะ abort)");
}

void missionCommand(const String& sub) {
  if (sub == "st") { printStatus(); return; }
  if (sub == "abort") { missionAbort("ผู้ใช้สั่ง mis abort"); return; }
  if (sub == "start" || sub.startsWith("start ")) {
    if (mastUpUs < 0 || mastDownUs < 0) {
      Serial.println("[mis] ปฏิเสธ: ยังไม่ตั้งตำแหน่งเสา — mis set up <us> · mis set down <us> (วัดจากกลไกจริงก่อน)");
      return;
    }
    if (sub.length() > 6) cfg.stops = (uint8_t)constrain(sub.substring(6).toInt(), 1, 20);
    if (!mission.start(cfg, millis())) { Serial.println("[mis] เริ่มไม่ได้ (กำลังเดินอยู่ หรือ config ผิด)"); return; }
    Serial.printf("[mis] เริ่ม %u จุด · ดูด→รอ %lu ms→ล้อ %d‰ %lu ms→หยุด→ยก %d us→นิ่ง %lu ms→ถ่าย→พับ %d us\n",
                  cfg.stops, (unsigned long)cfg.r2_gap_ms, cfg.drive_permille, (unsigned long)cfg.drive_ms,
                  mastUpUs, (unsigned long)cfg.settle_ms, mastDownUs);
    return;
  }
  if (sub.startsWith("set ")) {
    const String rest = sub.substring(4);
    const int sp = rest.indexOf(' ');
    if (sp < 0) { Serial.println("[mis] ใช้: mis set <key> <ค่า>"); return; }
    const String key = rest.substring(0, sp); const long v = rest.substring(sp + 1).toInt();
    if (mission.running()) { Serial.println("[mis] แก้ค่าระหว่างเดินไม่ได้ — mis abort ก่อน"); return; }
    if      (key == "up"     && v >= 500 && v <= 2500) mastUpUs = v;
    else if (key == "down"   && v >= 500 && v <= 2500) mastDownUs = v;
    else if (key == "drive"  && v >= 0 && v <= 600)    cfg.drive_permille = v;   // เพดาน 600‰ กันเผลอ (G14 ยังไม่มี PID)
    else if (key == "ms"     && v >= 500 && v <= 20000) cfg.drive_ms = v;        // MAX_RUN_MS ของโมดูลล้อ = 20 s
    else if (key == "settle" && v >= 0 && v <= 10000)  cfg.settle_ms = v;
    else if (key == "brush"  && v >= 0 && v <= 40)     brushPct = v;             // G7 เพดาน 40 %
    else { Serial.println("[mis] key/ค่าไม่ถูก — ดู ? mis"); return; }
    printStatus();
    return;
  }
  Serial.println("[mis] ไม่รู้จัก — ดู ? mis");
}
