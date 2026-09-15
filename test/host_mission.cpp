// ทดสอบ src/robot/mission_core.h บน host ด้วยเวลาจำลอง:
//   clang++ -std=c++17 -I src/robot test/host_mission.cpp -o /tmp/mission && /tmp/mission
// ตรวจ: ลำดับเรียกถูก · R2/R1/G1 เว้นเวลาจริง · ดูด/แปรงปิดก่อนยก · ถ่ายหลัง settle · timeout $K แล้วพับต่อ · G12 · abort
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include "mission_core.h"

using namespace mrc;
static int fails = 0;
#define CHECK(c) do { if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

// ── ตัวจำลองฮาร์ดแวร์: จด (เวลา, เหตุการณ์) ──
static uint32_t T = 0;
static std::vector<std::pair<uint32_t, std::string>> logv;
static bool suctionOn = false, brushOn = false; static int drivePm = 0;
static CapState cap = CapState::IDLE; static uint32_t capReqAt = 0; static int capMode = 0; // 0=ok หลัง 100ms · 1=ไม่ตอบ · 2=fail
static bool mastUpOk = true, mastDownOk = true;
static void ev(const std::string& s) { logv.push_back({T, s}); }

static MissionIO io = {
  [](bool on) { suctionOn = on; ev(on ? "suction on" : "suction off"); },
  [](bool on) { brushOn = on; ev(on ? "brush on" : "brush off"); },
  [](int pm) { drivePm = pm; ev("drive " + std::to_string(pm)); },
  []() { drivePm = 0; ev("stop"); },
  []() { ev("mastUp"); T += 4800; return mastUpOk; },        // slew blocking 4.8 s
  []() { ev("mastDown"); T += 4800; return mastDownOk; },
  []() { ev("mastRelease"); },
  []() { if (cap == CapState::WAITING) return false; cap = CapState::WAITING; capReqAt = T; ev("CAPTURE_REQ"); return true; },
  []() {
    if (cap == CapState::WAITING) {
      if (capMode == 0 && T - capReqAt >= 100) cap = CapState::OK;
      if (capMode == 2 && T - capReqAt >= 100) cap = CapState::FAIL;
      if (capMode == 1 && T - capReqAt >= 5000) cap = CapState::TIMEOUT;   // comm.cpp ตัดสินเองที่ 5 s
    }
    return cap;
  },
  [](const char* m) { ev(std::string("log: ") + m); },
  []() { return T; },
};

static uint32_t at(const char* name, int nth = 0) {   // เวลาที่เหตุการณ์ชื่อนี้เกิดครั้งที่ nth
  for (auto& e : logv) if (e.second == name && nth-- == 0) return e.first;
  return 0xFFFFFFFF;
}
static int count(const char* name) { int c = 0; for (auto& e : logv) c += (e.second == name); return c; }
static void reset() { T = 0; logv.clear(); suctionOn = brushOn = false; drivePm = 0; cap = CapState::IDLE; capMode = 0; mastUpOk = mastDownOk = true; }
static void run(Mission& m, uint32_t until) { while (T < until && m.running()) { m.tick(T); T += 10; } }

