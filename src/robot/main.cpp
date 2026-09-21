// ─────────────────────────────────────────────────────────────
// robot/main.cpp — เฟิร์มแวร์รวม (ก้าวที่ 1: คุมผ่าน Serial เหมือนเดิม)
//
// รวมชุดทดสอบ M1 (ล้อ+เอ็นโคดเดอร์) · M2 (เซอร์โว) · M3 (blower+แปรง)
// ไว้ในเฟิร์มแวร์เดียว โดย **ไม่แตะตรรกะการทดสอบเดิมเลย** — ไฟล์นี้ทำแค่
//   1. เป็นเจ้าของ setup()/loop() ตัวจริง และอ่าน Serial ที่เดียว
//   2. ส่งคำสั่งต่อให้โมดูลตาม prefix
//   3. บังคับ interlock ก่อนส่งต่อ  ← เหตุผลหลักที่ไฟล์นี้มีอยู่
//   4. มี `stop` ตัวเดียวที่หยุดทุกระบบ
//
// ทำไมต้องมี interlock: ตอนแยกเฟิร์มแวร์ `build_src_filter` กันไม่ให้เปิด
// สองระบบพร้อมกันได้ทางกายภาพ พอรวมไฟล์ เกราะนั้นหายไป
// ที่มาของกติกาและตัวเลขทั้งหมด: 08_การคำนวณ/18_interlock_เฟิร์มแวร์รวม.md
//
// 🔴 ยังไม่ได้บิลด์ทดสอบ — เครื่อง Mac ที่เขียนไฟล์นี้ไม่มี PlatformIO ติดตั้ง
// ─────────────────────────────────────────────────────────────
#include <Arduino.h>
#include "comm.h"      // ลิงก์ Pi 5 บน UART0 — ขั้น C: cap / cs
#include "mission.h"   // ภารกิจ 1 รอบแบบ script — ขั้น D: mis …
#include "manual.h"    // โหมดขับเองจาก Pi — ขั้น E: $V/$S/$E/$C
#include "wdt.h"       // Task WDT 1 s (C29) — loop() ค้าง → รีบูต → ล้อ coast
#include "../pins.h"   // ขาทุกขาอยู่ที่เดียว
#include "servo_x.h"   // เซอร์โวตัวที่ 2 แกน X ของกล้อง (GPIO18 · C30)
#include "tft.h"       // จอกลม GC9A01 (C32)

// ── จุดต่อของแต่ละโมดูล (นิยามอยู่ท้าย src/<ชุด>/main.cpp) ────
void motorSetup();  void motorTick();  void motorCommand(const String&);
void motorStop(const char*);  void motorHelp();  bool motorRunning();

void blowerSetup(); void blowerTick(); void blowerCommand(const String&);
void blowerStop(const char*); void blowerHelp(); void blowerStatus();
bool blowerOnNow(); bool brushOnNow();

void servoSetup();  void servoTick();  void servoCommand(const String&);
void servoStop(const char*);  void servoHelp();  bool servoAttachedNow();

// ── ขาที่ต้องกดลง LOW ให้เร็วที่สุดตอนบูต ────────────────────
// ต้องตรงกับ §3.2 และ config ของแต่ละโมดูล — ที่นี่ประกาศซ้ำโดยตั้งใจ
// เพราะ include config ทั้งสองไฟล์พร้อมกันจะชนกันที่ชื่อ PWM_MAX / PWM_RES_BITS
//   PIN_SUCTION_EN = blower_test/config.h  ·  PIN_BRUSH_PWM = blower_test/config.h
//   PIN_SERVO      = servo_test/main.cpp
// ⚠ ถ้าแก้ขาในไฟล์พวกนั้น ต้องแก้ที่นี่ด้วย
constexpr int GATE_SUCTION = PIN_SUCTION_EN;    // ../pins.h — ดึงเกตลง LOW ให้เร็วที่สุดตอนบูต
constexpr int GATE_BRUSH   = PIN_BRUSH_PWM;
constexpr int GATE_SERVO   = PIN_SERVO_MAST;

// ── ค่าเวลาของ interlock (ไฟล์ 18 §18.3 — ทั้งคู่เป็น [ประมาณการ]) ──
constexpr uint32_t SETTLE_MS        = 300;   // เว้นระหว่างแปรง ↔ เซอร์โว (ราง 5 V)
constexpr uint32_t BLOWER_SPINUP_MS = 1000;  // เว้นหลังเปิด blower ก่อนสั่งล้อ (ราง 12 V)

static uint32_t lastServoCmdMs   = 0;
static uint32_t lastBrushStartMs = 0;
static uint32_t lastBlowerOnMs   = 0;

