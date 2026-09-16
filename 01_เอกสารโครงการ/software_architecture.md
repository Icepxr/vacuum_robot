# สถาปัตยกรรมโปรแกรม — MRC-001 (Browser · Pi 5 · ESP32-S3)

**rev.2 — 11 ก.ย. 2026 (ค่ำ)** · แก้จาก rev.1 ตาม **C22**: Pi 5 ตัวจริงเป็น **Ubuntu 24.04 + กล้อง USB Logitech BRIO** ไม่ใช่ Raspberry Pi OS + CSI → §2.4 · §2.6 · §3.2 · §10 ข้อ 5 เปลี่ยน ส่วนอื่นคงเดิม

เอกสารนี้ออกแบบ *ซอฟต์แวร์ทั้งระบบ 3 ชั้น* — ชั้น ESP32 ภายใน (task/FSM/guard) **ไม่เขียนซ้ำ** ให้ยึด [`system_architecture.md`](system_architecture.md) §5–§8 เป็นหลัก เอกสารนี้เติมส่วนที่ยังไม่มีใครตัดสิน: **Pi 5 ทำอะไร · เว็บแอปอยู่ที่ไหน · ข้อมูลวิ่งทางไหน · หุ่นหยุดยังไงเมื่อ browser หาย**

ตัวเลขทุกตัวในเอกสารนี้ที่เป็นการคำนวณ อยู่ใน [`08_การคำนวณ/19_สถาปัตยกรรมซอฟต์แวร์_Pi5_และเว็บ.md`](../08_การคำนวณ/19_สถาปัตยกรรมซอฟต์แวร์_Pi5_และเว็บ.md) พร้อมป้ายระดับความมั่นใจ
ประเด็นที่เอกสารนี้ขัดกับของเดิม (C18–C21) อยู่ใน [`08_การคำนวณ/10_ประเด็นค้างและความขัดแย้ง.md`](../08_การคำนวณ/10_ประเด็นค้างและความขัดแย้ง.md)

---

## 0. หลักการ — สืบทอด 4 ข้อจาก `system_architecture.md` §0 แล้วเพิ่ม 3 ข้อ

| # | หลักการ | ผลต่อการออกแบบ |
|---|---|---|
| 1–4 | *(เดิม)* ESP32 เป็นเจ้าของความปลอดภัย · แยกชั้นอ่าน→ตัดสิน→สั่ง · guard เป็นโค้ด · ค่าคงที่มาจากที่เดียว | Pi 5 และ browser **ไม่มีทาง**สั่ง PWM ตรง ทุกอย่างผ่าน protocol §7 ที่ ESP32 ปฏิเสธได้ |
| **5** | **เครือข่ายไม่ใช่จุดตาย** (สืบจาก `11_pi5_vision/README.md`) | Pi 5 เป็น Wi-Fi hotspot เอง ไม่พึ่ง Wi-Fi สนาม · Supabase อยู่นอกเส้นทางเรียลไทม์ทั้งหมด · ภารกิจเดินครบได้แม้ไม่มี browser ต่ออยู่เลย |
| **6** | **browser หาย = หุ่นหยุด** (deadman 3 ชั้น) | browser → Pi 5 → ESP32 แต่ละชั้นมี timeout ของตัวเอง ชั้นล่างไม่เชื่อชั้นบน — ดู §5 |
| **7** | **Pi 5 เป็น "ผู้ประสานงาน" ไม่ใช่ "ผู้ควบคุม"** | Pi 5 ไม่มี control loop · ไม่มี state machine ของหุ่น (FSM อยู่บน ESP32) · Pi 5 แค่ แปล-ส่งต่อ-บันทึก-แสดงผล + งานหนักที่ ESP32 ทำไม่ได้ (กล้อง/OCR) |

> **ทำไมข้อ 7 สำคัญ:** ถ้า Pi 5 มี FSM ของตัวเองซ้อนกับ ESP32 จะได้สองสมองที่เห็นสถานะไม่ตรงกัน (Pi คิดว่าเสาพับแล้ว ESP32 ยังยกอยู่) นี่คือบั๊กประเภทที่ทำให้เซอร์โวไหม้ตอนสาธิต · **ความจริงของสถานะหุ่นมีที่เดียว = ฟิลด์ `state` ใน `#T` ที่ ESP32 ส่งมา** Pi 5 และ browser แค่สะท้อนมัน

---

## 1. ภาพรวม 3 ชั้น

