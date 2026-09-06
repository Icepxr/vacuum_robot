// ─────────────────────────────────────────────────────────────
// M2 — ชุดทดสอบเซอร์โวเสายก (MG996R)
//
// งานหลักของชุดนี้คือปิด C8 ซึ่งเป็นจุดตัดสินใจของวันที่ 7 ก.ย.
//   datasheet_component/MG996R.PDF ระบุ "approximately 120 degrees"
//   ทางเลือก A ของกลไกใหม่ต้องการ 171°  ← ถ้าหมุนได้แค่ 120° ทางนี้ตาย
//   ทางเลือก B ต้องการแค่ 46°           ← ทางนี้ไม่ติดปัญหา
// วัดได้เท่าไรเป็นตัวกำหนดว่าจะพิมพ์ชิ้นส่วนแบบไหน
//
// ⚠ ความละเอียด 14 บิต ไม่ใช่ 16 บิตตามที่ §3.5 เขียนไว้
//   ESP32-S3 มีเพดานความละเอียด LEDC ที่ 14 บิต — ดูไฟล์ 10 ข้อ C15 และไฟล์ 17
//
// ขั้นตอนเต็ม + ตารางกรอกผล: 03_ผลการทดสอบ/M2_เซอร์โวเสายก.md
// ─────────────────────────────────────────────────────────────
#include <Arduino.h>
#include <esp_idf_version.h>
#if ESP_IDF_VERSION_MAJOR < 5
#error "ต้องใช้ Arduino-ESP32 core 3.x (ESP-IDF v5) — ดู platformio.ini"
#endif

// ── ขา — ตรงกับ system_architecture.md §3.2 ─────────────────
// กลไกใหม่ (ไฟล์ 12 รอบแก้ที่ 2) ใช้เซอร์โว 1 ตัว → ทดสอบที่ SERVO_A
constexpr int PIN_SERVO = 17;

// ── PWM ──────────────────────────────────────────────────────
constexpr uint32_t SERVO_FREQ_HZ = 50;
constexpr uint8_t  SERVO_RES     = 14;      // เพดานของ ESP32-S3 · §3.5 เขียน 16 ซึ่งตั้งไม่ได้
constexpr int      SERVO_MAX     = (1 << SERVO_RES) - 1;   // 16383
constexpr float    PERIOD_US     = 1000000.0f / SERVO_FREQ_HZ;   // 20,000 us

// ── ช่วงความกว้างพัลส์ที่ยอมให้สั่ง ──────────────────────────
// datasheet MG996R ระบุ ~120° ที่ 1000-2000 us
// แต่หลายล็อตหมุนได้กว้างกว่านั้นถ้าป้อน 500-2500 us — ซึ่งเป็นสิ่งที่ต้องวัด
// เผื่อขอบไว้เล็กน้อยเพื่อหาขีดจริง แต่ไม่กว้างจนดันชนกลไกภายใน
constexpr int US_MIN   = 500;
constexpr int US_MAX   = 2500;
constexpr int US_CENTER = 1500;

// อัตราการเคลื่อนที่สูงสุด — กันไม่ให้เซอร์โวกระชากไปสุดทางในทีเดียว
// ถ้าฮอร์นติดกลไกอยู่ การกระชากทำให้เฟืองในตัวเซอร์โวแตกได้
constexpr int   SLEW_US_PER_STEP = 5;
constexpr int   SLEW_STEP_MS     = 12;      // ~417 us/s ≈ เดินเต็มช่วง 4.8 วินาที

static bool attached = false;
static int  currentUs = US_CENTER;
static uint32_t lastCommandMs = 0;

// ── ตัวช่วย ───────────────────────────────────────────────────

static int usToDuty(int us) {
  // duty = us / 20000 * 16384
  return (int)((float)us * SERVO_MAX / PERIOD_US + 0.5f);
}

