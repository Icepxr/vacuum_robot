#pragma once
// ─────────────────────────────────────────────────────────────
// config.h — ชุดทดสอบระบบดูด (M3)
//
// ที่มาของทุกค่าในไฟล์นี้:
//   01_เอกสารโครงการ/system_architecture.md  §3.2 (pin), §3.5 (วงจร blower + ความร้อน)
//   01_เอกสารโครงการ/test_design_1.1-1.3_revised.md  §1.1
//   08_การคำนวณ/16_ระบบดูด_blower_และ_MOSFET.md
// ─────────────────────────────────────────────────────────────
#include <esp_idf_version.h>
#if ESP_IDF_VERSION_MAJOR < 5
#error "ต้องใช้ Arduino-ESP32 core 3.x (ESP-IDF v5) — ดู platformio.ini"
#endif

// ── ขา GPIO — ตรงกับ system_architecture.md §3.2 ────────────
// §3.2 ระบุชัดว่าขานี้เป็น "GPIO ธรรมดา ไม่ผูก LEDC"
// วงจรที่ขา: R 100 Ω อนุกรมเข้าเกต + pull-down 10 kΩ ลงกราวด์ + ไดโอด SS34 คร่อมโหลด
constexpr int PIN_SUCTION_EN = 21;

// ── สเปกของ blower ที่ใช้จริง ────────────────────────────────
// AVC BA10033B12U · 12 V · 2.4 A (28.8 W) · centrifugal 97 mm  [สเปก]
constexpr float BLOWER_V_NOM      = 12.0f;
constexpr float BLOWER_I_RATED_A  = 2.4f;
// เกณฑ์ผ่านของกระแส: 2.4 × 1.15 = 2.76 A (test_design §1.1 ตารางที่ 1)
constexpr float BLOWER_I_LIMIT_A  = 2.76f;

// ── โหมดการขับ ───────────────────────────────────────────────
// §3.5 สรุปว่า "เริ่มด้วยเปิด-ปิดอย่างเดียว" เพราะไล่ FSM ทั้ง 12 state
// แล้วไม่มี state ไหนใช้กำลังดูดระดับกลาง
//
// 🔴 ห้าม PWM ที่ 20 kHz เด็ดขาด — §3.5 คำนวณไว้ว่าจะทิ้งความร้อน
//    1.066 W ทำให้ MOSFET ร้อนขึ้น +66 °C  (25 Hz ทิ้งแค่ 0.346 W = +21 °C)
//    blower เป็นมอเตอร์ไร้แปรงถ่านที่มีวงจรขับในตัว การสับไฟ 20,000 ครั้ง/วินาที
//    คือการปลุก-ดับวงจรนั้น ซึ่งมันไม่ได้ถูกออกแบบมาให้ทำแบบนั้น
//
// โค้ดนี้จึงบังคับช่วงความถี่ไว้ และจะปฏิเสธค่าที่เกิน
constexpr uint32_t PWM_FREQ_DEFAULT_HZ = 25;    // §3.5 timer T3
constexpr uint32_t PWM_FREQ_MIN_HZ     = 10;
constexpr uint32_t PWM_FREQ_MAX_HZ     = 50;    // เพดานแข็ง — เกินนี้ปฏิเสธ
constexpr uint8_t  PWM_RES_BITS        = 10;    // §3.5 timer T3 = 10-bit
constexpr int      PWM_MAX             = (1 << PWM_RES_BITS) - 1;

// ── ขีดจำกัดความปลอดภัยของการทดสอบ ──────────────────────────
constexpr uint32_t MAX_ON_MS   = 120000;  // เปิดค้างได้ไม่เกิน 2 นาที
constexpr uint32_t DEADMAN_MS  = 150000;  // ไม่มีคำสั่งใหม่เกินนี้ = ปิดเอง