```
┌─────────────── Browser (โน้ตบุ๊ก/มือถือ ต่อ Wi-Fi hotspot ของ Pi) ───────────────┐
│  หน้าเว็บเดียว (static HTML/JS · ไม่มี build step · ไม่โหลดอะไรจากอินเทอร์เน็ต)   │
│  · จอยสติ๊ก/ปุ่มขับ  · ปุ่ม ดูด/แปรง/ยกเสา/ถ่าย/STOP/E-STOP                        │
│  · ภาพสดจากกล้อง     · แดชบอร์ด: state · v/ω · ระยะ US · V_bat · ค่ามิเตอร์ล่าสุด  │
└──────────────┬───────────────────────────────────────┬───────────────────────────┘
               │ WebSocket  ws://mrc.local/ws          │ HTTP  /stream.mjpg (MJPEG)
               │ JSON · คำสั่ง ↓ 10 Hz · telemetry ↑ 20 Hz│ ภาพ lores 640×480 ~10 fps
┌──────────────┴───────────────────────────────────────┴───────────────────────────┐
│                       Raspberry Pi 5 — `mrc-robot.service` (Python · asyncio)     │
│                                                                                   │
│   web/app.py ──── hub.py (RobotHub) ──── link/uart.py ───── /dev/ttyAMA0          │
│   FastAPI+WS        · deadman browser→Pi     · เฟรม $/# + CRC8                    │
│   static/           · แปลง JSON ⇄ §7         · ทิ้ง boot log                      │
│                     · เก็บ state ล่าสุด      · นับ rx_hz / crc_err                │
│                     · trigger ถ่ายรูป                                            │
│                          │                                                        │
│   camera/cam.py ─────────┤   BRIO ผ่าน V4L2 · MJPG 1080p เปิดค้างใน thread (~16 fps)  │
│     preview ≤10 fps: ย่อ 640×480 + encode (6 ms) │ still: imwrite 1080p (14 ms) │
│                          │                                                        │
│   vision/meter_reader.py ┤   OCR ใน ProcessPool (ไม่บล็อก event loop)              │
│   store/                 ┤   readings.jsonl · images/ · runs/<id>/telemetry.jsonl │
│                                                                                   │
│   [แยก process] scripts/sync_supabase.py ← systemd timer · ล้มได้ ไม่กระทบอะไร     │
└──────────────────────────────────┬────────────────────────────────────────────────┘
                                   │ UART0 115200 · GPIO14/15 ↔ GPIO44/43 (§3.7)
┌──────────────────────────────────┴────────────────────────────────────────────────┐
│  ESP32-S3 — เฟิร์มแวร์ตาม system_architecture.md §5–§8 (ไม่เปลี่ยน)               │
│  comm/link.cpp บน Serial0 ⇄ FSM ⇄ motion_limiter ⇄ HAL   · Wi-Fi **ปิด**           │
│  USB-CDC (`Serial`) เหลือไว้เป็นคอนโซล debug/คำสั่งทดสอบเดิม m/sv/bl               │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 ใครเป็นเจ้าของอะไร

| เรื่อง | Browser | Pi 5 | ESP32 |
|---|:-:|:-:|:-:|
| control loop (PID · odometry · limiter) | — | — | **✓** |
| FSM และ guard ทั้งหมด | — | — | **✓** |
| ความจริงของ `state` | สะท้อน | สะท้อน + cache | **✓ ต้นทาง** |
| ตัดสินว่าคำสั่งไหน "ทำได้" | — | กรองเบื้องต้น (§4.3) | **✓ ตัดสินจริง** (`#N` ปฏิเสธ) |
| deadman | ส่งซ้ำ 10 Hz | timeout 300 ms → `$S` | G8 300 ms → หยุด |
| กล้อง / OCR / ฐานข้อมูล | แสดง | **✓** | — (แค่บอกว่า "ถ่ายได้แล้ว" และรอ ACK) |
| Wi-Fi / เว็บเซิร์ฟเวอร์ | client | **✓ hotspot + server** | **ไม่มี** |
| log สำหรับรายงาน | — | **✓** (telemetry 20 Hz ลง SD) | — |

---

## 2. ทางเลือกที่พิจารณาและเหตุผลที่เลือก

### 2.1 ใครโฮสต์เว็บแอป

| ทางเลือก | ข้อดี | ข้อเสีย | ตัดสิน |
|---|---|---|---|
| **A · Pi 5 โฮสต์ทั้งหมด** (เลือก) | Pi 5 ต้องมีอยู่แล้วเพื่อกล้อง · Python ตัวเดียวกับ OCR · ESP32 ไม่ต้องแบก TCP/IP | Pi ดับ = เว็บดับ (แต่หุ่นยังปลอดภัยเพราะ G8) | **✓** |
| B · ESP32 โฮสต์ (AsyncWebServer) | ไม่ต้องรอ Pi | Wi-Fi พีค ~500 mA บนราง 5 V ลอจิก (§3.7) · stack Wi-Fi แย่ง CPU/RAM กับ `T_Control` 100 Hz · ส่งภาพกล้องไม่ได้อยู่ดี | ✗ |
| C · Cloud (Supabase Realtime) เป็นตัวกลาง | ดูจากที่ไหนก็ได้ | ต้องมีอินเทอร์เน็ตที่สนาม = ขัดหลักการข้อ 5 · round-trip ระดับร้อย ms ผ่าน WAN ใช้ขับหุ่นไม่ได้ | ✗ (เก็บไว้เป็น sync แบบ batch เหมือนเดิม) |

→ **ESP32 ไม่เปิด Wi-Fi ในเฟิร์มแวร์ `robot`** — env `wifi_test` เก็บไว้เป็นชุดทดสอบเฉยๆ

### 2.2 ส่งภาพสดยังไง

| ทางเลือก | latency | ความยาก | ตัดสิน |
|---|---|---|---|
| **MJPEG ผ่าน HTTP** (`<img src="/stream.mjpg">`) (เลือก) | ~100–200 ms บน LAN | ต่ำที่สุด · `cv2.imencode` + multipart response 20 บรรทัด | **✓** พอสำหรับ "ดูว่ากล้องเห็นอะไร" |
| WebRTC | ~50 ms | สูง (signaling · STUN · aiortc) | ✗ ไม่คุ้มกับ 17 วัน |
| ส่งเฟรม JPEG ผ่าน WebSocket | ใกล้ MJPEG | ต้องเขียน decode ฝั่ง JS เอง | ✗ MJPEG ทำงานเดียวกันฟรี |

แบนด์วิดท์: 640×480 ~10 fps ≈ **3–5 Mbps** [ประมาณการ] เทียบ hotspot ของ Pi ที่ควรได้ ≥ 20 Mbps → headroom ≥ 4× (ไฟล์ 19 §19.1) · ถ้าช้าให้ลดเป็น 5 fps ก่อน ไม่ใช่ลดขนาดภาพ (ยังต้องเห็นตัวเลขมิเตอร์ตอนเล็งกล้อง)

### 2.3 ช่องคำสั่ง/แดชบอร์ด

