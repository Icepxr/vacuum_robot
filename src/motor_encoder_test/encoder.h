#pragma once
// ─────────────────────────────────────────────────────────────
// encoder.h — อ่าน quadrature encoder ด้วย PCNT (ESP-IDF v5)
//
// ทำไมต้อง PCNT ไม่ใช่ ISR: §1.4 คำนวณไว้ว่าที่ความเร็วเต็มจะได้
// 7,310 counts/s ต่อล้อ × 2 ล้อ = 14,620 interrupt/s — ISR จะกิน CPU
// และนับพลาดเมื่อ CPU ยุ่ง
//
// การถอดรหัส ×4: ใช้ 2 channel ต่อ 1 unit
//   ch A: นับที่ขอบของ A โดยใช้ B เป็นสัญญาณควบคุมทิศ
//   ch B: นับที่ขอบของ B โดยใช้ A เป็นสัญญาณควบคุมทิศ
// ─────────────────────────────────────────────────────────────
#include <Arduino.h>
#include <driver/pulse_cnt.h>
#include "config.h"

class QuadEncoder {
 public:
  // pinA/pinB = ขาสัญญาณ Hall A/B · invert = สลับทิศการนับ (ถ้าต่อสาย A/B สลับกัน)
  bool begin(int pinA, int pinB, bool invert = false);

  // ค่าสะสมทั้งหมดตั้งแต่ zero() ครั้งล่าสุด (รวมส่วนที่ล้นไปแล้ว)
  int64_t count();

  void zero();

  // จำนวนครั้งที่ตัวนับชน watch point ±30,000 — ใช้พิสูจน์ว่ากันล้นได้จริง (ขั้น T5)
  uint32_t wrapCount() const { return wraps_; }  // 32 บิต อ่านได้ atomic อยู่แล้ว

 private:
  static bool IRAM_ATTR onReach(pcnt_unit_handle_t unit,
                                const pcnt_watch_event_data_t* edata,
                                void* ctx);

  pcnt_unit_handle_t unit_ = nullptr;
  portMUX_TYPE mux_ = portMUX_INITIALIZER_UNLOCKED;  // กันอ่าน accum_ คาบเกี่ยวกับ ISR
  volatile int64_t accum_ = 0;   // ผลรวมของทุกครั้งที่ชน watch point
  volatile uint32_t wraps_ = 0;
  bool invert_ = false;
};