static void servoDetach(const char* why) {
  if (attached) {
    ledcDetach(PIN_SERVO);
    pinMode(PIN_SERVO, OUTPUT);
    digitalWrite(PIN_SERVO, LOW);
    attached = false;
  }
  Serial.printf("[ปล่อย] %s — เซอร์โวไม่มีสัญญาณแล้ว หมุนด้วยมือได้\n", why);
}

// ผูกสัญญาณโดยเริ่มที่ตำแหน่งที่ระบุ — ไม่กระโดดจากค่าเก่า
static bool servoAttachAt(int us) {
  us = constrain(us, US_MIN, US_MAX);
  if (!attached) {
    if (!ledcAttach(PIN_SERVO, SERVO_FREQ_HZ, SERVO_RES)) {
      Serial.println("[ERR] ผูก LEDC กับขาไม่สำเร็จ");
      Serial.printf("      %u Hz ที่ %u บิต ตั้งไม่ได้ — ดู 08_การคำนวณ/17\n",
                    (unsigned)SERVO_FREQ_HZ, (unsigned)SERVO_RES);
      return false;
    }
    attached = true;
  }
  currentUs = us;
  ledcWrite(PIN_SERVO, usToDuty(us));
  return true;
}

// เคลื่อนไปตำแหน่งใหม่แบบค่อยเป็นค่อยไป · กดปุ่มใดก็ได้เพื่อหยุดกลางทาง
static bool slewTo(int targetUs) {
  targetUs = constrain(targetUs, US_MIN, US_MAX);
  if (!attached && !servoAttachAt(currentUs)) return false;
  const int dir = (targetUs > currentUs) ? SLEW_US_PER_STEP : -SLEW_US_PER_STEP;
  while (abs(targetUs - currentUs) > SLEW_US_PER_STEP) {
    if (Serial.available()) {
      while (Serial.available()) Serial.read();
      Serial.printf("[หยุด] ค้างไว้ที่ %d us\n", currentUs);
      return false;
    }
    currentUs += dir;
    ledcWrite(PIN_SERVO, usToDuty(currentUs));
    delay(SLEW_STEP_MS);
  }
  currentUs = targetUs;
  ledcWrite(PIN_SERVO, usToDuty(currentUs));
  return true;
}

// ── ขั้นทดสอบ ────────────────────────────────────────────────

// V1 — วัดช่วงหมุนรวม (ปิด C8)
static void testRange() {
  Serial.println();
  Serial.println("=== V1: วัดช่วงหมุนจริง (ปิด C8) ===");
  Serial.println("⚠ ถอดฮอร์นออกจากกลไกก่อน ให้หมุนอิสระ — ห้ามทดสอบตอนติดอยู่กับเสายก");
  Serial.println("เตรียมไม้โปรแทรกเตอร์ · ทำเครื่องหมายบนฮอร์นให้เห็นชัด");
  Serial.println("จะเดินไปสุดฝั่งหนึ่ง หยุดให้วัด แล้วเดินไปสุดอีกฝั่ง");
  Serial.println("กด Enter เพื่อเริ่ม (กดปุ่มใดก็ได้ระหว่างเดินเพื่อหยุดฉุกเฉิน)");
  while (!Serial.available()) delay(20);
  while (Serial.available()) Serial.read();

  servoAttachAt(US_CENTER);
  Serial.printf("ไปตำแหน่งกลาง %d us ...\n", US_CENTER);
  delay(800);

  Serial.printf("\nเดินไป %d us ...\n", US_MIN);
  if (!slewTo(US_MIN)) return;
  Serial.println(">>> ถึงแล้ว — วัดมุมแล้วจดไว้เป็น A · กด Enter เพื่อไปต่อ");
  while (!Serial.available()) delay(20);
  while (Serial.available()) Serial.read();

  Serial.printf("\nเดินไป %d us ...\n", US_MAX);
  if (!slewTo(US_MAX)) return;
  Serial.println(">>> ถึงแล้ว — วัดมุมแล้วจดไว้เป็น B");
  Serial.println();
  Serial.println("ช่วงหมุนรวม = |B − A| องศา");
  Serial.println("  ถ้าได้ >= 171 องศา  → ทางเลือก A ของกลไกใหม่ใช้ได้");
  Serial.println("  ถ้าได้ 120-170     → ทางเลือก A ใช้ไม่ได้ ต้องใช้ทางเลือก B (ต้องการ 46 องศา)");
  Serial.println("  ถ้าได้ < 120       → ต่ำกว่า datasheet เอง ให้ตรวจสายและแหล่งจ่ายก่อนสรุป");
  Serial.println("จดผลลงตาราง V1 แล้วพิมพ์ off เพื่อปล่อยเซอร์โว");
}