| ทางเลือก | ตัดสิน |
|---|---|
| **WebSocket · JSON ทั้งสองทาง** (เลือก) | สองทางในช่องเดียว · browser API มีในตัว · ไม่ต้อง broker |
| MQTT | ต้องมี broker เพิ่ม · ดีถ้ามีหลาย client/หลายอุปกรณ์ ซึ่งเราไม่มี |
| REST polling | 20 Hz polling = สิ้นเปลืองและ latency สูง |

### 2.4 Backend stack

| ทางเลือก | ตัดสิน |
|---|---|
| **Python 3.12 (Ubuntu 24.04) · FastAPI + uvicorn · pyserial-asyncio · OpenCV/V4L2** (เลือก · rev.2) | OpenCV มีอยู่แล้วเพื่อ OCR · asyncio รวม UART/WS/กล้องใน event loop เดียว · requirements.txt ปักเวอร์ชันแล้ว · ~~picamera2~~ ใช้บน Ubuntu ไม่ได้ (C22 [วัดจริง]) |
| ROS 2 (เทอมหน้า) | ยังไม่ใช้ตอนนี้ — แต่แยก `link/` `camera/` `vision/` เป็นโมดูล import ได้ ไม่ผูกกับ FastAPI เพื่อให้ห่อเป็น ROS 2 node ได้ทีหลังโดยไม่เขียนใหม่ |
| Flask | ไม่มี WebSocket/asyncio ในตัว ต้องเพิ่มของอีกชั้น |
| Node.js | ต้องมี runtime ที่สอง แล้วเรียก Python สำหรับกล้อง/OCR ผ่าน IPC อีกที |
| ROS 2 | ถูกหลักการแต่เกินขนาดสำหรับ 17 วันและคน 1–2 คน |

### 2.5 Frontend

**HTML + vanilla JS ไฟล์เดียว ไม่มี bundler · ไม่มี CDN** — เพราะสนามไม่มีอินเทอร์เน็ต ทุก `<script src>` ต้องอยู่ใน `static/` ของ Pi
กราฟ: วาดด้วย `<canvas>` เอง (sparkline 3–4 เส้นพอ) หรือ vendor `uPlot` (~45 kB) ลงมาในโฟลเดอร์ · ห้ามใช้ไลบรารีที่ต้องโหลดจากเน็ตตอนรัน

### 2.6 เครือข่าย

| เรื่อง | ค่า |
|---|---|
| **2 โปรไฟล์เครือข่าย สลับกัน** (Pi มี Wi-Fi ตัวเดียว เป็น client กับ AP พร้อมกันไม่ได้) | **แล็บ:** client ของ Wi-Fi แล็บ (ปัจจุบัน `10.137.154.184` [วัดจริง]) — ใช้ SSH/deploy/sync · **สนาม:** hotspot `MRC-001` IP `10.42.0.1` (โปรไฟล์สร้างโดย `setup_pi.sh hotspot` · `autoconnect=no` · เปิดด้วย `sudo nmcli con up MRC-001` **จะตัด SSH ทันที** ต้องเปิดจากจอ/คีย์บอร์ดหรือผ่านหน้าเว็บ) · เว็บเซิร์ฟเวอร์ bind `0.0.0.0` จึงไม่สนว่าอยู่โปรไฟล์ไหน |
| ชื่อเข้าถึง | `http://mrc.local` (avahi มีใน Raspberry Pi OS อยู่แล้ว) หรือ `http://10.42.0.1` |
| การยืนยันตัวตน | **รหัสผ่าน WPA2 ของ hotspot คือชั้นเดียว** — ใครต่อ hotspot ได้ = ขับหุ่นได้ · ยอมรับได้สำหรับสนามแข่ง แต่**ห้าม**เอา service นี้ไปเปิดบน Wi-Fi สาธารณะ |
| อินเทอร์เน็ต | ไม่มีในโหมดสนาม · ตอนอยู่แล็บให้ต่อ Ethernet เพื่อ `sync_supabase.py` และ `apt` |

---

## 3. Pi 5 — โครงสร้าง process และโมดูล

**process เดียว** (`mrc-robot.service`) รัน asyncio event loop · งานที่บล็อกนาน (OCR, เขียนไฟล์ภาพ) ไปอยู่ใน executor · `sync_supabase.py` เป็น process แยกตาม timer

