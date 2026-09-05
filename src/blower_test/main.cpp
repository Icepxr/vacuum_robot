// ─────────────────────────────────────────────────────────────
// M3 — ชุดทดสอบระบบดูด (blower AVC BA10033B12U + MOSFET IRLZ44N)
//
// เป้าหมายของการเทสนี้ = ปิด 3 ข้อที่ยังเป็นการเดา
//   P1  R_DS(on) = 60 mΩ ที่ V_gs 3.3 V — datasheet ให้ค่าแค่ที่ 5 V และ 10 V
//       ไฟล์ 10 ระบุว่าเอกสารต้นทาง "ยอมรับเองว่าเดา" → ย้อนคำนวณจากอุณหภูมิที่วัดได้
//   —   กระแสจริงเทียบพิกัด 2.4 A (เกณฑ์ผ่าน ≤ 2.76 A)
//   —   ประสิทธิภาพเก็บก้อน PLA ≥ 80 % (เกณฑ์เดิมของแผนเทส §1.1)
//
// 🔴 กติกาที่โค้ดนี้บังคับ: ห้ามตั้งความถี่ PWM เกิน 50 Hz
//    §3.5 คำนวณไว้ว่าที่ 20 kHz MOSFET จะร้อนขึ้น +66 °C (ทิ้ง 1.066 W)
//
// วิธีใช้: serial monitor 115200 พิมพ์ ? เพื่อดูคำสั่ง
// ขั้นตอนเต็ม + ตารางกรอกผล: 03_ผลการทดสอบ/M3_ระบบดูด.md
// ─────────────────────────────────────────────────────────────
#include <Arduino.h>
#include "config.h"

static bool pwmMode = false;          // false = เปิด-ปิดด้วย GPIO ธรรมดา (โหมดหลักตาม §3.5)
static uint32_t pwmFreq = PWM_FREQ_DEFAULT_HZ;
static int dutyPercent = 0;
static bool blowerOn = false;
static uint32_t onSinceMs = 0;
static uint32_t lastCommandMs = 0;

// ── ควบคุม blower ────────────────────────────────────────────

static void applyOff() {
  if (pwmMode) ledcWrite(PIN_SUCTION_EN, 0);
  else digitalWrite(PIN_SUCTION_EN, LOW);
  blowerOn = false;
  dutyPercent = 0;
}

static void applyOn(int percent) {
  if (pwmMode) {
    dutyPercent = constrain(percent, 0, 100);
    ledcWrite(PIN_SUCTION_EN, (dutyPercent * PWM_MAX) / 100);
  } else {
    dutyPercent = 100;
    digitalWrite(PIN_SUCTION_EN, HIGH);
  }
  blowerOn = dutyPercent > 0;
  onSinceMs = millis();
}

static void stopAll(const char* why) {
  applyOff();
  Serial.printf("[STOP] %s\n", why);
}

// สลับระหว่างโหมด GPIO ธรรมดา กับ LEDC 25 Hz
static bool setPwmMode(bool enable) {
  applyOff();
  if (enable == pwmMode) return true;
  if (enable) {
    if (!ledcAttach(PIN_SUCTION_EN, pwmFreq, PWM_RES_BITS)) {
      Serial.println("[ERR] ผูก LEDC กับขาไม่สำเร็จ");
      return false;
    }
    ledcWrite(PIN_SUCTION_EN, 0);
    pwmMode = true;
    Serial.printf("[OK] เข้าโหมด PWM %u Hz (timer T3 ตาม §3.5)\n", (unsigned)pwmFreq);
    Serial.println("     หมายเหตุ: โหมดหลักที่เอกสารเลือกไว้คือเปิด-ปิดอย่างเดียว");
    Serial.println("     โหมดนี้มีไว้หา SUCTION_DUTY_MIN เท่านั้น (ขั้น S5)");
  } else {
    ledcDetach(PIN_SUCTION_EN);
    pinMode(PIN_SUCTION_EN, OUTPUT);
    digitalWrite(PIN_SUCTION_EN, LOW);
    pwmMode = false;
    Serial.println("[OK] กลับเข้าโหมดเปิด-ปิดด้วย GPIO ธรรมดา");
  }
  return true;
}

// ── ขั้นทดสอบ ────────────────────────────────────────────────

// S4 — เปิดดูดตามเวลาที่กำหนดเป๊ะ ใช้กับตารางเก็บก้อน PLA
// แผนเทส §1.1 ตารางที่ 2 กำหนดว่า "เวลาที่ใช้ดูด คงที่ทุกรอบ เพื่อเทียบกันได้"
// ให้เฟิร์มแวร์จับเวลาแทนนาฬิกาจับเวลาในมือ จะได้ไม่คลาดเคลื่อนระหว่างรอบ
static void timedRun(uint32_t ms) {
  if (ms > MAX_ON_MS) ms = MAX_ON_MS;
  Serial.printf("\n=== เปิดดูด %lu ms ===\n", (unsigned long)ms);
  Serial.println("นับถอยหลัง 3 วินาที — เตรียมวางก้อน PLA ให้พร้อม");
  for (int i = 3; i > 0; i--) { Serial.printf("  %d...\n", i); delay(1000); }

  const uint32_t t0 = millis();
  applyOn(100);
  Serial.println(">>> เปิดแล้ว");
  while (millis() - t0 < ms) delay(5);
  applyOff();
  const uint32_t actual = millis() - t0;
  Serial.printf(">>> ปิดแล้ว · เวลาที่เปิดจริง %lu ms (คลาด %+ld ms)\n",
                (unsigned long)actual, (long)actual - (long)ms);
  Serial.println("นับจำนวนก้อนในถังฝุ่นแล้วจดลงตาราง S4");
}

