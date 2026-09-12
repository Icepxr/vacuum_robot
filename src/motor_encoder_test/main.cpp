// ─────────────────────────────────────────────────────────────
// M1 — ชุดทดสอบมอเตอร์ JGB37-520 + เอ็นโคดเดอร์ Hall
// ไดรเวอร์ชั่วคราว: L298N (DRV8871 ยังไม่มาถึง)
//
// เป้าหมายของการเทสนี้ = ปิด 4 ข้อที่ยังเป็น [คำนวณ] ให้เป็น [วัดจริง]
//   G1  อัตราทดเกียร์ 56:1        → §1.1 (ตอนนี้เป็น [คำนวณ/อนุมาน])
//   G2  2,464 counts ต่อรอบล้อ     → §1.4
//   G3  178 rpm ไม่มีโหลด          → §3.6 [สเปก] ยังไม่วัด
//   C11 กระแสมอเตอร์ 0.65 หรือ 1.0 A → ไฟล์ 10 ข้อ C11
//
// วิธีใช้: เปิด serial monitor 115200 แล้วพิมพ์ ? เพื่อดูคำสั่ง
// ขั้นตอนเต็ม + ตารางกรอกผล: 03_ผลการทดสอบ/M1_มอเตอร์และเอ็นโคดเดอร์.md
// ─────────────────────────────────────────────────────────────
#include <Arduino.h>

#include "config.h"
#include "encoder.h"
#include "motor.h"

static Motor motL, motR;
static QuadEncoder encL, encR;

static uint32_t pwmFreq = PWM_FREQ_DEFAULT_HZ;
static uint32_t lastCommandMs = 0;
static bool running = false;
static uint32_t runUntilMs = 0;

// ── ตัวช่วย ───────────────────────────────────────────────────

// rpm ของ "เพลาออก" จากจำนวน counts ที่นับได้ในช่วงเวลา dt
static double rpmFromCounts(int64_t counts, uint32_t dtMs) {
  if (dtMs == 0) return 0.0;
  const double rev = static_cast<double>(counts) / COUNTS_PER_REV;
  return rev * 60000.0 / static_cast<double>(dtMs);
}

static void stopAll(const char* why) {
  motL.setDuty(0);
  motR.setDuty(0);
  motL.brake();
  motR.brake();
  running = false;
  Serial.printf("[STOP] %s\n", why);
}

// ไล่ duty ขึ้นช้าๆ เพื่อไม่ให้กระแสกระชากตอนออกตัว (§3.3 stall 2–3 A)
static void rampTo(int permilleL, int permilleR) {
  const uint32_t t0 = millis();
  const int startL = motL.duty(), startR = motR.duty();
  while (true) {
    const uint32_t el = millis() - t0;
    if (el >= RAMP_MS) break;
    const double k = static_cast<double>(el) / RAMP_MS;
    motL.setDuty(startL + static_cast<int>((permilleL - startL) * k));
    motR.setDuty(startR + static_cast<int>((permilleR - startR) * k));
    delay(5);
  }
  motL.setDuty(permilleL);
  motR.setDuty(permilleR);
}

// วิ่งที่ duty คงที่ "แยกซ้าย/ขวา" แล้วคืน rpm ทั้งสองข้าง
// ตรวจ stall เฉพาะข้างที่ถูกสั่ง (duty != 0) — ข้างที่สั่ง 0 ไม่ต้องขยับ จึงไม่นับเป็น stall
// คืน false ถ้าตัดเพราะสงสัยว่า stall
static bool runAndMeasureLR(int permilleL, int permilleR, uint32_t holdMs,
                            double* rpmL, double* rpmR, int64_t* cntL, int64_t* cntR) {
  if (holdMs > MAX_RUN_MS) holdMs = MAX_RUN_MS;
  rampTo(permilleL, permilleR);

  encL.zero();
  encR.zero();
  const uint32_t t0 = millis();
  uint32_t lastCheck = t0;
  int64_t lastL = 0, lastR = 0;
  bool ok = true;

  while (millis() - t0 < holdMs) {
    delay(20);
    if (millis() - lastCheck >= STALL_CHECK_MS) {
      const int64_t cl = encL.count(), cr = encR.count();
      const bool stalledL = (permilleL != 0) && (llabs(cl - lastL) < STALL_COUNT_MIN);
      const bool stalledR = (permilleR != 0) && (llabs(cr - lastR) < STALL_COUNT_MIN);
      if (stalledL || stalledR) {
        stopAll("สงสัย stall — เอ็นโคดเดอร์แทบไม่ขยับ ตัดไฟมอเตอร์แล้ว");
        ok = false;
        break;
      }
      lastL = cl;
      lastR = cr;
      lastCheck = millis();
    }
  }

  const uint32_t dt = millis() - t0;
  *cntL = encL.count();
  *cntR = encR.count();
  *rpmL = rpmFromCounts(*cntL, dt);
  *rpmR = rpmFromCounts(*cntR, dt);

  rampTo(0, 0);
  motL.brake();
  motR.brake();
  return ok;
}

