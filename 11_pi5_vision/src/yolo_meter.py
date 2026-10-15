"""engine `yolo` (ทดลอง · ไฟล์ 38) — โมเดลผู้ใช้ชุด weights/ 13 ต.ค.: counter (seg · water/elec + กรอบ) → digit
งานจริงอยู่ใน yolo_worker.py (โปรเซส/venv แยก · worker_client.py)

ผลทดสอบ: อ่านถูก 3/8 · ชนิดน้ำ/ไฟกลับด้าน 4/4 → ชนิดเป็นคำใบ้เท่านั้น · Pi ~1 s/รูป
ตั้งค่า: MRC_YOLO_PY (python ของ venv แยก) · MRC_YOLO_DIR (โฟลเดอร์โมเดล ค่าเริ่ม ~/mrc-models/yolo)
"""
from worker_client import WorkerClient

client = WorkerClient("yolo_worker.py")
last = client.last


def read(bgr):
    """คืน dict(text, conf, kind, kind_conf, box, digit_conf, ms_counter, ms_digit) · ไม่เจอกรอบ → text "" """
    return client.read(bgr)


def warmup():
    client.warmup()
