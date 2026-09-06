# 11_pi5_vision — กล้อง + OCR อ่านมิเตอร์ บน Raspberry Pi 5

**หน้าที่:** กล้องถ่ายรูปมิเตอร์ · Pi 5 จัดการทั้งหมด · OCR ดึงตัวเลข · เก็บเข้าฐานข้อมูล

```
กล้อง → Pi 5 ─┬─ ถ่ายภาพ (เสาต้องนิ่งแล้ว)
              ├─ preprocess ด้วย OpenCV
              ├─ OCR ดึงตัวเลข
              ├─ เขียนลง SD ทันที        ← meter_reader.py จบตรงนี้
              └─ sync ขึ้น Supabase       ← sync_supabase.py แยกต่างหาก
```

## 🔴 กติกาข้อเดียวที่ห้ามละเมิด

**เขียนลงเครื่องก่อนเสมอ แล้วค่อย sync** — เน็ตต้องไม่ใช่จุดตายของภารกิจ
`meter_reader.py` ไม่แตะเครือข่ายเลยแม้แต่บรรทัดเดียว ถ้าสนามไม่มี WiFi หุ่นยังทำงานครบ
ข้อมูลอยู่ใน `data/readings.jsonl` กับ `data/images/` ดึงออกทีหลังได้

## เริ่มพัฒนาได้ตั้งแต่วันนี้ — ยังไม่ต้องมีกล้องหรือ Pi

ถ่ายรูปมิเตอร์ด้วยมือถือ 20–30 รูป ใส่โฟลเดอร์ แล้วรันบนโน้ตบุ๊ก

```bash
pip install -r requirements.txt
python src/meter_reader.py --source folder --path ./photos --debug-dir ./debug
```

จะพิมพ์ออกมาว่าอ่านได้กี่ % และเซฟภาพหลัง threshold ไว้ใน `./debug` ให้ดูว่าที่อ่านพลาดเพราะอะไร
ปรับ `src/roi_config.json` แล้วรันซ้ำจนพอใจ **นี่คืองานของช่วง 8–15 ก.ย.**

## บน Pi 5

```bash
sudo apt install -y tesseract-ocr python3-picamera2
pip install -r requirements.txt
python src/meter_reader.py --source picamera2
```

## ส่งขึ้นฐานข้อมูล

```bash
export SUPABASE_URL="https://<ref>.supabase.co"
export SUPABASE_KEY="<key>"
python src/sync_supabase.py --dry-run     # ดูก่อนว่าจะส่งอะไร
python src/sync_supabase.py
```

⚠ **ต้องเปิดโปรเจกต์ Supabase ใหม่สำหรับหุ่นโดยเฉพาะ** — โปรเจกต์ `MCCMU's Project` ที่มีอยู่
เป็นเว็บชมรมของงานอื่น (มีตาราง `members` `albums` `places` `docs` `audit_log`) **ห้ามเอาข้อมูลหุ่นไปปน**
โครงตารางอยู่ใน `src/schema.sql`

## ⚠ ยังตัดสินไม่ได้จนกว่าจะเห็นมิเตอร์จริง

| ชนิดมิเตอร์ | ใช้ `--engine` | หมายเหตุ |
|---|---|---|
| ตัวเลขกลไกหมุน (มิเตอร์น้ำทั่วไป) | `tesseract` | ใช้ได้ดีถ้า preprocess ดี |
| จอ **7-segment** | `ssocr` | **Tesseract อ่านแทบไม่ได้** · `sudo apt install ssocr` · อาจต้องตั้ง `"invert": true` |
| เข็มชี้ | ❌ ยังไม่มีโค้ด | OCR ใช้ไม่ได้เลย ต้องหามุมเข็มด้วย Hough transform — ต้องเขียนเพิ่ม |

## สิ่งที่ยังไม่ได้ทำ

- ยังไม่เคยรันจริงสักครั้ง ทั้งบนโน้ตบุ๊กและบน Pi
- ยังไม่ได้เลือกรุ่นกล้อง ยังไม่อยู่ใน BOM
- ลิงก์ UART ไป ESP32 (`/dev/ttyAMA0` · ดู `system_architecture.md` §3.7) ยังไม่ได้เขียน