// V2 — ไล่ทีละขั้นเพื่อทำตารางแปลง us เป็นองศา
static void testStepTable() {
  Serial.println();
  Serial.println("=== V2: ตารางแปลงความกว้างพัลส์เป็นองศา ===");
  Serial.println("จะหยุดทุก 250 us ให้วัดมุมแล้วกด Enter เพื่อไปขั้นถัดไป");
  Serial.println("us,องศาที่วัดได้");
  servoAttachAt(US_MIN);
  delay(600);
  for (int us = US_MIN; us <= US_MAX; us += 250) {
    if (!slewTo(us)) return;
    Serial.printf("%d,____\n", us);
    while (!Serial.available()) delay(20);
    while (Serial.available()) Serial.read();
  }
  Serial.println("จบ V2 — คัดลอกทั้งบล็อกไปแปะในเอกสารเทส");
}

// V3 — วัดกระแสตอนถือตำแหน่งและตอนมีโหลด
static void testHold(int us, uint32_t seconds) {
  if (seconds > 30) seconds = 30;
  Serial.printf("\n=== V3: ถือที่ %d us นาน %lu วินาที ===\n", us, (unsigned long)seconds);
  Serial.println("อ่านกระแสจากจอแหล่งจ่าย — ทั้งตอนกำลังเคลื่อนและตอนถือนิ่ง");
  Serial.println("⚠ MG996R ตอน stall กินได้ถึงระดับ 2.5 A — ถ้ากระแสค้างสูงให้กดหยุดทันที");
  if (!slewTo(us)) return;
  const uint32_t t0 = millis();
  while (millis() - t0 < seconds * 1000UL) {
    if (Serial.available()) {
      while (Serial.available()) Serial.read();
      Serial.println("[หยุด] ผู้ใช้สั่งหยุด");
      return;
    }
    delay(50);
  }
  Serial.println(">>> ครบเวลา — จดกระแสตอนถือนิ่งลงตาราง V3");
}

// ── คำสั่ง ────────────────────────────────────────────────────

static void printHelp() {
  Serial.println();
  Serial.println("┌─ คำสั่ง ─────────────────────────────────────────────┐");
  Serial.println("│ ?             แสดงคำสั่ง                             │");
  Serial.println("│ v1            วัดช่วงหมุนจริง (ปิด C8) ← ทำอันนี้ก่อน  │");
  Serial.println("│ v2            ตารางแปลง us เป็นองศา ทีละ 250 us       │");
  Serial.println("│ hold <us> <s> ถือตำแหน่งเพื่อวัดกระแส                 │");
  Serial.println("│ us <ค่า>      ไปตำแหน่งที่ระบุ (500-2500)             │");
  Serial.println("│ c             ไปตำแหน่งกลาง 1500 us                  │");
  Serial.println("│ + / -         ขยับทีละ 25 us                         │");
  Serial.println("│ off           ปล่อยเซอร์โว (ไม่มีสัญญาณ หมุนมือได้)   │");
  Serial.println("│ st            แสดงสถานะ                              │");
  Serial.println("└──────────────────────────────────────────────────────┘");
  Serial.println("กดปุ่มใดก็ได้ระหว่างเซอร์โวกำลังเดิน = หยุดทันที");
}

