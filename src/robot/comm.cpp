// comm.cpp — ดู comm.h
//
// ทำไม Serial0 ไม่ใช่ Serial: ด้วย -D ARDUINO_USB_CDC_ON_BOOT=1 (platformio.ini) `Serial` คือ USB-CDC
// (คอนโซล debug/คำสั่งทดสอบ m/sv/bl) ส่วน `Serial0` คือ HardwareSerial(0) = UART0 ฮาร์ดแวร์
// ระบุขา RX=44 TX=43 ตรงๆ ใน begin() แทนการพึ่ง default ของ core — ถ้า core map ผิด โค้ดนี้ยังถูก
// ⚠ ยังไม่ได้ยืนยันบนบอร์ดจริงว่าออกขา 43/44 — ขั้นตอนยืนยันอยู่ใน 10_firmware_esp32/README.md
//
// CRC8: poly 0x07 · init 0x00 · ไม่ reflect · คำนวณจากตัวอักษรหลัง sentinel จนถึงก่อน '*'
//   test vector ต้องตรงกับ 11_pi5_vision/src/mrc_protocol.py:
//   crc8("123456789") = 0xF4 (ค่า check มาตรฐาน) · crc8("E,1000,CAPTURE_REQ,1") = 0xE0
#include "comm.h"
#include "comm_codec.h"   // crc8 / checkFrame — ทดสอบบน host ได้

namespace {

constexpr int      PIN_U0_RX = 44;         // §3.2 — Pi GPIO14 TXD → ESP32 GPIO44
constexpr int      PIN_U0_TX = 43;         // §3.2 — ESP32 GPIO43 → Pi GPIO15 RXD
constexpr uint32_t BAUD      = 115200;     // §3.7 · ไฟล์ 09 §9.5
constexpr uint32_t CAPTURE_TIMEOUT_MS = 5000;   // state CAMERA_CAPTURE §6.1
constexpr size_t   RX_LINE_MAX  = 96;         // #T เต็มฟิลด์ ~90 ตัวอักษร (ไฟล์ 09 §9.5) — กันบรรทัดหลุดยาว

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

void handleLine(char* line, size_t len) {
  if (!mrc::checkFrame(line, len)) { ++statBadLine; return; }   // boot log/ขยะ/CRC ผิด — ทิ้งเงียบ
  // $K,<seq>,<1|0>
  if (line[0] == '$' && line[1] == 'K' && line[2] == ',') {
    char* p = line + 3;
    const uint32_t gotSeq = strtoul(p, &p, 10);
    if (*p != ',') return;
    const int ok = atoi(p + 1);
    if (state != CaptureState::WAITING || gotSeq != seq) {
      Serial.printf("[comm] $K แปลกปลอม seq=%lu (รอ %lu, state %d) — ทิ้ง\n",
                    (unsigned long)gotSeq, (unsigned long)seq, (int)state);
      return;
    }
    roundtripMs = millis() - sentMs;
    state = ok ? CaptureState::OK : CaptureState::FAIL;
    if (ok) ++statOk; else ++statFail;
    Serial.printf("[comm] got $K,%lu,%d ใน %lu ms\n", (unsigned long)gotSeq, ok, (unsigned long)roundtripMs);
    return;
  }
  Serial.printf("[comm] เฟรมที่ยังไม่รองรับในขั้น C: %s\n", line);
}

}  // namespace

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