// เวอร์ชันเดิม: สั่งเท่ากันทั้งสองข้าง — T3/T5 และคำสั่ง r ยังเรียกตัวนี้
static bool runAndMeasure(int permille, uint32_t holdMs, double* rpmL, double* rpmR,
                          int64_t* cntL, int64_t* cntR) {
  return runAndMeasureLR(permille, permille, holdMs, rpmL, rpmR, cntL, cntR);
}

// ── ขั้นทดสอบ ─────────────────────────────────────────────────

// T1 — หมุนเพลาออกด้วยมือครบ 1 รอบพอดี ต้องได้ 2,464 counts
// นี่คือการยืนยันอัตราทด 56:1 วิธีที่ 2 ตาม §3.6
static void testHandTurn() {
  Serial.println();
  Serial.println("=== T1: ยืนยันอัตราทดด้วยการหมุนมือ ===");
  Serial.printf("คาดหวัง %d counts ต่อ 1 รอบเพลาออก (= %d PPR x 4 x %d)\n",
                COUNTS_PER_REV, ENC_PPR, GEAR_RATIO);
  Serial.println("ทำเครื่องหมายบนเพลา แล้วหมุนช้าๆ ครบ 1 รอบพอดี · กด Enter เมื่อเสร็จ");
  Serial.println("(ห้ามจ่ายไฟมอเตอร์ตอนนี้ — หมุนมืออย่างเดียว)");
  encL.zero();
  encR.zero();
  while (!Serial.available()) {
    Serial.printf("\r  L = %8lld   R = %8lld        ", encL.count(), encR.count());
    delay(150);
  }
  while (Serial.available()) Serial.read();
  const int64_t l = encL.count(), r = encR.count();
  Serial.println();
  Serial.printf("ผล: L = %lld counts  (%.1f%% ของค่าที่คาด)\n", l, 100.0 * l / COUNTS_PER_REV);
  Serial.printf("    R = %lld counts  (%.1f%% ของค่าที่คาด)\n", r, 100.0 * r / COUNTS_PER_REV);
  Serial.println("อัตราทดที่อนุมานกลับ (ถ้า PPR = 11 จริง):");
  Serial.printf("    L -> %.1f : 1     R -> %.1f : 1\n",
                fabs(static_cast<double>(l)) / (ENC_PPR * 4),
                fabs(static_cast<double>(r)) / (ENC_PPR * 4));
  Serial.println("จดค่านี้ลงตาราง T1 ในเอกสารเทส");
}

// T2 — ตรวจทิศ: duty บวกต้องได้ counts บวก ทั้งสองข้าง
static void testDirection() {
  Serial.println();
  Serial.println("=== T2: ตรวจทิศทางการหมุนกับเครื่องหมายของ counts ===");
  Serial.println("จะสั่งเดินหน้า 25% 2 วินาที แล้วถอยหลัง 25% 2 วินาที");
  double rl, rr;
  int64_t cl, cr;
  runAndMeasure(250, 2000, &rl, &rr, &cl, &cr);
  Serial.printf("เดินหน้า 25%%: L %+lld counts (%.1f rpm) · R %+lld counts (%.1f rpm)\n",
                cl, rl, cr, rr);
  delay(500);
  runAndMeasure(-250, 2000, &rl, &rr, &cl, &cr);
  Serial.printf("ถอยหลัง 25%%: L %+lld counts (%.1f rpm) · R %+lld counts (%.1f rpm)\n",
                cl, rl, cr, rr);
  Serial.println("เกณฑ์ผ่าน: เดินหน้าได้ค่าบวกทั้งคู่ · ถอยหลังได้ค่าลบทั้งคู่");
  Serial.println("ถ้าข้างไหนเครื่องหมายกลับ = สาย Hall A/B ข้างนั้นสลับกัน");
  Serial.println("  แก้ได้ 2 ทาง: สลับสายจริง หรือ ตั้ง invert=true ตอน encX.begin()");
}

