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

static int  brushDuty = 0;            // % ของ duty เต็ม
static bool brushReady = false;

static bool pwmMode = false;          // false = เปิด-ปิดด้วย GPIO ธรรมดา (โหมดหลักตาม §3.5)
static uint32_t pwmFreq = PWM_FREQ_DEFAULT_HZ;
static int dutyPercent = 0;
static bool blowerOn = false;
static uint32_t onSinceMs = 0;
static uint32_t lastCommandMs = 0;

// ── ควบคุมมอเตอร์แปรงข้าง ────────────────────────────────────
// แยกช่องกันคนละขากับ blower ทำงานพร้อมกันได้

static void brushSet(int percent) {
  if (!brushReady) { Serial.println("[ERR] ช่องแปรงยังไม่พร้อม"); return; }
  if (percent > BRUSH_DUTY_MAX_PCT) {
    Serial.printf("[ปฏิเสธ] duty %d %% = %.2f V เฉลี่ย ซึ่งเกินพิกัดมอเตอร์ 5 V\n",
                  percent, percent * 12.0f / 100.0f);
    Serial.printf("  เพดานที่ยอมให้ใช้คือ %d %% (= %.2f V เฉลี่ย)\n",
                  BRUSH_DUTY_MAX_PCT, BRUSH_DUTY_MAX_PCT * 12.0f / 100.0f);
    Serial.println("  มอเตอร์แปรงพิกัด 3-5 V แต่รางคือ 12 V — ต่อตรงคือไหม้ทันที");
    return;
  }
  brushDuty = constrain(percent, 0, BRUSH_DUTY_MAX_PCT);
  ledcWrite(PIN_BRUSH_PWM, (brushDuty * BRUSH_MAX) / 100);
  Serial.printf("[OK] แปรง duty %d %% ≈ %.2f V เฉลี่ย · เกณฑ์กระแส ≤ %.1f A\n",
                brushDuty, brushDuty * 12.0f / 100.0f, BRUSH_I_LIMIT_A);
}

// ไล่ duty ขึ้นทีละ 5 % ค้างระดับละ 4 วินาที ให้จดกระแสแต่ละระดับ
static void brushSweep() {
  Serial.println();
  Serial.println("=== B1: กวาด duty มอเตอร์แปรง ===");
  Serial.printf("ไล่ 10 %% ถึง %d %% ค้างระดับละ 4 วินาที — จดกระแสจากจอแหล่งจ่ายทุกระดับ\n",
                BRUSH_DUTY_MAX_PCT);
  Serial.println("กดปุ่มใดก็ได้แล้ว Enter เพื่อหยุด");
  Serial.println("duty_%,V_เฉลี่ย,กระแส_A,หมุนไหม");
  while (Serial.available()) Serial.read();
  for (int d = 10; d <= BRUSH_DUTY_MAX_PCT; d += 5) {
    brushDuty = d;
    ledcWrite(PIN_BRUSH_PWM, (d * BRUSH_MAX) / 100);
    Serial.printf("%d,%.2f,____,____\n", d, d * 12.0f / 100.0f);
    const uint32_t t0 = millis();
    while (millis() - t0 < 4000) {
      if (Serial.available()) {
        while (Serial.available()) Serial.read();
        brushDuty = 0; ledcWrite(PIN_BRUSH_PWM, 0);
        Serial.println("[หยุด] ปิดแปรงแล้ว");
        return;
      }
      delay(20);
    }
  }
  brushDuty = 0;
  ledcWrite(PIN_BRUSH_PWM, 0);
  Serial.println("จบ B1 — ปิดแปรงแล้ว · เลือก duty ที่แรงปัดพอดีและกระแสไม่เกิน 1 A");
}

// ── ควบคุม blower ────────────────────────────────────────────

static void applyOff() {
  if (pwmMode) ledcWrite(PIN_SUCTION_EN, 0);
  else digitalWrite(PIN_SUCTION_EN, LOW);
  blowerOn = false;
  dutyPercent = 0;
}

