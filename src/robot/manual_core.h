#pragma once
// manual_core.h — โหมดขับเอง (MANUAL · C19) แบบไม่พึ่ง Arduino → ทดสอบ test/host_manual.cpp
//
// รับ setpoint (v mm/s, ω mrad/s) จาก Pi ผ่าน $V · แปลงเป็น duty ซ้าย/ขวาแบบ open-loop (ยังไม่มี PID/odometry)
// · จำกัดตาม G14 · ไล่ duty ทีละขั้นกันกระชาก · deadman G8: ไม่ได้ $V ใหม่ใน 300 ms → หยุด
// ที่มาตัวเลข: ไฟล์ 19 §19.7.1 (210 ‰ ≈ 150 mm/s ไร้โหลด ล้อ Ø90) · system_architecture §3.6 track 180 mm [ยังไม่ยืนยันของจริง]
#include <stdint.h>

namespace mrc {

struct ManualCfg {
  int      v_max_mm_s      = 150;    // G14 เฟส 1
  int      w_max_mrad_s    = 1500;   // ≈ 86 °/s — หมุนตัวรอบละ ~4 s [ประมาณการ] · ปรับหน้างาน
  int      track_mm        = 180;    // ระยะล้อซ้าย–ขวา [ยังไม่ยืนยันของจริง]
  int      permille_per_mps = 1400;  // 210 ‰ / 0.15 m/s  [คำนวณจากค่าวัดจริงไร้โหลด]
  int      permille_max    = 260;    // เพดานเผื่อโหลด/หมุน ≈ 1.25 × 210 · ห้ามเกิน 600 (mission.cpp ใช้เพดานเดียวกัน)
  int      slew_permille_per_tick = 15;   // ต่อ tick 10 ms → 0→210 ใน ~140 ms (rampTo เดิม 300 ms แต่ blocking)
  uint32_t deadman_ms      = 300;    // G8
  int      deadband_permille = 40;   // ต่ำกว่านี้ล้อไม่หมุนอยู่ดี (M1 วัดว่า 25 % duty ยังหมุน — deadband จริงยังไม่วัด) → ตัดเป็น 0
};

struct WheelCmd { int l = 0, r = 0; };    // ‰ ที่ส่งจริง (หลัง slew)

class Manual {
 public:
  void configure(const ManualCfg& c) { cfg_ = c; }

  // รับ setpoint ใหม่ (จาก $V) · คืน false ถ้าเกินพิกัดแล้วถูก clamp (ยังรับ แต่บอกให้ log)
  bool setpoint(int v_mm_s, int w_mrad_s, uint32_t now) {
    bool clamped = false;
    if (v_mm_s >  cfg_.v_max_mm_s)   { v_mm_s =  cfg_.v_max_mm_s; clamped = true; }
    if (v_mm_s < -cfg_.v_max_mm_s)   { v_mm_s = -cfg_.v_max_mm_s; clamped = true; }
    if (w_mrad_s >  cfg_.w_max_mrad_s) { w_mrad_s =  cfg_.w_max_mrad_s; clamped = true; }
    if (w_mrad_s < -cfg_.w_max_mrad_s) { w_mrad_s = -cfg_.w_max_mrad_s; clamped = true; }
    v_ = v_mm_s; w_ = w_mrad_s; lastCmd_ = now; active_ = true; tripped_ = false;
    return !clamped;
  }

  void stop() { v_ = w_ = 0; active_ = false; }          // หยุดนุ่มนวล — slew ลงถึง 0 ใน tick
  void halt() { v_ = w_ = 0; active_ = false; out_ = WheelCmd{}; }   // ตัดทันที (E-STOP)

  // เรียกทุก tick (10 ms) · คืน duty ที่ต้องส่งให้ล้อ · ตั้ง tripped เมื่อ deadman ทำงาน
  WheelCmd tick(uint32_t now) {
    if (active_ && now - lastCmd_ > cfg_.deadman_ms) {
      v_ = w_ = 0; active_ = false; tripped_ = true;       // G8 — Pi หาย → หยุด
    }
    // v_l = v − ω·track/2 · v_r = v + ω·track/2  (mm/s · mrad/s · mm → /1000)
    const long half = (long)w_ * cfg_.track_mm / 2000;     // mm/s
    int tl = mmpsToPermille((long)v_ - half);
    int tr = mmpsToPermille((long)v_ + half);
    out_.l = slew(out_.l, tl);
    out_.r = slew(out_.r, tr);
    return out_;
  }

  bool active()  const { return active_; }
  bool tripped() const { return tripped_; }                // deadman เพิ่งตัด (อ่านแล้วเคลียร์ด้วย ackTrip)
  void ackTrip()       { tripped_ = false; }
  int  v() const { return v_; }
  int  w() const { return w_; }
  WheelCmd out() const { return out_; }

 private:
  int mmpsToPermille(long mmps) const {
    long p = mmps * cfg_.permille_per_mps / 1000;
    if (p >  cfg_.permille_max) p =  cfg_.permille_max;
    if (p < -cfg_.permille_max) p = -cfg_.permille_max;
    if (p > -cfg_.deadband_permille && p < cfg_.deadband_permille) p = 0;
    return (int)p;
  }
  int slew(int cur, int target) const {
    const int d = target - cur;
    if (d >  cfg_.slew_permille_per_tick) return cur + cfg_.slew_permille_per_tick;
    if (d < -cfg_.slew_permille_per_tick) return cur - cfg_.slew_permille_per_tick;
    return target;
  }

  ManualCfg cfg_{};
  int v_ = 0, w_ = 0;
  uint32_t lastCmd_ = 0;
  bool active_ = false, tripped_ = false;
  WheelCmd out_{};
};

}  // namespace mrc