// T2 แยกข้าง — สั่งทีละล้อ อีกข้างสั่ง 0 (ไม่ถูกนับเป็น stall)
static void testDirectionOne(bool isLeft) {
  const char* name = isLeft ? "ซ้าย" : "ขวา";
  Serial.println();
  Serial.printf("=== T2 เฉพาะล้อ%s: ตรวจทิศทางการหมุนกับเครื่องหมายของ counts ===\n", name);
  Serial.printf("จะสั่งล้อ%s เดินหน้า 25%% 2 วินาที แล้วถอยหลัง 25%% 2 วินาที (อีกข้างไม่สั่ง)\n", name);
  Serial.println(">>> ดูด้วยตาด้วยว่าเพลาหมุนไปทางไหนจริง <<<");
  double rl, rr;
  int64_t cl, cr;

  runAndMeasureLR(isLeft ? 250 : 0, isLeft ? 0 : 250, 2000, &rl, &rr, &cl, &cr);
  Serial.printf("เดินหน้า 25%%: L %+lld counts (%.1f rpm) · R %+lld counts (%.1f rpm)\n",
                cl, rl, cr, rr);
  delay(500);
  runAndMeasureLR(isLeft ? -250 : 0, isLeft ? 0 : -250, 2000, &rl, &rr, &cl, &cr);
  Serial.printf("ถอยหลัง 25%%: L %+lld counts (%.1f rpm) · R %+lld counts (%.1f rpm)\n",
                cl, rl, cr, rr);
  Serial.printf("เกณฑ์ผ่าน (ดูเฉพาะข้าง%s): เดินหน้า = บวก · ถอยหลัง = ลบ\n", name);
}

// T3 — กวาด duty แล้ววัด rpm → ได้เส้นโค้ง duty→rpm ของ "ชุด L298N"
// ⚠ เส้นโค้งนี้ย้ายไปใช้กับ DRV8871 ไม่ได้ ดูเหตุผลใน 08_การคำนวณ/15
static void testDutySweep() {
  Serial.println();
  Serial.println("=== T3: กวาด duty วัด rpm ===");
  Serial.printf("PWM = %u Hz · แต่ละจุดวิ่ง 3 วินาที\n", (unsigned)pwmFreq);
  Serial.println("duty_%,rpm_L,rpm_R,counts_L,counts_R,v_L_m_s,v_R_m_s");
  for (int d = 200; d <= 1000; d += 100) {
    double rl, rr;
    int64_t cl, cr;
    if (!runAndMeasure(d, 3000, &rl, &rr, &cl, &cr)) break;
    const double vL = rl / 60.0 * PI * WHEEL_DIAMETER_M;
    const double vR = rr / 60.0 * PI * WHEEL_DIAMETER_M;
    Serial.printf("%d,%.1f,%.1f,%lld,%lld,%.4f,%.4f\n", d / 10, rl, rr, cl, cr, vL, vR);
    delay(800);
  }
  Serial.println("จบ T3 — คัดลอกทั้งบล็อก CSV ไปแปะในเอกสารเทส");
  Serial.printf("อ้างอิง: สเปกบอก %.0f rpm ที่ 12 V ไม่มีโหลด → v = %.4f m/s\n",
                RPM_NOLOAD_SPEC, RPM_NOLOAD_SPEC / 60.0 * PI * WHEEL_DIAMETER_M);
}

// T5 — พิสูจน์ว่ากลไกกันตัวนับล้นทำงานจริง (§1.5)
static void testOverflow() {
  Serial.println();
  Serial.println("=== T5: ทดสอบกันตัวนับ PCNT ล้น ===");
  Serial.printf("วิ่ง 100%% นาน 15 วินาที · ที่ %d counts ต่อรอบ ตัวนับ 16 บิตจะชน\n",
                COUNTS_PER_REV);
  Serial.printf("watch point ที่ +/-%d อย่างน้อย 1 ครั้ง ถ้ากลไกทำงานถูก\n", (int)PCNT_LIMIT);
  double rl, rr;
  int64_t cl, cr;
  runAndMeasure(1000, 15000, &rl, &rr, &cl, &cr);
  Serial.printf("counts สะสม: L = %lld (ชน watch point %u ครั้ง)\n", cl, (unsigned)encL.wrapCount());
  Serial.printf("             R = %lld (ชน watch point %u ครั้ง)\n", cr, (unsigned)encR.wrapCount());
  Serial.println("เกณฑ์ผ่าน: counts เพิ่มขึ้นเรื่อยๆ ไม่กระโดดกลับ และ wrap >= 1");
  Serial.println("ถ้า wrap = 0 แปลว่ายังไม่เร็วพอจะทดสอบ — ให้ยกล้อลอยแล้วลองใหม่");
}