// ── จำแนกว่าคำสั่งนั้น "จ่ายไฟให้อะไร" ────────────────────────
// ดูจากคำแรกของคำสั่งย่อยเท่านั้น ชุดคำสั่งอยู่ใน printHelp() ของแต่ละโมดูล
static String firstWord(const String& s) {
  const int sp = s.indexOf(' ');
  return (sp < 0) ? s : s.substring(0, sp);
}
// ค่าตัวเลขตัวแรกหลังคำสั่ง (ไม่มี = -1) — ใช้แยก "สั่งให้หมุน" ออกจาก "สั่งให้หยุด"
// เช่น `b 0` กับ `d 0` คือการสั่งหยุด ต้องทำได้เสมอ ห้ามให้ interlock บล็อก
static int firstArgInt(const String& c) {
  const int sp = c.indexOf(' ');
  if (sp < 0) return -1;
  String rest = c.substring(sp + 1);
  rest.trim();
  return rest.length() ? rest.toInt() : -1;
}
static bool isBrushStart(const String& c) {
  const String w = firstWord(c);
  if (w == "b") return firstArgInt(c) > 0;
  return w == "bsweep" || w == "both";
}
static bool isBlowerStart(const String& c) {
  const String w = firstWord(c);
  if (w == "d") return firstArgInt(c) > 0;
  return w == "on" || w == "run" || w == "heat" || w == "sweep" || w == "both";
}
static bool isWheelMove(const String& c) {
  const String w = firstWord(c);
  return w == "d" || w == "r" || w == "dl" || w == "dr" ||
         w == "t2" || w == "t2l" || w == "t2r" || w == "t3" || w == "t5";
}
static bool isServoMove(const String& c) {
  const String w = firstWord(c);
  return w == "v1" || w == "v2" || w == "hold" || w == "us" ||
         w == "c" || w == "+" || w == "-";
}

static void stopAllSystems(const char* why) {
  Serial.printf("\n>>> หยุดทุกระบบ: %s\n", why);
  missionAbort(why);   // ก่อนโมดูล ไม่งั้น mission จะสั่งเปิดกลับใน tick ถัดไป
  manualHalt(why);     // เช่นกัน — ไม่งั้น manual จะเขียน duty ทับใน tick ถัดไป
  motorStop(why);
  blowerStop(why);
  servoStop(why);
  servoXRelease(why);
}

