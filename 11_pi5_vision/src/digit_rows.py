"""ทางสำรองเมื่อไม่เจอกล่อง REAI: หาแถวตัวเลขที่ไหนก็ได้ในภาพ แล้วให้ CNN ตัวเดิมอ่านทีละตัว
ก้อนที่ "หน้าตาเหมือนตัวเลข" (ทั้งเข้มบนสว่าง และสว่างบนเข้ม) → จัดกลุ่มที่สูงใกล้กัน + อยู่บรรทัดเดียวกัน + ห่างกันพอดี → แถว
เลือกแถวที่ CNN มั่นใจเฉลี่ยสูงสุด (ต้องมี ≥ 3 ตัว)"""
import cv2
import numpy as np


def _components(gray, polarity):
    g = gray if polarity == "dark" else 255 - gray
    out = []
    for bs in (31, 61):                                # 2 ขนาด — block เดียว (41) ทำหลักแดงท้ายของมิเตอร์ลูกกลิ้งหาย (7 ต.ค.)
        th = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, bs, 10)
        n, lab, st, _ = cv2.connectedComponentsWithStats(th, 8)
        H, W = gray.shape
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if not (0.025 * H <= h <= 0.6 * H) or h < 14:
                continue
            ar = h / max(w, 1)
            if not (1.0 <= ar <= 7.0):
                continue
            fill = a / float(w * h)
            if not (0.12 <= fill <= 0.85):
                continue
            if x == 0 or y == 0 or x + w >= W or y + h >= H:
                continue
            out.append((x, y, w, h))
    return out


def _dedup(boxes):
    """ก้อนเดียวกันที่เจอจากหลาย threshold → เก็บตัวใหญ่สุด (numpy · เดิมลูปซ้อนใช้ 182 ms บน Pi)"""
    if not boxes:
        return []
    b = np.array(sorted(boxes, key=lambda b: -b[2] * b[3]), np.float32)
    keep = np.ones(len(b), bool)
    for i in range(len(b)):
        if not keep[i]:
            continue
        x, y, w, h = b[i]
        dup = (np.abs(b[:, 0] - x) < 0.3 * w) & (np.abs(b[:, 1] - y) < 0.3 * h) & (np.abs(b[:, 3] - h) < 0.3 * h)
        dup[:i + 1] = False
        keep &= ~dup
    return [tuple(int(v) for v in r) for r in b[keep]]


def _rows(boxes):
    boxes = sorted(boxes, key=lambda b: b[0])
    rows, used = [], [False] * len(boxes)
    for i, b in enumerate(boxes):
        if used[i]:
            continue
        row, idx, last = [b], [i], b
        for j in range(i + 1, len(boxes)):
            c = boxes[j]
            gap = c[0] - (last[0] + last[2])
            if gap > 1.1 * last[3]:                    # เรียงตาม x แล้ว — ตัวถัดไปไกลกว่านี้แน่ หยุดได้
                break
            if used[j]:
                continue
            hc, hl = c[3], last[3]
            if 0.75 < hc / hl < 1.33 and abs((c[1] + hc / 2) - (last[1] + hl / 2)) < 0.3 * hl and gap > -0.1 * hl:
                row.append(c); idx.append(j); last = c
        if len(row) >= 3:
            rows.append(row)
            for k in idx:
                used[k] = True
    return rows


def _suppress_overlap(row):
    """ก้อนที่ซ้อนแนวนอนกับก้อนข้างๆ เกิน 40 % ของตัวที่แคบกว่า (เช่น เส้นแบ่งช่องลูกกลิ้ง) → เก็บตัวที่ใหญ่กว่า"""
    out = []
    for b in row:
        if out:
            a = out[-1]
            ov = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
            if ov > 0.4 * min(a[2], b[2]):
                if b[2] * b[3] > a[2] * a[3]:
                    out[-1] = b
                continue
        out.append(b)
    return out


