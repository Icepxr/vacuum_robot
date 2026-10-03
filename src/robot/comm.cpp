// comm.cpp — ดู comm.h
//
// ทำไม Serial0 ไม่ใช่ Serial: ด้วย -D ARDUINO_USB_CDC_ON_BOOT=1 (platformio.ini) `Serial` คือ USB-CDC
// (คอนโซล debug/คำสั่งทดสอบ m/sv/bl) ส่วน `Serial0` คือ HardwareSerial(0) = UART0 ฮาร์ดแวร์
// ระบุขา RX=44 TX=43 ตรงๆ ใน begin() แทนการพึ่ง default ของ core — ถ้า core map ผิด โค้ดนี้ยังถูก
// ✅ ยืนยันบนสายจริง 15 ก.ย. 2026 ว่าออกขา 43/44 · ขั้น E (16 ก.ย.): $V $S $E $C $P $L → #A/#N · #T 10 Hz
// ยังไม่มี: $M · $R · ฟิลด์ vbat/servo_i/us (ยังไม่มี ADC/US ในเฟิร์มแวร์รวม) — ส่ง 0 ตาม §7.2
//
// CRC8: poly 0x07 · init 0x00 · ไม่ reflect · คำนวณจากตัวอักษรหลัง sentinel จนถึงก่อน '*'
//   test vector ต้องตรงกับ 11_pi5_vision/src/mrc_protocol.py:
//   crc8("123456789") = 0xF4 (ค่า check มาตรฐาน) · crc8("E,1000,CAPTURE_REQ,1") = 0xE0
#include "comm.h"
#include "../pins.h"
#include "comm_codec.h"   // crc8 / checkFrame — ทดสอบบน host ได้
#include "manual.h"
#include "servo_x.h"
#include "tft.h"
void robotEmergencyStop(const char*);
int servoCurrentUs(); bool servoSetTarget(int us); void servoStop(const char*);
bool blowerOnNow(); bool brushOnNow(); uint32_t brushOnSinceMsNow(); bool missionRunning(); bool servoAttachedNow();

