#pragma once
// ─────────────────────────────────────────────────────────────
// config.h — ค่าคงที่ของชุดทดสอบมอเตอร์ + เอ็นโคดเดอร์ (M1)
//
// ที่มาของทุกค่าในไฟล์นี้:
//   01_เอกสารโครงการ/system_architecture.md  §3.2 (pin mapping), §3.6 (มอเตอร์)
//   08_การคำนวณ/01_ระบบขับเคลื่อนและ_odometry.md  §1.1–1.5
// ห้ามแก้ค่าที่นี่โดยไม่แก้เอกสารต้นทางด้วย
// ─────────────────────────────────────────────────────────────

// ── ตรวจว่าคอมไพล์ด้วย core ที่ถูกต้อง ────────────────────────
// เอกสารล็อกไว้ว่าใช้ Arduino-ESP32 core 3.x (ESP-IDF v5) เพราะ
// วิธีแก้ PCNT ล้น (§1.5) ผูกกับ API ใหม่ driver/pulse_cnt.h
#include <esp_idf_version.h>
#if ESP_IDF_VERSION_MAJOR < 5
#error "ต้องใช้ Arduino-ESP32 core 3.x (ESP-IDF v5) — platform espressif32 ตัวทางการของ PlatformIO ยังให้ core 2.0.x (ESP-IDF 4.4) ซึ่งไม่มี driver/pulse_cnt.h ดู 03_ผลการทดสอบ/M1_มอเตอร์และเอ็นโคดเดอร์.md หัวข้อ 'ก่อนกด Build'"
#endif

// ── ขา GPIO — ตรงกับ system_architecture.md §3.2 ทุกขา ────────
// L298N ต่อโดย "เสียบจัมเปอร์ ENA/ENB ค้างไว้" แล้ว PWM ที่ IN1/IN2
// → ใช้ 4 ขาเท่าเดิม ไม่กินขาเกินงบ 25 ขา และย้ายไป DRV8871 ได้โดยไม่แก้ pin
constexpr int PIN_MOT_L_IN1 = 4;   // LEDC ch0
constexpr int PIN_MOT_L_IN2 = 5;   // LEDC ch1
constexpr int PIN_MOT_R_IN1 = 6;   // LEDC ch2
constexpr int PIN_MOT_R_IN2 = 7;   // LEDC ch3

constexpr int PIN_ENC_L_A = 11;    // PCNT unit 0
constexpr int PIN_ENC_L_B = 12;
constexpr int PIN_ENC_R_A = 13;    // PCNT unit 1
constexpr int PIN_ENC_R_B = 14;

// GPIO 48 บน devkitc-1 เป็น LED แบบ WS2812 (สายข้อมูลเส้นเดียว) ไม่ใช่ LED ธรรมดา
// digitalWrite() ไม่ทำให้มันติด ต้องส่งเป็นสตรีมข้อมูลสี → ชุดทดสอบนี้ไม่ใช้
// constexpr int PIN_STATUS_LED = 48;

// ── PWM ───────────────────────────────────────────────────────
// 20 kHz คือค่าที่ล็อกไว้สำหรับ DRV8871 (§3.5 timer T0, 11-bit)
// แต่ L298N เป็นดาร์ลิงตันไบโพลาร์ ความเร็วสวิตช์ช้ากว่า MOSFET มาก
// → ตั้งค่าเริ่มต้นไว้ 1 kHz สำหรับการเทสด้วย L298N แล้วใช้คำสั่ง `f`
//   เทียบ 1 kHz กับ 20 kHz เอง (ดูขั้น T6 ในเอกสารเทส)
constexpr uint32_t PWM_FREQ_DEFAULT_HZ = 1000;
constexpr uint32_t PWM_FREQ_FINAL_HZ   = 20000;  // ค่าที่จะใช้จริงกับ DRV8871
constexpr uint8_t  PWM_RES_BITS        = 11;     // 0..2047
constexpr int      PWM_MAX             = (1 << PWM_RES_BITS) - 1;

// ── เอ็นโคดเดอร์ / odometry ───────────────────────────────────
// ทั้งสามค่านี้เป็น [คำนวณ] ยังไม่เคยวัดจริง — การเทสนี้มีไว้เพื่อยืนยัน
constexpr int    ENC_PPR          = 11;     // pulse ต่อรอบ "มอเตอร์" (ก่อนเกียร์)
constexpr int    GEAR_RATIO       = 56;     // [คำนวณ/อนุมาน] §1.1 — ยังไม่ยืนยัน
constexpr int    COUNTS_PER_REV   = ENC_PPR * 4 * GEAR_RATIO;  // = 2464
constexpr double WHEEL_DIAMETER_M = 0.065;
constexpr double RPM_NOLOAD_SPEC  = 178.0;  // [สเปก] ที่ 12 V

// PCNT เป็นตัวนับ 16 บิตมีเครื่องหมาย (ชนเพดาน 32,767)
// §1.5: ที่ 7,310 counts/s จะล้นใน 4.48 s → ตั้ง watch point ที่ ±30,000
// แล้วสะสมเข้า int64_t ฝั่งซอฟต์แวร์
constexpr int PCNT_LIMIT = 30000;

// ── ขีดจำกัดความปลอดภัยของการเทส ──────────────────────────────
// L298 มีพิกัดกระแสรวมทั้งชิป 4 A [สเปก ST] และมอเตอร์ตอน stall
// กินได้ 2–3 A ต่อตัว (§3.3) → สั่งสองตัวพร้อมกันตอน stall จะเกินพิกัด
constexpr uint32_t MAX_RUN_MS       = 20000;  // สั่งวิ่งต่อเนื่องได้ไม่เกิน 20 s
constexpr uint32_t DEADMAN_MS       = 25000;  // ไม่มีคำสั่งใหม่เกินนี้ = หยุดเอง
constexpr uint32_t RAMP_MS          = 300;    // ไล่ duty ขึ้นช้าๆ กันกระชากตอนออกตัว
constexpr int      STALL_COUNT_MIN  = 20;     // counts ที่ต้องเห็นใน STALL_CHECK_MS
constexpr uint32_t STALL_CHECK_MS   = 500;    // ถ้าน้อยกว่านี้ = ถือว่า stall → ตัด
