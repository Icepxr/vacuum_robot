#pragma once
// ─────────────────────────────────────────────────────────────
// motor.h — ขับมอเตอร์แบบ sign-magnitude / slow decay
//
// รูปแบบนี้ใช้ได้ทั้ง L298N (เสียบจัมเปอร์ ENA ค้าง) และ DRV8871
//   เดินหน้า : IN1 = PWM(d)   IN2 = 0
//   ถอยหลัง : IN1 = 0        IN2 = PWM(d)
//   เบรก    : IN1 = IN2 = สูงสุด
//
// ⚠ ต่างกัน 1 จุดระหว่างสองไดรเวอร์ — IN1 = IN2 = 0
//   DRV8871 : เข้าโหมด sleep = ปล่อยฟรี (coast)
//   L298N   : ทรานซิสเตอร์ฝั่งล่างนำทั้งคู่ = เบรก (ไม่ใช่ coast)
//   → ตอนเทสด้วย L298N "ปล่อยฟรี" ทำไม่ได้ถ้าเสียบจัมเปอร์ ENA ค้าง
// ─────────────────────────────────────────────────────────────
#include <Arduino.h>
#include "config.h"

class Motor {
 public:
  bool begin(int pinIn1, int pinIn2, uint32_t freqHz);

  // permille = -1000..+1000 (‰ ของ duty เต็ม) · บวก = เดินหน้า
  void setDuty(int permille);
  void brake();

  void setFrequency(uint32_t freqHz);
  int  duty() const { return duty_; }

 private:
  int pin1_ = -1, pin2_ = -1;
  int duty_ = 0;
};
