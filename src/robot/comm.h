#pragma once
// comm.h — ลิงก์ ESP32 ⇄ Pi 5 บน UART0 (GPIO 43 TX / 44 RX) ตาม system_architecture.md §3.7 §7
// ขั้น C ของแกนหลัก: มีแค่ 2 ข้อความ — ส่ง CAPTURE_REQ · รอ $K (C18 ปิด 12 ก.ย. 2026)
// ข้อความอื่นของ §7 ($V $C $M … #T) ค่อยเติมเข้าไฟล์นี้ในขั้น E โดยไม่ต้องรื้อ
#include <Arduino.h>

enum class CaptureState : uint8_t { IDLE, WAITING, OK, FAIL, TIMEOUT };

void         commSetup();            // Serial0.begin บนขา 44/43 — เรียกใน setup()
void         commTick();             // อ่าน/parse บรรทัดจาก Pi + ตรวจ timeout — เรียกทุกรอบ loop()
bool         commRequestCapture();   // ส่ง #E,<ms>,CAPTURE_REQ,<n> · false ถ้ายังรอครั้งก่อนอยู่
CaptureState commCaptureState();
uint32_t     commLastRoundtripMs();  // เวลาตั้งแต่ส่ง REQ จนได้ $K ครั้งล่าสุด (ms)
void         commPrintStatus();
