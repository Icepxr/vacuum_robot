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

void Motor::setDuty(int permille) {
  permille = constrain(permille, -1000, 1000);
  duty_ = permille;
  const int raw = (abs(permille) * PWM_MAX) / 1000;
  if (permille >= 0) {
    ledcWrite(pin1_, raw);
    ledcWrite(pin2_, 0);
  } else {
    ledcWrite(pin1_, 0);
    ledcWrite(pin2_, raw);
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
