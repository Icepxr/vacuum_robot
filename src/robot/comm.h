#pragma once
// comm.h — ลิงก์ ESP32 ⇄ Pi 5 บน UART0 (GPIO 43 TX / 44 RX) ตาม system_architecture.md §3.7 §7
// ขั้น C: #E CAPTURE_REQ · $K   ·   ขั้น E: $V $S $E $C $P → #A/#N · #T 10 Hz
#include <Arduino.h>

enum class CaptureState : uint8_t { IDLE, WAITING, OK, FAIL, TIMEOUT };

void         commSetup();            // Serial0.begin บนขา 44/43 — เรียกใน setup()
void         commTick();             // อ่าน/parse บรรทัดจาก Pi + ตรวจ timeout + ส่ง #T — เรียกทุกรอบ loop()
bool         commRequestCapture();   // ส่ง #E,<ms>,CAPTURE_REQ,<n> · false ถ้ายังรอครั้งก่อนอยู่
CaptureState commCaptureState();
uint32_t     commLastRoundtripMs();
void         commPrintStatus();
void         commSendEvent(const char* code, const char* detail);   // #E,<ms>,<code>,<detail>
