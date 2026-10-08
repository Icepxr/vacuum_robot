"""หาแถบ 4 ช่องของกล่อง REAI จากกรอบสีชมพู-ส้ม → ดัดภาพให้หน้าตรง (ไม่ขึ้นกับสี/แบบของตัวเลขในช่อง)"""
import cv2, numpy as np
RW, RH = 480, 120          # แถบหลังดัด (4 ช่อง × 120)

def frame_mask(im):
    """เส้นกรอบ = แดงกว่าเขียวชัด (R−G) เทียบกับพื้นรอบๆ — พื้นกล่องน้ำเงิน R−G≈−14 · ผนังขาว ≈0 · เส้น +10…+40 · ตัวอักษร REAI ≈+80
    ใช้ top-hat ของ R−G (เทียบพื้นในรัศมี ~15 px) แทนเกณฑ์ตายตัว เพื่อให้เส้นบนที่จางกว่ายังติด"""
    b, g, r = [x.astype(np.int16) for x in cv2.split(im)]
    d = np.clip(r - g + 64, 0, 255).astype(np.uint8)
    th = cv2.morphologyEx(d, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    return (((th > 14) & ((r - g) > 6) & (r > 80)) | (((r - g) > 22) & (r > 110))).astype(np.uint8) * 255

def order(q):
    """เรียงมุมเป็น ซ้ายบน→ขวาบน→ขวาล่าง→ซ้ายล่าง โดยให้ขอบยาวเป็นแนวนอน
    (วิธี x+y / y−x เดิมพังเมื่อแถบเอียงมาก — ได้มุมซ้ำกัน)"""
    q = np.asarray(q, np.float32).reshape(-1, 2)
    c = q.mean(0)
    q = q[np.argsort(np.arctan2(q[:, 1] - c[1], q[:, 0] - c[0]))]   # ตามเข็มนาฬิกาในพิกัดภาพ
    best = None
    for k in range(4):
        r = np.roll(q, -k, axis=0)
        top, right = np.linalg.norm(r[1] - r[0]), np.linalg.norm(r[2] - r[1])
        if top >= right and r[1][0] > r[0][0] and (best is None or (r[0][1] + r[1][1]) < (best[0][1] + best[1][1])):
            best = r
    return best if best is not None else q

def quad_of(c):
    h = cv2.convexHull(c)
    per = cv2.arcLength(h, True)
    for e in np.linspace(0.01, 0.12, 23):
        ap = cv2.approxPolyDP(h, e * per, True)
        if len(ap) == 4:
            return order(ap)
    return order(cv2.boxPoints(cv2.minAreaRect(c)))

def warp(im, q, w=RW, h=RH):
    H = cv2.getPerspectiveTransform(q, np.float32([[0, 0], [w, 0], [w, h], [0, h]]))
    return cv2.warpPerspective(im, H, (w, h), flags=cv2.INTER_CUBIC)

def frame_score(wm):
    """wm = mask ที่ดัดแล้ว · กรอบจริง: ขอบ 4 ด้าน + เส้นแบ่ง 3 เส้นติด, กลางช่องโล่ง(ส่วนใหญ่)"""
    m = wm > 0
    band = lambda a: a.mean()
    top, bot = band(m[:8]), band(m[-8:])
    colp = m[10:-10].mean(0)                                    # สัดส่วนหมึกต่อคอลัมน์
    sides = [colp[:12].max(), colp[-12:].max()]
    divs = [colp[x - 18:x + 18].max() for x in (120, 240, 360)]  # เส้นแบ่ง ±18 px เผื่อมุมเพี้ยน
    if sorted(divs)[1] < 0.45:                                   # ต้องเห็นเส้นแบ่งชัดอย่างน้อย 2 ใน 3
        return 0.0
    edge = (top + bot) / 2
    lines = np.mean(sorted(sides + divs)[1:])  # ทนเส้นขาดได้ 1 เส้น
    inner = m[18:-18, :].mean()                # ในช่อง (รวมตัวเลข) ต้องโปร่งกว่าเส้นกรอบมาก
    if inner > 0.45 or edge - inner < 0.25:
        return 0.0
    return 0.5 * edge + 0.5 * lines

def find_strip(im, dbg=False):
    m = frame_mask(im)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cs:
        (cx, cy), (w, h), a = cv2.minAreaRect(c)
        L, S = max(w, h), min(w, h)
        if S < 8 or L * S < 1200 or not (2.3 < L / S < 14):
            continue
        q = quad_of(c)
        H, W = im.shape[:2]
        if (q[:, 0] < -5).any() or (q[:, 1] < -5).any() or (q[:, 0] > W + 5).any() or (q[:, 1] > H + 5).any():
            continue
        if not cv2.isContourConvex(q.reshape(-1, 1, 2)) or not (0.6 < cv2.contourArea(q) / (L * S) < 1.4):
            continue
        sc = frame_score(warp(m, q))
        if sc > 0.35 and (best is None or sc > best[0]):
            best = (sc, q)
    if best is None:
        return None
    return {"quad": best[1], "score": round(float(best[0]), 3), "strip": warp(im, best[1])}

def cells(strip, inset=0.14):
    """แบ่ง 4 ช่องเท่ากัน · ตัดขอบเข้าไป inset เพื่อทิ้งเส้นกรอบ"""
    h, w = strip.shape[:2]; cw = w / 4; k = int(inset * h); kx = int(inset * cw)
    return [strip[k:h - k, int(i * cw) + kx:int((i + 1) * cw) - kx] for i in range(4)]
