"""mrc_config.py — ค่าฮาร์ดแวร์ฝั่ง Pi 5 **ที่เดียว** (21 ก.ย. 2026) · คู่กับ src/pins.h ของ ESP32
ทุกโมดูล/argparse ดึงค่าเริ่มต้นจากที่นี่ — จะย้ายพอร์ต/บัส/กล้อง แก้ที่นี่แล้วรีสตาร์ท mrc-web"""

# ── ลิงก์ ESP32 (UART บน header: GPIO14 TXD ขา 8 → ESP32 GPIO44 · GPIO15 RXD ขา 10 ← ESP32 GPIO43 · GND ขา 6) ──
SERIAL_PORT = "/dev/ttyAMA0"     # ต้องมี enable_uart=1 + ปิด serial console (setup_pi.sh)
SERIAL_BAUD = 115200

# ── กล้อง (Logitech BRIO 4K · USB) ──
CAMERA_INDEX = -1                # -1 = หาเอง (C45): /dev/v4l/by-id/*-video-index0 ก่อน (ชื่อคงที่ตามรุ่น+serial) · ใส่ 0/1/… = บังคับ /dev/videoN
# C45 (28 ก.ย.): เสียบใหม่/ไฟ USB กระตุก → BRIO กลับมาเป็น /dev/video1 ไม่ใช่ video0 → ล็อก index 0 ไว้ = ไม่มีภาพจนรีบูต
CAMERA_BY_ID_GLOB = "/dev/v4l/by-id/usb-*-video-index0"
CAMERA_SIZE  = (1920, 1080)      # ค่าเริ่มต้น 1080p · เลือก 4K ได้จากหน้าเว็บ (C46 — จำไว้ใน data/camera.json)
# C46 วัดจริง 28 ก.ย. บน Pi (BRIO MJPG · ห้องแสงปกติ): 1080p 15 fps CPU 26 % ของ 1 คอร์ · 1440p 15 fps 43 % · 4K 22 fps **100 %** (ถอดรหัส MJPG)
#   → 4K ใช้ได้จริง (C36 เคยเดาว่า ~4 fps — ผิด) แต่กิน 1 ใน 4 คอร์เต็ม + ภาพเซฟ 380 kB (1080p 152 kB)
CAMERA_RES = {"1080p": (1920, 1080), "1440p": (2560, 1440), "4k": (3840, 2160)}
# ภาพสดบนเว็บ (ย่อจากเฟรมกล้อง) — วัดจาก 1080p: ต่ำ 16 kB/เฟรม 1.3 Mbps @10 fps · กลาง 39 kB 3.2 Mbps · สูง 60 kB 4.9 Mbps
PREVIEW_QUALITY = {"low": ((640, 360), 80), "mid": ((960, 540), 85), "high": ((1280, 720), 85)}

# ── เซนเซอร์อากาศ ENS160 + AHT21 บน I2C-1 (GPIO2 SDA ขา 3 · GPIO3 SCL ขา 5 · 3.3 V) ──
I2C_BUS      = 1
ENS160_ADDRS = (0x53, 0x52)      # บอร์ดที่ใช้อยู่ตอบที่ 0x53 (ไฟล์ 21) — ลอง 0x53 ก่อน
AHT21_ADDR   = 0x38

# ── เว็บ ──
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000