int main() {
  MissionCfg cfg; cfg.stops = 2; cfg.drive_ms = 3000;

  // ── 1. รอบปกติ 2 จุด ──
  reset(); Mission m; m.bind(io);
  CHECK(m.start(cfg, T)); CHECK(m.state() == MState::SUCTION_ON);
  run(m, 60000);
  CHECK(m.state() == MState::DONE); CHECK(m.captured() == 2 && m.failed() == 0);
  CHECK(count("CAPTURE_REQ") == 2 && count("mastUp") == 2 && count("mastDown") == 2 && count("mastRelease") == 2);
  // R2: ล้อออกตัวหลังดูดเปิด ≥ 1000 ms
  CHECK(at("drive 210") - at("suction on") >= 1000);
  // ดูด/แปรงปิด "ก่อน" ยก และ R1: เซอร์โวขยับหลังแปรงปิด ≥ 300 ms · G1: หลังล้อหยุด ≥ 500 ms
  CHECK(at("brush off") < at("mastUp")); CHECK(at("suction off") < at("mastUp"));
  CHECK(at("mastUp") - at("brush off") >= 300); CHECK(at("mastUp") - at("stop") >= 500);
  // ถ่ายหลัง settle ≥ 2000 ms นับจากยกเสร็จ (mastUp กิน 4800 ms ในตัวจำลอง)
  CHECK(at("CAPTURE_REQ") - (at("mastUp") + 4800) >= 2000);
  // พับหลังได้ $K · ปล่อย PWM หลังพับ · แล้วจุดที่ 2 เปิดดูดใหม่
  CHECK(at("mastDown") > at("CAPTURE_REQ")); CHECK(at("mastRelease") > at("mastDown"));
  CHECK(at("suction on", 1) >= at("mastRelease"));
  CHECK(!suctionOn && !brushOn && drivePm == 0);          // จบแล้วทุกอย่างปิด

  // ── 2. Pi ไม่ตอบ: comm ตัดสิน TIMEOUT ที่ 5 s → พับต่อ นับ failed ──
  reset(); capMode = 1; Mission m2; m2.bind(io); cfg.stops = 1;
  m2.start(cfg, T); run(m2, 60000);
  CHECK(m2.state() == MState::DONE && m2.failed() == 1 && m2.captured() == 0);
  CHECK(at("mastDown") - at("CAPTURE_REQ") >= 5000 && at("mastDown") - at("CAPTURE_REQ") < 5400);

  // ── 3. Pi ตอบ $K,n,0 (เขียนภาพล้ม) → พับต่อ นับ failed ──
  reset(); capMode = 2; Mission m3; m3.bind(io); m3.start(cfg, T); run(m3, 60000);
  CHECK(m3.state() == MState::DONE && m3.failed() == 1);

  // ── 4. abort กลางทางตอนวิ่ง: ล้อหยุด ดูด/แปรงปิด เสาไม่ถูกแตะ ──
  reset(); Mission m4; m4.bind(io); m4.start(cfg, T); run(m4, 1500);
  CHECK(m4.state() == MState::DRIVE && drivePm == 210);
  m4.abort("ผู้ใช้สั่ง stop", T);
  CHECK(m4.state() == MState::ABORT && drivePm == 0 && !suctionOn && !brushOn);
  CHECK(count("mastRelease") == 0 && count("mastUp") == 0);
  CHECK(!m4.start(cfg, T) == false);                       // เริ่มใหม่หลัง abort ได้

  // ── 5. ยกเสาถูกขัดจังหวะ (slew คืน false) → abort ไม่ถ่าย ──
  reset(); mastUpOk = false; Mission m5; m5.bind(io); m5.start(cfg, T); run(m5, 60000);
  CHECK(m5.state() == MState::ABORT && count("CAPTURE_REQ") == 0);

  // ── 6. config ผิด: stop_settle < r1_gap ต้องปฏิเสธ ──
  reset(); MissionCfg bad = cfg; bad.stop_settle_ms = 100; Mission m6; m6.bind(io);
  CHECK(!m6.start(bad, T));

  // ── 7. G12: ถ้า $K ไม่มาและ comm ก็ไม่ตัดสิน (จำลอง captureState ค้าง WAITING) — mast_hold_max 15 s ต้องพับ ──
  reset(); capMode = 3; Mission m7; m7.bind(io); MissionCfg c7 = cfg; c7.capture_timeout_ms = 60000; c7.mast_hold_max_ms = 15000;
  m7.start(c7, T); run(m7, 120000);
  CHECK(m7.state() == MState::DONE && m7.failed() == 1);
  CHECK(at("mastDown") - (at("mastUp") + 4800) >= 15000 && at("mastDown") - (at("mastUp") + 4800) < 15100);

  printf(fails ? "%d FAILED\n" : "all ok (%d events in last run)\n", fails ? fails : (int)logv.size());
  return fails ? 1 : 0;
}