// ── คำสั่ง ────────────────────────────────────────────────────

static void printHelp() {
  Serial.println();
  Serial.println("┌─ คำสั่ง ─────────────────────────────────────────────┐");
  Serial.println("│ ?          แสดงคำสั่ง                                │");
  Serial.println("│ c          อ่าน counts ปัจจุบัน                       │");
  Serial.println("│ z          รีเซ็ต counts เป็น 0                       │");
  Serial.println("│ t1         T1 หมุนมือ 1 รอบ ยืนยันอัตราทด 56:1        │");
  Serial.println("│ t2         T2 ตรวจทิศทาง (สองล้อพร้อมกัน)            │");
  Serial.println("│ t2l / t2r  T2 ทีละล้อ (ซ้าย / ขวา)                    │");
  Serial.println("│ dl <‰> dr <‰>  สั่ง duty ทีละล้อ                      │");
  Serial.println("│ t3         T3 กวาด duty 20-100% วัด rpm (CSV)         │");
  Serial.println("│ t5         T5 ทดสอบกันตัวนับล้น                       │");
  Serial.println("│ d <‰>      สั่ง duty ค้างไว้ -1000..1000              │");
  Serial.println("│ r <‰> <ms> วิ่ง duty ตามเวลาที่กำหนดแล้ววัด rpm       │");
  Serial.println("│ f <Hz>     เปลี่ยนความถี่ PWM (T6: เทียบ 1k กับ 20k)  │");
  Serial.println("│ s          หยุด (เบรก)                               │");
  Serial.println("└──────────────────────────────────────────────────────┘");
  Serial.printf("ตอนนี้: PWM %u Hz · %d counts/รอบ · ล้อ %.0f mm\n",
                (unsigned)pwmFreq, COUNTS_PER_REV, WHEEL_DIAMETER_M * 1000);
}

static void handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  lastCommandMs = millis();

  if (cmd == "?" || cmd == "h") { printHelp(); return; }
  if (cmd == "s") { stopAll("สั่งหยุดเอง"); return; }
  if (cmd == "z") { encL.zero(); encR.zero(); Serial.println("[OK] รีเซ็ต counts แล้ว"); return; }
  if (cmd == "c") {
    Serial.printf("L = %lld counts (%.3f รอบ) · R = %lld counts (%.3f รอบ)\n",
                  encL.count(), static_cast<double>(encL.count()) / COUNTS_PER_REV,
                  encR.count(), static_cast<double>(encR.count()) / COUNTS_PER_REV);
    return;
  }
  if (cmd == "t1") { testHandTurn(); return; }
  if (cmd == "t2") { testDirection(); return; }
  if (cmd == "t2l") { testDirectionOne(true); return; }
  if (cmd == "t2r") { testDirectionOne(false); return; }
  if (cmd == "t3") { testDutySweep(); return; }
  if (cmd == "t5") { testOverflow(); return; }

  if (cmd.startsWith("dl ") || cmd.startsWith("dr ")) {
    const bool isLeft = cmd.startsWith("dl ");
    const int d = cmd.substring(3).toInt();
    rampTo(isLeft ? d : 0, isLeft ? 0 : d);
    running = (d != 0);
    runUntilMs = millis() + MAX_RUN_MS;
    Serial.printf("[OK] duty %s = %d‰ (อีกข้าง 0 · จะตัดเองใน %u ms)\n",
                  isLeft ? "ซ้าย" : "ขวา", d, (unsigned)MAX_RUN_MS);
    return;
  }
  if (cmd.startsWith("d ")) {
    const int d = cmd.substring(2).toInt();
    rampTo(d, d);
    running = (d != 0);
    runUntilMs = millis() + MAX_RUN_MS;
    Serial.printf("[OK] duty = %d‰ (จะตัดเองใน %u ms)\n", d, (unsigned)MAX_RUN_MS);
    return;
  }
  if (cmd.startsWith("f ")) {
    pwmFreq = cmd.substring(2).toInt();
    motL.setFrequency(pwmFreq);
    motR.setFrequency(pwmFreq);
    Serial.printf("[OK] PWM = %u Hz (ค่าที่จะใช้จริงกับ DRV8871 คือ %u Hz)\n",
                  (unsigned)pwmFreq, (unsigned)PWM_FREQ_FINAL_HZ);
    return;
  }
  if (cmd.startsWith("r ")) {
    const int sp = cmd.indexOf(' ', 2);
    if (sp < 0) { Serial.println("[ERR] ใช้: r <‰> <ms>"); return; }
    const int d = cmd.substring(2, sp).toInt();
    const uint32_t ms = cmd.substring(sp + 1).toInt();
    double rl, rr;
    int64_t cl, cr;
    runAndMeasure(d, ms, &rl, &rr, &cl, &cr);
    Serial.printf("duty %d‰ %u ms -> L %.1f rpm (%lld counts) · R %.1f rpm (%lld counts)\n",
                  d, (unsigned)ms, rl, cl, rr, cr);
    return;
  }
  Serial.printf("[ERR] ไม่รู้จักคำสั่ง \"%s\" — พิมพ์ ? เพื่อดูรายการ\n", cmd.c_str());
}