```
11_pi5_vision/
├── mrc/                         ← แพ็กเกจ Python (ของเดิม meter_reader.py ย้ายมาเป็นโมดูล)
│   ├── config.py                ★ ค่าคงที่ทั้งหมดที่เดียว: พอร์ต · baud · timeout · ขนาดภาพ · path
│   ├── link/
│   │   ├── crc8.py              CRC8 poly 0x07 — ต้องตรงกับฝั่ง ESP32 (unit test ด้วย vector ชุดเดียวกัน)
│   │   ├── protocol.py          encode `$…*CC` / decode `#T #E #A #N` → dataclass · ไม่รู้จัก serial
│   │   └── uart.py              asyncio reader/writer บน /dev/ttyAMA0 · ตัดบรรทัด · ทิ้งที่ไม่ขึ้นต้น `#` · นับ crc_err
│   ├── hub.py                   ★ RobotHub — state ล่าสุด · deadman browser→Pi · queue คำสั่ง · trigger ถ่าย · broadcast
│   ├── camera/
│   │   └── cam.py               BRIO/V4L2 MJPG 1080p เปิดค้างใน thread เก็บเฟรม BGR ล่าสุด · preview generator (ย่อ+encode) · capture_still() = imwrite เฟรมล่าสุด
│   ├── vision/
│   │   └── meter_reader.py      ของเดิม refactor ให้ import ได้: `read_meter(img, cfg) -> Reading` · CLI เดิมยังใช้ได้
│   ├── store/
│   │   ├── readings.py          append readings.jsonl (ตรรกะเดิมของ meter_reader)
│   │   └── run_log.py           runs/<run_id>/telemetry.jsonl — เขียน #T ทุกเฟรม · ปิดไฟล์ตอน state→IDLE
│   ├── web/
│   │   ├── app.py               FastAPI: `/` static · `/ws` · `/stream.mjpg` · `/images/<f>` · `/api/readings`
│   │   └── static/ index.html · app.js · app.css · (uplot.min.js ถ้าใช้)
│   └── main.py                  ประกอบทุกอย่าง · สร้าง task: uart_rx · deadman · mjpeg · ws_broadcast
├── scripts/
│   ├── sync_supabase.py         ของเดิม (ไม่แตะ)
│   └── setup_pi.sh              enable_uart · ลบ serial console · hotspot · venv --system-site-packages
├── systemd/
│   ├── mrc-robot.service        Restart=always · After=network.target
│   └── mrc-sync.timer/.service  ทุก 5 นาที · ล้มเงียบได้
├── tests/                       pytest บนโน้ตบุ๊ก ไม่ต้องมี Pi: test_crc8 · test_protocol · test_deadman · test_hub
├── requirements.txt             ของเดิม + fastapi · uvicorn[standard] · pyserial-asyncio · websockets
└── README.md
```

### 3.1 task ใน event loop

| task | คาบ / trigger | ทำอะไร | ห้ามทำ |
|---|---|---|---|
| `uart_rx` | ทุกบรรทัดที่มาถึง | parse → อัปเดต `hub.state` → ถ้าเป็น `#E CAPTURE_REQ` → สร้าง task ถ่าย · ถ้าเป็น `#T` → เขียน run_log + broadcast | บล็อก (ห้ามเรียก OCR ตรงนี้) |
| `deadman` | 50 ms | ถ้าโหมด MANUAL และไม่ได้รับ `drive` จาก browser เกิน **300 ms** → ส่ง `$S` 1 ครั้ง + หยุดส่ง `$V` ซ้ำ | — |
| `drive_repeat` | 100 ms (10 Hz) | ส่ง `$V` ค่าล่าสุดซ้ำ ตราบที่ deadman ยังไม่หมด — ให้ G8 (≤200 ms) ผ่านด้วย margin 2× | ส่งถ้า browser หายแล้ว |
| `capture_job` | เมื่อ ESP32 ขอ หรือ browser กด | `cam.capture_still()` → เขียน jpg ลง SD → **ส่ง `$K` ทันที** → ค่อยส่ง OCR เข้า executor → เขียน readings.jsonl → broadcast `reading` | รอ OCR ก่อนตอบ ESP32 (timeout 5 s ของ state 8) |
| `mjpeg` | ต่อ client ที่ขอ | yield เฟรมจาก lores stream | encode ซ้ำต่อ client (encode ครั้งเดียว fan-out) |
| `sys_stat` | 1 s | อุณหภูมิ CPU · พื้นที่ว่าง SD · จำนวนแถวรอ sync · สถานะกล้อง → broadcast `sys` | — |

### 3.2 กล้อง — BRIO ผ่าน V4L2 เปิดค้าง 1 stream แล้วแตกเป็น 2 เส้นทาง (rev.2)

**ของจริง [วัดจริง 11 ก.ย. — C22 · ไฟล์ 19 §19.4.1]:** Logitech BRIO บน USB 2.0 ของ Pi · YUYV 1080p ได้แค่ 5 fps · MJPG 1080p กล้องรายงาน 30 fps แต่ `cv2.VideoCapture.read()` ได้ **61 ms/เฟรม ≈ 16 fps** (OpenCV decode MJPEG→BGR บน CPU) · resize 640×480 + JPEG q80 = **6 ms · 38.8 kB** · `imwrite` 1080p = **14 ms · 316 kB** · แบบเดิมเปิด-ปิดต่อรูป = **1.66 s**

```
BRIO ──MJPG 1080p──▶ thread เดียว: cap.read() วนตลอด · เก็บ "เฟรม BGR ล่าสุด" + timestamp ไว้ 1 เฟรม (lock)
                        ├─ preview (≤10 fps · ข้ามเฟรมถ้า client ช้า): resize 640×480 → imencode q80 → /stream.mjpg
                        └─ still (ตอน CAPTURE): imwrite เฟรมล่าสุด 1080p ลง SD → $K   (≈ 71 + 14 ms · ไฟล์ 19 §19.4.1)
```

| เรื่อง | ทำไม |
|---|---|
| เปิดกล้องค้างตลอดใน thread (ไม่ใช่ใน event loop) | `cap.read()` บล็อก 61 ms — ถ้าอยู่ใน asyncio จะค้าง WS/UART · AE/AF นิ่งอยู่แล้ว → still ใช้เวลา 136 ms รวม UART แทน 1.7 s (ไฟล์ 19 §19.4.1) |
| preview ต้องย่อก่อนส่ง | 1080p JPEG 316 kB × 10 fps = 25 Mbps เกิน hotspot · ย่อแล้ว 38.8 kB × 10 fps ≈ 3.1 Mbps [คำนวณจากค่าวัด] |
| still = เฟรมเดียวกับ preview ไม่ต้องเปลี่ยนโหมดกล้อง | เปลี่ยนความละเอียด V4L2 กลางคันเสีย ~0.5–1 s [ประมาณการ] และ AE ต้องนิ่งใหม่ |
| **autofocus ต้องล็อก** | BRIO มี AF — ถ้าปล่อยอัตโนมัติจะ hunt ตอนเสาเพิ่งนิ่ง · `v4l2-ctl -c focus_automatic_continuous=0 -c focus_absolute=<ค่า>` หลังวัดระยะกล้อง→มิเตอร์จริง [ยังไม่ตัดสินใจ] |
| ถ้าอยาก >16 fps | ต้องอ่าน MJPG ดิบไม่ผ่าน decode ของ OpenCV (`CAP_PROP_CONVERT_RGB=0` หรือ v4l2 ตรง) — ไม่จำเป็นตอนนี้ preview 10 fps พอ |

