"""
scissor_cad.py — โมเดล 3D ของกลไก scissor lift ขับด้วยเซอร์โวตัวเดียว
รัน:  python3 scissor_cad.py

ออก:
  step/*.step   ← เฉพาะเมื่อมี CadQuery  (เปิดใน Fusion 360 / SolidWorks / FreeCAD)
  stl/*.stl     ← ได้เสมอ (พร้อมพิมพ์ 3D)
  stl/assembly_folded.stl, stl/assembly_extended.stl

ต้องรัน scissor_analysis.py ก่อน เพื่อสร้าง scissor_derived.json

--------------------------------------------------------------------
ระบบพิกัด
  X = แนวที่ scissor กางออก   (+X = ทิศที่ slider ถอยออกห่างจากจุดหมุนตายตัว)
  Y = แนวขวาง                 (ระนาบ scissor สองระนาบอยู่ที่ y = ±31)
  Z = ขึ้น, z = 0 คือผิวล่างแผ่นฐาน = ผิวที่แนบดาดฟ้าหุ่น

การวางตัวในแนว Z — จงใจให้ชุดขับอยู่ "ใต้ดาดฟ้า" เพื่อกดความสูงตอนพับ
   z = +11        แกนหมุดล่างของ scissor (ทั้งจุดตายตัวและ slider)
   z = 0 … +5     แผ่นฐาน
   z = -4 … -10   แผ่น yoke (เลื่อนตามแกน X)
   z = -12 … -16  แขน crank
   z = -16 … -54  ตัวเซอร์โว MG996R   ← ซ่อนในตัวหุ่น ไม่กินความสูงตอนพับ

การนำทางแคร่ (linear guide): ใช้ "ร่องในแผ่นฐาน" เป็นรางโดยตรง
   เสาแคร่ลอดร่องขึ้นมา มีปีกประกบบน-ล่าง → ไม่ต้องใช้เพลานำแยก
   ลดชิ้นส่วน ลดความหลวม และไม่กินความกว้างฐาน
"""

import math, json, os
import solidkit as sk
from solidkit import box, box_from, cyl, slot, rod
import scissor_params as P

HERE = os.path.dirname(os.path.abspath(__file__)) or "."
D = json.load(open(os.path.join(HERE, "scissor_derived.json")))

# ============================================================
# ค่าจัดวาง
# ============================================================
L, N   = P.L_LINK, P.N_STAGES
TH_MIN = math.radians(P.THETA_MIN)
TH_MAX = math.radians(P.THETA_MAX)

X_PIVOT = -43.0                                  # จุดหมุนตายตัวของแขนล่าง
#   เลือก -43 ไม่ใช่ -45: ครีบหมุดรัศมี 6 mm จะจบพอดีที่ -49 (ขอบฐาน -50)
X_CRANK = X_PIVOT + D["crank_centre_x_mm"]       # ศูนย์กลางเพลาเซอร์โว
R_CRANK = D["crank_r_mm"]
S_FOLD  = D["slider_x_fold_mm"]
S_UP    = D["slider_x_up_mm"]

Z_PIN   = 11.0                                   # ระดับแกนหมุดล่าง
Y_PLANE = P.TRACK_Y / 2.0                        # 31.0
TL      = P.LINK_T                               # 3.2  ความหนาแขน
Y_A     = -(TL + 0.4)                            # ชั้นแขน a  (เทียบกึ่งกลางระนาบ)
Y_B     = 0.4                                    # ชั้นแขน b
Y_FIN   = 37.5                                   # ครีบรับหมุด (นอกสุด)
FIN_T   = 4.0

Z_YOKE_T, Z_YOKE_B   = -4.0, -10.0
Z_CRK_T,  Z_CRK_B    = -12.0, -16.0

GUIDE_W   = 16.0                                 # ความกว้างร่องนำในแผ่นฐาน
POST_W    = GUIDE_W - 0.5                        # เสาแคร่ (เผื่อ clearance 0.5)
POST_LEN  = 18.0                                 # ความยาวเสาตามแกน X (กันส่าย/yaw)
PIN_D     = P.PIN_D
BR_OD     = P.BEARING_OD

def span(t): return L * math.cos(t)
def rise(t): return L * math.sin(t)

