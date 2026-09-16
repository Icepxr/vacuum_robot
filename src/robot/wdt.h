#pragma once
// wdt.h — Task Watchdog ของเฟิร์มแวร์รวม (C29/§19.8.4 · 16 ก.ย. 2026)
//
// ทำไม: loop() ค้าง (C29 วัดได้ 2 s) = ล้อค้าง duty เดิม ไม่มีใครหยุด — deadman ก็อยู่ใน loop() ที่ค้าง
// ทำอะไร: ถ้า loop() ไม่ได้เรียก wdtFeed() ภายใน WDT_TIMEOUT_MS → panic → รีบูต → GPIO ลอย →
//         DRV8871 coast (pulldown ในตัว · datasheet Table 1) · เกต MOSFET ดับ (pull-down 10 kΩ ไฟล์ 04)
// Arduino core 3.x init TWDT ไว้แล้ว (sdkconfig: 5 s · idle CPU0 · panic) — เรา deinit แล้ว init ใหม่ให้เฝ้า loopTask ตัวเดียว
// คำสั่งคอนโซลที่บล็อกโดยตั้งใจ (ชุดทดสอบ m/sv/bl) รันใต้ wdtSuspend()/wdtResume() — เป็นงานบนโต๊ะ ไม่ใช่ตอนวิ่ง
#include <esp_task_wdt.h>
#include <esp_system.h>

constexpr uint32_t WDT_TIMEOUT_MS = 1000;   // §19.8.4: จำกัดระยะวิ่งค้างที่ v × 1 s (150 mm ที่เพดานเริ่มต้น)

inline const char* wdtResetReason() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:   return "POWERON";
    case ESP_RST_SW:        return "SW";
    case ESP_RST_PANIC:     return "PANIC";
    case ESP_RST_INT_WDT:   return "INT_WDT";
    case ESP_RST_TASK_WDT:  return "TASK_WDT";
    case ESP_RST_WDT:       return "WDT";
    case ESP_RST_BROWNOUT:  return "BROWNOUT";
    case ESP_RST_DEEPSLEEP: return "DEEPSLEEP";
    case ESP_RST_EXT:       return "EXT";
    default:                return "UNKNOWN";
  }
}

inline bool wdtSetup() {
  esp_task_wdt_deinit();                                   // ของ core (5 s · idle CPU0) — ถ้าไม่มีก็คืน error เฉยๆ
  esp_task_wdt_config_t cfg{};
  cfg.timeout_ms = WDT_TIMEOUT_MS;
  cfg.idle_core_mask = 0;                                  // ไม่เฝ้า idle — เฝ้าเฉพาะ loopTask (บล็อกใน semaphore ก็โดน ซึ่ง idle จับไม่ได้)
  cfg.trigger_panic = true;                                // sdkconfig PANIC_PRINT_REBOOT → รีบูต
  if (esp_task_wdt_init(&cfg) != ESP_OK) return false;
  return esp_task_wdt_add(NULL) == ESP_OK;                 // NULL = task ปัจจุบัน (loopTask)
}
inline void wdtFeed()    { esp_task_wdt_reset(); }
inline void wdtSuspend() { esp_task_wdt_delete(NULL); }
inline void wdtResume()  { esp_task_wdt_add(NULL); }
