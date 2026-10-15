# คัดลอกจาก "text reader/meter_reader.py" ของผู้ใช้ (15 ต.ค. 2026) แบบไม่แก้ — tr_worker.py ใช้เฉพาะส่วน OpenCV
# (find_body / meter_type / find_strip / strip_quad / warp_quad / normalize_strip) · ส่วน MeterReader ต้องใช้ ultralytics ไม่ได้เรียกบน Pi
# ผลเทียบ: 08_การคำนวณ/39 (E4 อ่านถูก 26/28) · แก้ต้นฉบับแล้วต้องคัดลอกมาใหม่
"""อ่านมิเตอร์จำลอง (mockup) จากภาพกล้อง: OpenCV หาแถบ + EasyOCR + YOLO อ่านเลข

ไฟล์เดียวจบ ไม่มีโค้ดเปิดกล้อง — ส่งภาพ (numpy array แบบ BGR ของ OpenCV) เข้ามาแล้วได้ผลกลับไป

    from meter_reader import MeterReader

    reader = MeterReader("weights/digit.pt", easyocr_dir="weights/easyocr")   # ทำครั้งเดียวตอนเริ่ม
    res = reader.read(frame)                   # ภาพเดียว
    res, votes = reader.read_stable(frames)    # หลายเฟรม แล้วโหวต (แนะนำ)
    if res:
        print(res.meter, res.text, res.conf)   # "water" "8785" 1.0

ขั้นตอน
  1. หากล่องสีน้ำเงิน      Lab: a > 131 (อมม่วง) และ b < 110 (น้ำเงิน)
  2. แยกประเภทจากรูปทรง   กล่องสี่เหลี่ยม = ไฟ (elec), ทรงกระบอก = น้ำ (water)
  3. หาแถบตัวเลข          ส่วนที่ไม่ใช่สีกล่องและไม่ใช่สีส้ม/แดง ภายในกล่อง รูปร่างยาว
  4. ดัดภาพจาก 4 มุม      warpPerspective — แก้ทั้งเอียงและเฉียง
  5. อ่านเลข              EasyOCR (ภาพสีเดิม) + YOLO (ภาพตัวเข้มพื้นสว่าง)
                          ตรงกัน = conf 1.0 / ไม่ตรง = ใช้ EasyOCR ถ้าครบหลัก ไม่งั้นใช้ YOLO, conf ลดลง
  6. read_stable          โหวตประเภท แล้วโหวตเลขทีละหลักจากหลายเฟรม

ผลบนรูปทดสอบ 74 รูป (ไฟ 28, น้ำ 46): ทายประเภทถูก 74/74, อ่านถูก 74/74, ~0.3 วิ/รูปบน Mac CPU
ค่าคงที่ด้านล่างปรับจากรูปชุดนั้น — ถ้าสีกล่อง/แสง/จำนวนหลักเปลี่ยน ต้องปรับใหม่
"""
from collections import Counter
from dataclasses import dataclass
import cv2
import numpy as np

# ---------- ค่าคงที่ (ปรับได้) ----------
BODY_A, BODY_B = 131, 110      # สีกล่อง: Lab a > 131 และ b < 110 (Lab ของ OpenCV 0-255)
WARM_A = 140                   # ตัวอักษร REAI สีส้ม + เส้นแดง: Lab a > 140
# polygon_misfit: ไฟ 0.006–0.017, น้ำ 0.026–0.115 บนรูปทดสอบ -> ตัดกลางทาง
SHAPE_THR = 0.021
N_DIGITS = {"water": 4, "elec": 4}


@dataclass
class Reading:
    text: str                  # เลขที่อ่านได้ เช่น "8785"
    conf: float                # 1.0 = EasyOCR กับ YOLO อ่านตรงกัน (น่าเชื่อถือสุด)
    source: str                # "easyocr+yolo" | "easyocr" | "yolo_digit" | "vote(n)"
    crop: np.ndarray = None    # ภาพแถบที่ดัดตรงแล้ว ไว้แสดง/เก็บหลักฐาน
    meter: str = None          # "water" | "elec"
    meter_conf: float = 0.0    # 0 = รูปทรงก้ำกึ่ง, 1 = ชัดเจน (read_stable: สัดส่วนเฟรมที่ประเภทตรงกัน)

    def __str__(self):
        return f"[{self.meter}] {self.text} (conf {self.conf:.2f}, {self.source})"


