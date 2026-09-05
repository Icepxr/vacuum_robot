# 10_firmware_esp32 — เฟิร์มแวร์ ESP32-S3 N16R8

> ## ⚠️ โค้ดจริงยังอยู่ที่ **รากของ repo** ไม่ใช่ในโฟลเดอร์นี้
> commit แรกบน GitHub (`d54a05c` — ESP32-S3 Wi-Fi connection test) วางโปรเจกต์ PlatformIO
> ไว้ที่รากแล้ว: `platformio.ini`, `src/main.cpp`, `src/secrets.h.example`
>
> **ยังไม่ตัดสินใจว่าจะย้ายเข้ามาในโฟลเดอร์นี้หรือไม่** — ถ้าย้าย เครื่อง Windows ต้องเปิด
> VSCode/PlatformIO ที่โฟลเดอร์ `10_firmware_esp32/` แทนรากโปรเจกต์ (PlatformIO ต้องการ
> `platformio.ini` อยู่ที่รากของโฟลเดอร์ที่เปิด)

## ตั้งค่าก่อนคอมไพล์ครั้งแรก

```bash
cp src/secrets.h.example src/secrets.h   # แล้วใส่ SSID/รหัสผ่านจริง
```
`src/secrets.h` อยู่ใน `.gitignore` แล้ว — **ห้าม commit**

## ข้อมูลที่ยืนยันแล้วจาก `01_เอกสารโครงการ/system_architecture.md` (rev.6/rev.7)

| หัวข้อ | ค่า | อ้างอิง |
|---|---|---|
| บอร์ด | ESP32-S3 N16R8 | §1.1 |
| Framework | Arduino-ESP32 core 3.x (ESP-IDF v5 ข้างใน) | หัวเอกสาร |
| ลิงก์ไป Pi 5 | UART0 ฮาร์ดแวร์ GPIO 43/44 (**ไม่ใช่ USB-CDC**) — ถาวร | §3.7, §3 rev.5 |
| การ flash | **ผ่านช่อง USB native (GPIO 19/20) เท่านั้น** ห้าม flash ผ่านช่อง UART เพราะชิปแปลงสัญญาณจะแย่งขา 43/44 กับสาย Pi | §3 rev.5 |
| ความปลอดภัย | ESP32 เป็นเจ้าของ ไม่ใช่ Pi5 — Pi5 "ขอ" ได้ ESP32 "ปฏิเสธ" ได้เสมอ | §2 ข้อ 1 |

### ตรวจแล้ว: `platformio.ini` ปัจจุบันสอดคล้องกับข้อกำหนดข้างบน
`-D ARDUINO_USB_CDC_ON_BOOT=1` + `-D ARDUINO_USB_MODE=1` ทำให้ `Serial` ไปออกช่อง USB native
จึง**ไม่แย่งขา 43/44** ที่จองไว้ให้ Pi 5 — ตรงกับ §3.7 · `board = esp32-s3-devkitc-1`
(หมายเหตุ: บอร์ดในเอกสารระบุ **N16R8** = flash 16 MB + PSRAM 8 MB · ค่า default ของ
`esp32-s3-devkitc-1` ใน PlatformIO **ยังไม่ได้ตรวจว่าเปิด PSRAM/ตั้ง flash 16 MB ให้หรือไม่** —
ต้องยืนยันก่อนใช้ PSRAM จริง ยังไม่กระทบโค้ด Wi-Fi test ปัจจุบัน)

## ก่อนเขียนโค้ดจริง — อ่าน 2 ไฟล์นี้ก่อนเสมอ
1. `01_เอกสารโครงการ/system_architecture.md` §3 (pin mapping ฉบับจริง — งบ 25 ขา)
2. `08_การคำนวณ/10_ประเด็นค้างและความขัดแย้ง.md` (ประเด็นที่ยังไม่ปิด เช่น ช่วงหมุน MG996R, C11/C12)

## กติกา
- **ห้าม hardcode pin กระจายหลายไฟล์** — ให้มีไฟล์ config เดียวแล้วอ้างจากตาราง §3