// คืน true ถ้าอนุญาตให้ส่งคำสั่งต่อ · soft = อนุญาตให้ข้ามกติกา R4 ได้ด้วย `force`
static bool interlockAllows(char sys, const String& sub, bool force) {
  const uint32_t now = millis();

  // ── R1 · ราง 5 V "มอเตอร์เล็ก" — แปรง inrush 3.0 A + เซอร์โว stall
  //    ไฟล์ 18 §18.2: เซอร์โว 2 ตัว = 8.0 A เกินพิกัด buck 6 A อยู่ 33 %
  //    แม้เซอร์โว 1 ตัวก็เหลือแค่ 0.5 A (8.3 %) ซึ่งน้อยกว่าความคลาดเคลื่อนของตัวเลขเอง
  //    → กติกานี้ห้ามข้าม ไม่ว่ากรณีใด
  if (sys == 'b' && isBrushStart(sub)) {
    if (servoAttachedNow()) {
      Serial.println("[R1] ปฏิเสธ: เซอร์โวยังจับสัญญาณอยู่ — สั่ง `sv off` ก่อน");
      Serial.println("     เหตุผล: แปรง inrush 3.0 A + เซอร์โว stall บนราง 5 V เดียวกัน (ไฟล์ 18 §18.2)");
      return false;
    }
    if (now - lastServoCmdMs < SETTLE_MS) {
      Serial.printf("[R1] ปฏิเสธ: เพิ่งสั่งเซอร์โวไป — รออีก %lu ms\n",
                    (unsigned long)(SETTLE_MS - (now - lastServoCmdMs)));
      return false;
    }
  }
  if (sys == 's' && isServoMove(sub)) {
    if (brushOnNow()) {
      Serial.println("[R1] ปฏิเสธ: แปรงยังหมุนอยู่ — สั่ง `bl bs` ก่อน");
      return false;
    }
    if (now - lastBrushStartMs < SETTLE_MS) {
      Serial.printf("[R1] ปฏิเสธ: เพิ่งสั่งแปรงไป — รออีก %lu ms\n",
                    (unsigned long)(SETTLE_MS - (now - lastBrushStartMs)));
      return false;
    }
  }

  // ── R2 · ราง 12 V — ล้อพีค 5.0 A + blower 2.4 A = 7.4 A บน buck 8 A (เหลือ 7.5 %)
  //    และ inrush ของ blower ยังไม่เคยวัด → ห้ามให้ช่วงออกตัวทั้งสองซ้อนกัน
  if (sys == 'b' && isBlowerStart(sub) && motorRunning()) {
    Serial.println("[R2] ปฏิเสธ: ล้อกำลังหมุนอยู่ — สั่ง `m s` ก่อนเปิด blower");
    Serial.println("     เหตุผล: ราง 12 V เหลือ margin 0.6 A และ inrush ของ blower ยังไม่วัด (ไฟล์ 18 §18.2)");
    return false;
  }
  if (sys == 'm' && isWheelMove(sub) && (now - lastBlowerOnMs < BLOWER_SPINUP_MS)) {
    Serial.printf("[R2] ปฏิเสธ: blower เพิ่งออกตัว — รออีก %lu ms\n",
                  (unsigned long)(BLOWER_SPINUP_MS - (now - lastBlowerOnMs)));
    return false;
  }

  // ── R4 · ความถูกต้องของผลวัด (กติกาแบบอ่อน — ข้ามได้ด้วย `force`)
  //    โหลดอื่นทำรางตก (C9-a เหลือ +0.09 V ที่พีค) แล้ว rpm/กระแสที่วัดได้เพี้ยน
  if (sys == 'm' && isWheelMove(sub) && (blowerOnNow() || brushOnNow())) {
    if (!force) {
      Serial.println("[R4] ปฏิเสธ: blower หรือแปรงเปิดอยู่ ผลวัด rpm จะเพี้ยนเพราะรางตก");
      Serial.println("     ถ้าตั้งใจจริง (เช่น เทสรวมระบบ) ใช้:  force m <คำสั่ง>");
      return false;
    }
    Serial.println("[R4] ข้ามกติกาด้วย force — ตัวเลขที่วัดรอบนี้ห้ามเอาไปใส่ใบบันทึกผล M1");
  }
  if (sys == 'b' && (isBlowerStart(sub) || isBrushStart(sub)) && motorRunning() && !force) {
    Serial.println("[R4] ปฏิเสธ: ล้อกำลังวัดอยู่ — หยุดล้อก่อน หรือใช้ force");
    return false;
  }
  return true;
}

// ให้ comm.cpp เรียกได้ (E-STOP จาก Pi = เส้นทางเดียวกับ `stop` ในคอนโซล)
static uint32_t estopMs = 0;                 // เวลาที่ E-STOP ล่าสุด — จอโชว์ "E-STOP" 3 s (ไม่มี latch: คำสั่ง $V ถัดไปขับต่อได้ตามเดิม)
void robotEmergencyStop(const char* why) { stopAllSystems(why); estopMs = millis(); }
bool robotEstopped() { return estopMs && millis() - estopMs < 3000; }

static void printMergedHelp() {
  Serial.println();
  Serial.println("╔═ เฟิร์มแวร์รวม MRC-001 ═══════════════════════════════╗");
  Serial.println("║ พิมพ์ prefix นำหน้าคำสั่งเดิมของแต่ละชุด               ║");
  Serial.println("║   m  <คำสั่ง>   M1 ล้อ + เอ็นโคดเดอร์                  ║");
  Serial.println("║   sv <คำสั่ง>   M2 เซอร์โวเสายก                        ║");
  Serial.println("║   bl <คำสั่ง>   M3 blower + แปรง                       ║");
  Serial.println("║ คำสั่งกลาง                                             ║");
  Serial.println("║   stop หรือ !   หยุดทุกระบบทันที                       ║");
  Serial.println("║   st            สถานะรวม                               ║");
  Serial.println("║   il            ตาราง interlock ที่บังคับอยู่           ║");
  Serial.println("║   ? m | ? sv | ? bl   คำสั่งของชุดนั้น                 ║");
  Serial.println("║   cap           ส่ง CAPTURE_REQ ไป Pi 5 แล้วรอ $K (5 s) ║");
  Serial.println("║   cs            สถานะลิงก์ Pi 5                         ║");
  Serial.println("║   mis <คำสั่ง>  ภารกิจ 1 รอบแบบ script (? mis)          ║");
  Serial.println("║   force <คำสั่ง>  ข้ามกติกา R4 เท่านั้น (R1/R2 ข้ามไม่ได้)║");
  Serial.println("╚════════════════════════════════════════════════════════╝");
  Serial.println("ตัวอย่าง:  m t1   ·   sv v1   ·   bl on   ·   force m d 400");
}

