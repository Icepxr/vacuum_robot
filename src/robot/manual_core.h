#pragma once
// manual_core.h — โหมดขับเอง (MANUAL · C19) แบบไม่พึ่ง Arduino → ทดสอบ test/host_manual.cpp
//
// รับ setpoint (v mm/s, ω mrad/s) จาก Pi ผ่าน $V · แปลงเป็น duty ซ้าย/ขวาแบบ open-loop (ยังไม่มี PID/odometry)
// · เพดานความเร็ว "ผู้ใช้ตั้งเอง" ผ่าน setLimits (C28: G14 ไม่ใช่การห้ามอีกต่อไป · ค่าเริ่มต้น 150 mm/s)
//   เพดานฮาร์ดแวร์ v_hw_max = 810 mm/s (178 rpm × π × Ø87 · C61) — เกินนี้มอเตอร์ทำไม่ได้อยู่แล้ว
// · ไล่ duty ทีละขั้นกันกระชาก · deadman G8: ไม่ได้ $V ใหม่ใน 300 ms → หยุด
// ที่มาตัวเลข: C61 (4 ต.ค. 2026) ไฟล์ 01 §1.16 — เดิม Ø90 / track 180 / 1400 ‰ ต่อ m/s (ไฟล์ 19 §19.7.1) = superseded
#include <stdint.h>

namespace mrc {

// ── ค่าทางกลของหุ่นจริง (C61) · ทุกค่าข้างล่างคำนวณจาก 3 ตัวนี้ ────────────
constexpr int WHEEL_D_MM    = 87;    // [วัดจริง ผู้ใช้ 1 ต.ค.] เดิม Ø90 (C24)
constexpr int TRACK_MM      = 260;   // ระยะกึ่งกลางล้อซ้าย–ขวา [วัดจริง ผู้ใช้ 4 ต.ค.] เดิม 180 [ไม่เคยยืนยัน]
constexpr int RPM_FULL_DUTY = 178;   // rpm เพลาออกที่ duty 100 % ไร้โหลด 12 V [สเปก JGB37-520] — สอดคล้องผลวัด M1:
                                     //   152 rpm ที่มอเตอร์ได้ 10.29 V (L298N ตก 1.71 V) × 12/10.29 = 177.3 · DRV8871 ตก ~0.15 V → ~175 [ประมาณการ]
                                     // ⚠ ยังไม่วัดบน DRV8871 → วัดด้วย `m t3` แล้วแทนค่าที่นี่ที่เดียว (ไฟล์ 01 §1.16)
// v ที่ duty 100 % = rpm × πD / 60 → 178 × π × 87 / 60 = 810.8 → 810 mm/s
constexpr int V_HW_MAX_MM_S   = (int)(RPM_FULL_DUTY * 3.14159265358979 * WHEEL_D_MM / 60.0);
// หมุนอยู่กับที่เต็ม: ω = v / (track/2) = 810 / 130 = 6.2308 → ปัดขึ้น 6231 mrad/s (ให้หมุนเต็ม = duty เต็มพอดี)
constexpr int W_HW_MAX_MRAD_S = (V_HW_MAX_MM_S * 2000 + TRACK_MM - 1) / TRACK_MM;
// ‰ ต่อ m/s แบบเส้นตรงผ่านศูนย์: 1000 ‰ ↔ v_hw_max → 10⁶ / 810 = 1234.6 → ปัดขึ้น 1235 (810 mm/s = 1000 ‰ พอดี)
constexpr int PERMILLE_PER_MPS = (1000000 + V_HW_MAX_MM_S - 1) / V_HW_MAX_MM_S;
static_assert(V_HW_MAX_MM_S == 810 && W_HW_MAX_MRAD_S == 6231 && PERMILLE_PER_MPS == 1235,
              "เปลี่ยนค่าทางกลแล้ว → แก้ V_HW/W_HW ใน mrc_web.py + drive.js + drive.html และ test ให้ตรง แล้วแก้ assert นี้");

struct ManualCfg {
  int      v_max_mm_s      = 150;    // ค่าเริ่มต้น (เดิม G14) · ผู้ใช้เปลี่ยนได้ด้วย $L ไม่เกิน v_hw_max
  int      v_hw_max_mm_s   = V_HW_MAX_MM_S;    // 810 เพดานฮาร์ดแวร์ [คำนวณ] — $L ขอเกินถูก clamp ที่นี่ (เดิม 716 · Ø90)
  int      w_max_mrad_s    = 3000;   // ≈ 172 °/s (เดิม 1500 — C31: หมุนไม่ไป) · ปรับได้ด้วย $L
  int      w_hw_max_mrad_s = W_HW_MAX_MRAD_S;  // 6231 [คำนวณ] (เดิม 7950 = 716/90 · track 180)
  int      track_mm        = TRACK_MM;         // 260 [วัดจริง] (เดิม 180)
  int      permille_per_mps = PERMILLE_PER_MPS; // 1235 [คำนวณ: 178 rpm สเปก × Ø87 — DRV8871 ยังไม่วัด] (เดิม 1400)
  int      permille_max    = 262;    // เพดาน duty = 1.25 × (v_max→‰) เผื่อโหลด/หมุน · คำนวณใหม่ทุกครั้งที่ setLimits · ไม่เกิน 1000
  int      slew_permille_per_tick = 15;   // ต่อ tick 10 ms → 0→210 ใน ~140 ms (rampTo เดิม 300 ms แต่ blocking)
  uint32_t deadman_ms      = 300;    // G8
  int      deadband_permille = 40;   // ต่ำกว่านี้ล้อไม่หมุนอยู่ดี (M1 วัดว่า 25 % duty ยังหมุน — deadband จริงยังไม่วัด) → ตัดเป็น 0
  // C51 (29 ก.ย.): พื้น 250 ‰ ตลอดเวลา (C31) ทำให้ทุกคำสั่ง 40–250 ‰ ได้ความเร็วเดียวกัน (ไฟล์ 19 §19.9) → แยกเป็น 2 ค่า
  //   ออกตัว (kick): ล้อเพิ่งเริ่มจากหยุด/กลับทิศ → ใช้อย่างน้อย permille_start จนถึงแล้วค้างไว้ kick_ms เพื่อชนะแรงเสียดทานสถิต
  //   ประคอง (hold): หลัง kick ลดลงตามคำสั่งได้ถึง permille_hold (แรงเสียดทานขณะเคลื่อนที่ต่ำกว่าขณะหยุด)
  int      permille_start  = 250;    // kick — ค่าเดิม C31 (M1 วัด 25 % หมุนแน่ไร้โหลด) [ประมาณการ: มีโหลดยังไม่วัด]
  int      permille_hold   = 100;    // ต่ำสุดขณะวิ่งอยู่ [ประมาณการ — ยังไม่วัด · ต้องวัดบนพื้นจริง ไฟล์ 19 §19.9] · ต่ำไปผลคือล้อหยุดเอง (ปลอดภัย)
  uint32_t kick_ms         = 150;    // ค้าง kick หลังถึง permille_start [ประมาณการ]
};

struct WheelCmd { int l = 0, r = 0; };    // ‰ ที่ส่งจริง (หลัง slew)

class Manual {
 public:
  void configure(const ManualCfg& c) { cfg_ = c; setLimits(c.v_max_mm_s, c.w_max_mrad_s); }