static void applyOn(int percent) {
  const bool wasOn = blowerOn;
  if (pwmMode) {
    dutyPercent = constrain(percent, 0, 100);
    ledcWrite(PIN_SUCTION_EN, (dutyPercent * PWM_MAX) / 100);
  } else {
    // โหมดเปิด-ปิด: §3.5 ตีความ 0 = ปิด · >0 = เปิด
    if (percent <= 0) { applyOff(); return; }   // กัน applyOn(0) แล้วกลายเป็นเปิด
    dutyPercent = 100;
    digitalWrite(PIN_SUCTION_EN, HIGH);
  }
  blowerOn = dutyPercent > 0;
  // ⚠ ต้องจับเวลาจาก "จุดที่เริ่มเปิด" เท่านั้น
  // ถ้ารีเซ็ตทุกครั้งที่เรียก การพิมพ์ d ซ้ำๆ จะเลื่อนตัวตัดเวลาออกไปเรื่อยๆ
  // จน blower เปิดค้างได้ไม่จำกัด
  if (blowerOn && !wasOn) onSinceMs = millis();
}

static void stopAll(const char* why) {
  if (brushReady) { brushDuty = 0; ledcWrite(PIN_BRUSH_PWM, 0); }
  applyOff();
  Serial.printf("[STOP] %s\n", why);
}