namespace {

// PIN_U0_RX 44 / PIN_U0_TX 43 มาจาก ../pins.h (§3.2 · ไขว้กับ Pi GPIO14/15)
constexpr uint32_t BAUD      = 115200;     // §3.7 · ไฟล์ 09 §9.5
constexpr uint32_t CAPTURE_TIMEOUT_MS = 5000;   // state CAMERA_CAPTURE §6.1
constexpr size_t   RX_LINE_MAX  = 128;        // #T เต็มฟิลด์ ~90 ตัวอักษร (ไฟล์ 09 §9.5) · $D 13 ฟิลด์ (C35) สูงสุด ~90 — กันบรรทัดหลุดยาว

char     rxBuf[RX_LINE_MAX];
size_t   rxLen = 0;

CaptureState state = CaptureState::IDLE;
uint32_t seq = 0;                // n ของ CAPTURE_REQ ล่าสุด
uint32_t sentMs = 0;
uint32_t roundtripMs = 0;
uint32_t statReq = 0, statOk = 0, statFail = 0, statTimeout = 0, statBadLine = 0;

// ส่ง <kind><body>*CC\n
void sendFrame(char kind, const char* body) {
  char out[RX_LINE_MAX];
  if (!mrc::appendCrc(body, out, sizeof out)) return;
  Serial0.write(kind);
  Serial0.print(out);
  Serial0.write('\n');          // จบด้วย \n ตัวเดียวตาม §7 (ไม่ใช่ \r\n ของ println)
}

// ── คำสั่งจาก Pi (ขั้น E) ──
void ack(uint32_t seq)                     { char b[24]; snprintf(b, sizeof b, "A,%lu", (unsigned long)seq); sendFrame('#', b); }
void nack(uint32_t seq, const char* why)   { char b[48]; snprintf(b, sizeof b, "N,%lu,%s", (unsigned long)seq, why); sendFrame('#', b);
                                             Serial.printf("[comm] #N %lu %s\n", (unsigned long)seq, why); }

// parse ตัวเลขคั่นด้วย ',' · คืนจำนวนที่ได้
int parseInts(const char* p, long* out, int maxN) {
  int n = 0;
  while (n < maxN && *p) {
    char* e; out[n] = strtol(p, &e, 10);
    if (e == p) break;
    ++n;
    if (*e != ',') break;
    p = e + 1;
  }
  return n;
}

uint32_t lastRxMs = 0;                        // เฟรมดีล่าสุดจาก Pi (ให้จอ/สถานะรู้ว่าลิงก์ยังอยู่)

void handleLine(char* line, size_t len) {
  if (!mrc::checkFrame(line, len)) { ++statBadLine; return; }   // boot log/ขยะ/CRC ผิด — ทิ้งเงียบ
  if (line[0] != '$' || line[2] != ',') { Serial.printf("[comm] เฟรมไม่รู้จัก: %s\n", line); return; }
  lastRxMs = millis();
  if (line[1] == 'D') {                          // $D,<seq>,<ip>,<reading>,<co2>,<tvoc>,<aqi>,<temp×10>,<rh×10>,<clients>,<warn>,<evt>,<arg> — ข้อความให้จอ (C32/C35) · สตริง ไม่ผ่าน parseInts
    char* f[13] = {}; int n = 0;
    char* p = line + 3; f[n++] = p;
    while (*p && n < 13) { if (*p == ',') { *p = '\0'; f[n++] = p + 1; } ++p; }
    char* star = strchr(f[n - 1], '*'); if (star) *star = '\0';
    if (n < 4) { nack(0, "BAD_ARGS"); return; }
    auto num = [&](int i, int dflt) { return (i < n && f[i][0]) ? atoi(f[i]) : dflt; };
    auto str = [&](int i) { return i < n ? (const char*)f[i] : ""; };
    tftSetInfo(f[1], f[2], num(3, -1), num(4, -1), num(5, -1), num(6, -1000), num(7, -1),
               num(8, -1), str(9), str(10), str(11));
    ack((uint32_t)strtoul(f[0], nullptr, 10));
    return;
  }
  long f[4] = {0, 0, 0, 0};
  const int n = parseInts(line + 3, f, 4);
  const uint32_t rseq = n >= 1 ? (uint32_t)f[0] : 0;
  switch (line[1]) {
    case 'K': {                                   // $K,<seq>,<1|0>
      if (n < 2) return;
      const int ok = (int)f[1];
      if (state != CaptureState::WAITING || rseq != seq) {
        Serial.printf("[comm] $K แปลกปลอม seq=%lu (รอ %lu, state %d) — ทิ้ง\n", (unsigned long)rseq, (unsigned long)seq, (int)state);
        return;
      }
      roundtripMs = millis() - sentMs;
      state = ok ? CaptureState::OK : CaptureState::FAIL;
      if (ok) ++statOk; else ++statFail;
      Serial.printf("[comm] got $K,%lu,%d ใน %lu ms\n", (unsigned long)rseq, ok, (unsigned long)roundtripMs);
      return;
    }
    case 'V': {                                   // $V,<seq>,<v_mm_s>,<w_mrad_s>
      if (n < 3) { nack(rseq, "BAD_ARGS"); return; }
      const char* why = manualSetpoint((int)f[1], (int)f[2]);
      if (why) nack(rseq, why); else ack(rseq);
      return;
    }
    case 'S': manualStop("Pi สั่ง $S"); ack(rseq); return;
    case 'E': robotEmergencyStop("Pi สั่ง $E (E-STOP)"); ack(rseq); return;
    case 'C': {                                   // $C,<seq>,<suction_pct>,<brush_pct>
      if (n < 3) { nack(rseq, "BAD_ARGS"); return; }
      const char* why = manualSetCleaning((int)f[1], (int)f[2]);
      if (why) nack(rseq, why); else ack(rseq);
      return;
    }
    case 'P': ack(rseq); return;                  // ping
    case 'L': {                                   // $L,<seq>,<v_max_mm_s>,<w_max_mrad_s> — เพดานที่ผู้ใช้ตั้ง (C28)
      if (n < 3) { nack(rseq, "BAD_ARGS"); return; }
      manualSetLimits((int)f[1], (int)f[2]);      // ถูก clamp ที่ฮาร์ดแวร์ก็ยัง ack — ค่าจริงดูใน #T ไม่ได้ จึงพิมพ์ทางคอนโซล
      ack(rseq);
      return;
    }
    case 'X': {                                   // $X,<seq>,<us> — เซอร์โวแกน X ของกล้อง (0 = ปล่อยสัญญาณ) · C30
      if (n < 2) { nack(rseq, "BAD_ARGS"); return; }
      const int us = (int)f[1];
      if (us == 0) { servoXRelease("Pi สั่ง $X,0"); ack(rseq); return; }
      if (!servoXMoveTo(us)) { nack(rseq, "OUT_OF_RANGE"); return; }
      ack(rseq);
      return;
    }
    case 'M': {                                   // $M,<seq>,<us> — เสายกกล้อง (เซอร์โว 1 · scissor) ไม่บล็อก · 0 = ปล่อยสัญญาณ · C30
      if (n < 2) { nack(rseq, "BAD_ARGS"); return; }
      if (missionRunning()) { nack(rseq, "IN_MISSION"); return; }
      const int us = (int)f[1];
      if (us == 0) { servoStop("Pi สั่ง $M,0"); ack(rseq); return; }
      if (us < MAST_US_MIN || us > MAST_US_MAX) { nack(rseq, "OUT_OF_RANGE"); return; }   // C47/C48: ต่ำสุด 300 (เดิม 500)
      if (!servoSetTarget(us)) { nack(rseq, "SERVO_FAIL"); return; }
      ack(rseq);
      return;
    }
    case 'R': nack(rseq, "NOT_IMPLEMENTED"); return;
    default:  nack(rseq, "UNKNOWN"); return;
  }
}

// ── #T telemetry 10 Hz — ฟิลด์ตาม §7.2 · ที่ยังไม่มีส่ง 0 ──
//  #T,<ms>,<state>,<v_mm_s>,<w_mrad_s>,<dutyL‰>,<dutyR‰>,<us_mast>,<us_x>,<vbat_mV=0>,<servo_i_mA=0>,<mast>,<flags>
//  state: 0 IDLE · 1 MANUAL · 2 MISSION · mast: 0 ปล่อย PWM · 2 จับสัญญาณ · flags 0x02 = comm-lost (deadman) · 0x04 = R2 spin-up hold
//         0x08 = ดูดเปิดอยู่ · 0x10 = แปรงหมุนอยู่ (C57 — ให้เว็บเห็นสถานะจริง ไม่ใช่สถานะที่กดไว้)
//  ⚠ ช่อง enc_l/enc_r ของ §7.2 ส่ง duty ‰ ไปก่อน (ยังไม่มี PCNT ในเฟิร์มแวร์รวม) — Pi ต้องรู้ (C27)
constexpr uint32_t TELE_PERIOD_MS = 100;
uint32_t lastTeleMs = 0;
uint8_t  flags = 0;

void sendTelemetry() {
  const int st = missionRunning() ? 2 : (manualActive() ? 1 : 0);
  const mrc::WheelCmd w = manualOut();
  char b[96];
  snprintf(b, sizeof b, "T,%lu,%d,%d,%d,%d,%d,%d,%d,0,0,%d,%u",
           (unsigned long)millis(), st, manualActive() ? manualV() : 0, manualActive() ? manualW() : 0,
           w.l, w.r, servoAttachedNow() ? servoCurrentUs() : 0, servoXCurrentUs(),   // us_l = เสา · us_r = แกน X (0 = ปล่อย) · C30
           servoAttachedNow() ? 2 : 0, (unsigned)flags);
  sendFrame('#', b);
}

}  // namespace