static void handleCommand(String cmd) {
  cmd.trim();
  if (!cmd.length()) return;
  lastCommandMs = millis();

  if (cmd == "?" || cmd == "h") { printHelp(); return; }
  if (cmd == "off")  { servoDetach("สั่งปล่อยเอง"); return; }
  if (cmd == "v1")   { testRange(); return; }
  if (cmd == "v2")   { testStepTable(); return; }
  if (cmd == "c")    { slewTo(US_CENTER); Serial.printf("[OK] อยู่ที่ %d us\n", currentUs); return; }
  if (cmd == "+")    { slewTo(currentUs + 25); Serial.printf("[OK] %d us\n", currentUs); return; }
  if (cmd == "-")    { slewTo(currentUs - 25); Serial.printf("[OK] %d us\n", currentUs); return; }
  if (cmd == "st") {
    Serial.printf("สัญญาณ: %s · ตำแหน่ง %d us · duty %d/%d · %u Hz %u บิต\n",
                  attached ? "ผูกอยู่" : "ปล่อยแล้ว", currentUs, usToDuty(currentUs),
                  SERVO_MAX, (unsigned)SERVO_FREQ_HZ, (unsigned)SERVO_RES);
    return;
  }
  if (cmd.startsWith("us ")) {
    const int us = cmd.substring(3).toInt();
    if (us < US_MIN || us > US_MAX) {
      Serial.printf("[ปฏิเสธ] %d us อยู่นอกช่วง %d-%d us\n", us, US_MIN, US_MAX);
      return;
    }
    slewTo(us);
    Serial.printf("[OK] อยู่ที่ %d us\n", currentUs);
    return;
  }
  if (cmd.startsWith("hold ")) {
    const int sp = cmd.indexOf(' ', 5);
    if (sp < 0) { Serial.println("[ERR] ใช้: hold <us> <วินาที>"); return; }
    testHold(cmd.substring(5, sp).toInt(), (uint32_t)cmd.substring(sp + 1).toInt());
    return;
  }
  Serial.printf("[ERR] ไม่รู้จักคำสั่ง \"%s\" — พิมพ์ ? เพื่อดูรายการ\n", cmd.c_str());
}

// ── setup / loop ──────────────────────────────────────────────

void setup() {
  // ตั้งขาเป็น LOW ก่อน กันเซอร์โวได้รับพัลส์ขยะตอนบูต
  // (ตัวที่กันจริงคือ pull-down 10 kΩ ตาม §3.2 — โค้ดทำหน้าที่ต่อจากนั้น)
  pinMode(PIN_SERVO, OUTPUT);
  digitalWrite(PIN_SERVO, LOW);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("=== M2: เทสเซอร์โวเสายก (MG996R) ===");
  Serial.printf("ESP-IDF %d.%d.%d · ขาสัญญาณ GPIO %d · %u Hz %u บิต\n",
                ESP_IDF_VERSION_MAJOR, ESP_IDF_VERSION_MINOR, ESP_IDF_VERSION_PATCH,
                PIN_SERVO, (unsigned)SERVO_FREQ_HZ, (unsigned)SERVO_RES);
  Serial.println();
  Serial.println("⚠ ตรวจ 5 ข้อก่อนจ่ายไฟ:");
  Serial.println("  1. ถอดฮอร์นออกจากกลไกก่อน ให้หมุนอิสระ — ห้ามทดสอบตอนติดอยู่กับเสายก");
  Serial.println("  2. เซอร์โวกินไฟจากราง 5 V แยก ไม่ใช่จากขา 5V ของบอร์ด ESP32");
  Serial.println("  3. GND ของ ESP32 · เซอร์โว · แหล่งจ่าย ต่อถึงกันหมด");
  Serial.println("  4. pull-down 10 kΩ ที่ขาสัญญาณ (§3.2)");
  Serial.println("  5. ตั้ง current limit ของแหล่งจ่ายที่ 3.0 A (MG996R ตอน stall ถึง ~2.5 A)");
  Serial.println();
  Serial.println("เซอร์โวยังไม่ได้รับสัญญาณตอนนี้ — พิมพ์ v1 เพื่อเริ่ม");
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
  delay(10);
}
