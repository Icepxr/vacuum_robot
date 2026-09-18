"""sevenseg.py — อ่านตัวเลขแบบ 7-segment (จอ LCD/LED หรือเขียนมือเลียนแบบ) โดยไม่ใช้ OCR ฟอนต์

ทำไมไม่ใช่ tesseract: ตัวเลข 7-segment เส้นขาด/บาง tesseract อ่านผิดหรืออ่านไม่ออก (18 ก.ย. 2026: 1509 → '', '1505', '4409')
วิธี: หาหมึก → แยกหลักตามช่องว่างแนวนอน → วัดว่าแต่ละ segment (a–g) มีหมึกไหม → ถอดรหัสจากตาราง
ข้อจำกัด: ต้องรู้ว่าหมึกสีอะไร (cfg["ink"]: "red" / "dark") · ตัวเลขต้องเรียงแนวนอนบรรทัดเดียว · เอียงได้เล็กน้อย
"""
import cv2
import numpy as np

# segment → (x0, y0, x1, y1) สัดส่วนของกล่องหลัก · a บน · g กลาง · d ล่าง · f/b ซ้าย/ขวาบน · e/c ซ้าย/ขวาล่าง
# โซนต้อง "ไม่ซ้อนกัน" — เดิม e กับ d ซ้อนที่มุมล่างซ้าย ทำให้ปลายซ้ายของขีดล่างของ 5/9 ไปติด e → อ่านเป็น 6/8
SEG_ZONES = {
    "a": (0.25, 0.00, 0.75, 0.15),
    "b": (0.75, 0.20, 1.00, 0.45),
    "c": (0.75, 0.55, 1.00, 0.80),
    "d": (0.25, 0.85, 0.75, 1.00),
    "e": (0.00, 0.55, 0.25, 0.80),
    "f": (0.00, 0.20, 0.25, 0.45),
    "g": (0.25, 0.42, 0.75, 0.58),
}
DIGITS = {
    "abcdef": "0", "bc": "1", "abdeg": "2", "abcdg": "3", "bcfg": "4",
    "acdfg": "5", "acdefg": "6", "abc": "7", "abcdefg": "8", "abcdfg": "9",
    "abcf": "7",      # 7 แบบมีขีดซ้ายบน
    "acdeg": "2",     # 2 เขียนมือบางแบบ
}


def ink_mask(bgr, ink="red"):
    """คืน mask 0/255 ของหมึก · red = ปากกาแดง/ชมพู (hue 165–180 ∪ 0–10) · dark = หมึกดำ/จอ LCD บนพื้นสว่าง"""
    if ink == "red":
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        m = ((h >= 165) | (h <= 10)) & (s >= 30) & (v >= 80)
        return m.astype(np.uint8) * 255
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, 15)


def find_text_box(mask, min_area=200):
    """กล่องรอบกลุ่มหมึกที่ดูเหมือนแถวตัวเลข (กว้าง 1.2–8 เท่าของสูง) · เลือกกลุ่มที่พื้นที่หมึกมากสุด · None ถ้าไม่เจอ"""
    h, w = mask.shape
    k = max(9, int(min(h, w) * 0.02))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k * 3), np.uint8))   # เชื่อมหลักที่อยู่ติดกันเป็นแถว
    n, lab, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    best, best_ink = None, 0
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < min_area or bh == 0:
            continue
        ar = bw / bh
        if not (0.03 <= ar <= 8.0):            # หลักเดียว "1" = เส้นเดียว (ar ~0.05) จนถึงแถว 8 หลัก · closing ไม่ขยายรูป จึงต้องยอมแคบ
            continue
        ink = int((mask[y:y + bh, x:x + bw] > 0).sum())
        if ink > best_ink:
            best, best_ink = (int(x), int(y), int(bw), int(bh)), ink
    return best