bool commLinkAlive() { return lastRxMs && millis() - lastRxMs < 1500; }   // Pi ส่ง $V/$P/$D อย่างน้อยทุก 1 s เมื่อเว็บรัน
uint32_t commRxAgeMs() { return lastRxMs ? millis() - lastRxMs : UINT32_MAX; }   // C57: ใช้เฝ้าดูด/แปรง (เผื่อ $D ช้ากว่า 1 s ตอน Pi ทำงานหนัก)

void commSetup() {
  Serial0.begin(BAUD, SERIAL_8N1, PIN_U0_RX, PIN_U0_TX);
  Serial.printf("[comm] UART0 %lu baud · RX=GPIO%d TX=GPIO%d · รอ Pi 5\n",
                (unsigned long)BAUD, PIN_U0_RX, PIN_U0_TX);
}

bool commRequestCapture() {
  if (state == CaptureState::WAITING) {
    Serial.printf("[comm] ยังรอ $K ของครั้งที่ %lu อยู่ (อีก %lu ms จะ timeout)\n",
                  (unsigned long)seq, (unsigned long)(CAPTURE_TIMEOUT_MS - (millis() - sentMs)));
    return false;
  }
  ++seq; ++statReq;
  char body[48];
  snprintf(body, sizeof body, "E,%lu,CAPTURE_REQ,%lu", (unsigned long)millis(), (unsigned long)seq);
  sentMs = millis();
  state = CaptureState::WAITING;
  sendFrame('#', body);
  Serial.printf("[comm] → #%s  (รอ $K ไม่เกิน %lu ms)\n", body, (unsigned long)CAPTURE_TIMEOUT_MS);
  return true;
}

