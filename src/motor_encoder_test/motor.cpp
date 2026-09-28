#include "motor.h"

bool Motor::begin(int pinIn1, int pinIn2, uint32_t freqHz) {
  pin1_ = pinIn1;
  pin2_ = pinIn2;
  // Arduino-ESP32 core 3.x ผูก LEDC กับ "ขา" ไม่ใช่ "channel" แล้ว
  if (!ledcAttach(pin1_, freqHz, PWM_RES_BITS)) return false;
  if (!ledcAttach(pin2_, freqHz, PWM_RES_BITS)) return false;
  setDuty(0);
  return true;
}

// C51 (29 ก.ย.): สลับ "ขับ ↔ เบรก" (slow decay) ตามที่ TI แนะนำ [สเปก DRV8871 SLVSCY9A §7.3.1]
//   เดินหน้า d ‰ : IN1 = 1 ค้าง · IN2 = PWM (1000−d) ‰  → ช่วง IN2=0 ขับ (1,0) · ช่วง IN2=1 เบรก (1,1)
//   ถอยหลัง d ‰ : IN2 = 1 ค้าง · IN1 = PWM (1000−d) ‰
//   0 ‰          : IN1 = IN2 = 1 = เบรก
// เดิม IN1 = PWM · IN2 = 0 → ช่วงดับ (0,0) บน DRV8871 = coast/fast decay (บน L298N ที่ต่อ ENA ค้าง = เบรก)
// → ย้ายมา DRV8871 แล้วพฤติกรรมเปลี่ยนเงียบๆ: duty ต่ำได้แรงน้อยกว่าตอนวัด M1 (L298N) และค่า 1.4 ‰/(mm/s) ใช้ไม่ตรง
// แบบใหม่ใช้ได้ทั้งสองไดรเวอร์ (L298N: H,H = เบรกเหมือนกัน)
void Motor::setDuty(int permille) {
  permille = constrain(permille, -1000, 1000);
  duty_ = permille;
  const int off = ((1000 - abs(permille)) * PWM_MAX) / 1000;   // สัดส่วนเวลาที่เบรก
  if (permille >= 0) {
    ledcWrite(pin1_, PWM_MAX);
    ledcWrite(pin2_, off);
  } else {
    ledcWrite(pin1_, off);
    ledcWrite(pin2_, PWM_MAX);
  }
}

void Motor::brake() {
  duty_ = 0;
  ledcWrite(pin1_, PWM_MAX);
  ledcWrite(pin2_, PWM_MAX);
}

void Motor::setFrequency(uint32_t freqHz) {
  ledcChangeFrequency(pin1_, freqHz, PWM_RES_BITS);
  ledcChangeFrequency(pin2_, freqHz, PWM_RES_BITS);
  setDuty(duty_);
}