`meter_reader.py` มี `grab_usb()` ที่ตั้ง MJPG 1080p แล้ว (แก้ 11 ก.ย.) — ใช้เป็น CLI ทดสอบได้ต่อ · แต่ `cam.py` ในระบบจริงต้องเป็นแบบเปิดค้างตามข้างบน ไม่ใช่เรียก `grab_usb()` ต่อรูป (1.66 s/รูป [วัดจริง])

---

## 4. โปรโตคอลทั้ง 3 ช่วง

### 4.1 ESP32 ⇄ Pi 5 — ใช้ §7 เดิม + เติม 2 ข้อความที่ขาด

§6.1 state 8 `CAMERA_CAPTURE` ออกเมื่อ "Pi5 ตอบ ACK" แต่ §7.1 ไม่มีคำสั่งนั้น — **C18 ปิดแล้ว 12 ก.ย. 2026 ผู้ใช้ยืนยันใช้ 2 ข้อความนี้** · โค้ด: `src/robot/comm.cpp` · `11_pi5_vision/src/mrc_protocol.py` + `capture_daemon.py`

**นิยาม CRC8 ที่ล็อก (ทั้งสองฝั่งต้องเหมือนกันทุกบิต):** poly 0x07 · init 0x00 · ไม่ reflect · ไม่ xor-out · คำนวณจาก**ทุกตัวอักษรหลัง sentinel (`$`/`#`) จนถึงก่อน `*`** · CC = hex 2 หลักตัวพิมพ์ใหญ่ · check value `crc8("123456789") = 0xF4` · `crc8("E,1000,CAPTURE_REQ,1") = 0xE0` — ทดสอบไว้ใน `11_pi5_vision/tests/test_protocol.py` และ `test/host_comm_codec.cpp`

| ทิศ | ข้อความ | ความหมาย |
|---|---|---|
| ESP32 → Pi5 | `#E,<ms>,CAPTURE_REQ,<n>*CC` | เข้า state 8 แล้ว เสานิ่ง ถ่ายได้ · `n` = ลำดับครั้งในรอบ |
| Pi5 → ESP32 | `$K,<seq>,<1\|0>*CC` | 1 = ภาพเขียนลง SD สำเร็จ → ESP32 ไป `LIFT_LOWERING` · 0 = ล้ม → ESP32 ตัดสินเอง (พับเลย) |

Pi5 ต้อง**ไม่**พึ่ง `#E` อย่างเดียว: ให้ตรวจขอบ `state` 7→8 ใน `#T` เป็นทางสำรอง (ถ้า `#E` หายเพราะ CRC พลาด 1 บรรทัด ก็ยังถ่ายภายใน 50 ms ถัดไป)

`flags` ใน `#T` — §7.2 ระบุแค่รายการ ยังไม่ระบุบิต เสนอ: bit0 stall · bit1 comm-lost · bit2 low-batt · bit3 servo-overcurrent · bit4–7 สงวน [ยังไม่ตัดสินใจ — ต้องตรงกับ `robot_state.h`]

### 4.2 Browser ⇄ Pi 5 — WebSocket JSON

**Browser → Pi 5** (ฟิลด์ `t` = type)

| ข้อความ | แปลเป็น §7 | หมายเหตุ |
|---|---|---|
| `{"t":"drive","v":120,"w":0}` | `$V` | mm/s · mrad/s · **browser ส่งซ้ำ 10 Hz ตราบที่ผู้ใช้ยังกดอยู่** · ปล่อย = ส่ง `{"t":"drive","v":0,"w":0}` |
| `{"t":"clean","suction":100,"brush":40}` | `$C` | |
| `{"t":"limits","v_max":300,"w_max":2000}` | `$L` | C28: เพดานที่ผู้ใช้ตั้งเอง · Pi/ESP32 clamp ที่ฮาร์ดแวร์ 716 mm/s · 7950 mrad/s · Pi broadcast `{"t":"limits",…}` กลับให้ทุก client |
| `{"t":"mast","up":1}` | `$M` | ESP32 เดิน `LIFT_*` เอง · browser แค่ดู `mast` ใน telemetry |
| `{"t":"stop"}` / `{"t":"estop"}` / `{"t":"reset"}` / `{"t":"ping"}` | `$S` / `$E` / `$R` / `$P` | `estop` ทำได้ทุกโหมด ไม่ผ่านตัวกรองใดๆ |
| `{"t":"capture"}` | — (Pi ทำเอง) | ถ่าย+OCR โดยไม่ยกเสา — ไว้จูน ROI ที่สนามโดยไม่ต้องเดินภารกิจ |
| `{"t":"mode","mode":"manual"\|"auto"}` | ดู C19 | `auto` = ส่ง `CMD_START` ให้ FSM วิ่งเอง · `manual` = Pi ส่ง `$V` ตาม browser |

**Pi 5 → Browser**

| ข้อความ | ที่มา | อัตรา |
|---|---|---|
| `{"t":"tele", "ms","state","v","w","enc":[l,r],"us":[l,r],"vbat_mV","servo_i_mA","mast","flags", "link":{"rx_hz","crc_err","age_ms"}}` | `#T` + สถิติลิงก์ | 20 Hz (ตามที่ ESP32 ส่ง) |
| `{"t":"event","ms","code","detail"}` | `#E` | ทันที |
| `{"t":"ack","seq"}` / `{"t":"nack","seq","reason"}` | `#A` / `#N` | ทันที — **UI ต้องโชว์ reason ของ nack ให้เห็น** ไม่ใช่เงียบ |
| `{"t":"reading","local_id","captured_at","value","confidence","raw_text","image":"/images/<f>.jpg"}` | OCR เสร็จ | ต่อรูป |
| `{"t":"sys","cpu_temp_c","disk_free_mb","pending_sync","cam_ok","mode"}` | Pi เอง | 1 Hz |
| `{"t":"hello","proto":1,"run_id"}` | ตอนต่อ WS | ครั้งเดียว |

