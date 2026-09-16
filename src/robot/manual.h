#pragma once
// manual.h — โหมดขับเองจาก Pi (state MANUAL · C19) ผูก manual_core.h เข้ากับล้อจริง
// เข้าโหมดอัตโนมัติเมื่อได้ $V · ออกเมื่อ $S / deadman / E-STOP / mission เริ่ม · C28: ไม่มี guard ที่คนมองเห็นได้เองแล้ว
#include <Arduino.h>
#include "manual_core.h"

void manualSetup();
void manualTick();                                 // ทุกรอบ loop() (≈10 ms)
// คืน nullptr = รับ · ไม่งั้นคืนเหตุผลปฏิเสธสำหรับ #N (MAST_UP / IN_MISSION / SUCTION_SPINUP / …)
const char* manualSetpoint(int v_mm_s, int w_mrad_s);
void manualStop(const char* why);                  // $S — ไล่ลง 0
void manualHalt(const char* why);                  // E-STOP — ตัดทันที
bool manualActive();
bool manualTripped();                              // deadman เพิ่งตัด (อ่านแล้วเคลียร์)
mrc::WheelCmd manualOut();
int manualV(); int manualW();          // setpoint ปัจจุบัน (สำหรับ #T)
const char* manualSetCleaning(int suctionPct, int brushPct);   // $C — คืน nullptr หรือเหตุผลปฏิเสธ
bool manualSetLimits(int vMax_mm_s, int wMax_mrad_s);          // $L — เพดานที่ผู้ใช้ตั้ง · false = ถูก clamp ที่ฮาร์ดแวร์
int  manualVMax(); int manualWMax();
bool manualSpinupHold();                                        // R2 กำลังหน่วงล้อ (flag 0x04 ใน #T)