# ============================================================
# 1. แขน scissor (link) — เหมือนกันทุกชิ้น 28 ชิ้น
# ============================================================
def make_link():
    """ยาวตามแกน X (0→L), หนาตามแกน Y (0→t), กว้างตามแกน Z
       พร้อมหมุนรอบแกน Y ไปวางในระนาบได้ทันที"""
    w, t, r = P.LINK_W, P.LINK_T, P.LINK_W / 2.0
    s = box(L, t, w, (L / 2.0, t / 2.0, 0))
    for x in (0.0, L):
        s = s + cyl(r, t, "Y", (x, 0, 0))
    for x in (0.0, L / 2.0, L):                          # รูหมุด 3 จุด
        s = s - cyl(PIN_D / 2.0, t + 2, "Y", (x, -1, 0))
    # ไม่เจาะโปร่ง: แขนกว้างแค่ 10 mm เนื้อรอบรูหมุดเหลือ 3.4 mm อยู่แล้ว
    # เจาะเพิ่มจะทำให้จุดวิกฤต (ปลายแขนล่างที่รับแรงอัด 23 N) อ่อนเกินไป
    return s

def place_link(pa, pb, y0):
    ang = math.degrees(math.atan2(pb[1] - pa[1], pb[0] - pa[0]))
    return make_link().rotate("Y", -ang).translate((pa[0], y0, pa[1]))

# ============================================================
# 2. เรขาคณิตของกอง scissor
# ============================================================
def scissor_nodes(theta):
    """A[k] = คอลัมน์ฝั่งจุดหมุนตายตัว, B[k] = คอลัมน์ฝั่ง slider  (พิกัด x,z)"""
    s, h = span(theta), rise(theta)
    A = [(X_PIVOT,     Z_PIN + k * h) for k in range(N + 1)]
    B = [(X_PIVOT + s, Z_PIN + k * h) for k in range(N + 1)]
    return A, B

def scissor_links(theta):
    """stage k:  แขน a = A[k-1]→B[k] (ชั้น 1)   แขน b = B[k-1]→A[k] (ชั้น 2)
       สลับชั้นแบบนี้ทำให้ทุกหมุดมีแขนคนละชั้นมาเจอกันเสมอ ไม่ชนกัน"""
    A, B = scissor_nodes(theta)
    out = []
    for k in range(1, N + 1):
        out.append((A[k - 1], B[k], Y_A))
        out.append((B[k - 1], A[k], Y_B))
    return out

# ============================================================
# 3. แผ่นฐาน
# ============================================================
def make_base():
    bp = box_from(-P.BASE_X / 2, -P.BASE_Y / 2, 0, P.BASE_X / 2, P.BASE_Y / 2, P.BASE_T)

    # --- ร่องนำแคร่ (ทำหน้าที่เป็นรางเลื่อนด้วย) ---
    gx0 = X_PIVOT + S_UP - POST_LEN / 2 - 1
    gx1 = X_PIVOT + S_FOLD + POST_LEN / 2 + 1
    bp = bp - box_from(gx0, -GUIDE_W / 2, -2, gx1, GUIDE_W / 2, P.BASE_T + 2)

    # --- รูเพลาเซอร์โว + รูยึดเซอร์โว MG996R (ระยะรู 49.5 x 10) ---
    bp = bp - cyl(7.0, P.BASE_T + 4, "Z", (X_CRANK, 0, -2))
    for sx in (-24.75, 24.75):
        for sy in (-5.0, 5.0):
            bp = bp - cyl(1.6, P.BASE_T + 4, "Z", (X_CRANK + sx, sy, -2))

    # --- ครีบรับหมุดจุดหมุนตายตัว 4 ครีบ ---
    #     ครีบนอก (±37.5) สูงถึงจุดยึดสปริง / ครีบใน (±25) สูงแค่ระดับหมุด
    z_spring = Z_PIN + D["spring_anchor_y_mm"]
    x_spring = X_PIVOT + D["spring_anchor_x_mm"]
    for yf, ztop in ((-Y_FIN, z_spring), (-25.0, Z_PIN), (25.0, Z_PIN), (Y_FIN, z_spring)):
        bp = bp + box_from(X_PIVOT - 5, yf - FIN_T / 2, P.BASE_T - 0.01,
                           X_PIVOT + 11, yf + FIN_T / 2, ztop)
        bp = bp + cyl(6.0, FIN_T, "Y", (X_PIVOT, yf - FIN_T / 2, Z_PIN))
        if ztop > Z_PIN:                                  # หัวครีบนอก = ตายึดสปริง
            bp = bp + cyl(4.0, FIN_T, "Y", (x_spring, yf - FIN_T / 2, ztop))
    # รูหมุดตายตัว ทะลุตลอดแนว Y
    bp = bp - cyl(PIN_D / 2.0, 120, "Y", (X_PIVOT, -60, Z_PIN))
    # รูตายึดสปริง (เฉพาะครีบนอก)
    for yf in (-Y_FIN, Y_FIN):
        bp = bp - cyl(1.8, FIN_T + 2, "Y", (x_spring, yf - FIN_T / 2 - 1, z_spring))

    # --- ปีกรางกดใต้แผ่นฐาน: กันแคร่หลุดขึ้น/ลง (ร่อง T) ---
    for ys in (-1, 1):
        bp = bp + box_from(gx0, ys * (GUIDE_W / 2 + 7), -3.0,
                           gx1, ys * (GUIDE_W / 2), -0.01)

    # --- รูยึดกับดาดฟ้าหุ่น M4 4 มุม ---
    for mx in (-42.0, 42.0):
        for my in (-44.0, 44.0):
            bp = bp - cyl(2.1, P.BASE_T + 4, "Z", (mx, my, -2))
    return bp