// สลับระหว่างโหมด GPIO ธรรมดา กับ LEDC 25 Hz
static bool setPwmMode(bool enable) {
  applyOff();
  if (enable == pwmMode) {
    Serial.printf("[OK] อยู่โหมด%sอยู่แล้ว — ปิด blower ให้แล้ว\n",
                  pwmMode ? "PWM" : "เปิด-ปิด");
    return true;
  }
  if (enable) {
    if (!ledcAttach(PIN_SUCTION_EN, pwmFreq, PWM_RES_BITS)) {
      Serial.println("[ERR] ผูก LEDC กับขาไม่สำเร็จ");
      return false;
    }
    ledcWrite(PIN_SUCTION_EN, 0);
    pwmMode = true;
    // หมายเหตุ: ledcAttach() เลือก channel/timer ให้เอง ระบุเป็น T3 ตาม §3.5 ไม่ได้
    // (ต้องใช้ ledcAttachChannel() ถึงจะเลือก channel ได้) — ในเฟิร์มแวร์ทดสอบตัวเดียว
    // โดดๆ ไม่มีผล แต่ตอนเขียนเฟิร์มแวร์จริงต้องรู้ว่าล็อก timer แบบนี้ไม่ได้
    Serial.printf("[OK] เข้าโหมด PWM %u Hz · %u-bit\n",
                  (unsigned)pwmFreq, (unsigned)PWM_RES_BITS);
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
  Serial.println(">>> เปิดแล้ว (กดปุ่มใดก็ได้แล้ว Enter เพื่อหยุดกลางคัน)");
  bool aborted = false;
  while (millis() - t0 < ms) {
    if (Serial.available()) {
      while (Serial.available()) Serial.read();
      aborted = true;
      break;
    }
    delay(5);
  }
  applyOff();
  if (aborted) { Serial.println(">>> หยุดกลางคัน — รอบนี้ใช้ไม่ได้ ต้องทำใหม่"); return; }
  const uint32_t actual = millis() - t0;
  Serial.printf(">>> ปิดแล้ว · เวลาที่เปิดจริง %lu ms (คลาด %+ld ms)\n",
                (unsigned long)actual, (long)actual - (long)ms);
  Serial.println("นับจำนวนก้อนในถังฝุ่นแล้วจดลงตาราง S4");
}

// S2 — เปิดค้างยาวเพื่อวัดอุณหภูมิ MOSFET จนนิ่ง
// MAX_ON_MS (2 นาที) สั้นเกินกว่าจะถึงสถานะคงตัวทางความร้อน จึงต้องมีคำสั่งแยก
// กด key ใดๆ เพื่อหยุดกลางคัน
static void heatRun(uint32_t minutes) {
  uint32_t ms = minutes * 60000UL;
  if (ms == 0 || ms > MAX_HEAT_MS) ms = MAX_HEAT_MS;
  Serial.printf("\n=== S2: เปิดค้าง %lu นาที เพื่อวัดอุณหภูมิ MOSFET ===\n",
                (unsigned long)(ms / 60000UL));
  Serial.println("วัดอุณหภูมิผิว MOSFET ทุก 1 นาที จนค่านิ่ง (ไม่เพิ่มเกิน 1 °C ใน 2 นาที)");
  Serial.println("เกณฑ์ §3.5: <=60 °C ผ่าน · 60-80 °C ก้ำกึ่ง · >80 °C ต้องใส่ level shifter");
  Serial.println("กดปุ่มใดก็ได้แล้ว Enter เพื่อหยุดก่อนกำหนด");
  while (Serial.available()) Serial.read();

  const uint32_t t0 = millis();
  applyOn(100);
  uint32_t nextMark = 30000;
  while (millis() - t0 < ms) {
    if (Serial.available()) {
      while (Serial.available()) Serial.read();
      applyOff();
      Serial.printf(">>> หยุดเอง ที่ %lu s\n", (unsigned long)((millis() - t0) / 1000));
      return;
    }
    if (millis() - t0 >= nextMark) {
      Serial.printf("  ผ่านไป %3lu s — จดอุณหภูมิ ณ ตอนนี้\n",
                    (unsigned long)(nextMark / 1000));
      nextMark += 30000;
    }
    delay(20);
  }
  applyOff();
  Serial.printf(">>> ครบ %lu s แล้ว ปิด blower · จดอุณหภูมิสุดท้ายและอุณหภูมิห้อง\n",
                (unsigned long)(ms / 1000));
  Serial.println("คำนวณต่อ: R_DS(on) โดยประมาณ = (T_ผิว - T_ห้อง) / 345.6  [ohm]");
  Serial.println("  ดูข้อจำกัดของสูตรนี้ที่ 08_การคำนวณ/16 §16.4 ก่อนเอาไปใช้");
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
        Serial.println("⚠ ค่านี้เป็น *ขอบบน* เพราะรวมเวลาปฏิกิริยาของคน (ปกติ 200-400 ms)");
        return;
      }
      delay(10);
    }
    applyOff();
    // ต้องโพลล์ Serial ต่อระหว่างพักด้วย ไม่งั้นถ้าผู้ใช้กด Enter ช้าไปนิด
    // ตัวอักษรจะค้างในบัฟเฟอร์แล้วไปถูกอ่านในรอบถัดไป → รายงานค่าสูงเกินจริง 1 ขั้น
    const uint32_t tRest = millis();
    while (millis() - tRest < 400) {
      if (Serial.available()) {
        while (Serial.available()) Serial.read();
        Serial.printf("\n>>> SUCTION_DUTY_MIN = %d %% ที่ %u Hz (กดหลังจบช่วงพอดี)\n",
                      d, (unsigned)pwmFreq);
        Serial.println("จดค่านี้ลงตาราง S5 — ค่านี้เป็น *ขอบบน* เพราะรวมเวลาปฏิกิริยาคน");
        return;
      }
      delay(5);
    }
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
  Serial.println("│ heat <นาที> เปิดค้างยาววัดอุณหภูมิ (ขั้น S2 · สูงสุด 10) │");
  Serial.println("│ pwm on|off  สลับโหมด PWM 25 Hz (ขั้น S5 เท่านั้น)     │");
  Serial.println("│ d <0-100>   ตั้ง duty % (เฉพาะโหมด PWM)              │");
  Serial.println("│ sweep       หา SUCTION_DUTY_MIN (ขั้น S5)            │");
  Serial.printf ("│ f <Hz>      เปลี่ยนความถี่ (%u-%u Hz เท่านั้น)         │\n",
                 (unsigned)PWM_FREQ_MIN_HZ, (unsigned)PWM_FREQ_MAX_HZ);
  Serial.println("│ b <0-40>    ตั้ง duty มอเตอร์แปรง (เพดาน 40 %)        │");
  Serial.println("│ bs          ปิดแปรง                                  │");
  Serial.println("│ bsweep      กวาด duty แปรง 10-40 % วัดกระแส (ขั้น B1) │");
  Serial.println("│ both        เปิดดูดเต็ม + แปรง 30 % พร้อมกัน          │");
  Serial.println("│ st          แสดงสถานะปัจจุบัน                        │");
  Serial.println("└──────────────────────────────────────────────────────┘");
}

