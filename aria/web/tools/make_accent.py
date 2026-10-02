"""สร้างธีมสี "teal" (เขียวฟ้า) จากธีมม่วงต้นฉบับ · ผู้ใช้ขอ 2 ต.ค. 2569 (เก็บม่วงไว้สลับกลับได้)
ไฟล์ม่วงไม่ถูกแก้ · ได้ css/<ชื่อ>.teal.css คู่กับแต่ละไฟล์ + img/aria-logo-teal.png
แปลงเฉพาะสีโทนม่วง/บานเย็น (hue 235–335°) · สีสถานะ (เขียว/เหลือง/แดง) และขาว/ดำคงเดิม
แก้ CSS ม่วงเมื่อไหร่ ให้รันใหม่:  python3 tools/make_accent.py   (จาก aria/web)
ต้องตรงกับ shiftHue() + matchLum() ใน js/liquid.js
"""
import colorsys, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ["styles", "theme", "app", "glass"]


def shift(r, g, b):
    """r,g,b 0–255 → สีใหม่ · ม่วง 250° → teal 172° · บานเย็น 292° → ฟ้าอมเขียว 195°"""
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    deg = h * 360
    if not (235 <= deg <= 335) or s < 0.08:
        return r, g, b
    nd = 172 + (deg - 250) * 0.55
    c = colorsys.hls_to_rgb((nd % 360) / 360, l, s * 0.9)
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
    if len(t) == 3:
        t = "".join(c * 2 for c in t)
    r, g, b = (int(t[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % shift(r, g, b)


def rgb_sub(m):
    fn, a, b, c, rest = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    r, g, bb = shift(int(a), int(b), int(c))
    return f"{fn}({r}, {g}, {bb}{rest})"


HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB = re.compile(r"\b(rgba?)\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(\s*(?:,[^)]*)?)\)")


def convert(css):
    css = RGB.sub(rgb_sub, css)
    return HEX.sub(hex_sub, css)


def main():
    for name in FILES:
        src = (ROOT / "css" / f"{name}.css").read_text()
        head = f"/* สร้างอัตโนมัติจาก css/{name}.css โดย tools/make_accent.py — ห้ามแก้ไฟล์นี้ตรงๆ */\n"
        (ROOT / "css" / f"{name}.teal.css").write_text(head + convert(src))
    # โลโก้หน้าเข้าสู่ระบบ (ม่วงพลัม) → เขียวฟ้า ด้วยฟังก์ชันเดียวกันทีละพิกเซล
    from PIL import Image
    import numpy as np
    im = Image.open(ROOT / "img" / "aria-logo-plum.png").convert("RGBA")
    a = np.array(im)
    rgb = a[..., :3].reshape(-1, 3)
    uniq, inv = np.unique(rgb, axis=0, return_inverse=True)
    mapped = np.array([shift(*map(int, c)) for c in uniq], dtype=np.uint8)
    a[..., :3] = mapped[inv.reshape(-1)].reshape(a.shape[0], a.shape[1], 3)
    Image.fromarray(a).save(ROOT / "img" / "aria-logo-teal.png", optimize=True)
    print("ok", [f"{n}.teal.css" for n in FILES], "aria-logo-teal.png", f"theme-color {hex_sub(HEX.match('#1a0d38'))}")


if __name__ == "__main__":
    main()