  // ผู้ใช้ตั้งเพดานเอง ($L) · clamp ที่เพดานฮาร์ดแวร์ · คืน true ถ้าได้ตามขอพอดี
  // permille_max ตามไป: 1.25 × (v_max × ‰/m/s) เพื่อให้หมุน+เดินพร้อมกันได้ แต่ไม่เกิน 1000 ‰ (duty เต็ม)
  bool setLimits(int v_max_mm_s, int w_max_mrad_s) {
    bool exact = true;
    if (v_max_mm_s < 0) v_max_mm_s = 0;
    if (w_max_mrad_s < 0) w_max_mrad_s = 0;
    if (v_max_mm_s > cfg_.v_hw_max_mm_s)   { v_max_mm_s = cfg_.v_hw_max_mm_s;   exact = false; }
    if (w_max_mrad_s > cfg_.w_hw_max_mrad_s) { w_max_mrad_s = cfg_.w_hw_max_mrad_s; exact = false; }
    cfg_.v_max_mm_s = v_max_mm_s; cfg_.w_max_mrad_s = w_max_mrad_s;
    // เพดาน duty ต้องรองรับทั้งเดินตรง (v_max) และหมุนตัว (ω_max × track/2) — C31 รอบ 2: เดิมคิดจาก v_max อย่างเดียว
    // ทำให้ที่ v_max 150 การหมุนถูกตัดที่ 262 ‰ (26 % duty) แม้ตั้ง ω 3000 → ล้อไถลข้างไม่ไหว
    const long v_turn = (long)w_max_mrad_s * cfg_.track_mm / 2000;              // mm/s ต่อล้อตอนหมุนอยู่กับที่
    const long v_ref = v_max_mm_s > v_turn ? v_max_mm_s : v_turn;
    long pm = v_ref * cfg_.permille_per_mps / 1000 * 5 / 4;
    if (pm > 1000) pm = 1000;
    if (pm < 0) pm = 0;
    cfg_.permille_max = (int)pm;
    // setpoint ปัจจุบันต้องไม่เกินเพดานใหม่ (ลดเพดานขณะขับ → ช้าลงทันทีผ่าน slew)
    if (v_ >  cfg_.v_max_mm_s) v_ =  cfg_.v_max_mm_s;
    if (v_ < -cfg_.v_max_mm_s) v_ = -cfg_.v_max_mm_s;
    if (w_ >  cfg_.w_max_mrad_s) w_ =  cfg_.w_max_mrad_s;
    if (w_ < -cfg_.w_max_mrad_s) w_ = -cfg_.w_max_mrad_s;
    return exact;
  }
  int vMax() const { return cfg_.v_max_mm_s; }
  int wMax() const { return cfg_.w_max_mrad_s; }
  int permilleMax() const { return cfg_.permille_max; }

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
  void halt() { v_ = w_ = 0; active_ = false; out_ = WheelCmd{}; kicking_[0] = kicking_[1] = false; }   // ตัดทันที (E-STOP)

