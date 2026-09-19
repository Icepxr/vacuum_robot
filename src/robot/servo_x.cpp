// servo_x.cpp — ดู servo_x.h
#include "servo_x.h"

namespace {
constexpr int      PIN_SERVO_X   = 18;      // §3.2 SERVO_B · ไม่ใช่ strapping pin ของ S3 (0/3/45/46) · ไม่ชน USB 19/20
constexpr uint32_t FREQ_HZ       = 50;
constexpr uint8_t  RES_BITS      = 14;      // ไฟล์ 17: 16 บิตตั้งไม่ได้บน S3
constexpr int      DUTY_MAX      = (1 << RES_BITS) - 1;
constexpr float    PERIOD_US     = 1000000.0f / FREQ_HZ;
constexpr int      US_MIN = 500, US_MAX = 2500, US_CENTER = 1500;   // ช่วงเดียวกับ servo_test (ยังไม่วัดขีดจริงของตัวนี้)
constexpr int      SLEW_US       = 25;      // มุมกล้อง = โหลดเบา ให้ตามนิ้วทัน: 25 us/12 ms ≈ 2,083 us/s → เต็มช่วง ~1 s [ยังไม่ทดสอบกับกลไกจริง]
constexpr uint32_t SLEW_MS       = 12;

bool     attached = false;
int      curUs = 0, targetUs = 0;
uint32_t lastStepMs = 0;

int usToDuty(int us) { return (int)((float)us * DUTY_MAX / PERIOD_US + 0.5f); }

bool attachAt(int us) {
  if (!attached) {
    if (!ledcAttach(PIN_SERVO_X, FREQ_HZ, RES_BITS)) { Serial.println("[sx] ผูก LEDC GPIO18 ไม่สำเร็จ (ช่อง/timer เต็ม? ดูไฟล์ 17)"); return false; }
    attached = true;
  }
  curUs = targetUs = us;
  ledcWrite(PIN_SERVO_X, usToDuty(us));
  return true;
}
}  // namespace

void servoXSetup() {
  pinMode(PIN_SERVO_X, OUTPUT); digitalWrite(PIN_SERVO_X, LOW);   // pull-down 10 kΩ ภายนอกกันตอนบูต โค้ดรับช่วงต่อ
  Serial.printf("[sx] เซอร์โว X ที่ GPIO%d · ยังไม่ผูกสัญญาณ (sx <us> เพื่อเริ่ม)\n", PIN_SERVO_X);
}

bool servoXMoveTo(int us) {
  if (us < US_MIN || us > US_MAX) return false;
  if (!attached) {
    // ครั้งแรกไม่รู้ว่าฮอร์นอยู่ไหน — ผูกที่ค่าที่ขอเลย (เซอร์โววิ่งไปเองด้วยความเร็วเต็มครั้งเดียว)
    // ต่างจากเสาที่ต้องระวังกลไกชน: แกน X ของกล้องเป็นโหลดเบา ยอมรับได้ [ยังไม่ทดสอบกับกลไกจริง]
    return attachAt(us);
  }
  targetUs = us;
  return true;
}

void servoXTick() {
  if (!attached || curUs == targetUs) return;
  const uint32_t now = millis();
  if (now - lastStepMs < SLEW_MS) return;
  lastStepMs = now;
  const int d = targetUs - curUs;
  curUs += (d > SLEW_US) ? SLEW_US : (d < -SLEW_US) ? -SLEW_US : d;
  ledcWrite(PIN_SERVO_X, usToDuty(curUs));
}

void servoXRelease(const char* why) {
  if (!attached) return;
  ledcDetach(PIN_SERVO_X);
  pinMode(PIN_SERVO_X, OUTPUT); digitalWrite(PIN_SERVO_X, LOW);
  attached = false; targetUs = curUs;
  Serial.printf("[sx] ปล่อยสัญญาณ: %s\n", why);
}

bool servoXAttached()  { return attached; }
bool servoXMoving()    { return attached && curUs != targetUs; }
int  servoXCurrentUs() { return attached ? curUs : 0; }

void servoXCommand(const String& cmd) {
  String c = cmd; c.trim();
  if (c == "off")      { servoXRelease("ผู้ใช้สั่ง"); return; }
  if (c == "st" || !c.length()) {
    Serial.printf("[sx] %s · ตอนนี้ %d us → เป้า %d us%s\n", attached ? "ผูกอยู่" : "ปล่อย", curUs, targetUs, servoXMoving() ? " (กำลังเดิน)" : "");
    return;
  }
  const int us = c.toInt();
  if (!servoXMoveTo(us)) { Serial.printf("[sx] ช่วงที่รับ %d–%d us\n", US_MIN, US_MAX); return; }
  Serial.printf("[sx] → %d us\n", us);
}
