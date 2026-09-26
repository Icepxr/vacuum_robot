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

> **Pi 5 ตัวจริง (`uchida@uchida-pi5.local` (บน hotspot iPhone)) เป็น Ubuntu 24.04 + กล้อง USB Logitech BRIO** — ไม่ใช่ Raspberry Pi OS + CSI ตามที่เคยเขียน (เหตุผล: ต้องใช้ ROS เทอมหน้า · ดู C22 ในไฟล์ 10) · picamera2 ใช้บน Ubuntu ไม่ได้ ให้ใช้ `--source usb` (OpenCV/V4L2) แทน

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

**16 ก.ย. — โหมดขับเอง:** หน้า **`/drive`** rev.2 (ดีไซน์ใหม่: viewport มุมมน · HUD แก้ว · จอย+วงโค้งทิศ · dial ความเร็ว · dock ดูด/แปรง/ถ่าย · ปุ่มหยุดฉุกเฉินกลม) + **ตั้งค่า 7 แท็บ** (ขับ: เพดาน/ความไวหมุน/ramp/deadzone/กลับทิศ/ด้าน+ขนาดจอย/ดูดอัตโนมัติ · กล้อง: fps/ตาราง/กระจก/**ลากกรอบ OCR บนภาพ → `POST /api/roi`** · ทำความสะอาด · การเตือน เสียง/สั่น · จอ: สีเน้น/ความหนาแน่น/ปุ่มใหญ่/กันจอดับ · ปุ่ม · สถานะ) เก็บใน localStorage · `/` = หน้าวินิจฉัยสำหรับช่าง

**26 ก.ย. — ARIA POV (ยังไม่ได้ deploy ลง Pi):** หน้า `/drive` ใน workspace ปรับให้ภาพกล้องเต็มพื้นที่, ใช้โลโก้ ARIA จาก `design/aria-logo-reference.png`, วางปุ่มขับและเครื่องมือเป็นแผงลอยที่ใช้บนมือถือได้, แยกปุ่มหยุดฉุกเฉินไว้ด้านล่างเสมอ และแสดงสถานะเมื่อไม่มีภาพจริง ตรวจเลย์เอาต์ในเบราว์เซอร์แล้ว แต่ยังต้องทดลองกับกล้องและหุ่นจริงก่อนใช้งานภาคสนาม

หน้าตั้งค่าใหม่แบ่งเป็น **ใช้งาน / ภาพและจอ / ขั้นสูง / สถานะ**: หน้าแรกมีรูปแบบขับ ความเร็ว เสียงและสั่น ส่วนค่ามอเตอร์และคาลิเบรตพับเป็นกลุ่มที่เปิดได้ทีละกลุ่ม ค่าที่บันทึกเดิมยังใช้ต่อได้ และการคืนค่าเริ่มต้นต้องยืนยันอีกครั้ง การลากกรอบ OCR จะกลับมาที่หมวดภาพพร้อมปุ่มบันทึกโดยตรง

**27 ก.ย. — แถบอากาศ + จอเตือนหยุดฉุกเฉิน (workspace เท่านั้น):** HUD แสดง eCO₂ / TVOC / AQI / อุณหภูมิ / ความชื้น แตะเพื่อดูรายละเอียดได้ แยกสถานะรอข้อมูล เซนเซอร์กำลังอุ่น ค่าผิดปกติ และลิงก์หลุดโดยไม่ค้างค่าครั้งก่อน; eCO₂ เป็นค่าประมาณจาก VOC ไม่ใช่ CO₂ ที่วัดตรง และ AQI ของ ENS160 มีระดับ 1–5

ปุ่มหยุดฉุกเฉินเปิดจอแดงและพักคำสั่งจากเบราว์เซอร์นี้ ล้างอินพุตและคำสั่งที่ตั้งเวลารอส่งไว้ สถานะเตือนคงอยู่เมื่อรีโหลดแท็บ ต้องยืนยันเองและปล่อยอินพุตขับกลับตำแหน่งกลางก่อนเริ่มใหม่ **ไม่ใช่ hardware interlock และไม่ล็อกผู้ควบคุมรายอื่น** การส่ง WebSocket สำเร็จไม่ได้ยืนยันว่าหุ่นหยุดจริง จอจึงแจ้งให้ตรวจหุ่นและพื้นที่ก่อนกลับไปควบคุม ตรวจเลย์เอาต์ที่ 390×844, 320×568 และ 844×390 ใน static preview แล้ว แต่ยังไม่ได้ deploy หรือทดสอบกับ Pi/ESP32 จริง

ทดสอบ view-state และสคริปต์ควบคุมจริงกับ DOM/WebSocket จำลอง (ไม่ต่อหุ่น): `node 11_pi5_vision/tests/test_drive_state.cjs` จาก root ของ repo

## หา Pi ให้เจอ — ใช้ชื่อ ไม่ใช้ IP (17 ก.ย. 2026)

Pi ต่อ **hotspot iPhone (`دياس`)** เป็นวงหลัก (autoconnect-priority 10 · Wi-Fi อาคาร `JumboPlus_ISB_1415` เป็นสำรอง priority 0)
- หน้าขับ: **`http://uchida-pi5.local:8000/drive`** · ssh: `ssh uchida@uchida-pi5.local` — mDNS ใช้ได้บน hotspot (บนวงมหาลัยถูกกัน ใช้ไม่ได้)
- IP ที่ได้จาก iPhone มักเป็น `172.20.10.2` แต่ DHCP ไม่รับประกัน → อย่าจำเลข ใช้ชื่อ
- ลำดับเปิดใช้: เปิด Personal Hotspot บน iPhone (เปิดหน้านั้นค้างไว้จน Pi ต่อ) → เปิด Pi → มือถือ/Mac ต่อ hotspot เดียวกัน → เปิดหน้าขับ · เว็บขึ้นเองใน ~50 s (systemd)
- เพิ่ม Wi-Fi ใหม่: `bash ~/mrc/scripts/wifi_add.sh` (ถามชื่อ+รหัสบนจอ) · `/api/status` มีฟิลด์ `ip`

## รันเป็น service (systemd) — ทดสอบบน Pi แล้ว 16 ก.ย. 2026 ✅

ติดตั้งไว้แล้วบน Pi ตัวจริง (`enable`) → **เสียบไฟ Pi แล้วเว็บขึ้นเองที่ `http://<ip>:8000/drive` โดยไม่ต้อง ssh**

| ทดสอบ | ผล |
|---|---|
| `enable --now` โดยไม่มีกล้องเสียบ | รันต่อด้วยรูปล่าสุด (`open_camera_or_fallback`) · `cam_ok=false` หน้าเว็บบอก "ไม่มีภาพ" · ลิงก์ ESP32 ปกติ · ไม่วน restart |
| `kill -9` MainPID | systemd เริ่มใหม่เองใน 2 s · process เดียวถือ `/dev/ttyAMA0` (`fuser` ยืนยัน) |
| `systemctl restart` | เว็บตอบใน 1.25 s |
| `sudo reboot` | เว็บตอบ **51 s** หลังสั่ง (Ubuntu Desktop บูต ~46 s + แอป 3 s) · 0 restart · ลิงก์ alive · bad lines 0 |
| ESP32 ตอน Pi รีบูต | **รีบูตตามด้วย** (บนโต๊ะ ESP32 กินไฟจาก USB-C ของ Pi — Pi ดับ USB ตอน shutdown) · บนหุ่นจริง ESP32 อยู่ราง 5 V แยก จะไม่รีบูต |

คำสั่งประจำวัน (บน Pi):
```
sudo systemctl status mrc-web        # ดูว่ารันอยู่ไหม
sudo systemctl restart mrc-web       # หลัง deploy โค้ดใหม่
journalctl -u mrc-web -f             # log สด
sudo systemctl stop mrc-web          # หยุด (เช่นจะรัน start_web.sh --image เพื่อทดสอบ)
```
⚠ `scripts/start_web.sh` จะปฏิเสธถ้า service เปิดอยู่ (กัน 2 process ถือ UART ซ้อน — C25) · ถ้าเสียบกล้องทีหลังต้อง `restart` (ยังไม่ทำ hot-plug)

C29 (16 ก.ย.): ESP32 มี task WDT 1 s — loop ค้าง → รีบูตใน 1.44 s → `#E BOOT,TASK_WDT` → Pi ส่ง `$L` ซ้ำ + log เตือน · บูตปกติ 40 ms
C28 (16 ก.ย.): โหมดแมนวล "คนขับตัดสินใจเอง" — เพดานความเร็วตั้งได้จากแท็บตั้งค่า (`{"t":"limits"}` → `$L`, clamp ที่ฮาร์ดแวร์ 716 mm/s) · เสายกไม่ห้ามขับ (ชิป "เสายกอยู่") · เปิดดูดแล้วล้อรอ 1 s เอง (ชิป "ไต่รอบดูด" จาก `#T` flag 0x04) — รายละเอียดใน `08_การคำนวณ/10` C28
กติกาความปลอดภัยฝั่ง Pi: browser ส่ง `drive` ทุก 100 ms ขณะกด · Pi ถือค่าล่าสุดแล้วส่ง `$V` ซ้ำ 10 Hz เอง · browser เงียบ > 300 ms → Pi ส่ง `$S` · ESP32 มี deadman ของตัวเองอีก 300 ms (G8) · `estop` ไม่ผ่านตัวกรองใดๆ
ปุ่มยกเสาจาก Pi ยังไม่มี (`$M` ยังไม่ทำ) · แบตยังไม่แสดงเพราะเฟิร์มแวร์รวมยังไม่มี ADC (C27) · เซนเซอร์อากาศ ENS160/AHT21 ยังไม่ต่อ (ไฟล์ 21)
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