// S5 — หา duty ต่ำสุดที่ใบพัดยังออกตัวได้ (SUCTION_DUTY_MIN)
// §3.5 คาดว่ามีโซนตายช่วง duty ต่ำ ให้จดค่านี้ไว้ใช้ในเฟิร์มแวร์จริง
static void dutySweep() {
  if (!pwmMode) {
    Serial.println("[ERR] ต้องเข้าโหมด PWM ก่อน — พิมพ์  pwm on");
    return;
  }
  Serial.println("\n=== S5: หา SUCTION_DUTY_MIN ===");
  Serial.printf("ไล่ duty ขึ้นทีละ 5 %% ที่ %u Hz ค้างระดับละ 2 วินาที\n", (unsigned)pwmFreq);
  Serial.println("กด Enter ทันทีที่เห็นใบพัด 'ออกตัว' (เริ่มหมุนเองจากหยุดนิ่ง)");
  while (Serial.available()) Serial.read();

  for (int d = 5; d <= 100; d += 5) {
    applyOn(d);
    Serial.printf("  duty = %3d %%\n", d);
    const uint32_t t0 = millis();
    while (millis() - t0 < 2000) {
      if (Serial.available()) {
        while (Serial.available()) Serial.read();
        applyOff();
        Serial.printf("\n>>> SUCTION_DUTY_MIN = %d %% ที่ %u Hz\n", d, (unsigned)pwmFreq);
        Serial.println("จดค่านี้ลงตาราง S5 — ต่ำกว่านี้ใบพัดจะไม่ออกตัว");
        return;
      }
      delay(10);
    }
    applyOff();
    delay(400);   // ให้ใบพัดหยุดสนิทก่อนลองระดับถัดไป
  }
  applyOff();
  Serial.println(">>> ไล่จนถึง 100 % แล้วยังไม่ได้กด — ตรวจว่าวงจรต่อถูกไหม");
}

// ── คำสั่ง ────────────────────────────────────────────────────

static void printHelp() {
  Serial.println();
  Serial.println("┌─ คำสั่ง ─────────────────────────────────────────────┐");
  Serial.println("│ ?           แสดงคำสั่ง                               │");
  Serial.println("│ on          เปิดดูด (ค้างไว้)                         │");
  Serial.println("│ off / s     ปิดดูด                                   │");
  Serial.println("│ run <ms>    เปิดตามเวลาเป๊ะแล้วปิดเอง (ขั้น S4)        │");
  Serial.println("│ pwm on|off  สลับโหมด PWM 25 Hz (ขั้น S5 เท่านั้น)     │");
  Serial.println("│ d <0-100>   ตั้ง duty % (เฉพาะโหมด PWM)              │");
  Serial.println("│ sweep       หา SUCTION_DUTY_MIN (ขั้น S5)            │");
  Serial.printf ("│ f <Hz>      เปลี่ยนความถี่ (%u-%u Hz เท่านั้น)         │\n",
                 (unsigned)PWM_FREQ_MIN_HZ, (unsigned)PWM_FREQ_MAX_HZ);
  Serial.println("│ st          แสดงสถานะปัจจุบัน                        │");
  Serial.println("└──────────────────────────────────────────────────────┘");
}

static void printStatus() {
  Serial.printf("โหมด: %s · ความถี่ %u Hz · duty %d %% · blower %s\n",
                pwmMode ? "PWM" : "เปิด-ปิด (GPIO)", (unsigned)pwmFreq,
                dutyPercent, blowerOn ? "เปิดอยู่" : "ปิด");
  if (blowerOn)
    Serial.printf("เปิดมาแล้ว %lu ms (จะตัดเองที่ %lu ms)\n",
                  (unsigned long)(millis() - onSinceMs), (unsigned long)MAX_ON_MS);
}