// ── setup / loop ──────────────────────────────────────────────

void motorSetup() {
#ifndef ROBOT_MERGED
  Serial.begin(115200);
  delay(2000);  // รอ USB CDC พร้อมก่อน ไม่งั้นบรรทัดแรกๆ จะหาย
#endif

  Serial.println();
  Serial.println("=== M1: เทสมอเตอร์ + เอ็นโคดเดอร์ (ไดรเวอร์ L298N ชั่วคราว) ===");
  Serial.printf("ESP-IDF %d.%d.%d\n", ESP_IDF_VERSION_MAJOR, ESP_IDF_VERSION_MINOR,
                ESP_IDF_VERSION_PATCH);

  bool ok = true;
  ok &= motL.begin(PIN_MOT_L_IN1, PIN_MOT_L_IN2, pwmFreq);
  ok &= motR.begin(PIN_MOT_R_IN1, PIN_MOT_R_IN2, pwmFreq);
  ok &= encL.begin(PIN_ENC_L_A, PIN_ENC_L_B);
  ok &= encR.begin(PIN_ENC_R_A, PIN_ENC_R_B);

  if (!ok) {
    Serial.println("!!! เริ่มต้นฮาร์ดแวร์ไม่สำเร็จ — หยุด");
    while (true) delay(1000);
  }

  Serial.println();
  Serial.println("⚠ ก่อนจ่ายไฟ 12 V ตรวจ 4 ข้อนี้ก่อน (ดูรายละเอียดในเอกสารเทส):");
  Serial.println("  1. encoder VCC ต่อกับ 3.3 V ของ ESP32 เท่านั้น — ห้าม 5 V (§3.6 ข้อ 2)");
  Serial.println("  2. GND ของ L298N · ESP32 · แหล่งจ่าย 12 V ต่อถึงกันหมด");
  Serial.println("  3. เสียบจัมเปอร์ ENA/ENB ค้างไว้ (ไม่งั้นมอเตอร์ไม่หมุน)");
  Serial.println("  4. ยกล้อให้ลอย ก่อนสั่งวิ่งครั้งแรก");
  printHelp();
  lastCommandMs = millis();
}

// เฝ้าความปลอดภัยอย่างเดียว (ไม่อ่าน Serial) — เฟิร์มแวร์รวมเรียกทุกรอบ
void motorTick() {
  // ตัดไฟเองถ้าสั่ง `d` ค้างไว้แล้วลืม
  if (running && millis() > runUntilMs) stopAll("ครบเวลาสูงสุดของคำสั่ง d");
  if (running && millis() - lastCommandMs > DEADMAN_MS) stopAll("ไม่มีคำสั่งใหม่นานเกินไป");
}

void motorLoop() {
  static String buf;
  while (Serial.available()) {
    const char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (buf.length()) { handleCommand(buf); buf = ""; }
    } else {
      buf += c;
    }
  }

  motorTick();
  delay(10);
}

// ── จุดต่อสำหรับเฟิร์มแวร์รวม (src/robot/main.cpp) ────────────
// ตรรกะการทดสอบไม่ถูกแตะเลย — ห่อของเดิมออกมาให้ชั้นบนเรียกได้เท่านั้น
void motorCommand(const String& cmd) { handleCommand(cmd); }
void motorStop(const char* why)      { stopAll(why); }
void motorHelp()                     { printHelp(); }
bool motorRunning()                  { return running; }

#ifndef ROBOT_MERGED
void setup() { motorSetup(); }
void loop()  { motorLoop(); }
#endif