static void printInterlock() {
  Serial.println();
  Serial.println("กติกาที่บังคับอยู่ (ที่มา: 08_การคำนวณ/18 §18.3)");
  Serial.println("  R1 แปรง ↔ เซอร์โว : ห้ามซ้อนกัน · เว้น 300 ms  [ราง 5 V/6 A · เกิน 33% ถ้าซ้อน]");
  Serial.println("  R2 blower ↔ ล้อ   : ห้ามออกตัวซ้อนกัน · เว้น 1000 ms  [ราง 12 V/8 A · เหลือ 7.5%]");
  Serial.println("  R4 วัด M1         : ห้ามเปิด blower/แปรงระหว่างวัด rpm  (ข้ามได้ด้วย force)");
  Serial.println("  R5 stop           : หยุดทุกระบบเสมอ");
  Serial.println("  R6 dead-man       : ของเดิมแต่ละชุดยังทำงานอยู่ (ล้อ 25 s · blower 60 s)");
  Serial.printf ("สถานะตอนนี้: ล้อ %s · blower %s · แปรง %s · เซอร์โว %s\n",
                 motorRunning() ? "วิ่ง" : "หยุด", blowerOnNow() ? "เปิด" : "ปิด",
                 brushOnNow() ? "หมุน" : "หยุด", servoAttachedNow() ? "จับสัญญาณ" : "ปล่อย");
}

static void route(String line) {
  line.trim();
  if (!line.length()) return;

  bool force = false;
  if (line.startsWith("force ")) { force = true; line = line.substring(6); line.trim(); }

  if (line == "stop" || line == "!") { stopAllSystems("ผู้ใช้สั่ง stop"); return; }
  if (line == "?")  { printMergedHelp(); return; }
  if (line == "sx" || line.startsWith("sx ")) { servoXCommand(line.substring(2)); return; }   // เซอร์โว X: sx <us> | sx off | sx st
  if (line == "il") { printInterlock(); return; }
  if (line == "cap") { commRequestCapture(); return; }
  if (line == "cs")  { commPrintStatus(); return; }
  if (line == "? mis") { missionHelp(); return; }
  if (line.startsWith("mis ")) { String sub = line.substring(4); sub.trim(); missionCommand(sub); return; }
  if (line == "st") {
    printInterlock();
    blowerStatus();
    return;
  }
  if (line == "? m")  { motorHelp();  return; }
  if (line == "? sv") { servoHelp();  return; }
  if (line == "? bl") { blowerHelp(); return; }

  char sys = 0;
  String sub;
  if (line.startsWith("m "))       { sys = 'm'; sub = line.substring(2); }
  else if (line.startsWith("sv ")) { sys = 's'; sub = line.substring(3); }
  else if (line.startsWith("bl ")) { sys = 'b'; sub = line.substring(3); }
  else {
    Serial.printf("[ERR] ต้องมี prefix นำหน้า (m / sv / bl) — ได้รับ \"%s\"\n", line.c_str());
    Serial.println("      พิมพ์ ? เพื่อดูวิธีใช้");
    return;
  }
  sub.trim();
  if (!sub.length()) { Serial.println("[ERR] ไม่มีคำสั่งหลัง prefix"); return; }

  if (!interlockAllows(sys, sub, force)) return;

  // จำเวลาไว้ "ก่อน" ส่งต่อ เพราะ routine ของโมดูลเป็นแบบ blocking
  // ถ้าจับเวลาหลังจบ ช่วงที่โหลดกำลังกินไฟจริงจะไม่ถูกนับ
  if (sys == 's' && isServoMove(sub))   lastServoCmdMs   = millis();
  if (sys == 'b' && isBrushStart(sub))  lastBrushStartMs = millis();
  if (sys == 'b' && isBlowerStart(sub)) lastBlowerOnMs   = millis();

  switch (sys) {
    case 'm': motorCommand(sub);  break;
    case 's': servoCommand(sub);  break;
    case 'b': blowerCommand(sub); break;
  }
}

