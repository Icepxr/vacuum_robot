#pragma once
// tft.h — จอกลม GC9A01 1.28" 240×240 SPI บน ESP32-S3 (19 ก.ย. 2026 · C32)
// ขาตาม system_architecture §3.2: SCK GPIO38 · MOSI GPIO39 · DC GPIO40 · CS GPIO47 · RST → EN (รีเซ็ตพร้อมชิป) · BL → 3.3 V
// ไลบรารี LovyanGFX (GC9A01 native · SPI DMA) · วาดลง sprite ใน PSRAM แล้ว push ทีเดียว (ไม่กะพริบ) · ~5 fps พอสำหรับสถานะ
// ข้อมูลที่จอโชว์แต่ ESP32 ไม่รู้เอง (IP ของ Pi · ค่ามิเตอร์ล่าสุด · CO2) มาจาก Pi ทางเฟรม $D ทุก 1 s
#include <Arduino.h>

struct TftInfo {            // ที่ Pi ส่งมา ($D) — ว่าง = ยังไม่ได้รับ
  char ip[24]      = "";
  char reading[16] = "";
  int  co2 = -1, tvoc = -1, aqi = -1;
  int  temp10 = -1000, rh10 = -1;       // ×10 (ไม่ใช้ float ในเฟรม) · -1000/-1 = ไม่มี
  uint32_t rxMs = 0;
};

void tftSetup();
void tftTick();                                   // ทุกรอบ loop() · วาดใหม่ทุก 200 ms
void tftSetInfo(const char* ip, const char* reading, int co2, int tvoc, int aqi, int temp10, int rh10);   // จาก comm.cpp เมื่อได้ $D
bool tftReady();
