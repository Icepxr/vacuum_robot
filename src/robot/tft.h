#pragma once
// tft.h — จอกลม GC9A01 1.28" 240×240 SPI บน ESP32-S3 (19 ก.ย. 2026 · C32)
// ขาตาม system_architecture §3.2: SCK GPIO38 · MOSI GPIO39 · DC GPIO40 · CS GPIO47 · RST → EN (รีเซ็ตพร้อมชิป) · BL → 3.3 V
// ไลบรารี LovyanGFX (GC9A01 native · SPI DMA) · วาดลง sprite ใน PSRAM แล้ว push ทีเดียว (ไม่กะพริบ) · ~5 fps พอสำหรับสถานะ
// ข้อมูลที่จอโชว์แต่ ESP32 ไม่รู้เอง (IP ของ Pi · ค่ามิเตอร์ล่าสุด · CO2) มาจาก Pi ทางเฟรม $D ทุก 1 s (+ทันทีเมื่อมีเหตุการณ์)
// C35 (21 ก.ย.): จอ "นิ่ง" ไม่สลับหน้าเอง — หน้าปกติ = อากาศ · เปลี่ยนเฉพาะเมื่อมีเหตุ (ถ่ายภาพ/ค่าอ่าน/Pi มีปัญหา/ยังไม่มี browser)
//   ลำดับความสำคัญ: E-STOP > Pi เงียบ > เหตุการณ์ (evt) > ปัญหาร้ายแรง (warn NOIP/HOT) > ไม่มี browser (IP) > อากาศ (+แถบเตือน NOCAM/DISK/NOAIR)
//   เวลาค้างของเหตุการณ์อยู่ที่ Pi (DISPLAY_HOLD_S ใน mrc_web.py) — จอโชว์ตามเฟรมล่าสุดเท่านั้น ไม่มี timer เอง
#include <Arduino.h>

struct TftInfo {            // ที่ Pi ส่งมา ($D) — ว่าง = ยังไม่ได้รับ
  char ip[24]      = "";
  char reading[16] = "";
  int  co2 = -1, tvoc = -1, aqi = -1;
  int  temp10 = -1000, rh10 = -1;       // ×10 (ไม่ใช้ float ในเฟรม) · -1000/-1 = ไม่มี
  int  clients = -1;                    // C35 จำนวน browser ที่ต่อ Pi อยู่ · 0 = ยังไม่มีใครเปิด → โชว์ IP · -1 = Pi รุ่นเก่าไม่ส่ง
  char warn[8] = "";                    // C35 ปัญหาค้างฝั่ง Pi: NOIP HOT (เต็มจอ) · NOCAM DISK NOAIR (แถบเตือน) · "" = ปกติ
  char evt[8]  = "";                    // C35 เหตุการณ์ที่ Pi ยังถือไว้: CAP SAVED READ NOREAD CAPFAIL DEADMAN · "" = ไม่มี
  char arg[16] = "";                    //   ค่าประกอบ (READ → ค่ามิเตอร์ · CAPFAIL → เหตุ)
  uint32_t rxMs = 0;
};

void tftSetup();
void tftTick();                                   // ทุกรอบ loop() · วาดใหม่ทุก 200 ms
void tftSetInfo(const char* ip, const char* reading, int co2, int tvoc, int aqi, int temp10, int rh10,
                int clients = -1, const char* warn = "", const char* evt = "", const char* arg = "");   // จาก comm.cpp เมื่อได้ $D
bool tftReady();
