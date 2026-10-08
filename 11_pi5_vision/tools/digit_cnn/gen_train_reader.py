"""สร้างภาพช่องตัวเลขสังเคราะห์ → ink_map 40×40 + label (0–9, 10 = ว่าง)
ช่องจำลอง 120×120 (= 1 ช่องของแถบที่ดัดแล้ว 480×120) แล้วตัดขอบเข้าไปเท่ากับตอนใช้งานจริง (INSET)
สไตล์: ฟอนต์พิมพ์ / ฟอนต์ลายมือ + บิดเส้น / 7-segment (มีขีดดับจางแบบ LCD ได้) · สีพื้น/หมึก/การ์ด สุ่มทั้งหมด"""
import json, sys, random, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from multiprocessing import Pool
sys.path.insert(0, '../../src')
from cellread import ink_map

BOX = 120
INSET = 0.08
F = json.load(open('fonts.json'))
SEG = {'0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg', '5': 'acdfg', '6': 'acdefg',
       '7': 'abc', '8': 'abcdefg', '9': 'abcdfg'}
_font_cache = {}


def font(p, idx, size):
    k = (p, idx, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(p, size, index=idx)
    return _font_cache[k]


def rand_color(rng):
    return np.array([rng.randint(0, 255) for _ in range(3)], np.float32)


def lab_dist(a, b):
    la = cv2.cvtColor(np.uint8([[a]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    lb = cv2.cvtColor(np.uint8([[b]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    la[0] *= 100 / 255; lb[0] *= 100 / 255
    return np.linalg.norm(la - lb)


def glyph_font(rng, d, fonts):
    p, idx, _, _ = fonts[rng.randrange(len(fonts))]
    size = 160
    im = Image.new('L', (240, 240), 0)
    dr = ImageDraw.Draw(im)
    f = font(p, idx, size)
    bb = dr.textbbox((0, 0), d, font=f)
    dr.text((120 - (bb[0] + bb[2]) / 2, 120 - (bb[1] + bb[3]) / 2), d, 255, font=f)
    g = np.array(im)
    if rng.random() < 0.3:                                    # เปลี่ยนความหนาเส้น
        k = rng.choice([3, 5, 7])
        g = cv2.dilate(g, np.ones((k, k), np.uint8)) if rng.random() < 0.6 else cv2.erode(g, np.ones((3, 3), np.uint8))
    return g


def glyph_7seg(rng, d):
    g = np.zeros((240, 240), np.uint8); ghost = np.zeros_like(g)
    w = rng.randint(10, 26); x0, x1 = 80, 160; y0, y1, y2 = 40, 120, 200
    sl = rng.uniform(-0.18, 0.05)                              # เอียงแบบจอ LED
    gap = rng.randint(0, 6)
    segs = {'a': ((x0, y0), (x1, y0)), 'b': ((x1, y0), (x1, y1)), 'c': ((x1, y1), (x1, y2)), 'd': ((x0, y2), (x1, y2)),
            'e': ((x0, y1), (x0, y2)), 'f': ((x0, y0), (x0, y1)), 'g': ((x0, y1), (x1, y1))}
    for s, ((a, b), (c, e)) in segs.items():
        dx, dy = (gap if a != c else 0), (gap if b != e else 0)
        p0 = (int(a + dx - sl * (b - 120)), b + dy); p1 = (int(c - dx - sl * (e - 120)), e - dy)
        tgt = g if s in SEG[d] else ghost
        cv2.line(tgt, p0, p1, 255, w)
    if d == '7' and rng.random() < 0.3:                         # 7 แบบมีขีด f
        cv2.line(g, (x0 - int(sl * (y0 - 120)), y0), (x0 - int(sl * (y1 - 120)), y1), 255, w)
    if d in '69' and rng.random() < 0.3:                        # 6/9 ไม่มีหาง
        cv2.line(g, (x0, y0) if d == '6' else (x0, y2), (x1, y0) if d == '6' else (x1, y2), 0, w + 2)
    return g, ghost, (40, 27, 200, 213)        # กรอบของ "หลัก" ทั้งหลัก ไม่ใช่กรอบหมึก → เลข 1 ชิดขวาแบบจอจริง


def elastic(rng, g, alpha=8, sigma=6):
    h, w = g.shape
    dx = cv2.GaussianBlur((np.random.default_rng(rng.randrange(1 << 30)).random((h, w)) * 2 - 1).astype(np.float32), (0, 0), sigma) * alpha
    dy = cv2.GaussianBlur((np.random.default_rng(rng.randrange(1 << 30)).random((h, w)) * 2 - 1).astype(np.float32), (0, 0), sigma) * alpha
    X, Y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(g, X + dx, Y + dy, cv2.INTER_LINEAR)


def place(rng, g, scale_h, bbox=None):
    """ย่อ/หมุน/เลื่อน glyph 240×240 ให้สูง scale_h ของช่อง แล้ววางบนช่อง BOX · bbox = กรอบอ้างอิง (ไม่ให้ = กรอบหมึก)"""
    if bbox is None:
        ys, xs = np.where(g > 40)
        if len(ys) == 0:
            return np.zeros((BOX, BOX), np.float32)
        bbox = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    g = g[bbox[1]:bbox[3], bbox[0]:bbox[2]]
    h, w = g.shape
    th = scale_h * BOX; s = th / h
    if w * s > 0.92 * BOX:
        s = 0.92 * BOX / w
    ang = rng.uniform(-10, 10); sh = rng.uniform(-0.15, 0.15)
    cx = BOX / 2 + rng.uniform(-0.08, 0.08) * BOX; cy = BOX / 2 + rng.uniform(-0.08, 0.08) * BOX
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, s)
    M[0, 1] += sh * s
    M[0, 2] += cx - w / 2; M[1, 2] += cy - h / 2
    return cv2.warpAffine(g, M, (BOX, BOX), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0


def background(rng):
    if rng.random() < 0.5:                                     # น้ำเงินแบบกล่อง REAI (ช่วงกว้าง)
        base = np.array([rng.randint(120, 255), rng.randint(40, 180), rng.randint(20, 160)], np.float32)
    else:
        base = rand_color(rng)
    bg = np.ones((BOX, BOX, 3), np.float32) * base
    gx = np.linspace(-1, 1, BOX)[None, :, None] * rng.uniform(-25, 25)
    gy = np.linspace(-1, 1, BOX)[:, None, None] * rng.uniform(-25, 25)
    bg += gx + gy
    tex = cv2.GaussianBlur(np.random.default_rng(rng.randrange(1 << 30)).normal(0, 1, (BOX, BOX)).astype(np.float32), (0, 0), rng.uniform(2, 8))
    bg += tex[..., None] * rng.uniform(0, 30)
    return bg, base


def sample(seed):
    rng = random.Random(seed)
    label = rng.randrange(11)                                 # 10 = ว่าง
    bg, base = background(rng)
    img = bg.copy(); surf = base
    if rng.random() < 0.35:                                   # การ์ดแปะทับ
        card = rng.choice([np.array([235, 235, 235], np.float32), np.array([200, 240, 250], np.float32), rand_color(rng)])
        m = rng.uniform(0.0, 0.14) * BOX
        x0, y0 = int(m + rng.uniform(-4, 4)), int(m + rng.uniform(-4, 4))
        x1, y1 = int(BOX - m + rng.uniform(-4, 4)), int(BOX - m + rng.uniform(-4, 4))
        img[max(y0, 0):y1, max(x0, 0):x1] = card + np.random.default_rng(seed).normal(0, 4, (1, 1, 3)).astype(np.float32)
        surf = card
    if label < 10:
        d = str(label)
        r = rng.random()
        ghost = None; bb = None
        if r < 0.45:
            g = glyph_font(rng, d, F['train'])
            if rng.random() < 0.3:
                g = elastic(rng, g, alpha=rng.uniform(4, 12))
        elif r < 0.70:
            g = glyph_font(rng, d, F['train'])
            g = elastic(rng, g, alpha=rng.uniform(8, 20), sigma=rng.uniform(5, 9))
        else:
            g, ghost, bb = glyph_7seg(rng, d)
        scale = rng.uniform(0.45, 0.95)
        rng_state = rng.getstate()
        mask = place(rng, g, scale, bb)
        for _ in range(30):                                   # หมึกต้องต่างจากพื้นพอให้คนอ่านออก (ΔE ≥ 28)
            ink = rand_color(rng)
            if lab_dist(ink, surf) > 28:
                break
        if ghost is not None and rng.random() < 0.35:         # ขีดดับจางๆ แบบ LCD
            rng.setstate(rng_state); gm = place(rng, ghost, scale, bb)
            a = rng.uniform(0.1, 0.25)
            img = img * (1 - a * gm[..., None]) + ink * a * gm[..., None]
        img = img * (1 - mask[..., None]) + ink * mask[..., None]
    elif rng.random() < 0.3:                                  # ช่องว่างแต่มีจุดเปื้อนเล็กๆ
        for _ in range(rng.randint(1, 3)):
            cv2.circle(img, (rng.randint(15, 105), rng.randint(15, 105)), rng.randint(1, 4), rand_color(rng).tolist(), -1)
    # เส้นกรอบรอบช่อง (หนา/บาง/ขาดบางด้าน) — ตัด inset แล้วอาจเหลือติดขอบ
    if rng.random() < 0.8:
        fc = np.array([rng.randint(120, 230), rng.randint(90, 170), rng.randint(170, 255)], np.float32) if rng.random() < 0.7 else rand_color(rng)
        t = rng.randint(2, 10)
        for side in range(4):
            if rng.random() < 0.85:
                o = rng.randint(-3, 6) if rng.random() < 0.7 else rng.randint(6, 16)
                if side == 0: cv2.line(img, (0, o), (BOX, o + rng.randint(-4, 4)), fc.tolist(), t)
                if side == 1: cv2.line(img, (0, BOX - 1 - o), (BOX, BOX - 1 - o + rng.randint(-4, 4)), fc.tolist(), t)
                if side == 2: cv2.line(img, (o, 0), (o + rng.randint(-4, 4), BOX), fc.tolist(), t)
                if side == 3: cv2.line(img, (BOX - 1 - o, 0), (BOX - 1 - o + rng.randint(-4, 4), BOX), fc.tolist(), t)
    # ความผิดพลาดของการดัดภาพ: เลื่อน/หมุน/ซูมเล็กน้อย
    M = cv2.getRotationMatrix2D((BOX / 2, BOX / 2), rng.uniform(-4, 4), rng.uniform(0.92, 1.08))
    M[:, 2] += [rng.uniform(-7, 7), rng.uniform(-7, 7)]
    img = cv2.warpAffine(img, M, (BOX, BOX), borderMode=cv2.BORDER_REFLECT)
    # แสง: เงา/ไฮไลต์
    if rng.random() < 0.4:
        cx, cy, rr = rng.uniform(0, BOX), rng.uniform(0, BOX), rng.uniform(30, 90)
        Y, X = np.mgrid[0:BOX, 0:BOX]
        spot = np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (2 * rr ** 2))[..., None]
        img = img + spot * rng.uniform(-60, 60)
    img *= rng.uniform(0.55, 1.25)
    # กล้อง: เบลอ + noise + JPEG + ย่อความละเอียด (กล่องไกล)
    if rng.random() < 0.7:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.3, 2.2))
    if rng.random() < 0.15:
        k = rng.randint(3, 9); ker = np.zeros((k, k), np.float32); ker[k // 2] = 1 / k
        img = cv2.filter2D(img, -1, cv2.warpAffine(ker, cv2.getRotationMatrix2D((k / 2, k / 2), rng.uniform(0, 180), 1), (k, k)))
    img += np.random.default_rng(seed + 1).normal(0, rng.uniform(1, 9), img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    if rng.random() < 0.5:
        lo = rng.randint(18, 60)
        img = cv2.resize(cv2.resize(img, (lo, lo), interpolation=cv2.INTER_AREA), (BOX, BOX), interpolation=cv2.INTER_LINEAR)
    q = rng.randint(35, 95)
    img = cv2.imdecode(cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, q])[1], 1)
    k = int(INSET * BOX)
    cell = img[k:BOX - k, k:BOX - k]
    return ink_map(cell), label, cell


def work(rng_range):
    a, b = rng_range
    X = np.zeros((b - a, 40, 40), np.float32); y = np.zeros(b - a, np.int64)
    for i, s in enumerate(range(a, b)):
        X[i], y[i], _ = sample(s)
    return X, y


if __name__ == '__main__':
    N = int(sys.argv[1]); off = int(sys.argv[2]) if len(sys.argv) > 2 else 0; out = sys.argv[3] if len(sys.argv) > 3 else 'train.npz'
    step = 2000
    chunks = [(off + i, off + min(i + step, N)) for i in range(0, N, step)]
    with Pool(8) as p:
        res = p.map(work, chunks)
    X = np.concatenate([r[0] for r in res]); y = np.concatenate([r[1] for r in res])
    np.savez_compressed(out, X=X, y=y); print(out, X.shape, np.bincount(y))