# ============================================================
# 4. แคร่ yoke + slider (ชิ้นเดียว พิมพ์ทีเดียว)
# ============================================================
def make_carriage():
    slot_len = 2 * R_CRANK + BR_OD + 2.0            # ช่วงที่ลูกปืนต้องวิ่งได้
    plate_y  = slot_len + 12.0

    # แผ่น yoke (ใต้แผ่นฐาน) + ร่องรับลูกปืน 623ZZ
    c = box_from(-13, -plate_y / 2, Z_YOKE_B, 13, plate_y / 2, Z_YOKE_T)
    c = c - slot(slot_len, P.YOKE_SLOT_W, 20, (0, 0, Z_YOKE_B + 1), axis="Z")

    # ปีกล่างที่สอดใต้ปีกรางของแผ่นฐาน (กันแคร่ยกตัว)
    c = c + box_from(-POST_LEN / 2, -(GUIDE_W / 2 + 6.5), -3.0,
                     POST_LEN / 2, GUIDE_W / 2 + 6.5, Z_YOKE_T)

    # เสาลอดร่องแผ่นฐานขึ้นมา
    Z_BEAM = P.BASE_T + 1.0        # ใต้คานขวางต้องสูงกว่าผิวบนแผ่นฐาน 1 mm
    c = c + box_from(-POST_LEN / 2, -POST_W / 2, -3.0, POST_LEN / 2, POST_W / 2, Z_BEAM)

    # คานขวางรับหมุด B0 ที่ y = ±31 (ครีบคร่อมชุดแขนทั้งสองระนาบ)
    # รัศมีหัวคาน 5 mm (ไม่ใช่ 8) — 8 mm จะจมลงไปชนแผ่นฐานตอนเลื่อน
    # (ตรวจพบด้วย scissor_verify.py ข้อ 7: ชนกัน 757 mm³)
    c = c + box_from(-9, -(Y_FIN + FIN_T / 2), Z_BEAM, 9, Y_FIN + FIN_T / 2, Z_PIN + 8.0)
    c = c + cyl(5.0, 2 * (Y_FIN + FIN_T / 2), "Y", (0, -(Y_FIN + FIN_T / 2), Z_PIN))
    # เซาะร่องให้ชุดแขน scissor สอดเข้าไปได้
    for ys in (-Y_PLANE, Y_PLANE):
        c = c - box_from(-20, ys + Y_A - 0.5, Z_PIN - 4.0,
                         20, ys + Y_B + TL + 0.5, Z_PIN + 10.0)
    # รูหมุด B0
    c = c - cyl(PIN_D / 2.0, 120, "Y", (0, -60, Z_PIN))
    return c

# ============================================================
# 5. แขน crank (ประกบฮอร์นเซอร์โว)
# ============================================================
def make_crank():
    t = Z_CRK_T - Z_CRK_B
    c = box(R_CRANK, 15.0, t, (R_CRANK / 2.0, 0, Z_CRK_B + t / 2))
    c = c + cyl(10.0, t, "Z", (0, 0, Z_CRK_B))
    c = c + cyl(8.0, t, "Z", (R_CRANK, 0, Z_CRK_B))
    # โพรงฝังฮอร์นพลาสติกเดิมของเซอร์โว + รูสกรูยึด 4 ตัว
    c = c - cyl(9.0, 2.6, "Z", (0, 0, Z_CRK_B - 0.01))
    c = c - cyl(3.2, t + 2, "Z", (0, 0, Z_CRK_B - 1))
    for a in (0, 90, 180, 270):
        c = c - cyl(1.1, t + 2, "Z", (6.5 * math.cos(math.radians(a)),
                                      6.5 * math.sin(math.radians(a)), Z_CRK_B - 1))
    # เพลาหมุด Ø3 รับลูกปืน 623ZZ ยื่นขึ้นไปในร่อง yoke
    c = c + cyl(PIN_D / 2.0 - 0.1, 12.0, "Z", (R_CRANK, 0, Z_CRK_T - 0.01))
    return c