static void handleCommand(String cmd) {
  cmd.trim();
  if (!cmd.length()) return;
  lastCommandMs = millis();

  if (cmd == "?" || cmd == "h") { printHelp(); return; }
  if (cmd == "st") { printStatus(); return; }
  if (cmd == "off" || cmd == "s") { stopAll("สั่งปิดเอง"); return; }

  if (cmd == "on") {
    applyOn(100);
    Serial.printf("[OK] เปิดดูดแล้ว (จะตัดเองใน %lu ms)\n", (unsigned long)MAX_ON_MS);
    Serial.println("     อ่านค่ากระแสจากจอแหล่งจ่ายตอนนี้ — เกณฑ์ผ่าน ≤ 2.76 A");
    return;
  }
  if (cmd == "sweep") { dutySweep(); return; }

  if (cmd.startsWith("run ")) { timedRun((uint32_t)cmd.substring(4).toInt()); return; }

  if (cmd == "pwm on")  { setPwmMode(true);  return; }
  if (cmd == "pwm off") { setPwmMode(false); return; }

  if (cmd.startsWith("d ")) {
    if (!pwmMode) { Serial.println("[ERR] โหมดเปิด-ปิดตั้ง duty ไม่ได้ — พิมพ์  pwm on  ก่อน"); return; }
    const int d = cmd.substring(2).toInt();
    applyOn(d);
    Serial.printf("[OK] duty = %d %%\n", dutyPercent);
    return;
  }

  if (cmd.startsWith("f ")) {
    const uint32_t hz = (uint32_t)cmd.substring(2).toInt();
    if (hz < PWM_FREQ_MIN_HZ || hz > PWM_FREQ_MAX_HZ) {
      Serial.printf("[ปฏิเสธ] %u Hz อยู่นอกช่วงที่ยอมให้ใช้ (%u-%u Hz)\n",
                    (unsigned)hz, (unsigned)PWM_FREQ_MIN_HZ, (unsigned)PWM_FREQ_MAX_HZ);
      Serial.println("  system_architecture.md §3.5 คำนวณไว้ว่าที่ 20 kHz MOSFET จะทิ้งความร้อน");
      Serial.println("  1.066 W ทำให้ร้อนขึ้น +66 °C และ blower เป็นมอเตอร์ไร้แปรงถ่านที่มี");
      Serial.println("  วงจรขับในตัว การสับไฟถี่ขนาดนั้นคือการปลุก-ดับวงจรของมันเอง");
      return;
    }
    pwmFreq = hz;
    if (pwmMode) { ledcChangeFrequency(PIN_SUCTION_EN, pwmFreq, PWM_RES_BITS); applyOn(dutyPercent); }
    Serial.printf("[OK] ความถี่ = %u Hz\n", (unsigned)pwmFreq);
    return;
  }

  Serial.printf("[ERR] ไม่รู้จักคำสั่ง \"%s\" — พิมพ์ ? เพื่อดูรายการ\n", cmd.c_str());
}

// ── setup / loop ──────────────────────────────────────────────

void setup() {
  // ตั้งขาให้เป็น LOW ก่อนทุกอย่าง กัน blower ออกตัวเองตอนบูต
  pinMode(PIN_SUCTION_EN, OUTPUT);
  digitalWrite(PIN_SUCTION_EN, LOW);

  Serial.begin(115200);
  delay(2000);   // รอ USB CDC พร้อม ไม่งั้นบรรทัดแรกๆ จะหาย

  Serial.println();
  Serial.println("=== M3: เทสระบบดูด (blower + MOSFET) ===");
  Serial.printf("ESP-IDF %d.%d.%d · ขาควบคุม GPIO %d\n",
                ESP_IDF_VERSION_MAJOR, ESP_IDF_VERSION_MINOR, ESP_IDF_VERSION_PATCH,
                PIN_SUCTION_EN);
  Serial.printf("blower: %.1f V · พิกัด %.1f A · เกณฑ์ผ่าน ≤ %.2f A\n",
                BLOWER_V_NOM, BLOWER_I_RATED_A, BLOWER_I_LIMIT_A);
  Serial.println();
  Serial.println("⚠ ตรวจ 5 ข้อก่อนจ่ายไฟ 12 V (รายละเอียดในเอกสารเทส):");
  Serial.println("  1. MOSFET ต้องเป็น logic-level — IRF520 ใช้ไม่ได้ ต้องการ V_gs ~10 V");
  Serial.println("  2. R 100 Ω อนุกรมเข้าเกต + pull-down 10 kΩ ลงกราวด์ (§3.2)");
  Serial.println("  3. ไดโอด SS34 คร่อมโหลด ขั้วถูกด้าน");
  Serial.println("  4. GND ของ ESP32 · MOSFET · แหล่งจ่าย 12 V ต่อถึงกันหมด");
  Serial.println("  5. ตั้ง current limit ของแหล่งจ่ายที่ 4.0 A (สูงกว่าเกณฑ์ 2.76 A เผื่อ inrush)");
  printHelp();
  lastCommandMs = millis();
}

void loop() {
  static String buf;
  while (Serial.available()) {
    const char c = Serial.read();
    if (c == '\n' || c == '\r') { if (buf.length()) { handleCommand(buf); buf = ""; } }
    else buf += c;
  }

  if (blowerOn && millis() - onSinceMs > MAX_ON_MS) stopAll("ครบเวลาเปิดสูงสุด");
  if (blowerOn && millis() - lastCommandMs > DEADMAN_MS) stopAll("ไม่มีคำสั่งใหม่นานเกินไป");

  delay(10);
}