# =====================================================================
# OpenCV: หากล่อง แยกประเภท หาแถบ ดัดตรง
# =====================================================================

def _lab_ab(frame):
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    return lab[..., 1].astype(np.int16), lab[..., 2].astype(np.int16)


def find_body(frame):
    """คืนจุด contour ของกล่องสีน้ำเงิน (รวมทุกชิ้น) หรือ None

    แถบกระดาษบนหน้าบนของทรงกระบอกตัดกล่องเป็นสองชิ้นได้ ถ้าเอาชิ้นใหญ่สุดชิ้นเดียว
    จะเสียขอบโค้งด้านบน แล้วแยกประเภทผิด จึงรวมชิ้นที่อยู่ใกล้ชิ้นใหญ่สุดเข้าด้วยกัน
    """
    a, b = _lab_ab(frame)
    m = ((a > BODY_A) & (b < BODY_B)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    big = max(cnts, key=cv2.contourArea)
    A = cv2.contourArea(big)
    if A < 0.01 * m.size:
        return None
    x, y, w, h = cv2.boundingRect(big)
    gx, gy = 0.3 * w, 0.6 * h
    keep = []
    for c in cnts:
        if cv2.contourArea(c) < 0.03 * A:
            continue
        cx, cy, cw, ch = cv2.boundingRect(c)
        if cx + cw >= x - gx and cx <= x + w + gx and cy + ch >= y - gy and cy <= y + h + gy:
            keep.append(c)
    return np.vstack(keep)


def _min_eps_polygon(hull, k):
    """epsilon น้อยสุดของ approxPolyDP ที่ได้ไม่เกิน k มุม (binary search)"""
    lo, hi = 0.0, 0.5 * cv2.arcLength(hull, True)
    for _ in range(30):
        mid = (lo + hi) / 2
        if len(cv2.approxPolyDP(hull, mid, True)) <= k:
            hi = mid
        else:
            lo = mid
    return hi


def polygon_misfit(body_pts, frame_hw, k=6):
    """ขอบของกล่องเบี่ยงจากรูปหลายเหลี่ยม <= k มุมแค่ไหน (หารด้วย sqrt พื้นที่)

    เงาของกล่องสี่เหลี่ยมมองจากมุมไหนก็เป็นหลายเหลี่ยมไม่เกิน 6 มุม -> ค่าน้อย
    ทรงกระบอกมีขอบบน/ล่างเป็นวงรี ประมาณด้วย 6 มุมไม่สนิท -> ค่ามาก
    ถ้ากล่องล้นขอบภาพ ขอบภาพเพิ่มมุมได้อีกด้านละ 2
    """
    H, W = frame_hw
    hull = cv2.convexHull(body_pts)
    p = hull.reshape(-1, 2)
    edges = int(p[:, 0].min() <= 2) + int(p[:, 1].min() <= 2) + \
        int(p[:, 0].max() >= W - 3) + int(p[:, 1].max() >= H - 3)
    return _min_eps_polygon(hull, k + 2 * edges) / np.sqrt(cv2.contourArea(hull))


def meter_type(body_pts, frame_hw):
    """คืน ("water" | "elec", ค่า misfit)"""
    v = polygon_misfit(body_pts, frame_hw)
    return ("water" if v > SHAPE_THR else "elec"), v


def find_strip(frame, body_pts):
    """หา contour ของแถบตัวเลขในกล่อง หรือ None

    แถบ = บริเวณที่ไม่ใช่สีกล่องและไม่ใช่สีส้ม/แดง ภายใน convex hull ของกล่อง (หดเข้า 1%
    ไม่งั้นผนังรอบกล่องจะติดมาเป็นชิ้นเดียวกับแถบ) เลือกชิ้นที่ยาว 2–12 เท่าของความสูง
    และเต็มกรอบมากสุด ใช้ได้ทั้งแถบขาวตัวดำ และแถบฟ้าตัวขาว
    """
    H, W = frame.shape[:2]
    a, b = _lab_ab(frame)
    hull = cv2.convexHull(body_pts)
    hm = np.zeros((H, W), np.uint8)
    cv2.fillPoly(hm, [hull], 255)
    _, _, w, h = cv2.boundingRect(hull)
    k = max(3, int(0.01 * w))
    hm = cv2.erode(hm, np.ones((k, k), np.uint8))
    body = (a > BODY_A) & (b < BODY_B)
    cand = ((hm > 0) & ~body & ~(a > WARM_A)).astype(np.uint8) * 255
    kc = max(3, int(0.015 * w))               # ปิดรูที่เส้นแดงตัดแถบเป็นช่อง ๆ
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((kc, kc), np.uint8))
    cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(cand, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    best, best_score = None, 0.0
    for c in cnts:
        A = cv2.contourArea(c)
        if A < 0.005 * w * h:
            continue
        _, (rw, rh), _ = cv2.minAreaRect(c)
        L, S = max(rw, rh), min(rw, rh)
        if S < 5 or not (2.0 <= L / S <= 12):
            continue
        score = A * A / (rw * rh)              # พื้นที่ x ความเต็มกรอบ
        if score > best_score:
            best, best_score = c, score
    return best


def order_strip(q):
    """เรียง 4 มุมของแถบยาวเป็น tl, tr, br, bl — ทนแถบที่เฉียงมาก

    เรียงตามมุมรอบจุดกลาง แล้วให้ขอบยาวที่อยู่สูงกว่าเป็นขอบบน
    """
    q = np.asarray(q, np.float32).reshape(-1, 2)
    c = q.mean(axis=0)
    q = q[np.argsort(np.arctan2(q[:, 1] - c[1], q[:, 0] - c[0]))]
    L = [np.linalg.norm(q[(i + 1) % 4] - q[i]) for i in range(4)]
    i = 0 if L[0] + L[2] >= L[1] + L[3] else 1
    if q[i, 1] + q[(i + 1) % 4, 1] > q[(i + 2) % 4, 1] + q[(i + 3) % 4, 1]:
        i += 2
    q = np.roll(q, -i, axis=0)
    return np.float32(q) if q[0, 0] <= q[1, 0] else np.float32(q[[1, 0, 3, 2]])


def strip_quad(strip_cnt, expand=(0.03, 0.08)):
    """4 มุมของแถบ ขยายออก (สัดส่วนของความยาว, ความสูง) กันเลขริมโดนตัด"""
    hull = cv2.convexHull(strip_cnt)
    q = cv2.approxPolyDP(hull, _min_eps_polygon(hull, 4), True).reshape(-1, 2)
    if len(q) != 4:
        q = cv2.boxPoints(cv2.minAreaRect(strip_cnt))
    tl, tr, br, bl = order_strip(q)
    ux, uy = (tr - tl + br - bl) / 2, (bl - tl + br - tr) / 2      # แกนยาว / แกนสั้น
    dx, dy = ux * expand[0], uy * expand[1]
    return np.float32([tl - dx - dy, tr + dx - dy, br + dx + dy, bl - dx + dy])


def warp_quad(frame, q, out_h=96):
    tl, tr, br, bl = q
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    out_w = int(round(out_h * w / max(h, 1.0)))
    dst = np.float32([[0, 0], [out_w, 0], [out_w, out_h], [0, out_h]])
    return cv2.warpPerspective(frame, cv2.getPerspectiveTransform(q, dst), (out_w, out_h))


def normalize_strip(strip):
    """ทำให้เป็นตัวเลขเข้มบนพื้นสว่างเสมอ (แถบขาว = ตัวดำ, แถบฟ้า = ตัวขาว) สำหรับ YOLO

    ใช้ช่อง R: พื้นฟ้ามี R ต่ำ ตัวขาว R สูง / พื้นขาว R สูง ตัวดำ R ต่ำ -> contrast ดีทั้งสองแบบ
    """
    r = strip[..., 2]
    _, bw = cv2.threshold(r, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if (bw > 0).mean() < 0.5:                  # ส่วนสว่างน้อยกว่าครึ่ง = ตัวเลขสว่าง -> กลับสี
        r = 255 - r
    r = cv2.normalize(r, None, 0, 255, cv2.NORM_MINMAX)
    return cv2.cvtColor(r, cv2.COLOR_GRAY2BGR)


# =====================================================================
# อ่านเลข
# =====================================================================

class MeterReader:
    def __init__(self, digit_weights, easyocr_dir=None, use_easyocr=True,
                 n_digits=None, gpu=False):
        """
        digit_weights : โมเดล YOLO อ่านเลข 0-9 (.pt หรือโฟลเดอร์ *_ncnn_model สำหรับ Pi)
        easyocr_dir   : โฟลเดอร์ที่มี craft_mlt_25k.pth + english_g2.pth (รัน offline ได้)
                        None = ให้ EasyOCR โหลดจากเน็ตเองครั้งแรก
        use_easyocr   : False = YOLO อย่างเดียว เร็วกว่า ~4 เท่า แต่ถ้าฟอนต์เปลี่ยนจะไม่มีตัวสำรอง
        n_digits      : {"water": 4, "elec": 4}
        """
        from ultralytics import YOLO
        self.digit = YOLO(str(digit_weights))
        # รับเฉพาะ class ที่ชื่อเป็นเลขหลักเดียว (โมเดลจาก Roboflow บางตัวมี class ขยะ)
        self.digit_classes = [k for k, v in self.digit.names.items()
                              if str(v).isdigit() and len(str(v)) == 1]
        self.n_digits = dict(n_digits or N_DIGITS)
        self.ocr = None
        if use_easyocr:
            import easyocr
            # โหลดครั้งเดียวตอนสร้าง object (กินเวลาหลายวินาที) อย่าสร้างใหม่ทุกครั้งที่อ่าน
            kw = {"gpu": gpu, "verbose": False}
            if easyocr_dir:
                kw.update(model_storage_directory=str(easyocr_dir), download_enabled=False)
            self.ocr = easyocr.Reader(["en"], **kw)
        self.last_box = self.last_quad = self.last_meter = self.last_fail = None

    # ---------- ขั้นที่ 1-4: หาแถบ ----------
    def locate(self, frame, meter=None):
        """คืน (ภาพแถบที่ดัดตรงแล้ว, ประเภท) หรือ (None, ประเภทหรือ None)

        meter: ถ้ารู้อยู่แล้วว่าเป็นมิเตอร์อะไร ส่ง "water"/"elec" มาแทนการดูรูปทรง
        ผลข้างเคียงไว้วาดบนจอ: self.last_box (x1, y1, x2, y2) ของกล่อง, self.last_quad 4 มุมของแถบ
        """
        self.last_box = self.last_quad = self.last_meter = None
        self.last_meter_conf = 0.0
        body = find_body(frame)
        if body is None:
            return None, None
        t, misfit = meter_type(body, frame.shape[:2])
        t = meter or t
        self.last_meter = t
        # ห่างจากเกณฑ์แค่ไหน: 0 = ก้ำกึ่ง, 1 = ห่างเกิน 2 เท่า
        self.last_meter_conf = float(min(1.0, abs(np.log(misfit / SHAPE_THR)) / np.log(2)))
        x, y, w, h = cv2.boundingRect(cv2.convexHull(body))
        self.last_box = (x, y, x + w, y + h)
        cnt = find_strip(frame, body)
        if cnt is None:
            return None, t
        self.last_quad = strip_quad(cnt)
        return warp_quad(frame, self.last_quad), t

    # ---------- ขั้นที่ 5: อ่านเลข ----------
    def ocr_digits(self, strip):
        if self.ocr is None:
            return "", 0.0
        out = self.ocr.readtext(strip, allowlist="0123456789", detail=1, paragraph=False)
        out.sort(key=lambda r: r[0][0][0])        # ซ้าย -> ขวา
        return "".join(r[1] for r in out), (float(np.mean([r[2] for r in out])) if out else 0.0)

    def yolo_digits(self, strip, n):
        """เลือก n กล่องที่มั่นใจสุด แล้วเรียงซ้าย -> ขวา"""
        d = self.digit(strip, conf=0.05, classes=self.digit_classes,
                       agnostic_nms=True, verbose=False)[0]
        if len(d.boxes) == 0:
            return "", 0.0
        keep = d.boxes.conf.argsort(descending=True)[:n]
        keep = keep[d.boxes.xyxy[keep, 0].argsort()]
        text = "".join(str(self.digit.names[int(d.boxes.cls[j])]) for j in keep)
        return text, float(d.boxes.conf[keep].mean())

    def read(self, frame, meter=None):
        """อ่านภาพเดียว คืน Reading หรือ None

        ถ้า None ดูสาเหตุที่ self.last_fail: "no_meter" = หากล่อง/แถบไม่เจอ,
        "no_digits" = เจอแถบแต่อ่านได้ไม่ครบหลัก
        """
        self.last_fail = None
        strip, t = self.locate(frame, meter=meter)
        if strip is None:
            self.last_fail = "no_meter"
            return None
        n = self.n_digits.get(t, 4)
        mk = dict(crop=strip, meter=t, meter_conf=self.last_meter_conf)

        text_a, conf_a = self.ocr_digits(strip)                    # ภาพสีเดิมดีกับ EasyOCR
        text_b, conf_b = self.yolo_digits(normalize_strip(strip), n)  # ตัวเข้มพื้นสว่างดีกับ YOLO

        if len(text_a) == n and text_a == text_b:
            return Reading(text_a, 1.0, "easyocr+yolo", **mk)
        if len(text_a) == n:                      # ไม่ตรงกัน: เชื่อ EasyOCR ก่อน เผื่อฟอนต์เปลี่ยน
            return Reading(text_a, 0.7 * conf_a, "easyocr", **mk)
        if len(text_b) == n:
            return Reading(text_b, 0.7 * conf_b, "yolo_digit", **mk)
        self.last_fail = "no_digits"
        return None

    # ---------- ขั้นที่ 6: หลายเฟรม ----------
    def read_stable(self, frames, meter=None, min_votes=3, min_conf=0.5):
        """อ่านหลายเฟรม โหวตประเภทก่อน แล้วโหวตเลขทีละหลักเฉพาะเฟรมที่ประเภทตรงกัน

        คืน (Reading หรือ None, รายการเลขที่ใช้โหวต)
        Reading.conf = สัดส่วนเฟรมที่อ่านตรงกับผลโหวต, meter_conf = สัดส่วนเฟรมที่ประเภทตรงกัน
        """
        reads = [r for r in (self.read(f, meter=meter) for f in frames)
                 if r and r.conf >= min_conf]
        if not reads:
            return None, []
        t, _ = Counter(r.meter for r in reads).most_common(1)[0]
        n = self.n_digits.get(t, 4)
        votes = [r.text for r in reads if r.meter == t and len(r.text) == n]
        if len(votes) < min_votes:
            return None, votes
        text = "".join(Counter(v[i] for v in votes).most_common(1)[0][0] for i in range(n))
        agree = sum(v == text for v in votes) / len(votes)
        meter_agree = sum(r.meter == t for r in reads) / len(reads)
        crop = next(r.crop for r in reads if r.text == text) if text in votes else reads[0].crop
        return Reading(text, agree, f"vote({len(votes)})", crop, t, meter_agree), votes

    # ---------- วาดผลบนภาพ (ไม่บังคับ) ----------
    def draw(self, frame, res=None):
        """วาดกรอบกล่อง (เขียว) 4 มุมของแถบ (เหลือง) และผลลงบนสำเนาของภาพ"""
        out = frame.copy()
        if self.last_box:
            cv2.rectangle(out, self.last_box[:2], self.last_box[2:], (0, 255, 0), 2)
        if self.last_quad is not None:
            cv2.polylines(out, [self.last_quad.astype(np.int32)], True, (0, 255, 255), 2)
        if res is not None and self.last_box:
            cv2.putText(out, f"{res.meter}: {res.text} ({res.conf:.2f})",
                        (self.last_box[0], max(30, self.last_box[1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        return out