void commTick() {
  while (Serial0.available()) {
    const char c = (char)Serial0.read();
    if (c == '\n' || c == '\r') {
      if (rxLen) { rxBuf[rxLen] = '\0'; handleLine(rxBuf, rxLen); rxLen = 0; }
    } else if (rxLen < RX_LINE_MAX - 1) {
      rxBuf[rxLen++] = c;
    } else {
      rxLen = 0; ++statBadLine;            // ยาวเกิน = ไม่ใช่เฟรมของเรา ทิ้งทั้งบรรทัด
    }
  }
  if (manualTripped()) flags |= 0x02; else flags &= ~0x02;
  if (manualSpinupHold()) flags |= 0x04; else flags &= ~0x04;
  if (blowerOnNow()) flags |= 0x08; else flags &= ~0x08;
  if (brushOnNow())  flags |= 0x10; else flags &= ~0x10;
  if (millis() - lastTeleMs >= TELE_PERIOD_MS) { lastTeleMs = millis(); sendTelemetry(); }
  if (state == CaptureState::WAITING && millis() - sentMs >= CAPTURE_TIMEOUT_MS) {
    state = CaptureState::TIMEOUT; ++statTimeout;
    Serial.printf("[comm] timeout: ไม่ได้ $K ของครั้งที่ %lu ใน %lu ms — FSM ต้องพับเสาต่อเอง (§6.1)\n",
                  (unsigned long)seq, (unsigned long)CAPTURE_TIMEOUT_MS);
  }
}

CaptureState commCaptureState()   { return state; }
uint32_t     commLastRoundtripMs() { return roundtripMs; }

void commPrintStatus() {
  static const char* names[] = { "IDLE", "WAITING", "OK", "FAIL", "TIMEOUT" };
  Serial.printf("[comm] state=%s seq=%lu roundtrip=%lu ms · req %lu · ok %lu · fail %lu · timeout %lu · bad lines %lu\n",
                names[(int)state], (unsigned long)seq, (unsigned long)roundtripMs,
                (unsigned long)statReq, (unsigned long)statOk, (unsigned long)statFail,
                (unsigned long)statTimeout, (unsigned long)statBadLine);
}

void commSendEvent(const char* code, const char* detail) {
  char b[64];
  snprintf(b, sizeof b, "E,%lu,%s,%s", (unsigned long)millis(), code, detail ? detail : "");
  sendFrame('#', b);
}