void setup() {
  // ── กดขาเกตทั้งสามลง LOW ก่อนอย่างอื่นทุกอย่าง ──
  // ต้องมาก่อน Serial.begin() + delay(2000) ไม่งั้นเกตลอยนาน ~2.3 วินาที
  // (ตัวที่กันจริงในช่วง ~300 ms แรกของ bootloader คือ pull-down 10 kΩ ตาม §3.2
  //  ไม่ใช่โค้ด — โค้ดรับช่วงต่อจากนั้น)
  pinMode(GATE_SUCTION, OUTPUT); digitalWrite(GATE_SUCTION, LOW);
  pinMode(GATE_BRUSH,   OUTPUT); digitalWrite(GATE_BRUSH,   LOW);
  pinMode(GATE_SERVO,   OUTPUT); digitalWrite(GATE_SERVO,   LOW);

  Serial.begin(115200);
  // C29 (16 ก.ย. 2026): คอนโซล USB CDC จะ "บล็อก" ตอนเขียนถ้าโฮสต์เปิดพอร์ตค้างไว้แต่ไม่อ่าน (buffer เต็ม → รอ timeout)
  // วัดจริง: Serial.printf ~100 B ทำให้ loop() ค้าง ~2 s → #T หาย · $V ไม่ถูกอ่าน · deadman ตัด
  // ตั้ง TX timeout = 0 → ถ้าส่งไม่ได้ให้ทิ้ง log แทนที่จะหยุดหุ่น (คอนโซลเป็นของเสริม ลิงก์ Pi เป็นของจริง)
  Serial.setTxTimeoutMs(0);
  // เดิม delay(2000) รอ USB CDC — วัดจริง 16 ก.ย.: รีเซ็ต → #T แรก 2.04 s ทั้งที่ setup เอง ~40 ms (§19.8.1)
  // บนหุ่นคือ "ตาบอด 2 s ทุกครั้งที่รีบูต/WDT" แลกกับบรรทัดแรกบนคอนโซล → ตัดออก (พิมพ์ ? เพื่อดู help ทีหลังได้)

  Serial.println();
  Serial.println("════════════════════════════════════════════════════════");
  Serial.println(" MRC-001 · เฟิร์มแวร์รวม (M1 + M2 + M3) — คุมผ่าน Serial");
  Serial.println("════════════════════════════════════════════════════════");

  // เรียง blower ก่อน เพราะ setup ของมันเป็นตัวเดียวที่ผูก LEDC ค้างไว้ (ช่องแปรง)
  blowerSetup();
  servoSetup();
  servoXSetup();
  tftSetup();
  motorSetup();
  commSetup();   // UART0 ไป Pi 5 — ไม่แตะขาของสามชุดข้างบน (43/44 จองไว้ตาม §3.2)
  missionSetup();
  manualSetup();

  printInterlock();
  printMergedHelp();
  // บอกเหตุผลที่บูตทั้งคอนโซลและ Pi (#E BOOT,<reason>) — Pi ใช้แยกว่าเป็น WDT/brownout/เปิดเครื่อง และส่ง $L ซ้ำ
  Serial.printf("[boot] reset reason: %s\n", wdtResetReason());
  commSendEvent("BOOT", wdtResetReason());
  Serial.printf("[wdt] task WDT %lu ms: %s\n", (unsigned long)WDT_TIMEOUT_MS, wdtSetup() ? "on" : "FAILED");
}

void loop() {
  wdtFeed();                                   // ต้องถึงบรรทัดนี้ทุก < 1 s ไม่งั้นรีบูต
  static String buf;
  while (Serial.available()) {
    const char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (buf.length()) {
        if (buf.startsWith("hang")) {          // ทดสอบ WDT: บล็อก loop() จงใจ (ไม่ suspend) — ต้องรีบูตถ้า > 1 s
          const uint32_t ms = buf.length() > 5 ? buf.substring(5).toInt() : 3000;
          Serial.printf("[wdt] hang %lu ms (busy-wait) — ถ้า > %lu ms ต้องรีบูตด้วย TASK_WDT\n", (unsigned long)ms, (unsigned long)WDT_TIMEOUT_MS);
          const uint32_t t0 = millis(); while (millis() - t0 < ms) { }
          Serial.println("[wdt] hang จบโดยไม่รีบูต");
        } else {
          wdtSuspend();                        // คำสั่งคอนโซล (ชุดทดสอบ m/sv/bl) บล็อกโดยตั้งใจได้ — งานบนโต๊ะ
          route(buf);
          wdtResume();
        }
        buf = "";
      }
    }
    else buf += c;
  }

  // ตัวเฝ้าของทั้งสามระบบยังทำงานเหมือนเดิมทุกประการ (R6)
  motorTick();
  blowerTick();
  servoTick();
  servoXTick();
  tftTick();
  commTick();
  missionTick();   // หลัง commTick เพื่อให้เห็น $K ในรอบเดียวกัน
  manualTick();    // เขียน duty ล้อทุก 10 ms ตาม setpoint จาก $V (หรือ 0 เมื่อ deadman)

  delay(10);
}
