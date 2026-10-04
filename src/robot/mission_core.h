#pragma once
// mission_core.h — ลำดับภารกิจ 1 รอบ (ขั้น D) แบบไม่พึ่ง Arduino → ทดสอบบน host ได้ (test/host_mission.cpp)
//
//   [ต่อจุดมิเตอร์]  SUCTION_ON ─(R2 เว้น 1000 ms)─▶ DRIVE ─(drive_ms)─▶ STOPPING (ล้อหยุด · ดูด/แปรงปิด)
//                    ─(G1 นิ่ง 500 ms และ R1 เว้น 300 ms)─▶ LIFT (ยกเสา · blocking ในโมดูลเซอร์โว)
//                    ─▶ SETTLE (settle_ms) ─▶ CAPTURE (ส่ง CAPTURE_REQ) ─▶ WAIT_ACK ($K หรือ timeout 5 s)
//                    ─▶ LOWER (พับเสา + ปล่อย PWM) ─▶ จุดถัดไป หรือ DONE
//
// ที่มาของกติกา: system_architecture.md §6.1 (LIFT_* / CAMERA_CAPTURE) · ไฟล์ 18 (R1/R2) · ไฟล์ 19 §19.7 (ค่าตั้งต้น)
// ยังไม่ใช่ FSM 12 state ของ §6 — เป็น "script ตายตัว" ให้เดินครบ 1 รอบก่อน (แผน rev.4 ขั้น D)
#include <stdint.h>

namespace mrc {

struct MissionCfg {
  uint8_t  stops            = 3;      // จำนวนจุดมิเตอร์ต่อรอบ (สนามอ้างอิง: น้ำ 3 + ไฟ 1)
  int      drive_permille   = 210;    // ‰ duty ล้อ — ≈0.17 m/s ไร้โหลด = 210/1235 (C61 ล้อ Ø87 · เดิมคิด 0.15 m/s ที่ Ø90) [คำนวณ]
  uint32_t drive_ms         = 5000;   // วิ่งต่อจุด [ประมาณการ — ยังไม่รู้ระยะระหว่างมิเตอร์]
  uint32_t r2_gap_ms        = 1000;   // เปิดดูดแล้วเว้นก่อนออกตัวล้อ (ไฟล์ 18 R2 · inrush blower ยังไม่วัด)
  uint32_t stop_settle_ms   = 500;    // ล้อนิ่งก่อนยก (G1) — ต้อง ≥ r1_gap
  uint32_t r1_gap_ms        = 300;    // ปิดแปรงแล้วเว้นก่อนขยับเซอร์โว (ไฟล์ 18 R1)
  uint32_t settle_ms        = 2000;   // เสานิ่งก่อนถ่าย (§6.1 LIFT_SETTLE ค่าตั้งต้น)
  uint32_t capture_timeout_ms = 5000; // §6.1 CAMERA_CAPTURE
  uint32_t mast_hold_max_ms = 15000;  // G12 — เสาอยู่บนได้ไม่เกินนี้ (นับตั้งแต่ยกเสร็จ)
};

enum class MState : uint8_t {
  IDLE, SUCTION_ON, DRIVE, STOPPING, LIFT, SETTLE, CAPTURE, WAIT_ACK, LOWER, DONE, ABORT
};

enum class CapState : uint8_t { IDLE, WAITING, OK, FAIL, TIMEOUT };   // ต้องตรงกับ comm.h CaptureState

// ฟังก์ชันที่ mission เรียก — ฝั่ง ESP32 ผูกกับโมดูลจริง · ฝั่ง host ผูกกับตัวจำลอง
struct MissionIO {
  void (*suction)(bool on);
  void (*brush)(bool on);
  void (*drive)(int permille);       // ล้อทั้งสองข้าง (ramp อยู่ในโมดูลล้อ)
  void (*stop)();                    // เบรกล้อ
  bool (*mastUp)();                  // blocking · false = ถูกขัดจังหวะ/ล้มเหลว
  bool (*mastDown)();                // blocking
  void (*mastRelease)();             // ตัด PWM เซอร์โวเมื่อพับสุด (กลไกล็อกตัวเองตอนพับ)
  bool (*requestCapture)();          // ส่ง CAPTURE_REQ · false = ยังรอครั้งก่อน
  CapState (*captureState)();
  void (*log)(const char* msg);
  uint32_t (*now)();                 // นาฬิกา ms — ต้องอ่านใหม่หลังทุก blocking call (mastUp/mastDown)
};

inline const char* mstateName(MState s) {
  static const char* n[] = {"IDLE","SUCTION_ON","DRIVE","STOPPING","LIFT","SETTLE","CAPTURE","WAIT_ACK","LOWER","DONE","ABORT"};
  return n[(int)s];
}

class Mission {
 public:
  void bind(const MissionIO& io) { io_ = io; }

