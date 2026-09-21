#pragma once
// ═════════════════════════════════════════════════════════════════════════
// pins.h — ขา GPIO ทุกขาของ MRC-001 บน ESP32-S3 N16R8 (DevKitC-1) **ที่เดียว**
//
// กฎ: จะย้ายขา แก้ที่นี่ที่เดียว แล้วแก้ตาราง 01_เอกสารโครงการ/system_architecture.md §3.2 ให้ตรงกัน
//      ห้ามประกาศ constexpr ขาซ้ำในไฟล์อื่น (config.h ของชุดทดสอบและ src/robot/* include ไฟล์นี้)
//
// ขาที่ "ห้ามใช้" บน S3 N16R8 (เช็คก่อนเลือกขาใหม่ทุกครั้ง — กฎใน CLAUDE.md):
//   0 / 3 / 45 / 46  strapping (โหมดบูต · แรงดัน flash · ROM log)      19 / 20  USB D-/D+ (คอนโซล + แฟลช)
//   26–32            SPI flash (ห้ามแตะ)                                   33–37  octal PSRAM ของ N16R8 (ห้ามแตะ — บอร์ด R8)
//   43 / 44          UART0 = ลิงก์ Pi (ถาวร §3.7)                           48     RGB LED WS2812 บนบอร์ด (RMT ไม่ใช่ digitalWrite)
//   ADC2 (11–20)     ชนกับ Wi-Fi → อนาล็อกใช้ ADC1 (1–10) เท่านั้น
//
// ตำนานคอลัมน์: [ใช้จริง] = มีโค้ดขับอยู่ใน src/robot · [จอง] = อยู่ในตาราง §3.2 ยังไม่มีโค้ด · [ตัดแล้ว] = ตัดสินใจไม่ใช้ (ไฟล์ 10)
// ═════════════════════════════════════════════════════════════════════════

// ── มอเตอร์ขับเคลื่อน — DRV8871 ×2 (LEDC T0 20 kHz 11-bit · ไฟล์ 17)               [ใช้จริง] src/motor_encoder_test/
constexpr int PIN_MOT_L_IN1 = 4;    // LEDC ch0 · เดินหน้า = PWM ที่ IN1, IN2 = 0
constexpr int PIN_MOT_L_IN2 = 5;    // LEDC ch1 · ถอย = สลับ · เบรก = ทั้งคู่ HIGH
constexpr int PIN_MOT_R_IN1 = 6;    // LEDC ch2
constexpr int PIN_MOT_R_IN2 = 7;    // LEDC ch3

// ── เอ็นโคดเดอร์ (PCNT · ไฟล์ 01 §1.5 กันล้นที่ ±30000)                            [ใช้จริง] src/motor_encoder_test/encoder.cpp
constexpr int PIN_ENC_L_A = 11;     // PCNT unit 0
constexpr int PIN_ENC_L_B = 12;
constexpr int PIN_ENC_R_A = 13;     // PCNT unit 1
constexpr int PIN_ENC_R_B = 14;

// ── ทำความสะอาด (MOSFET · R 100 Ω + pull-down 10 kΩ + SS34 · ไฟล์ 16)              [ใช้จริง] src/blower_test/
constexpr int PIN_SUCTION_EN = 21;  // เกต blower 12 V · GPIO ธรรมดา เปิด/ปิด (PWM ได้แค่ 10–50 Hz — ห้าม 20 kHz §3.5)
constexpr int PIN_BRUSH_PWM  = 16;  // เกตแปรงข้าง ราง 5 V · LEDC ch5 T1 20 kHz 10-bit · มอเตอร์ 6 V 200 rpm (C30)

// ── เซอร์โว MG996R ×2 (LEDC T2 50 Hz 14-bit · pull-down 10 kΩ ที่ขาสัญญาณ)
constexpr int PIN_SERVO_MAST = 17;  // SERVO_A · เสา scissor (ตัวเดียว ไฟล์ 12)                [ใช้จริง] src/servo_test/main.cpp
constexpr int PIN_SERVO_X    = 18;  // SERVO_B · มุมกล้อง (ก้ม-เงย · C30 19 ก.ย.)                [ใช้จริง] src/robot/servo_x.cpp

// ── จอกลม GC9A01 1.28" SPI2 40 MHz (RST → EN · BL → 3.3 V · C32)                    [ใช้จริง] src/robot/tft.cpp
constexpr int PIN_TFT_SCK  = 38;
constexpr int PIN_TFT_MOSI = 39;
constexpr int PIN_TFT_DC   = 40;
constexpr int PIN_TFT_CS   = 47;

// ── ลิงก์ Pi 5 — UART0 115200 8N1 ไขว้ TX↔RX ลอจิก 3.3 V ต่อตรง (§3.7)              [ใช้จริง] src/robot/comm.cpp
constexpr int PIN_U0_RX = 44;       // ← Pi GPIO14 TXD (header ขา 8)
constexpr int PIN_U0_TX = 43;       // → Pi GPIO15 RXD (header ขา 10) · GND ↔ GND (ขา 6)

// ── จองไว้ (ตาราง §3.2 · ยังไม่มีโค้ด — ค่าใน #T ยังเป็น 0 · C27)                 [จอง]
constexpr int PIN_VBAT_SENSE    = 10;   // ADC1_CH9 · ตัวแบ่ง 150 k/33 k (§3.4)
constexpr int PIN_SERVO_I_SENSE = 1;    // ADC1_CH0 · ACS712-5A ผ่านตัวแบ่ง 6.8 k/10 k (§3.8) — ต่อตรงไม่ได้
constexpr int PIN_I2C0_SDA      = 8;    // จองให้ IMU / INA226 — อย่าใช้อย่างอื่น
constexpr int PIN_I2C0_SCL      = 9;
constexpr int PIN_STATUS_LED    = 48;   // WS2812 บนบอร์ด (RMT)

// ── ตัดแล้ว (C26 16 ก.ย.: HC-SR04 ×2 ออก — โหมดแมนวล คนขับดูกล้องเอง) — ขา 15/41/42 ว่างให้ใช้ต่อ   [ตัดแล้ว]
// constexpr int PIN_US_TRIG = 15, PIN_US_ECHO_L = 41, PIN_US_ECHO_R = 42;

// ── ฝั่ง Pi 5 (ไม่ใช่ขาของ ESP32 — จดไว้ให้เห็นภาพรวมที่เดียว · ค่าจริงอยู่ 11_pi5_vision/src/mrc_config.py)
//   UART  /dev/ttyAMA0  GPIO14 TXD / GPIO15 RXD (header 8/10)  ↔ ESP32 44/43 ข้างบน
//   I2C-1 GPIO2 SDA / GPIO3 SCL (header 3/5)                  → ENS160 0x53 (บอร์ดนี้) + AHT21 0x38 · ไฟ 3.3 V
//   USB   BRIO 4K (/dev/video0)                               · ESP32 USB-C จาก Pi (คอนโซล/แฟลช — Pi รีบูต = ESP32 รีบูต)