ขนาด `tele` ~250–300 B × 20 Hz ≈ **6 kB/s** — เล็กมากเทียบภาพ (ไฟล์ 19 §19.2)

### 4.3 ตัวกรองฝั่ง Pi 5 — กรองเพื่อความสะดวก ไม่ใช่เพื่อความปลอดภัย

Pi 5 กรองคำสั่งที่ "รู้อยู่แล้วว่าจะโดน `#N`" เพื่อให้ UI ตอบเร็วและไม่ถม UART เช่น `drive` ตอน `state=FAULT` หรือ `mast` ตอน `v≠0` — แต่ **ทุกกติกายังถูกบังคับซ้ำที่ ESP32** ถ้าตัวกรองนี้หายไปทั้งก้อน หุ่นต้องยังปลอดภัยเท่าเดิม (หลักการข้อ 1)

---

## 5. Deadman 3 ชั้น — เส้นทางที่ทำให้หุ่นหยุดเมื่ออะไรก็ตามหาย

```
browser กดจอย ──10 Hz──▶ Pi: hub.last_drive_ms ──10 Hz $V──▶ ESP32: G8 timer
       │                        │                                  │
   หาย/แฮงก์            ไม่ได้ drive > 300 ms              ไม่ได้ $V > 300 ms
       ▼                        ▼                                  ▼
   (ไม่มีอะไรทำ)        ส่ง $S · เลิกส่ง $V                    หยุดขับ (T_Comm)
```

| สถานการณ์ | ใครจับได้ | เวลาจนล้อหยุด (worst case) | ระยะไถลที่ 0.15 m/s |
|---|---|---|---|
| browser หาย / แท็บถูกปิด / Wi-Fi หลุด | Pi deadman | 300 + 50 (คาบ deadman) + 50 (T_Comm) ≈ **400 ms** | **60 mm** |
| Pi 5 แฮงก์ / process ตาย / สาย UART หลุด | ESP32 G8 | 300 + 50 ≈ **350 ms** | 53 mm |
| ESP32 แฮงก์ | hardware watchdog ของ ESP32 → reboot → `BOOT` state ตัด PWM | ขึ้นกับ WDT ที่ตั้ง [ยังไม่ตัดสินใจ] | — |

ทั้งหมด [คำนวณ] ในไฟล์ 19 §19.3 · ระยะไถล 53–60 mm อยู่ระดับเดียวกับระยะดันของ stall-as-bumper (45 mm, §6.2) ถือว่าสอดคล้องกับที่ระบบยอมรับอยู่แล้ว · ถ้าอยากสั้นกว่านี้ให้ลด timeout ฝั่ง Pi เป็น 200 ms (ทน packet หาย 1 ชุด แทน 2 ชุด) — trade-off ระหว่างหยุดเร็วกับหยุดหลอนตอน Wi-Fi กระตุก

> **ห้ามให้ browser เป็นคนส่ง `$V` ซ้ำโดยตรง** (เช่น ส่ง WS ทุก 100 ms แล้ว Pi forward เฉยๆ) เพราะ Wi-Fi jitter จะทำให้ G8 หลุดเป็นพักๆ ทั้งที่ผู้ใช้ยังกดอยู่ · Pi ต้องเป็นคน "ถือ" ค่าล่าสุดแล้วส่งซ้ำอย่างสม่ำเสมอเอง (task `drive_repeat`) และตัดเมื่อ deadman ของตัวเองหมด

---

## 6. ลำดับเหตุการณ์สำคัญ

### 6.1 ถ่ายมิเตอร์ (โหมด auto — FSM เป็นคนเริ่ม)