  bool start(const MissionCfg& cfg, uint32_t now) {
    if (state_ != MState::IDLE && state_ != MState::DONE && state_ != MState::ABORT) return false;
    if (cfg.stop_settle_ms < cfg.r1_gap_ms) return false;    // ไม่งั้น R1 หลุด
    cfg_ = cfg; stop_ = 0; captured_ = 0; failed_ = 0;
    io_.suction(true); io_.brush(true);                          // ดูดก่อน ล้อรอ R2
    enter(MState::SUCTION_ON, now);
    return true;
  }

  // หยุดทุกอย่างที่ขยับได้ · เสา "คงที่" ไม่ปล่อย PWM (§6.1 FAULT) — ปล่อยกลางทางเสาจะร่วง
  void abort(const char* why, uint32_t now) {
    if (state_ == MState::IDLE || state_ == MState::DONE || state_ == MState::ABORT) return;
    io_.stop(); io_.brush(false); io_.suction(false);
    io_.log(why);
    enter(MState::ABORT, now);
  }

  void tick(uint32_t now) {
    const uint32_t el = now - t0_;
    switch (state_) {
      case MState::SUCTION_ON:
        if (el >= cfg_.r2_gap_ms) { io_.drive(cfg_.drive_permille); enter(MState::DRIVE, now); }
        break;
      case MState::DRIVE:
        if (el >= cfg_.drive_ms) {
          io_.stop(); io_.brush(false); io_.suction(false);       // §6.1 LIFT_PREPARE: ปิดทั้งคู่
          enter(MState::STOPPING, now);
        }
        break;
      case MState::STOPPING:
        if (el >= cfg_.stop_settle_ms) {                           // ครอบ G1 500 ms และ R1 300 ms
          enter(MState::LIFT, now);
          const bool ok = io_.mastUp();
          now = io_.now();                                         // ⚠ slew กิน ~4.8 s — ห้ามใช้ now เดิม
          if (!ok) { abort("ยกเสาไม่สำเร็จ/ถูกขัดจังหวะ", now); return; }
          enter(MState::SETTLE, now); liftedAt_ = now;
        }
        break;
      case MState::SETTLE:
        if (el >= cfg_.settle_ms) {
          if (!io_.requestCapture()) { abort("ส่ง CAPTURE_REQ ไม่ได้ (ยังรอครั้งก่อน)", now); return; }
          enter(MState::WAIT_ACK, now);
        }
        break;
      case MState::WAIT_ACK: {
        const CapState c = io_.captureState();
        const bool done = (c == CapState::OK || c == CapState::FAIL || c == CapState::TIMEOUT);
        if (done || el >= cfg_.capture_timeout_ms + 200) {        // +200: กัน comm ตัดสินช้ากว่า mission
          if (c == CapState::OK) ++captured_; else ++failed_;
          lower(now);
        }
        break;
      }
      default: break;                                            // IDLE/LIFT/LOWER/DONE/ABORT ไม่มีอะไรทำใน tick
    }
    // G12 — ไม่ว่าจะอยู่ state ไหนขณะเสายก ถ้าเกินเวลาต้องพับ
    if ((state_ == MState::SETTLE || state_ == MState::WAIT_ACK) && now - liftedAt_ >= cfg_.mast_hold_max_ms) {
      io_.log("G12: เสาอยู่บนเกินเวลา — พับ");
      ++failed_; lower(now);
    }
  }

  MState   state()    const { return state_; }
  uint8_t  stopIndex() const { return stop_; }
  uint8_t  captured() const { return captured_; }
  uint8_t  failed()   const { return failed_; }
  bool     running()  const { return state_ != MState::IDLE && state_ != MState::DONE && state_ != MState::ABORT; }

 private:
  void enter(MState s, uint32_t now) { state_ = s; t0_ = now; }

  void lower(uint32_t now) {
    enter(MState::LOWER, now);
    const bool ok = io_.mastDown();
    now = io_.now();                                               // blocking เช่นกัน
    if (!ok) { abort("พับเสาไม่สำเร็จ/ถูกขัดจังหวะ — เสาค้างอยู่ ตรวจก่อนสั่งต่อ", now); return; }
    io_.mastRelease();
    ++stop_;
    if (stop_ >= cfg_.stops) { io_.log("ครบทุกจุด"); enter(MState::DONE, now); }
    else { io_.suction(true); io_.brush(true); enter(MState::SUCTION_ON, now); }
  }

  MissionIO  io_{};
  MissionCfg cfg_{};
  MState     state_ = MState::IDLE;
  uint32_t   t0_ = 0, liftedAt_ = 0;
  uint8_t    stop_ = 0, captured_ = 0, failed_ = 0;
};

}  // namespace mrc