def make_bearing():
    """623ZZ 3x10x4 — ใส่ไว้ในชุดประกอบเพื่อตรวจระยะ (ไม่ต้องพิมพ์)"""
    b = cyl(BR_OD / 2.0, P.BEARING_W, "Z", (0, 0, 0))
    return b - cyl(P.BEARING_ID / 2.0, P.BEARING_W + 2, "Z", (0, 0, -1))

# ============================================================
# 6. แพลตฟอร์มบน
# ============================================================
def make_platform():
    """หมุด A_n ยึดตายตัวกับแพลตฟอร์ม, หมุด B_n เลื่อนในร่อง
       → แพลตฟอร์มขึ้นตรงในแนวดิ่งเสมอ ไม่เอียง

       *** พิกัดในชิ้นนี้ใช้ระบบเดียวกับชุดประกอบ (x=0 คือกึ่งกลางฐานหุ่น) ***
       จึงวางลงชุดประกอบได้ด้วยการเลื่อนแกน Z อย่างเดียว — ไม่มีการเยื้องแกน X
       (บั๊กเดิม: เคยอ้างอิง -S_FOLD/2 ทำให้แพลตฟอร์มเยื้องไป 6 mm และล้นขอบฐาน)"""
    x_fix  = X_PIVOT                       # A_n อยู่ตรงกับจุดหมุนตายตัวเสมอ
    x_s_lo = X_PIVOT + S_UP                # B_n ตอนยกสุด
    x_s_hi = X_PIVOT + S_FOLD              # B_n ตอนพับสุด
    FH, FT = 10.0, 3.0                     # ความสูง/หนาครีบ (รับแค่ payload 0.6 N)

    pl = box_from(-P.PLAT_X / 2, -P.PLAT_Y / 2, 0, P.PLAT_X / 2, P.PLAT_Y / 2, P.PLAT_T)

    for yf in (-Y_FIN, -25.0, 25.0, Y_FIN):
        pl = pl + box_from(x_fix - 4, yf - FT / 2, -FH, x_fix + 10, yf + FT / 2, 0.01)
        pl = pl + box_from(x_s_lo - 9, yf - FT / 2, -FH, x_s_hi + 9, yf + FT / 2, 0.01)
    pl = pl - cyl(PIN_D / 2.0, 120, "Y", (x_fix, -60, -FH / 2))
    pl = pl - slot(x_s_hi - x_s_lo + PIN_D, PIN_D, 120,
                   ((x_s_lo + x_s_hi) / 2.0, 0, -FH / 2), axis="Y")

    # เจาะโปร่งลดน้ำหนัก — หลบแนวครีบ (y = ±25, ±37.5) และหลบรูยึดกล้องกลางแผ่น
    for xw in (-34.0, 34.0):
        pl = pl - box_from(xw - 11, -20, -1, xw + 11, 20, P.PLAT_T + 1)
    for yw in (-45.0, 45.0):
        pl = pl - box_from(-44, yw - 3, -1, 44, yw + 3, P.PLAT_T + 1)

    # --- รูยึดกล้อง: ต้องอยู่ "ระหว่างหมุดสองคอลัมน์ตอนยกสุด" เท่านั้น ---
    # ตอนยกสุด แพลตฟอร์มถูกรองรับที่หมุดสองจุด: x = x_fix และ x = x_s_lo
    # ถ้าวางกล้องนอกช่วงนี้ จะกลายเป็นคานยื่น → แพลตฟอร์มโยกและภาพสั่น
    # จึงย้ายชุดรูยึดไปไว้ "กึ่งกลางช่วงรองรับ" ไม่ใช่กึ่งกลางแผ่น
    x_cam = (x_fix + x_s_lo) / 2.0
    for cx in (x_cam - 15.0, x_cam + 15.0):
        for cy in (-15.0, 15.0):
            pl = pl - cyl(1.4, P.PLAT_T + 2, "Z", (cx, cy, -1))
    pl = pl - cyl(3.2, P.PLAT_T + 2, "Z", (x_cam, 0, -1))      # รูขาตั้ง 1/4"-20
    return pl