def _cell(img, b):
    """ช่องสี่เหลี่ยมจัตุรัส 1.3 h รอบก้อน · ล้นขอบภาพให้ต่อขอบเฉพาะส่วนเล็กๆ (เดิม pad ทั้งภาพทุกช่อง ~390 ms/ภาพบน Pi)"""
    x, y, w, h = b
    s = int(1.3 * h); cx, cy = x + w / 2, y + h / 2
    x0, y0 = int(cx - s / 2), int(cy - s / 2)
    H, W = img.shape[:2]
    cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x0 + s, W), min(y0 + s, H)
    c = img[cy0:cy1, cx0:cx1]
    if c.shape[0] != s or c.shape[1] != s:
        c = cv2.copyMakeBorder(c, cy0 - y0, y0 + s - cy1, cx0 - x0, x0 + s - cx1, cv2.BORDER_REPLICATE)
    return c


def find_rows(bgr, net, verifier=None, max_side=1920, min_mean=0.7, max_junk=0.3):
    """net = ตัวอ่าน (0–9/ว่าง) · verifier = โมเดลที่มีคลาส "ไม่ใช่ตัวเลข" ใช้ตัดแถวขยะ (ขอบตู้ มู่ลี่ ตัวหนังสือ)
    7 ต.ค.: แถวเลขมิเตอร์จริง ก้อนที่ verifier ว่าไม่ใช่เลข 14 % · แถวขยะในรูปไม่มีมิเตอร์ 33–100 % → ตัดที่ 30 %"""
    sc = min(1.0, max_side / max(bgr.shape[:2]))
    img = cv2.resize(bgr, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA) if sc < 1 else bgr
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cands = []
    boxes = _dedup(_components(gray, "dark") + _components(gray, "light"))
    rows = [r for r in (_suppress_overlap(r) for r in _rows(boxes)) if len(r) >= 3]
    if not rows:
        return []
    cells = [[_cell(img, b) for b in r] for r in rows]
    flat = net.predict([c for cs in cells for c in cs])         # เรียก CNN ครั้งเดียวทั้งภาพ (cv2.dnn มีค่าโสหุ้ยต่อครั้ง)
    k0, pending = 0, []
    for row, cs in zip(rows, cells):
        out = flat[k0:k0 + len(row)]; k0 += len(row)
        w_med = float(np.median([b[2] for b in row]))
        # ก้อนแคบผิดปกติ (< 45 % ของความกว้างกลางแถว) ที่ไม่ใช่ "1" = เส้นแบ่งช่อง/ขอบ ไม่ใช่ตัวเลข
        keep = [(o[0], o[1], b, c) for o, b, c in zip(out, row, cs)
                if o[0] not in "_x" and (b[2] >= 0.45 * w_med or o[0] == "1")]
        if len(keep) < 3 or len(keep) < 0.7 * len(row):          # ก้อนส่วนใหญ่ไม่ใช่ตัวเลข = ไม่ใช่แถวเลข
            continue
        text = "".join(k[0] for k in keep)
        if text.count("1") > 0.8 * len(text):                     # เส้นตั้งเรียงกัน (ขอบตู้/มู่ลี่) ไม่ใช่เลข
            continue
        confs = [k[1] for k in keep]
        mean = float(np.mean(confs))
        if mean < min_mean:
            continue
        pending.append(({"text": text, "conf": min(confs), "mean": mean, "score": mean * min(len(text), 8) ** 0.5,
                         "boxes": [tuple(int(v / sc) for v in k[2]) for k in keep]}, [k[3] for k in keep]))
    if verifier is not None and pending:
        vflat = verifier.predict([c for _, cs in pending for c in cs])
        k0 = 0
        for cand, cs in pending:
            junk = float(np.mean([o[0] == "x" for o in vflat[k0:k0 + len(cs)]])); k0 += len(cs)
            if junk <= max_junk:
                cands.append(cand)
    else:
        cands = [c for c, _ in pending]
    cands = [c for c in cands if c["mean"] >= min_mean]
    cands.sort(key=lambda c: -c["score"])
    return cands