  // เรียกทุก tick (10 ms) · คืน duty ที่ต้องส่งให้ล้อ · ตั้ง tripped เมื่อ deadman ทำงาน
  WheelCmd tick(uint32_t now) {
    if (active_ && now - lastCmd_ > cfg_.deadman_ms) {
      v_ = w_ = 0; active_ = false; tripped_ = true;       // G8 — Pi หาย → หยุด
    }
    // v_l = v − ω·track/2 · v_r = v + ω·track/2  (mm/s · mrad/s · mm → /1000)
    const long half = (long)w_ * cfg_.track_mm / 2000;     // mm/s
    long pl = ((long)v_ - half) * cfg_.permille_per_mps / 1000;
    long pr = ((long)v_ + half) * cfg_.permille_per_mps / 1000;
    // C51 desaturate: ล้อไหนเกินเพดาน → ลดทั้งคู่ตามสัดส่วน (เดิมตัดข้างเดียว → ที่ 100 % แก้ทิศเหลือ 7 % · §19.9)
    // duty มีแต่ลดลง ไม่มีทางเกินที่เคยได้
    const long mx = (pl < 0 ? -pl : pl) > (pr < 0 ? -pr : pr) ? (pl < 0 ? -pl : pl) : (pr < 0 ? -pr : pr);
    if (mx > cfg_.permille_max && mx > 0) { pl = pl * cfg_.permille_max / mx; pr = pr * cfg_.permille_max / mx; }
    const int tl = shape(0, pl, out_.l, now);
    const int tr = shape(1, pr, out_.r, now);
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
  // deadband + พื้น (kick ตอนออกตัว / hold ขณะวิ่ง) ต่อล้อ · cur = duty ที่ล้อได้อยู่ตอนนี้ (ก่อน slew รอบนี้)
  int shape(int i, long p, int cur, uint32_t now) {
    if (p > -cfg_.deadband_permille && p < cfg_.deadband_permille) { kicking_[i] = false; kickAt_[i] = 0; return 0; }
    const int sgn = p > 0 ? 1 : -1;
    const long mag = p > 0 ? p : -p;
    const bool fromRest = cur == 0 || (cur > 0) != (p > 0);            // หยุดอยู่ หรือกลับทิศ
    if (fromRest && !kicking_[i]) { kicking_[i] = true; kickAt_[i] = 0; }
    if (kicking_[i]) {
      const int a = cur < 0 ? -cur : cur;
      if (!fromRest && a >= cfg_.permille_start && kickAt_[i] == 0) kickAt_[i] = now ? now : 1;
      if (kickAt_[i] && now - kickAt_[i] >= cfg_.kick_ms) kicking_[i] = false;
    }
    const long floor = kicking_[i] ? cfg_.permille_start : cfg_.permille_hold;
    return (int)(sgn * (mag < floor ? floor : mag));
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
  bool kicking_[2] = {false, false};
  uint32_t kickAt_[2] = {0, 0};             // เวลาที่ล้อถึงระดับ kick (0 = ยังไม่ถึง)
};

}  // namespace mrc
