#pragma once
// servo_x.h — เซอร์โวตัวที่ 2 (MG996R) "ขยับแกน X" ของกล้อง — แยกขาจากเซอร์โวยกเสา (19 ก.ย. 2026 · C30)
// ขา GPIO18 = SERVO_B ตาม system_architecture §3.2 (LEDC 50 Hz 14 บิต แชร์ timer กับ SERVO_A ได้เพราะ freq/res เท่ากัน)
// ไม่บล็อก: เดินทีละ 10 us ทุก 24 ms ใน servoXTick() (อัตราเดียวกับเสา — กันกระชากเฟือง)
// ยังไม่มี G11 (สองตัวต้องมุมเท่ากัน) เพราะตัวนี้ทำหน้าที่คนละอย่างกับเสา
#include <Arduino.h>

void servoXSetup();                       // กดขา LOW · ยังไม่ผูก PWM (ไม่มีสัญญาณ = เซอร์โวไม่ขยับ)
void servoXTick();                        // ทุกรอบ loop()
bool servoXMoveTo(int us);                // 500–2500 us · เริ่ม slew · false ถ้านอกช่วง/ผูกขาไม่ได้
void servoXRelease(const char* why);      // ปล่อยสัญญาณ (ฮอร์นหมุนมือได้ · ตำแหน่งจะไม่รู้)
bool servoXAttached();
bool servoXMoving();
int  servoXCurrentUs();                   // 0 = ยังไม่ผูก
void servoXCommand(const String& cmd);    // คอนโซล: sx <us> | sx off | sx st
