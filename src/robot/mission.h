#pragma once
// mission.h — ผูก mission_core.h เข้ากับโมดูลจริง (ล้อ/ดูด/เซอร์โว/comm) · คำสั่งคอนโซล `mis …`
#include <Arduino.h>
void missionSetup();
void missionTick();                       // เรียกทุกรอบ loop()
void missionCommand(const String& sub);   // "start [n]" · "abort" · "st" · "set <key> <ค่า>"
void missionAbort(const char* why);       // เรียกจาก stopAllSystems
bool missionRunning();
void missionHelp();