static void printStatus() {
  Serial.printf("blower: โหมด %s · %u Hz · duty %d %% · %s\n",
                pwmMode ? "PWM" : "เปิด-ปิด (GPIO)", (unsigned)pwmFreq,
                dutyPercent, blowerOn ? "เปิดอยู่" : "ปิด");
  Serial.printf("แปรง : duty %d %% ≈ %.2f V เฉลี่ย (เพดาน %d %%)\n",
                brushDuty, brushDuty * 12.0f / 100.0f, BRUSH_DUTY_MAX_PCT);
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
  if (cmd == "bsweep") { brushSweep(); return; }
  if (cmd == "bs") { brushSet(0); return; }
  if (cmd.startsWith("b ")) { brushSet(cmd.substring(2).toInt()); return; }
  if (cmd == "both") {
    applyOn(100);
    brushSet(30);
    Serial.println("[OK] เปิดดูดเต็มที่ + แปรงที่ 30 % พร้อมกัน — จดกระแสรวม");
    running = true;
    runUntilMs = millis() + MAX_ON_MS;
    return;
  }

  if (cmd.startsWith("run ")) { timedRun((uint32_t)cmd.substring(4).toInt()); return; }
  if (cmd.startsWith("heat ")) { heatRun((uint32_t)cmd.substring(5).toInt()); return; }

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
      Serial.println("  1.066 W ทำให้ร้อนขึ้น +66 °C [ประมาณการ — คำนวณจาก R_DS(on) และ R_th");
      Serial.println("  ที่ไฟล์ 10 ข้อ P1/P2 ระบุว่าเป็นการเดา · M3 นี้เองคือการทดสอบเพื่อปิดข้อนั้น]");
      Serial.println("  และ blower เป็นมอเตอร์ไร้แปรงถ่านที่มี");
      Serial.println("  วงจรขับในตัว การสับไฟถี่ขนาดนั้นคือการปลุก-ดับวงจรของมันเอง");
      return;
    }
    if (pwmMode) {
      // ledcChangeFrequency คืน 0 เมื่อล้มเหลว · คืนความถี่จริงหลังปัดเศษเมื่อสำเร็จ
      // ห้ามอัปเดต pwmFreq ก่อนรู้ผล ไม่งั้นจะรายงานค่าที่ฮาร์ดแวร์ไม่ได้ใช้จริง
      const uint32_t actual = ledcChangeFrequency(PIN_SUCTION_EN, hz, PWM_RES_BITS);
      if (actual == 0) {
        Serial.printf("[ERR] ตั้ง %u Hz ที่ %u บิตไม่สำเร็จ — ยังใช้ %u Hz เหมือนเดิม\n",
                      (unsigned)hz, (unsigned)PWM_RES_BITS, (unsigned)pwmFreq);
        Serial.println("  ดู 08_การคำนวณ/17 — ตัวหาร LEDC ต้องอยู่ในช่วง [256, 262143]");
        applyOn(dutyPercent);
        return;
      }
      pwmFreq = actual;
      applyOn(dutyPercent);
      Serial.printf("[OK] ความถี่จริงที่ฮาร์ดแวร์ใช้ = %u Hz (สั่งไป %u Hz)\n",
                    (unsigned)actual, (unsigned)hz);
    } else {
      pwmFreq = hz;
      Serial.printf("[OK] ตั้งไว้ %u Hz — จะมีผลเมื่อเข้าโหมด PWM\n", (unsigned)hz);
    }
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
  // ช่องแปรง — ผูก LEDC ที่ 20 kHz ตาม §3.5 T1 · เริ่มที่ duty 0 เสมอ
  pinMode(PIN_BRUSH_PWM, OUTPUT);
  digitalWrite(PIN_BRUSH_PWM, LOW);
  brushReady = ledcAttach(PIN_BRUSH_PWM, BRUSH_FREQ_HZ, BRUSH_RES_BITS);
  if (brushReady) {
    ledcWrite(PIN_BRUSH_PWM, 0);
    Serial.printf("ช่องแปรง: GPIO %d · %u Hz · เพดาน duty %d %% (= %.2f V เฉลี่ย)\n",
                  PIN_BRUSH_PWM, (unsigned)BRUSH_FREQ_HZ, BRUSH_DUTY_MAX_PCT,
                  BRUSH_DUTY_MAX_PCT * 12.0f / 100.0f);
  } else {
    Serial.println("!!! ผูก LEDC ช่องแปรงไม่สำเร็จ — คำสั่งแปรงจะใช้ไม่ได้");
  }

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