def split_digits(mask):
    """แยกหลักด้วย projection แนวนอน · คืน list ของ (x0, x1) เรียงซ้าย→ขวา"""
    col = (mask > 0).sum(axis=0)
    on = col > 0
    runs, start = [], None
    for x, v in enumerate(on):
        if v and start is None: start = x
        if not v and start is not None: runs.append((start, x)); start = None
    if start is not None: runs.append((start, len(on)))
    if not runs:
        return []
    # รวม run ที่ห่างกันน้อยกว่า 10 % ของความสูง (เส้นขาดในหลักเดียวกัน) · ช่องว่างระหว่างหลักของ 7-seg ปกติ ≥ 15 % ของสูง
    gap = max(2, int(mask.shape[0] * 0.10))
    merged = [list(runs[0])]
    for a, b in runs[1:]:
        if a - merged[-1][1] <= gap: merged[-1][1] = b
        else: merged.append([a, b])
    minw = max(2, int(mask.shape[0] * 0.06))
    return [(a, b) for a, b in merged if b - a >= minw]


def split_merged(span, x_off):
    """หั่นช่วงที่หลักชนกัน: ใช้ "ขีดตั้ง" (คอลัมน์ที่หมึกยาว ≥ 40 % ของสูง) เป็นหลัก —
    ขีดตั้งสองอันที่ห่างกัน < 35 % ของสูง = ขอบขวาของหลักหนึ่งชนขอบซ้ายของหลักถัดไป → ตัดตรงกลาง
    (ภายในหลักเดียว ขอบซ้าย–ขวาห่างกัน ~0.4–0.8 h) · ถ้าหาขีดตั้งไม่พอ ถอยไปหั่นเท่าๆ กันตามความกว้าง ~0.65 h"""
    H, W = span.shape
    frac = (span > 0).mean(axis=0)
    on = frac >= 0.4
    runs, st = [], None
    for x, v in enumerate(on):
        if v and st is None: st = x
        if not v and st is not None: runs.append((st, x)); st = None
    if st is not None: runs.append((st, W))
    cuts = []
    if runs:
        t = float(np.median([b - a for a, b in runs]))          # ความหนาเส้นโดยประมาณ
        for a, b in runs:
            if b - a > 1.8 * t:                                  # ขีดตั้งกว้างผิดปกติ = ขอบสองหลักซ้อนกันพอดี → ตัดกลาง
                cuts.append((a + b) // 2)
    for (a0, a1), (b0, b1) in zip(runs, runs[1:]):
        if b0 - a1 < 0.22 * H:                                   # วัดจริง 18 ก.ย.: ระหว่างหลัก 0.15–0.18 h · ภายในหลัก 0.28–0.38 h
            cuts.append((a1 + b0) // 2)
    cuts.sort()
    if not cuts:
        n = max(2, int(round(W / (0.65 * H))))
        edges = np.linspace(0, W, n + 1).astype(int)
    else:
        edges = [0] + cuts + [W]
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        if b - a >= max(2, int(H * 0.06)):
            out.append((int(a) + x_off, int(b) + x_off))
    return out


def decode_digit(cell, thin_ratio=0.38):
    """cell = mask ของหลักเดียว (ตัดขอบแล้ว) · คืน (ตัวเลขหรือ '?', segments ที่ติด, รายละเอียด)
    ไม่ใช้โซนตายตัว (เขียนมือ ขีดกลางเลื่อนได้) แต่:
      ขีดนอน a/g/d  = แถวที่มีหมึกกว้าง > 45 % ของความกว้าง → จัดกลุ่มแถว → ดูว่ากลุ่มอยู่บน/กลาง/ล่าง
      ขีดตั้ง f/b/e/c = ในครึ่งบน/ล่าง ฝั่งซ้าย/ขวา มี "คอลัมน์" ที่หมึกยาว > 50 % ของครึ่งนั้น (ปลายขีดนอนที่โผล่มาไม่ยาวพอ)"""
    h, w = cell.shape
    if h == 0 or w == 0:
        return "?", "", {}
    if w / h < thin_ratio:                     # แท่งเดียวแคบๆ = 1
        return "1", "bc", {}
    m = cell > 0
    rows = m.mean(axis=1)
    bar_rows = np.where(rows > 0.45)[0]
    bands = []
    for y in bar_rows:
        if bands and y - bands[-1][1] <= max(2, h * 0.06): bands[-1][1] = y
        else: bands.append([y, y])
    on = set()
    for y0, y1 in bands:
        c = (y0 + y1) / 2 / h
        if c < 0.30: on.add("a")
        elif c > 0.70: on.add("d")
        else: on.add("g")
    def vstroke(x0, x1, y0, y1):
        sub = m[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        if sub.size == 0: return False
        return bool((sub.mean(axis=0) > 0.5).any())
    if vstroke(0.00, 0.35, 0.10, 0.48): on.add("f")
    if vstroke(0.65, 1.00, 0.10, 0.48): on.add("b")
    if vstroke(0.00, 0.35, 0.52, 0.90): on.add("e")
    if vstroke(0.65, 1.00, 0.52, 0.90): on.add("c")
    key = "".join(s for s in "abcdefg" if s in on)
    return DIGITS.get(key, "?"), key, {"bands": [[int(a), int(b)] for a, b in bands]}


def read(bgr, ink="red", debug=None):
    """อ่านตัวเลขทั้งแถว · คืน dict {text, digits:[…], box, ok}
    debug = path จะเซฟภาพกล่อง/segment ไว้ดู"""
    mask = ink_mask(bgr, ink)
    box = find_text_box(mask)
    if box is None:
        return {"text": "", "digits": [], "box": None, "ok": False, "why": "ไม่เจอกลุ่มหมึกที่ดูเป็นแถวตัวเลข"}
    x, y, w, h = box
    pad = int(h * 0.12)
    sub = mask[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
    k = max(3, int(h * 0.03))
    sub = cv2.dilate(sub, np.ones((k, k), np.uint8))                 # เส้นปากกาบาง → หนาพอให้ segment ติด (อย่าหนาจนหลักชนกัน)
    ys = np.where((sub > 0).any(axis=1))[0]
    if len(ys) == 0:
        return {"text": "", "digits": [], "box": box, "ok": False, "why": "mask ว่าง"}
    sub = sub[ys[0]:ys[-1] + 1]
    digits = []
    H = sub.shape[0]
    spans = []
    for x0, x1 in split_digits(sub):
        if (x1 - x0) > 0.85 * H:                                 # หลักชนกัน (เช่น ขีดล่างของ 5 ยาวไปแตะ 0)
            spans += split_merged(sub[:, x0:x1], x0)
        else:
            spans.append((x0, x1))
    for x0, x1 in spans:
        cell = sub[:, x0:x1]
        yy = np.where((cell > 0).any(axis=1))[0]
        cell = cell[yy[0]:yy[-1] + 1] if len(yy) else cell
        d, on, cov = decode_digit(cell)
        digits.append({"d": d, "seg": on, "w": int(x1 - x0), "h": int(cell.shape[0])})
    text = "".join(dg["d"] for dg in digits)
    ok = bool(digits) and "?" not in text
    if debug is not None:
        vis = cv2.cvtColor(sub, cv2.COLOR_GRAY2BGR)
        for (x0, x1), dg in zip(spans, digits):
            cv2.rectangle(vis, (x0, 0), (x1 - 1, sub.shape[0] - 1), (0, 200, 0) if dg["d"] != "?" else (0, 0, 255), 1)
            cv2.putText(vis, dg["d"], (x0, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 120, 0), 1)
        cv2.imwrite(str(debug), vis)
    return {"text": text, "digits": digits, "box": box, "ok": ok, "why": "" if ok else "ถอดรหัสบางหลักไม่ได้"}


if __name__ == "__main__":
    import sys, json
    for f in sys.argv[1:]:
        r = read(cv2.imread(f), debug=f + ".7seg.png")
        print(f.split("/")[-1], json.dumps(r, ensure_ascii=False))