def make_servo_stub():
    """ทรงกล่องแทน MG996R (40.5 x 20 x 38 + ปีกยึด) ใช้ตรวจพื้นที่เท่านั้น"""
    s = box(40.5, 20.0, 38.0, (X_CRANK, 0, Z_CRK_B - 19.0))
    s = s + box(54.0, 20.0, 2.5, (X_CRANK, 0, Z_CRK_B - 10.0))
    return s

# ============================================================
# 7. ประกอบ
# ============================================================
def build_assembly(theta, include_servo=True):
    """คืน dict ชื่อชิ้น → Solid ที่วางตำแหน่งแล้ว"""
    parts = {}
    s = span(theta)
    parts["base"] = make_base()
    parts["carriage"] = make_carriage().translate((X_PIVOT + s, 0, 0))

    cosphi = max(-1.0, min(1.0, (X_PIVOT + s - X_CRANK) / R_CRANK))
    phi = math.degrees(math.acos(cosphi))
    parts["crank"] = make_crank().rotate("Z", phi).translate((X_CRANK, 0, 0))
    parts["bearing"] = make_bearing().translate(
        (X_CRANK + R_CRANK * math.cos(math.radians(phi)),
         R_CRANK * math.sin(math.radians(phi)), Z_YOKE_B + 1))

    i = 0
    for (pa, pb, dy) in scissor_links(theta):
        for yp in (-Y_PLANE, Y_PLANE):
            parts[f"link{i:02d}"] = place_link(pa, pb, yp + dy)
            i += 1

    A, _ = scissor_nodes(theta)
    parts["platform"] = make_platform().translate((0, 0, A[N][1] + 6.0))

    if include_servo:
        parts["servo"] = make_servo_stub()
    return parts, phi

def fuse(parts):
    it = iter(parts.values())
    tot = next(it)
    for p in it:
        tot = tot + p
    return tot

# ============================================================
# main
# ============================================================
if __name__ == "__main__":
    print(f"CAD backend = {sk.BACKEND}"
          f"{'  (ได้ทั้ง STEP + STL)' if sk.BACKEND=='cadquery' else '  (ได้ STL อย่างเดียว — ติดตั้ง cadquery เพื่อให้ได้ STEP)'}")
    os.makedirs(os.path.join(HERE, "step"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)

    qty = {"01_base_plate": 1, "02_link": N * 2 * 2, "03_yoke_carriage": 1,
           "04_crank_arm": 1, "05_top_platform": 1}
    parts = {
        "01_base_plate":    make_base(),
        "02_link":          make_link(),
        "03_yoke_carriage": make_carriage(),
        "04_crank_arm":     make_crank(),
        "05_top_platform":  make_platform(),
    }
    print(f"\n{'ชิ้นส่วน':<20}{'จำนวน':>6}{'ปริมาตร cm³':>14}{'มวล PETG g':>13}")
    print("-" * 55)
    m_tot = 0.0
    for name, s in parts.items():
        v = s.volume()
        m = v * P.RHO_PETG * qty[name]
        m_tot += m
        if sk.BACKEND == "cadquery":
            sk.export(s, os.path.join(HERE, "step", name))     # ได้ทั้ง .step และ .stl
        sk.export(s, os.path.join(HERE, "stl", name), step=False)
        print(f"{name:<20}{qty[name]:>6}{v/1000:>14.2f}{m:>13.1f}")
    print("-" * 55)
    print(f"{'รวมชิ้นพิมพ์':<20}{'':<6}{'':<14}{m_tot:>13.1f}")

    for tag, th in [("folded", TH_MIN), ("extended", TH_MAX)]:
        asm, phi = build_assembly(th)
        whole = fuse(asm)
        sk.export(whole, os.path.join(HERE, "stl", f"assembly_{tag}"), step=False)
        if sk.BACKEND == "cadquery":
            sk.export(whole, os.path.join(HERE, "step", f"assembly_{tag}"))
        x0, y0, z0, x1, y1, z1 = whole.bbox()
        print(f"\nassembly_{tag}  (θ={math.degrees(th):.1f}°, crank φ={phi:.0f}°)")
        print(f"   X {x0:7.1f} … {x1:6.1f}  = {x1-x0:6.1f} mm")
        print(f"   Y {y0:7.1f} … {y1:6.1f}  = {y1-y0:6.1f} mm")
        print(f"   Z {z0:7.1f} … {z1:6.1f}  = {z1-z0:6.1f} mm")
    print("\nเสร็จ → โฟลเดอร์ step/ และ stl/")
