"""สร้างธีมสีจากธีมม่วงต้นฉบับ · teal (เขียวฟ้า) 2 ต.ค. 2569 · graphite/rose/gold/sapphire/navy/emerald/ruby/copper 6 ต.ค. 2569
ไฟล์ม่วงไม่ถูกแก้ · ได้ css/<ชื่อ>.<ธีม>.css คู่กับแต่ละไฟล์ + img/aria-logo-<ธีม>.png
แปลงเฉพาะสีโทนม่วง/บานเย็น (hue 235–335°) · สีสถานะ (เขียว/เหลือง/แดง) และขาว/ดำคงเดิม
แก้ CSS ม่วงเมื่อไหร่ ให้รันใหม่:  python3 tools/make_accent.py   (จาก aria/web)
แล้ว ⚠ เปลี่ยน ?v= ของทุก link[data-css] ใน index.html — ไฟล์ธีมใช้ query เดียวกับไฟล์ม่วง ไม่เปลี่ยน = เบราว์เซอร์ใช้ธีมเก่าจากแคช (เจอ 6 ต.ค.: หลัง logout/login สีครึ่งม่วงครึ่งชมพู)
ต้องตรงกับ ACCENT_SPECS + shiftHue() + matchLum() ใน js/liquid.js
"""
import colorsys, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ["styles", "theme", "app", "glass"]
# hue ใหม่ = base + (hue เดิม − 250°) × k · saturation × s · แล้วสเกลให้สว่างจริงเท่าสีม่วงเดิม (คอนทราสต์ตัวอักษรเท่าเดิม)
ACCENTS = {
    "teal":     dict(base=172, k=0.55, s=0.90),   # ม่วง 250° → 172° · บานเย็น 292° → 195°
    "graphite": dict(base=225, k=0.00, s=0.07),   # ดำเทา: ทุกสีม่วง → เทาเหล็กอมฟ้านิดๆ (แทบไม่มีสี)
    "rose":     dict(base=338, k=0.30, s=0.78),   # ชมพูหรู: ม่วง → ชมพูกุหลาบหม่น 338° · บานเย็น → rose gold 351° · พื้นมืด = ไวน์
    "gold":     dict(base=36, k=0.12, s=0.88),    # ทอง: ม่วง → ทองอำพัน 36° · บานเย็น → ทอง 41° (40° ขึ้นไปที่ความสว่างต่ำออกเขียวขี้ม้า) · พื้นมืด = น้ำตาลบรอนซ์
    "sapphire": dict(base=222, k=0.35, s=0.95),   # ไพลิน: น้ำเงินลึก 222° → อินดิโก 237°
    "navy":     dict(base=218, k=0.15, s=0.42),   # กรมท่า: น้ำเงินหม่น สุขุม (saturation ต่ำ)
    "emerald":  dict(base=152, k=0.30, s=0.85),   # มรกต: เขียวมรกต 152° → 165°
    "ruby":     dict(base=352, k=0.20, s=0.85),   # ทับทิม: แดงอมชมพู 352° → แดง 0°
    "copper":   dict(base=20, k=0.15, s=0.85),    # ทองแดง: ส้มทองแดง 20° → 26°
    # ชมพูพาสเทล = Pantone 7422 C #F4CDD4 (ผู้ใช้เลือก 6 ต.ค.: hue 349° · HSL s 0.64) — ทุกสีม่วง → hue เดียว · ปุ่มหลักใช้สี Pantone ตรงๆ + ตัวอักษรเข้ม
    "blush":    dict(base=349, k=0.00, s=0.66, accent=("#f4cdd4", "#fbe3e8"), accent_ink="#4a1f2b"),
    "hotpink":  dict(base=326, k=0.20, s=1.00),   # ชมพูสด: บานเย็นอมชมพูสด 326° → 334°
}
SPEC = ACCENTS["teal"]


def shift(r, g, b):
    """r,g,b 0–255 → สีใหม่ตาม SPEC ปัจจุบัน"""
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    deg = h * 360
    if not (235 <= deg <= 335) or s < 0.08:
        return r, g, b
    nd = SPEC["base"] + (deg - 250) * SPEC["k"]
    c = colorsys.hls_to_rgb((nd % 360) / 360, l, s * SPEC["s"])
    # รักษาความสว่างจริง (relative luminance) เท่าสีม่วงเดิม: เขียวที่ lightness เท่ากันสว่างกว่า → ตัวอักษร/พื้นคอนทราสต์ตก
    c = match_lum(c, (r / 255, g / 255, b / 255))
    return tuple(round(x * 255) for x in c)


