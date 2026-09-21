# archive — โค้ดที่ไม่ได้ใช้แล้ว (เก็บไว้ ไม่ลบ · 21 ก.ย. 2026)

ไม่มีอะไรในโฟลเดอร์นี้ถูกบิลด์/รัน/ทดสอบ · ย้ายมาเพื่อให้ `src/` และ `11_pi5_vision/src/` เหลือแต่ของที่ใช้จริง

| ไฟล์ | เดิมอยู่ที่ | ทำอะไร | ทำไมเลิกใช้ |
|---|---|---|---|
| `firmware_wifi_test/main.cpp` + `secrets.h.example` | `src/` (env `wifi_test`) | ทดสอบ ESP32 ต่อ Wi-Fi (commit แรกๆ) | เฟิร์มแวร์ `robot` ไม่เปิด Wi-Fi — Pi เป็นคนต่อเน็ต ESP32 คุยกับ Pi ทาง UART เท่านั้น (software_architecture.md) · env `wifi_test` ถูกถอดออกจาก `platformio.ini` |
| `pi5/oled_status.py` | `11_pi5_vision/src/` (`--oled`) | ขับจอ OLED SSD1306 I²C บน Pi 4 บรรทัด | จอจริงเป็น GC9A01 SPI ต่อกับ ESP32 (ไฟล์ 10 C32) — จอบน Pi ไม่มี · ถ้าวันหนึ่งใส่จอ I²C ที่ Pi ค่อยหยิบกลับ (ต้อง `pip install luma.oled`) |

วิธีหยิบกลับ: `git mv` กลับที่เดิม แล้วดู `git log --follow <ไฟล์>` ว่าตอนถอดออกแก้อะไรไปบ้าง
