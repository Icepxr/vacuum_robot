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

> **Pi 5 ตัวจริง (`uchida@10.137.154.184`) เป็น Ubuntu 24.04 + กล้อง USB Logitech BRIO** — ไม่ใช่ Raspberry Pi OS + CSI ตามที่เคยเขียน (เหตุผล: ต้องใช้ ROS เทอมหน้า · ดู C22 ในไฟล์ 10) · picamera2 ใช้บน Ubuntu ไม่ได้ ให้ใช้ `--source usb` (OpenCV/V4L2) แทน

```bash
# บนโน้ตบุ๊ก: ส่งโค้ดขึ้น Pi (~/mrc) แล้วรัน setup — ดู scripts/
bash scripts/deploy_to_pi.sh --setup      # ครั้งแรก (ต้อง sudo บน Pi) แล้ว sudo reboot
bash scripts/deploy_to_pi.sh --status     # ตรวจว่าอะไรพร้อม

# บน Pi
source ~/mrc/.venv/bin/activate
python src/meter_reader.py --source usb
```

## ขั้น C — daemon รับคำสั่งถ่ายจาก ESP32 (12 ก.ย. 2026 · C18 ปิดแล้ว)

```
ESP32 ──#E,<ms>,CAPTURE_REQ,<n>*CC──▶ capture_daemon.py ── หยิบเฟรมล่าสุด → jpg ลง SD ──▶ $K,<n>,1*CC
                                                         └─ OCR ทีหลังใน thread → readings.jsonl
```

```bash
# บน Pi (venv เปิดแล้ว · ต้องมี /dev/ttyAMA0 จาก setup_pi.sh base + reboot)
python src/capture_daemon.py                        # BRIO index 0 · MJPG 1080p เปิดค้าง
python src/capture_daemon.py --port /dev/ttyUSB0    # ทดสอบผ่าน USB-TTL ก่อนต่อสาย GPIO
python src/capture_daemon.py --image photos/x.jpg   # ไม่มีกล้อง: ทดสอบลิงก์ล้วนๆ

# ทดสอบบนโน้ตบุ๊ก ไม่ต้องมี Pi/กล้อง/cv2 (pty ปลอม + backend ปลอม) — ผ่านแล้ว 12 ก.ย.
python -m pytest tests/ -q
```

กติกาในไฟล์: ตอบ `$K` **ทันทีที่ภาพลง SD ไม่รอ OCR** (หน้าต่าง 5 s) · กล้องเปิดค้างใน thread (แบบเปิด-ปิดต่อรูปช้า 1.66 s [วัดจริง]) · ทิ้ง boot log ของ ESP32 เงียบๆ · ไม่แตะเครือข่าย
รูปแบบเฟรม + CRC8 อยู่ใน `src/mrc_protocol.py` (ต้องตรงกับ `src/robot/comm_codec.h`)
**ยังไม่เคยรันบน Pi กับ ESP32 จริง** — ทำวันที่ 16 ก.ย.

## ขั้น E ขั้นต่ำ — แอปควบคุมบน Pi (15 ก.ย. 2026 · **รันบน Pi จริงผ่านแล้ว 16 ก.ย.** — `cap` จาก ESP32 เด้งขึ้นเว็บ · CPU ~17 % · ยังใช้ `--image` แทนกล้อง)

`src/mrc_web.py` **ครอบ** `capture_daemon.py` (ไม่แทนที่): daemon ยังคุย UART เหมือนเดิม · FastAPI เพิ่มภาพสด MJPEG · WebSocket เหตุการณ์ · ปุ่มถ่ายจากเว็บ · รายการค่าที่อ่านได้ · หน้าเว็บ vanilla ไม่โหลดอะไรจากเน็ต

```bash
python src/mrc_web.py                      # UART /dev/ttyAMA0 · BRIO · http://<pi>:8000
python src/mrc_web.py --no-serial          # ไม่มี ESP32
python -m pytest tests/ -q                 # 19 เทสต์ (daemon + web) — ผ่านบน Mac 15 ก.ย.
bash scripts/start_web.sh [--image|--stop]   # รันเบื้องหลังบน Pi · log ที่ logs/web.log (ใช้แทน systemd ระหว่างพัฒนา)
sudo cp systemd/mrc-web.service /etc/systemd/system/ && sudo systemctl enable --now mrc-web
```

**สิ่งที่หน้าเว็บตั้งใจ *ไม่* มี:** ปุ่ม E-STOP/ขับ/ยกเสาที่กดได้ — ESP32 ยังรับแค่ `CAPTURE_REQ`/`$K` (C19/C20) ปุ่มที่กดแล้วหุ่นไม่หยุดจริงอันตรายกว่าไม่มีปุ่ม · จะเปิดเมื่อ ESP32 รับ `$E`/`$V`
**schema กลาง (C23):** ทุกแถวใน `readings.jsonl` มี `meter_id` · `status` (`ocr`→`confirmed`/`rejected`) · `confirmed_value` แยกจาก `value` ตั้งแต่แถวแรก — ARIA ใช้ร่วมได้โดยไม่ต้อง migrate

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
- กล้องที่ต่ออยู่จริงคือ Logitech BRIO (USB) — ยังไม่อยู่ใน BOM · เสียบพอร์ต USB 2.0 อยู่ (ได้สูงสุด 1080p@30 MJPG) ย้ายไป USB 3 น่าจะได้ 4K [ยังไม่ยืนยัน]
- ลิงก์ UART ไป ESP32 (`/dev/ttyAMA0` · ดู `system_architecture.md` §3.7) ยังไม่ได้เขียน
- **โครงสร้างเป้าหมายของโฟลเดอร์นี้ (แพ็กเกจ `mrc/` · เว็บแอป · UART · กล้อง 2 stream) อยู่ใน [`01_เอกสารโครงการ/software_architecture.md`](../01_เอกสารโครงการ/software_architecture.md) §3** — `grab_picamera2()` แบบเปิด-ปิดต่อรูปใช้ในระบบจริงไม่ได้ (เสีย 1.5 s ในหน้าต่าง 5 s · ดูไฟล์ 19 §19.4)