def lum(c):
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def match_lum(c, ref):
    """สเกล c ลง (คงสี) จน luminance = ref · ถ้า c มืดกว่าอยู่แล้วให้คงไว้"""
    target = lum(ref)
    if lum(c) <= target:
        return c
    lo, hi = 0.0, 1.0
    for _ in range(30):
        m = (lo + hi) / 2
        if lum([x * m for x in c]) > target: hi = m
        else: lo = m
    return [x * lo for x in c]


def hex_sub(m):
    t = m.group(1)
    if len(t) in (3, 4):
        t = "".join(c * 2 for c in t)
    r, g, b = (int(t[i:i + 2], 16) for i in (0, 2, 4))
    alpha = t[6:]                          # #rrggbbaa (6 ต.ค.: เดิมข้ามสีแบบมี alpha → ม่วงอ่อนค้างในธีมอื่น)
    return "#%02x%02x%02x" % shift(r, g, b) + alpha


def rgb_sub(m):
    fn, a, b, c, rest = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    r, g, bb = shift(int(a), int(b), int(c))
    return f"{fn}({r}, {g}, {bb}{rest})"


HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
RGB = re.compile(r"\b(rgba?)\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(\s*(?:,[^)]*)?)\)")


def convert(css):
    css = RGB.sub(rgb_sub, css)
    return HEX.sub(hex_sub, css)


def accent_override(spec):
    """ธีมที่กำหนดสีหลักเอง (สีอ่อน) → ปุ่ม/ป้ายที่ใช้ --accent ต้องใช้ตัวอักษรเข้ม ไม่งั้นขาวบนชมพูอ่อนอ่านไม่ออก"""
    a, b = spec["accent"]
    ink = spec["accent_ink"]
    return f"""
/* สีหลักของธีมนี้กำหนดตรง ({a}) — ปุ่ม/ป้ายบนสีหลักใช้ตัวอักษรเข้ม {ink} */
:root {{ --accent: linear-gradient(135deg, {a}, {b}); }}
.btn.primary, .btn.primary:hover:not(:disabled), .filter.active, .side-nav em, button.avatar, .acct-av {{ color: {ink}; text-shadow: none; }}
.btn.primary svg, .filter.active svg {{ color: {ink}; }}
"""


def main():
    global SPEC
    from PIL import Image
    import numpy as np
    for accent, spec in ACCENTS.items():
        SPEC = spec
        for name in FILES:
            src = (ROOT / "css" / f"{name}.css").read_text()
            head = f"/* สร้างอัตโนมัติจาก css/{name}.css โดย tools/make_accent.py — ห้ามแก้ไฟล์นี้ตรงๆ */\n"
            out = head + convert(src)
            if name == "glass" and "accent" in spec:
                out += accent_override(spec)
            (ROOT / "css" / f"{name}.{accent}.css").write_text(out)
        # โลโก้หน้าเข้าสู่ระบบ (ม่วงพลัม) → ธีมนี้ ด้วยฟังก์ชันเดียวกันทีละพิกเซล
        im = Image.open(ROOT / "img" / "aria-logo-plum.png").convert("RGBA")
        a = np.array(im)
        rgb = a[..., :3].reshape(-1, 3)
        uniq, inv = np.unique(rgb, axis=0, return_inverse=True)
        mapped = np.array([shift(*map(int, c)) for c in uniq], dtype=np.uint8)
        a[..., :3] = mapped[inv.reshape(-1)].reshape(a.shape[0], a.shape[1], 3)
        Image.fromarray(a).save(ROOT / "img" / f"aria-logo-{accent}.png", optimize=True)
        sw = [hex_sub(HEX.match(c)) for c in ("#8b5cf6", "#d946ef")]
        print(f"{accent}: meta {hex_sub(HEX.match('#1a0d38'))} · sw {sw[0]} {sw[1]}")   # ใส่ใน ACCENTS (app.js) + META (accent.js)


if __name__ == "__main__":
    main()