```
ESP32 FSM        Pi 5 hub                      กล้อง/OCR                browser
   │ LIFT_SETTLE ครบ
   ├─ state=8 ──#E CAPTURE_REQ──▶│
   │                             ├─ capture_still() ──▶ main stream (< 0.5 s)
   │                             ├─ เขียน images/<id>.jpg ลง SD
   │◀──── $K,seq,1 ──────────────┤                        (t ≈ 0.5–1 s หลัง #E)
   ├─ LIFT_LOWERING              ├─ executor: read_meter() ─▶ OCR 0.3–2 s
   │                             ├─ append readings.jsonl
   │                             └─ broadcast reading ──────────────────────────▶ แสดงค่า+รูป
   │ ถ้าไม่ได้ $K ใน 5 s → LOWERING เอง (timeout เดิม §6.1)
```
จุดสำคัญ: **`$K` ส่งเมื่อภาพลง SD แล้ว ไม่ใช่เมื่อ OCR เสร็จ** — OCR อาจช้าหรือล้มได้โดยไม่กระทบจังหวะเสา (สอดคล้องลำดับตัด #2: OCR ตัดได้ แต่ถ่ายรูปห้ามตัด)

### 6.2 ขับเอง (โหมด manual)

```
browser: กดจอย → {"t":"drive",v,w} ทุก 100 ms
Pi:      hub.last_drive = now · hub.setpoint = (v,w)
         drive_repeat: ทุก 100 ms ส่ง $V,seq,v,w   ← ESP32 clamp ด้วย G14 (0.15 m/s) และ G2 (เสาไม่พับ = 0) เสมอ
ESP32:   #A หรือ #N (เช่น MAST_UP) → Pi → browser แสดง
```
ต้องมี state ที่ FSM ยอมรับ `$V` — ดู **C19**

### 6.3 บูตและกู้คืน

| เหตุการณ์ | พฤติกรรมที่ต้องการ |
|---|---|
| Pi บูตก่อน ESP32 พร้อม | `uart_rx` ทิ้ง boot log (ไม่ขึ้นต้น `#`) จนกว่าจะเห็น `#T` แรก · UI โชว์ "รอ ESP32" |
| ESP32 รีเซ็ตกลางทาง | Pi เห็น `age_ms` โต → UI แดง · พอ `#T` กลับมา state=BOOT/IDLE → ต้องกด start ใหม่ ไม่ต่ออัตโนมัติ |
| `mrc-robot.service` crash | systemd `Restart=always` · ESP32 หยุดไปแล้วด้วย G8 · หน้าเว็บ reconnect WS เองทุก 1 s |
| SD เต็ม | `sys.disk_free_mb` < 200 → UI เตือน · หยุดเขียน run_log ก่อน หยุดเขียน readings ทีหลังสุด |

---

## 7. หน้าเว็บ — สิ่งที่ต้องมี (ขั้นต่ำ) และลำดับทำ

| ลำดับ | ส่วน | ที่มาของข้อมูล |
|---|---|---|
| 1 | แถบสถานะ: `state` (ชื่อ ไม่ใช่เลข) · `mast` · V_bat (V) · flags เป็นไฟสี · `link.age_ms` | `tele` |
| 2 | ปุ่ม **E-STOP** ใหญ่ (ทำงานทุกโหมด) · STOP · RESET | ส่ง WS |
| 3 | ภาพสด `<img src="/stream.mjpg">` | MJPEG |
| 4 | จอยสติ๊กแบบ touch/ปุ่มลูกศร + slider ความเร็ว (0–150 mm/s) | ส่ง `drive` 10 Hz ขณะกด |
| 5 | ปุ่ม ดูด/แปรง (toggle + %) · ยกเสา/พับ · ถ่ายเดี๋ยวนี้ | `clean` `mast` `capture` |
| 6 | ค่ามิเตอร์ล่าสุด + รูป + confidence · ตารางค่าย้อนหลังในรอบนี้ | `reading` · `/api/readings` |
| 7 | กราฟ v/ω · US ซ้าย-ขวา · V_bat (หน้าต่าง 30 s) | `tele` |
| 8 | log ของ `event` / `nack` (พร้อม reason) | `event` `nack` |
| 9 | สถานะ Pi: อุณหภูมิ · SD · รอ sync | `sys` |

ข้อ 1–4 คือขั้นต่ำที่ทำให้ "บังคับเอง" ได้ (ทางเลือกสำรองของลำดับตัด #4 ในแผน rev.3) — ทำก่อน ที่เหลือเติมทีหลัง

---

## 8. ฝั่ง ESP32 — สิ่งที่ต้องเพิ่มจากที่มีตอนนี้ (ไม่รื้อของเดิม)

| # | ทำอะไร | หมายเหตุ |
|---|---|---|
| 1 | `comm/link.cpp` เปิด **`Serial0`** (UART0 บน GPIO 43/44) ที่ 115200 แยกจาก `Serial` (USB-CDC) | ด้วย `ARDUINO_USB_CDC_ON_BOOT=1` ใน core 3.x `Serial` = USB · `Serial0` = HardwareSerial(0) → **ต้องยืนยันตอนบิลด์ว่า `Serial0` map ไป 43/44 จริง** (พิมพ์ `Serial0` แล้ววัดด้วย logic analyzer/USB-TTL ก่อนต่อ Pi) |
| 2 | `comm/parser.cpp` — parse `$V $C $M $S $E $R $P` (+`$K`) · CRC8 · ตอบ `#A/#N` | 7–8 คำสั่ง · ทดสอบบน host ได้ตาม §8 `test/` |
| 3 | `T_Comm` ส่ง `#T` 20 Hz ตาม §7.2 · ส่ง `#E` จาก evt_q | เว้นตำแหน่งฟิลด์ที่ยังไม่มีเป็น `0` ตาม §7.2 |
| 4 | G8 ทำงานเฉพาะเมื่อเคยได้ `$V` แล้ว (ไม่งั้นเดินโหมด auto ไม่ได้) | ตรงกับหมายเหตุ G8 เดิม |
| 5 | state สำหรับ teleop — ดู C19 | |
| 6 | **ไม่ include Wi-Fi ใน env `robot`** | เหตุผล §2.1 |

คำสั่งทดสอบเดิม `m/sv/bl` ผ่าน USB ยังอยู่ — เป็นคนละช่องกับ Pi จึงไม่ชนกัน · แต่ interlock R1/R2 (ไฟล์ 18) ต้องบังคับกับคำสั่งจาก **ทั้งสองช่อง** ที่จุดเดียว ไม่ใช่เฉพาะช่อง USB

---

## 9. ลำดับพัฒนา

### 9.0 ลำดับที่ใช้จริง (rev.2 · ผู้ใช้ตัดสิน 12 ก.ย.): แกนหลักก่อน A→E

ดูตารางใน [`แผนงาน_25วัน` rev.4](แผนงาน_25วัน_6-30กันยายน2026.md) — **A** ESP32 เดี่ยว · **B** Pi เดี่ยว · **C** ลิงก์ 2 ข้อความ (`CAPTURE_REQ`/`$K`) · **D** 1 รอบภารกิจแบบ script · **E** ค่อยเติม telemetry/เว็บ/guard ที่เหลือ · แต่ละขั้นต้องมีหลักฐานว่าทำงานก่อนไปขั้นถัดไป · ตาราง §9.1 ด้านล่างคือแผนเต็ม (ขั้น E) เก็บไว้อ้างอิง

**สถานะ 15 ก.ย. 2026:** ขั้น E ขั้นต่ำเริ่มแล้ว "พลางๆ" ระหว่างรอฮาร์ดแวร์ (ผู้ใช้สั่ง) — `11_pi5_vision/src/mrc_web.py` + `static/` ครอบ daemon ขั้น C · มีเฉพาะส่วนที่ ESP32 รองรับจริง (ภาพสด · ถ่ายจากเว็บ · รายการค่า · สถานะลิงก์) · ปุ่มขับ/E-STOP ยังปิดจนกว่า C19/C20 · 19 เทสต์ผ่านบน host · **ยังไม่ได้รันบน Pi** · C23 ตัดสินแล้ว: แยก 2 แอป schema เดียวกัน

### 9.1 แผนเต็ม — วางบนแผน rev.3 (เส้นตายตัวหุ่น 22 ก.ย.)

| วัน (แผนเดิม) | งานเดิม | งานซอฟต์แวร์ที่เพิ่ม | ทำบนอะไร |
|---|---|---|---|
| **ก่อน 14 ก.ย.** (ทำได้เลยบนโน้ตบุ๊ก) | OCR บนโน้ตบุ๊ก | `link/crc8.py` `protocol.py` + tests · `hub.py` + deadman test · `web/app.py` + `index.html` ขั้นต่ำ (ข้อ 1–4 ของ §7) โดยใช้ **ESP32 จำลอง** (`tests/fake_esp32.py` ยิง `#T` ปลอมผ่าน pty) | โน้ตบุ๊ก ไม่ต้องมี Pi/หุ่น |
| 14 ก.ย. | ตั้ง Pi · กล้อง | `setup_pi.sh` · hotspot · `cam.py` 2 stream · `/stream.mjpg` | Pi |
| 15 ก.ย. | OCR บน Pi · DB | `capture_job` ครบ (ถ่าย→SD→OCR→jsonl→WS) · ปุ่ม `capture` ใช้ได้ | Pi |
| 16 ก.ย. | ลิงก์ UART | ESP32 ข้อ 1–3 ของ §8 · Pi `uart.py` ต่อของจริง · แดชบอร์ดเห็น `#T` จริง · **ทดสอบ deadman ทั้ง 2 ชั้นด้วยการดึงสาย/ปิดแท็บ** | หุ่น |
| 17–18 ก.ย. | FSM หลัก | ESP32 `$K` + state teleop (C19) · โหมด auto/manual จากเว็บ | หุ่น |
| 19–20 ก.ย. | ภารกิจเต็ม | run_log เก็บ telemetry ทุกรอบ → ได้ข้อมูลรายงาน P5 ฟรี | หุ่น |

> ⚠ แผน rev.3 **ไม่มีบรรทัด "เว็บแอป"** — งานนี้เป็นขอบเขตใหม่ที่เพิ่มเข้ามา (บันทึกเป็น **C21**) ประมาณ **3–4 วัน-คน** ถ้าทำขนานกับงานกลไก 12–13 ก.ย. ได้จะไม่กินวันกันชน 21–22 ก.ย. · ถ้าช้า ลำดับตัดภายในเว็บแอปเอง: ตัดข้อ 9→7→6 ของ §7 ก่อน · **ข้อ 1–4 ห้ามตัด** เพราะเป็นทางสำรองของ "บังคับเอง"

---

## 10. สิ่งที่ต้องตัดสินก่อนเขียนโค้ด (รอผู้ใช้)

| # | เรื่อง | ข้อเสนอ | ทำไมต้องตัดสินก่อน |
|---|---|---|---|
| 1 | ~~**C18** เติม `#E CAPTURE_REQ` + `$K` เข้า §7~~ **✓ ปิดแล้ว 12 ก.ย.** | ใช้ตามที่เสนอ · โค้ดสองฝั่งเขียนแล้ว | รอทดสอบบนสายจริง 16 ก.ย. |
| 2 | **C19** FSM ต้องมี state ที่รับ `$V` จาก Pi (teleop) — **เลื่อนไปขั้น E** | เพิ่ม `MANUAL` (#12) เข้า-ออกจาก `IDLE` · guard เดิมทุกตัวยังบังคับ | §6.1 ตอนนี้ไม่มีทางที่ `$V` จะถูกใช้เลย |
| 3 | **C20** `src/robot/` พูด dialect ทดสอบผ่าน USB ไม่ใช่ §7 — **เริ่มแล้ว 12 ก.ย.** | `src/robot/comm.cpp` บน `Serial0` (ขา 44/43 ระบุตรงๆ) เป็นช่องที่สอง · ตอนนี้มีแค่ `CAPTURE_REQ`/`$K` | ยังต้องยืนยันบนบอร์ดว่า `Serial0` ออก 43/44 จริง (README เฟิร์มแวร์) |
| 4 | timeout deadman ฝั่ง Pi: 300 หรือ 200 ms | 300 ms (ทน packet หาย 2 ชุด) | trade-off ในตาราง §5 |
| 5 | ~~รุ่นกล้อง (CSI vs USB)~~ **✓ ปิดแล้ว rev.2** — USB Logitech BRIO บน Ubuntu (C22) | เหลือ: **ค่า focus_absolute** หลังวัดระยะกล้อง→มิเตอร์จริง | AF hunt ตอนถ่ายทำให้ OCR พลาด |
| 6 | ที่อยู่โค้ด Pi: อยู่ใน `11_pi5_vision/` ต่อ หรือย้ายเป็น `12_pi5_app/` | อยู่ที่เดิม เปลี่ยนโครงเป็นแพ็กเกจ `mrc/` | เอกสาร/แผนอ้าง `11_pi5_vision/` อยู่หลายที่ |
| 7 | อุปกรณ์ที่ใช้เปิดหน้าเว็บที่สนาม | โน้ตบุ๊ก (จอใหญ่พอสำหรับภาพ+กราฟ) · มือถือใช้ได้แต่จอย touch ต้องทำเพิ่ม | กำหนด layout ขั้นต่ำ |

---

*rev.2 · 11 ก.ย. 2026 (ค่ำ) — C22 Ubuntu + BRIO · rev.1 บ่าย · อ้างอิง `system_architecture.md` rev.6/7 §0 §3.7 §5–§8 · `11_pi5_vision/README.md` · `แผนงาน_25วัน` rev.3 · ไฟล์คำนวณ 09, 18, 19*
