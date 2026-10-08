"""cellread.py — แปลงภาพช่องตัวเลข 1 ช่อง → "แผนที่หมึก" ที่ไม่ขึ้นกับสี แล้วจำแนก 0–9 / ว่าง ด้วย CNN จิ๋ว (ONNX ผ่าน cv2.dnn)

ไม่รู้ว่าวันแข่งตัวเลขจะเป็นสีอะไร/แบบไหน → ไม่หาหมึกจาก "สี" แต่หาจาก "ต่างจากพื้นแค่ไหน":
  พื้น = สีมัธยฐานของช่อง (หมึกกินพื้นที่น้อยกว่าครึ่งเสมอ · ถ้าแปะการ์ดขาวทับ พื้นก็จะกลายเป็นสีการ์ดเอง)
  หมึก = ระยะสีใน Lab จากพื้น → หมึกแดง/ดำ/ขาว/เหลืองบนน้ำเงิน ได้ภาพเดียวกัน
"""
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent / "models" / "digitnet.onnx"          # ตัวอ่าน 0–9/ว่าง (v2 · 11 คลาส)
CHECK_MODEL = Path(__file__).resolve().parent / "models" / "digitcheck.onnx"   # ตัวคัดแถวขยะ มีคลาส "ไม่ใช่ตัวเลข" (v4 · 12 คลาส)

S = 40                      # ขนาดอินพุตของ CNN
CLASSES = list("0123456789") + ["_", "x"]     # "_" = ช่องว่าง · "x" = ไม่ใช่ตัวเลข (เส้นขอบ ตัวอักษร เลขครึ่งตัว)
DE_FLOOR = 22.0             # ΔE ขั้นต่ำที่ถือว่า "เข้มเต็ม" — กันช่องว่างที่มีแค่ noise ถูกขยายจนดูเหมือนหมึก


def ink_map(cell_bgr):
    lab = cv2.cvtColor(cv2.GaussianBlur(cell_bgr, (3, 3), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0                     # L ของ OpenCV 8-bit อยู่ 0–255 → 0–100 ให้ใกล้ ΔE
    bg = np.median(lab.reshape(-1, 3), axis=0)
    d = np.linalg.norm(lab - bg, axis=2)
    s = max(float(np.percentile(d, 98)), DE_FLOOR)
    m = np.clip(d / s, 0, 1)
    return cv2.resize(m, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32)


class DigitNet:
    def __init__(self, onnx_path=MODEL):
        self.net = cv2.dnn.readNetFromONNX(str(onnx_path))

    def predict(self, cells):
        """cells = list ของภาพ BGR → [(ตัวอักษร, ความมั่นใจ, prob ทั้ง 11 คลาส)]"""
        x = np.stack([ink_map(c) for c in cells])[:, None]          # N×1×S×S
        self.net.setInput(x)
        z = self.net.forward()
        z = z - z.max(1, keepdims=True)
        p = np.exp(z) / np.exp(z).sum(1, keepdims=True)
        return [(CLASSES[int(k.argmax())], float(k.max()), k) for k in p]


_net = None
_check = None


def warmup():
    """โหลด ONNX ทั้งสองตัว + รันหนึ่งครั้ง (cv2.dnn จัดหน่วยความจำตอนรันแรก)"""
    global _net, _check
    if _net is None:
        _net = DigitNet()
    if _check is None:
        _check = DigitNet(CHECK_MODEL)
    _net.predict([np.zeros((100, 100, 3), np.uint8)] * 4)
    _check.predict([np.zeros((100, 100, 3), np.uint8)] * 4)


def read_meter(bgr, conf_review=0.8):
    """ภาพเต็มจากกล้อง → {text, conf, digits, ok, strip, source, why}
    1) หากล่อง REAI (กรอบ 4 ช่อง) → อ่านทีละช่อง · text ใช้ "_" แทนช่องว่าง, "?" แทนช่องที่ไม่ใช่ตัวเลข
    2) ไม่เจอกล่อง → หาแถวตัวเลขที่ไหนก็ได้ในภาพ (digit_rows.py — มิเตอร์จริงแบบลูกกลิ้ง/จอ ฯลฯ · 7 ต.ค.)
    conf = ความมั่นใจของหลักที่ต่ำที่สุด · conf_review: ต่ำกว่านี้ควรให้คนดูรูป (ไฟล์ 26 §26.6)"""
    global _net, _check
    import reai_strip
    if _net is None:
        _net = DigitNet()
    r = reai_strip.find_strip(bgr)
    if r is not None:
        out = _net.predict(reai_strip.cells(r["strip"], inset=0.08))
        text = "".join("?" if o[0] == "x" else o[0] for o in out)
        conf = min(o[1] for o in out)
        ok = text.strip("_") != "" and "?" not in text
        why = "" if ok else ("มีช่องที่ไม่ใช่ตัวเลข" if "?" in text else "เจอกล่องแต่ทุกช่องว่าง")
        src, strip = "reai", r["strip"]
        digits = [(o[0], round(o[1], 3)) for o in out]
    else:
        import digit_rows
        if _check is None:
            _check = DigitNet(CHECK_MODEL)
        rows = digit_rows.find_rows(bgr, _net, verifier=_check)
        if not rows:
            return {"text": "", "conf": 0.0, "digits": [], "ok": False, "strip": None, "source": None,
                    "why": "ไม่เจอกล่อง REAI และไม่เจอแถวตัวเลข"}
        best = rows[0]
        text, conf, ok, why, src, strip = best["text"], best["conf"], True, "", "row", None
        digits = [(t, None) for t in text]
    if ok and conf < conf_review:
        why = f"ไม่มั่นใจบางหลัก (ต่ำสุด {conf:.2f})"
    return {"text": text, "conf": round(float(conf), 3), "digits": digits, "ok": ok, "strip": strip, "source": src, "why": why}
