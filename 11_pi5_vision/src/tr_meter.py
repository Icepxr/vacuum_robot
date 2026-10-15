"""engine `tr` (ทดลอง · ไฟล์ 39 · 15 ต.ค. 2026) — วิธีของ "text reader" ที่ผู้ใช้ทำ:
หากล่องสีน้ำเงิน → แยกน้ำ/ไฟจากรูปทรง → หาแถบ → ดัดภาพจาก 4 มุม (แก้มุมเอียง/เฉียง) → YOLO digit ตัวใหม่ (YOLO11s)
งานจริงอยู่ใน tr_worker.py (โปรเซส/venv แยก · worker_client.py)

ผลเทียบนอกระบบ (ไฟล์ 39): อ่านถูก 26/28 · ชนิดถูก 28/29 · ผิดแต่มั่นใจ 0 · รูปไม่มีมิเตอร์อ่านเป็นเลข 0/24
ตั้งค่า: MRC_YOLO_PY (python ของ venv แยก) · MRC_TR_DIR (โฟลเดอร์ digit_ncnn_model ค่าเริ่ม ~/mrc-models/tr)
"""
from worker_client import WorkerClient

client = WorkerClient("tr_worker.py")
last = client.last


def read(bgr):
    """คืน dict(text, conf, kind, kind_conf, quad, digit_conf, strip_path, why, ms) · อ่านไม่ได้ → text "" """
    return client.read(bgr)


def warmup():
    client.warmup()
