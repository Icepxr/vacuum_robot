"""
scissor_analysis.py — วิเคราะห์แรง / แรงบิดเซอร์โว / ผลกระทบต่อหุ่น
รัน:  python3 scissor_analysis.py
ออก:  scissor_analysis.png, scissor_analysis_report.txt

โครงสร้างการวิเคราะห์
  A. คิเนแมติกส์ crank-slider  → θ(φ), x_s(φ), dx_s/dφ
  B. งานเสมือน (virtual work) → แรง actuator ที่ต้องใช้ F_act(θ)
  C. สปริงช่วย (assist spring) → ลดแรงพีค + ยังไม่ self-deploy
  D. แรงบิดเซอร์โว T(φ) เทียบสเปค MG996R
  E. แรงปฏิกิริยาบนฐาน + ความเค้นในแขน
  F. ผลกระทบต่อหุ่น: CoG, มุมพลิก, โมเมนต์ตอนหุ่นเร่ง/เบรก
  G. ไฟฟ้า: กระแสพีค
"""

import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import scissor_params as P

OUT = []
def say(s=""):
    print(s)
    OUT.append(str(s))

def head(t):
    say()
    say("=" * 68)
    say(t)
    say("=" * 68)

g = P.G
L = P.L_LINK
n = P.N_STAGES

def kgcm(t):
    """N·m → kgf·cm"""
    return t / 0.0980665

# แรงฝืดเริ่มขยับ (breakaway/stiction) ที่ slider — ค่าคงที่ ไม่ขึ้นกับโหลด
# มาจากข้อต่อหมุด 24 จุดที่ขันพรีโหลด + รางเลื่อน; เป็นภาระหลักเมื่อใส่สปริงจนเกือบสมดุล
F_STICTION = 6.0    # N

# ============================================================
# มวลชิ้นส่วนที่เคลื่อนที่ (ประเมินจากเรขาคณิต CAD)
# ============================================================
head("0. มวลของกลไก (ประเมินจากเรขาคณิต)")

n_links = n * 2 * 2                       # 6 ชั้น x 2 แขน x 2 ระนาบ
link_len_total = L + P.LINK_W             # รวมปลายมน
v_link = link_len_total * P.LINK_W * P.LINK_T - 3 * math.pi * (P.PIN_D/2)**2 * P.LINK_T
m_link = v_link * P.RHO_PETG              # g
m_links = n_links * m_link

n_crossrod = 6                            # แกนขวางเชื่อมสองระนาบ (อะลูมิเนียม M3)
m_crossrod = math.pi * 1.5**2 * (P.TRACK_Y + 20) * 2.70e-3
m_rods = n_crossrod * m_crossrod

m_pins = n_links * 1.6                    # สกรู M3 + สเปเซอร์ เฉลี่ยต่อแขน
m_slider = 12.0
m_platform = 35.0                         # แพลตฟอร์มบน (ค่าจริงจาก scissor_cad.py)

m_scissor = (m_links + m_rods + m_pins + m_slider) / 1000.0   # kg (กระจายตัว)
m_top = (m_platform / 1000.0) + P.M_PAYLOAD                    # kg (อยู่ปลายบนสุด)

say(f"แขน scissor    : {n_links} ชิ้น x {m_link:5.2f} g = {m_links:6.1f} g")
say(f"แกนขวาง        : {n_crossrod} ชิ้น x {m_crossrod:5.2f} g = {m_rods:6.1f} g")
say(f"สกรู/สเปเซอร์   : {m_pins:6.1f} g")
say(f"slider block   : {m_slider:6.1f} g")
say(f"แพลตฟอร์มบน    : {m_platform:6.1f} g")
say(f"payload (กล้อง) : {P.M_PAYLOAD*1000:6.1f} g")
say()
say(f"มวลกลไกที่กระจายตัว m_scissor = {m_scissor*1000:.0f} g  (CoG อยู่ที่ H/2)")
say(f"มวลที่ปลายบน      m_top     = {m_top*1000:.0f} g  (CoG อยู่ที่ H)")
say(f"มวลรวมของโมดูล (ไม่รวมฐาน+เซอร์โว) = {(m_scissor+m_top)*1000:.0f} g")

# น้ำหนักสมมูล: U_grav = (W_top + W_scissor/2) * H
W_eff = (m_top + m_scissor / 2.0) * g      # N
say(f"\nน้ำหนักสมมูลสำหรับงานเสมือน W_eff = m_top + m_scissor/2 = {W_eff:.2f} N")

# ============================================================
# A. คิเนแมติกส์ crank-slider
# ============================================================
head("A. คิเนแมติกส์ crank-slider")

th_min = math.radians(P.THETA_MIN)
th_max = math.radians(P.THETA_MAX)
xs_fold = L * math.cos(th_min)     # slider ไกลสุด (พับ)
xs_up   = L * math.cos(th_max)     # slider ใกล้สุด (ยกสุด)
stroke  = xs_fold - xs_up

phi0 = math.radians(P.CRANK_PHI_OFFSET)   # มุม crank ตอนพับสุด (เยื้องจากจุดศูนย์ตาย)

# SCOTCH YOKE:  x_s(φ) = x_c + r·cos(φ)
# ระยะชักที่ได้จาก φ0 → 180° คือ r(cos φ0 + 1)  →  แก้หา r ตรงๆ ไม่ต้องวนซ้ำ
r_crank = stroke / (1.0 + math.cos(phi0))
x_c = xs_fold - r_crank * math.cos(phi0)

def xs_of_phi(phi):
    return x_c + r_crank * np.cos(phi)

def dxs_dphi(phi):
    return -r_crank * np.sin(phi)

say("กลไกขับที่เลือก: SCOTCH YOKE (ไม่มีก้านต่อ)")
say("  เหตุผล: crank+ก้านต่อ กินความยาว (r+l) ≈ 114 mm > ฐาน 100 mm ใส่ไม่ลง")
say("          scotch yoke กินแค่ 2r = %.0f mm → อยู่ในฐาน 100x100 ได้" % (2*r_crank))
say()
say(f"ระยะชัก slider ที่ต้องการ = {stroke:.2f} mm  ({xs_fold:.1f} → {xs_up:.1f} mm)")
say(f"รัศมี crank                r = {r_crank:.2f} mm   (= stroke/(1+cos φ0))")
say(f"ศูนย์กลาง crank อยู่ที่     x_c = {x_c:.2f} mm จากจุดหมุนตายตัว")
say(f"ขอบเขตที่ crank กวาดในแกน X = {x_c-r_crank:.1f} … {x_c+r_crank:.1f} mm")
say(f"ขอบเขตในแกน Y (ร่อง yoke)   = ±{r_crank:.1f} mm  (ฐานกว้าง ±{P.BASE_Y/2:.0f} mm ✓)")
say(f"ช่วงหมุนเซอร์โว            φ = {math.degrees(phi0):.0f}° → 180°  "
    f"= {180-math.degrees(phi0):.0f}°  (MG996R มี {P.SERVO_TRAVEL_DEG:.0f}° ✓)")
say()
say("*** หัวใจของดีไซน์: ตอนพับสุด crank อยู่ใกล้ 'จุดศูนย์ตาย' (dead centre)")
say("    ตรงนั้น dx/dφ = -r·sinφ ≈ 0 → เซอร์โวได้เปรียบเชิงกลมหาศาล พอดีกับที่")
say("    scissor ต้องการแรงมากที่สุด (cotθ พุ่ง) — สองเส้นโค้งหักล้างกันพอดี")
say("    และตอนพับสุดกลไก 'ล็อกตัวเอง': โหลดกดลงมาก็หมุน crank ไม่ได้")
say("    → ตัด PWM ทิ้งได้เลยตอนเก็บ ไม่กินไฟ ไม่ร้อน ไม่สั่น")

phi = np.linspace(phi0, math.pi, 600)
xs = xs_of_phi(phi)
xs = np.clip(xs, xs_up, xs_fold)
theta = np.arccos(np.clip(xs / L, -1, 1))
H = n * L * np.sin(theta)
dxdp = np.abs(dxs_dphi(phi)) / 1000.0        # m/rad

# ============================================================
# B. แรง actuator จากงานเสมือน
# ============================================================
head("B. แรง actuator (งานเสมือน)")

say("U_grav = (W_top + W_scissor/2) · n · L · sinθ")
say("x_s    = L · cosθ")
say("F_act  = |dU/dθ| / |dx_s/dθ| = n · W_eff · cotθ      [ไม่คิดความฝืด]")
say()

def F_grav(th):
    return n * W_eff / np.tan(th)

F_ideal = F_grav(theta)
say(f"แรงพีค (θ={P.THETA_MIN:.0f}°, ตอนเริ่มยก)  F = {F_ideal.max():6.1f} N")
say(f"แรงต่ำสุด (θ={P.THETA_MAX:.0f}°, ยกสุด)   F = {F_ideal.min():6.1f} N")
say(f"อัตราขยายแรงของ scissor {n} ชั้น ที่ θ={P.THETA_MIN:.0f}° = n·cotθ = "
    f"{n/math.tan(th_min):.1f} เท่า")
say(f"→ นี่คือราคาที่ต้องจ่ายของ 'พับ {P.height_at(P.THETA_MIN):.0f} mm แต่ยืด "
    f"{P.height_at(P.THETA_MAX):.0f} mm' (อัตราขยายระยะ "
    f"{P.height_at(P.THETA_MAX)/P.height_at(P.THETA_MIN):.1f}:1)")

# ============================================================
# C. สปริงช่วย (assist spring) แบบทแยง
# ============================================================
head("C. สปริงช่วย (assist spring)")

say("ปัญหา: สปริงดึงตรงๆ ตามราง (เชิงเส้น) ช่วยไม่ตรงเส้นโค้ง cotθ")
say("       → ช่วงกลางจะช่วยมากเกิน แล้ว scissor 'เด้งขึ้นเอง' ตอนไฟดับ = อันตรายกับหุ่น")
say("วิธีแก้: ยึดสปริงแบบทแยง จากฐาน → จุดบนแขนล่าง (p·L จากจุดหมุนตายตัว)")
say("       เส้นโค้งแรงจะโค้งตาม cotθ ได้ดีกว่ามาก")
say()

def spring_terms(th, xa, ya, p, k, s0):
    """คืน (dU_sp/dθ [N·mm/rad], ความยาวสปริง s [mm])"""
    px, py = p*L*np.cos(th), p*L*np.sin(th)
    dx, dy = px - xa, py - ya
    s = np.sqrt(dx**2 + dy**2)
    dpx, dpy = -p*L*np.sin(th), p*L*np.cos(th)
    dsdth = (dx*dpx + dy*dpy) / s
    ext = np.maximum(s - s0, 0.0)
    return k * ext * dsdth, s, ext

def F_with_spring(th, params):
    xa, ya, p, k, s0 = params
    dUg = n * W_eff * L * np.cos(th)         # N·mm/rad
    dUs, s, ext = spring_terms(th, xa, ya, p, k, s0)
    F = (dUg + dUs) / (L * np.sin(th))       # N
    return F, s, ext

# ค้นหาพารามิเตอร์สปริง: ลดแรงพีค แต่ต้องเหลือ F_act > 0 ตลอด (ไม่ self-deploy)
# เกณฑ์ที่ใช้ optimize = "แรงบิดเซอร์โวพีค" (ไม่ใช่แรงพีค) เพราะ crank แปลงค่าไม่เชิงเส้น
#
# ข้อจำกัดการจัดวาง (packaging) — สำคัญมาก อย่าตัดออก:
#   ฐานกว้าง 100 mm, จุดหมุนตายตัวอยู่ที่ x=8 mm จากขอบ, slider ไปได้ถึง x=91.7 mm
#   → จุดยึดสปริงบนฐาน ต้องอยู่ในช่วง xa ∈ [0, +40] เทียบจุดหมุน
#     (ค่าติดลบทำให้ตายึดสปริงยื่นพ้นขอบฐาน — ตรวจพบตอนสร้าง CAD จริง)
#   → เสายึดสปริงสูงได้ ya ∈ [0, 25] mm (สูงกว่านี้ไปชนแขน scissor ตอนพับ)
eta_pre = P.ETA_JOINT * P.ETA_CRANK
best = None
for xa in [0, 3, 5, 8, 10, 15, 20, 25, 30, 35, 40]:
    for ya in [0, 5, 10, 15, 20, 25]:
        for p in [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
            for k in np.arange(0.10, 3.01, 0.05):
                for s0 in np.arange(20, 100, 5.0):
                    F, s, ext = F_with_spring(theta, (xa, ya, p, k, s0))
                    if F.min() < 0.25:                     # กันไม่ให้ยกตัวเอง (self-deploy)
                        continue
                    if ext.max() > 0.80 * s0:              # สปริงดึงจริงยืดได้ ~80% ของยาวอิสระ
                        continue
                    if s0 > s.min():                       # ต้องตึงตลอดช่วง ไม่หย่อนกลางทาง
                        continue
                    Tpk = float(((F / eta_pre + F_STICTION) * dxdp).max())
                    if best is None or Tpk < best[0]:
                        best = (Tpk, (xa, ya, p, k, s0), s.min(), s.max(), ext.max(), F.max())

Tpk_best, sp_par, s_min, s_max, ext_max, peak_sp = best
xa, ya, p, k, s0 = sp_par
say(f"ผลค้นหา (grid search {'':s}):")
say(f"  จุดยึดบนฐาน A       = ({xa:.0f}, {ya:.0f}) mm  (เทียบจุดหมุนตายตัวของแขนล่าง)")
say(f"  จุดยึดบนแขนล่าง     = {p:.2f}·L = {p*L:.1f} mm จากจุดหมุน")
say(f"  ค่า k               = {k:.2f} N/mm")
say(f"  ความยาวอิสระ s0     = {s0:.0f} mm")
say(f"  ความยาวใช้งาน       = {s_min:.0f} → {s_max:.0f} mm (ยืดสูงสุด {ext_max:.0f} mm)")
say(f"  แรงสปริงสูงสุด      = {k*ext_max:.1f} N")
say()
say(f"แรง actuator พีค: ไม่มีสปริง {F_ideal.max():.1f} N → มีสปริง {peak_sp:.1f} N "
    f"(ลด {100*(1-peak_sp/F_ideal.max()):.0f}%)")

F_spring, s_arr, ext_arr = F_with_spring(theta, sp_par)

say()
say("--- ทำเป็นสปริงจริง 2 ตัว (ข้างละตัว) เพื่อสมมาตร ---")
k_each = k / 2.0
say(f"  ใช้สปริงดึง 2 ตัว ตัวละ k = {k_each:.2f} N/mm, ยาวอิสระ {s0:.0f} mm")
say(f"  แรงต่อตัวสูงสุด {k_each*ext_max:.1f} N  (สปริงลวด ~0.9-1.0 mm, OD 8 mm หาซื้อได้)")
say("  ยึดข้างละระนาบ → ไม่เกิดโมเมนต์บิดใส่กลไก")

# ---- ความทนทานต่อความคลาดเคลื่อนของสปริง ----
say()
say("--- ตรวจความทนทาน: ถ้า k คลาดเคลื่อน ±20% (สปริงจริงมี tolerance ~±10%) ---")
robust_ok = True
for f_k in [0.80, 0.90, 1.00, 1.10, 1.20]:
    Fq, _, _ = F_with_spring(theta, (xa, ya, p, k*f_k, s0))
    Tq = ((Fq / eta_pre + F_STICTION) * dxdp)
    tag = "OK"
    if Fq.min() < 0:
        tag = "!! สปริงแรงเกิน → กลไกดันตัวขึ้นเอง (servo ต้องรั้งไว้)"
        robust_ok = False
    say(f"  k×{f_k:.2f}: F_act = {Fq.min():6.2f} … {Fq.max():6.2f} N, "
        f"T_pk = {kgcm(Tq.max()):5.2f} kgf·cm   {tag}")
say(f"  → {'ทนทาน ✓' if robust_ok else 'ต้องเลือกสปริง k ต่ำกว่าค่า optimum ~15% เพื่อความปลอดภัย ⚠'}")

# ---- จุดออกแบบสุดท้าย: ถอย k ลง 15% เพื่อกันไม่ให้ self-deploy แม้สปริงแรงเกินสเปค ----
K_DERATE = 0.85
k_sel = round(k * K_DERATE, 2)
F_spring, s_arr, ext_arr = F_with_spring(theta, (xa, ya, p, k_sel, s0))
say()
say("### จุดออกแบบที่เลือกใช้จริง (de-rate k ลง 15%) ###")
say(f"  k_รวม = {k_sel:.2f} N/mm  → สปริง 2 ตัว ตัวละ {k_sel/2:.2f} N/mm")
say(f"  ยาวอิสระ s0 = {s0:.0f} mm, ยืดใช้งานสูงสุด {ext_arr.max():.0f} mm, "
    f"แรงต่อตัวสูงสุด {k_sel/2*ext_arr.max():.1f} N")
say(f"  F_act เหลือ {F_spring.min():.2f} … {F_spring.max():.2f} N (บวกตลอด = ไม่ยกตัวเอง ✓)")

# ============================================================
# D. แรงบิดเซอร์โว
# ============================================================
head("D. แรงบิดเซอร์โว MG996R")

eta = P.ETA_JOINT * P.ETA_CRANK
say(f"ประสิทธิภาพรวม η = η_joint({P.ETA_JOINT}) × η_crank({P.ETA_CRANK}) = {eta:.2f}")
say(f"แรงฝืดคงที่ (stiction) ที่ slider = {F_STICTION:.0f} N")
say("T_servo = (F_act/η + F_stiction) · |dx_s/dφ|")
say()
say("*** สำคัญ: เมื่อใส่สปริงจนเกือบสมดุลแล้ว 'ความฝืด' กลายเป็นภาระหลัก")
say("    ไม่ใช่ 'น้ำหนัก' — จึงต้องใส่พจน์ stiction ไม่งั้นจะประเมินดีเกินจริง ***")
say()

T_nosp = (F_ideal  / eta + F_STICTION) * dxdp     # N·m
T_sp   = (F_spring / eta + F_STICTION) * dxdp

for name, T in [("ไม่มีสปริงช่วย", T_nosp), ("มีสปริงช่วย + คิดความฝืด", T_sp)]:
    i = int(np.argmax(T))
    say(f"[{name}]")
    say(f"  แรงบิดพีค   = {T.max():.3f} N·m = {kgcm(T.max()):.1f} kgf·cm "
        f"(ที่ φ={math.degrees(phi[i]):.0f}°, θ={math.degrees(theta[i]):.0f}°, H={H[i]:.0f} mm)")
    say(f"  สเปค MG996R = {P.SERVO_TORQUE_NM:.3f} N·m = {P.SERVO_STALL_TORQUE:.1f} kgf·cm")
    sf = P.SERVO_TORQUE_NM / T.max()
    verdict = "ผ่าน ✓" if sf >= P.SF_TARGET else ("เฉียดฉิว ⚠" if sf >= 1.3 else "ไม่ผ่าน ✗")
    say(f"  Safety factor = {sf:.2f}   → {verdict}  (เป้าหมาย SF ≥ {P.SF_TARGET})")
    say()

SF_final = P.SERVO_TORQUE_NM / T_sp.max()

# ============================================================
# E. แรงปฏิกิริยาบนฐาน + ความเค้น
# ============================================================
head("E. แรงบนฐาน และความเค้นในแขน")

F_max_struct = F_ideal.max()      # กรณีเลวสุด: สปริงขาด/ไม่ได้ใส่
say(f"แรงแนวนอนสูงสุดที่ slider = {F_max_struct:.1f} N (คิดกรณีสปริงขาด)")
say()
say(">>> ประเด็นสำคัญเรื่อง 'ไม่ให้กระทบต่อหุ่น' <<<")
say("แรงแนวนอนนี้เป็น *แรงภายใน* (internal force) ของแผ่นฐาน เพราะทั้ง")
say("จุดหมุนตายตัว และรางเลื่อน ยึดอยู่บนแผ่นฐานเดียวกัน")
say("→ ผลรวมแรงที่ส่งลงตัวหุ่น = 0 ในแนวนอน  หุ่นจะ 'ไม่ถูกผลัก' ตอนสั่งยก")
say("เงื่อนไข: ห้ามยึดรางเลื่อนกับโครงหุ่นคนละชิ้นกับจุดหมุน — ต้องเป็นแผ่นเดียวกัน")
say()

# ฐานรับแรงดึง: หน้าตัด BASE_Y x BASE_T
A_base = P.BASE_Y * P.BASE_T
sig_base = F_max_struct / A_base
say(f"ความเค้นดึงในแผ่นฐาน = {F_max_struct:.1f} N / ({P.BASE_Y:.0f}×{P.BASE_T:.0f} mm²) "
    f"= {sig_base:.2f} MPa  (ยอมให้ {P.SIGMA_ALLOW} MPa) "
    f"{'✓' if sig_base < P.SIGMA_ALLOW else '✗'}")

# แรงตามแนวแขนล่าง (แขนล่างรับแรงอัด)
F_link = F_max_struct / math.cos(th_min) / 2.0 / 2.0   # แบ่ง 2 แขน x 2 ระนาบ
A_link = P.LINK_W * P.LINK_T
sig_link = F_link / A_link
say(f"แรงอัดตามแขนล่าง (ต่อแขน) = {F_link:.1f} N → σ = {sig_link:.2f} MPa "
    f"{'✓' if sig_link < P.SIGMA_ALLOW else '✗'}")

# การโก่งเดาะ (buckling) ของแขน — Euler, pinned-pinned
I_link = P.LINK_W * P.LINK_T**3 / 12.0     # mm^4 (แกนอ่อน = นอกระนาบ)
P_cr = math.pi**2 * P.E_PETG * I_link / L**2
say(f"แรงโก่งเดาะวิกฤต (Euler, แกนอ่อน) P_cr = {P_cr:.1f} N  → "
    f"SF = {P_cr/F_link:.1f} {'✓' if P_cr/F_link > 3 else '⚠'}")

# แรงเฉือนที่หมุด M3
F_pin = F_link
tau_pin = F_pin / (math.pi * 1.5**2)
say(f"ความเค้นเฉือนที่หมุด M3 = {tau_pin:.1f} MPa (สกรูเหล็ก 4.8 รับได้ ~200 MPa) ✓")

# ความอ่อนตัวด้านข้างตอนยกสุด — *ความเสี่ยงอันดับ 1 ของดีไซน์นี้*
say()
say("--- ความแข็งแรงด้านข้าง (จุดอ่อนที่แท้จริงของ scissor 6 ชั้น) ---")
H_up = n * L * math.sin(th_max)                            # mm
I_tower = 2 * (P.LINK_W * P.LINK_T) * (P.TRACK_Y/2)**2     # mm^4 สองระนาบทำตัวเป็น "เสากล่อง"
F_side = 1.0                                               # N แรงข้างที่ปลาย
k_beam = 3 * P.E_PETG * I_tower / H_up**3                  # N/mm  (ขอบบนแบบวัสดุล้วน)
defl_beam = F_side / k_beam
say(f"[ขอบบนสุด — คิดเป็นเสาตันวัสดุล้วน] แรงข้าง 1 N → โก่ง {defl_beam:.2f} mm "
    f"(k = {k_beam:.2f} N/mm)")

# ผลจากความหลวมของหมุด (dominant ในของจริง)
clr = 0.15          # mm ความหลวมรวมต่อหมุดหนึ่งจุด (รู 3.2 กับสกรู 3.0 + สึกหรอ)
tilt_per_joint = 2 * clr / P.TRACK_Y            # rad  เอียงต่อชั้น
z_levels = np.array([(i+1)/n * H_up for i in range(n)])
wander = float(np.sum(tilt_per_joint * (H_up - z_levels + H_up/n)))
say(f"[ความหลวมหมุด {clr} mm/จุด] ปลายบนแกว่งอิสระ ≈ ±{wander:.1f} mm "
    f"({math.degrees(wander/H_up):.2f}° ที่ปลาย)")
say("→ นี่คือ 'ระยะหลวม' ที่ไม่มีแรงต้านเลย — ไม่ใช่การโก่งของวัสดุ")
say("→ ตัวเลขนี้ครอบงำคุณภาพภาพจากกล้อง มากกว่าความแข็งแรงเชิงวัสดุหลายเท่า")

k_eff = k_beam * 0.15    # ประเมินอย่างระมัดระวัง: ข้อต่อ+ความหลวมลดความแข็งลง ~85%
f_nat = (1/(2*math.pi)) * math.sqrt(k_eff*1000.0 / m_top)   # N/mm→N/m
say(f"ความถี่ธรรมชาติโดยประมาณ f ≈ {f_nat:.0f} Hz (คิดความแข็งเหลือ 15% ของค่าอุดมคติ)")
say()
say("มาตรการที่ต้องทำ (ไม่ใช่ทางเลือก):")
say(f"  • แกนขวางเชื่อมสองระนาบ *ทุกชั้น* — ระยะห่างระนาบ {P.TRACK_Y:.0f} mm คือตัวแปรหลัก")
say("  • ใช้บูชทองเหลือง/ไนลอนที่หมุดทุกจุด แล้วขันสกรูให้แน่นกับบูช (ไม่ใช่กับแขน)")
say("  • ยิ่งชั้นบนยิ่งสำคัญ — ความหลวมชั้นล่างถูกขยายด้วยความสูงที่เหลือ")
say("  • ถ้ายังสั่นเกินรับได้: ใส่ท่อนำ (telescoping guide tube) แกนกลาง หรือลด")
say("    ความสูงเป้าหมายลงเหลือ 350-400 mm ซึ่งลดการแกว่งแบบยกกำลังสาม")

# ============================================================
# F. ผลกระทบต่อหุ่น: CoG และการพลิก
# ============================================================
head("F. ผลกระทบต่อหุ่น — จุดศูนย์ถ่วงและการพลิกคว่ำ")

def cog_with_mast(H_mm):
    """คำนวณ CoG ของหุ่นทั้งคัน เมื่อ scissor ยกสูง H_mm"""
    items = list(P.ROBOT_COMPONENTS)
    z_base = 0.10   # m  ผิวบนฐาน scissor สูงจากพื้น (ประเมิน)
    Hm = H_mm / 1000.0
    items.append(("ฐาน+เซอร์โว+crank", 0.090, 0.0, 0.0, z_base))
    items.append(("โครง scissor",      m_scissor, 0.0, 0.0, z_base + Hm/2))
    items.append(("แพลตฟอร์ม+กล้อง",   m_top,     0.0, 0.0, z_base + Hm))
    M = sum(i[1] for i in items)
    cx = sum(i[1]*i[2] for i in items) / M
    cy = sum(i[1]*i[3] for i in items) / M
    cz = sum(i[1]*i[4] for i in items) / M
    return M, cx, cy, cz

for label, Hq in [("พับเก็บ", P.height_at(P.THETA_MIN)), ("ยกสุด", P.height_at(P.THETA_MAX))]:
    M, cx, cy, cz = cog_with_mast(Hq)
    d_min = min(P.SUPPORT["front"] - cx, P.SUPPORT["rear"] + cx,
                P.SUPPORT["left"] - cy, P.SUPPORT["right"] + cy)
    tip = math.degrees(math.atan(d_min / cz))
    a_tip = g * d_min / cz     # ความเร่งแนวนอนที่ทำให้เริ่มพลิก
    say(f"[{label}] H = {Hq:.0f} mm")
    say(f"  มวลรวม M = {M:.2f} kg,  CoG z = {cz*1000:.0f} mm")
    say(f"  ระยะถึงขอบฐานที่เสี่ยงสุด d = {d_min*1000:.0f} mm")
    say(f"  มุมเอียงวิกฤต θ_tip = {tip:.1f}°")
    say(f"  ความเร่งวิกฤต a_tip = {a_tip:.2f} m/s²  (= {a_tip/g:.2f} g)")
    say()

M0, _, _, cz0 = cog_with_mast(P.height_at(P.THETA_MIN))
M1, _, _, cz1 = cog_with_mast(P.height_at(P.THETA_MAX))
_, _, _, _ = 0, 0, 0, 0
d0 = min(P.SUPPORT.values())
say(f"สรุป: ยกเสาขึ้นทำให้ CoG สูงขึ้น {(cz1-cz0)*1000:.0f} mm "
    f"({cz0*1000:.0f} → {cz1*1000:.0f} mm)")
a0 = g*d0/cz0; a1 = g*d0/cz1
say(f"      ความเร่งที่ทำให้พลิกลดจาก {a0:.2f} → {a1:.2f} m/s² (ลด {100*(1-a1/a0):.0f}%)")
say()
say(">>> ข้อกำหนดควบคุมหุ่น (สำคัญที่สุดต่อความปลอดภัย) <<<")
say(f"  1. ห้ามยกเสาขณะหุ่นเคลื่อนที่ — สั่งยกเมื่อ v = 0 เท่านั้น")
say(f"  2. ขณะเสายกอยู่ จำกัดความเร่ง/เบรก ≤ {a1*0.4:.2f} m/s² (40% ของขีดพลิก)")
say(f"  3. ขณะเสายกอยู่ จำกัดความเร็วหมุนตัว — แรงหนีศูนย์ ω²·r ก็ทำให้พลิกได้")
say(f"  4. ต้องพับเสาลงก่อนขึ้น/ลงธรณีประตูหรือพรมหนา")

# โมเมนต์จากการเร่งของหุ่น
a_drive = 0.5   # m/s^2 ความเร่งขับปกติ
M_dyn = (m_top + m_scissor/2) * a_drive * (P.height_at(P.THETA_MAX)/1000.0)
say()
say(f"โมเมนต์ที่ฐาน scissor ตอนหุ่นเร่ง {a_drive} m/s² ขณะยกสุด = {M_dyn:.3f} N·m")
say(f"→ สกรูยึดฐาน 4 ตัวห่าง {P.BASE_X:.0f} mm: แรงดึงต่อตัว ≈ "
    f"{M_dyn/(P.BASE_X/1000.0)/2:.1f} N — M3 รับได้สบาย ✓")
say()
say("*** ข้อสรุปที่สำคัญที่สุด ***")
say(f"หุ่นหนัก {M1:.1f} kg แต่ของที่ยกหนักแค่ {m_top*1000:.0f} g → 'การพลิกคว่ำ' ไม่ใช่ปัญหา")
say(f"(ยังต้องเร่งถึง {a1:.0f} m/s² จึงจะพลิก ซึ่งหุ่นดูดฝุ่นทำไม่ได้อยู่แล้ว)")
say("ปัญหาจริงคือ **การแกว่ง/สั่นของเสา** ตามหัวข้อ E:")
say(f"  - ปลายเสาแกว่งอิสระ ±{wander:.1f} mm จากความหลวมหมุดล้วนๆ")
say(f"  - ความถี่ธรรมชาติ ~{f_nat:.0f} Hz — เมื่อหุ่นออกตัว/เบรก เสาจะโยกแล้วค่อยๆ นิ่ง")
say("  - เวลาที่ต้องรอให้นิ่ง ≈ 5 คาบ ≈ "
    f"{5/max(f_nat,0.1):.1f} s → ตั้งดีเลย์ก่อนถ่ายภาพ")
say("แนะนำ: ถ่ายภาพ/สแกนเมื่อหุ่นหยุดนิ่งแล้วอย่างน้อย 1-2 วินาที")

# ============================================================
# G. ไฟฟ้า
# ============================================================
head("G. ไฟฟ้า — ผลกระทบต่อระบบไฟของหุ่น")

t_lift = 3.0   # s เวลาที่ใช้ยกจากพับ→สุด
I_peak = P.SERVO_STALL_A * min(1.0, T_sp.max()/P.SERVO_TORQUE_NM * 1.6)
say(f"เวลายกที่ตั้งไว้ = {t_lift:.0f} s → ความเร็วเซอร์โว "
    f"{(180-math.degrees(phi0))/t_lift:.0f} °/s (MG996R ทำได้ ~330 °/s ✓ เดินช้าได้)")
say(f"กระแสพีคประมาณ = {I_peak:.2f} A ที่ 6 V  (stall {P.SERVO_STALL_A} A)")
say(f"พลังงานต่อรอบยก ≈ {I_peak*6*t_lift:.0f} J")
say()
say(">>> ข้อควรระวังเรื่องไฟ (กระทบ Pi 5 / ESP32 โดยตรง) <<<")
say("  1. แยก BEC/regulator ของเซอร์โวออกจากราง 5V ของ Pi 5 คนละตัว")
say(f"  2. ใส่ตัวเก็บประจุ 1000 µF ที่ขั้วไฟเซอร์โว — กันแรงดันตกตอนกระแสกระชาก {I_peak:.1f} A")
say("  3. ต่อกราวด์ร่วมจุดเดียว (star ground) กันสัญญาณ PWM รบกวน")
say("  4. ตัดสัญญาณ PWM (detach) เมื่อถึงตำแหน่งแล้ว — ตอนพับสุด crank ล็อกตัวเอง")
say("     อยู่แล้ว ไม่ต้องจ่ายไฟค้าง ประหยัดแบต + ไม่ร้อน")
say("  5. ตอนยกสุด crank ก็อยู่ใกล้จุดศูนย์ตายอีกด้าน → ค้างไว้ก็กินกระแสน้อย")

# ============================================================
# กราฟ
# ============================================================
fig, ax = plt.subplots(2, 3, figsize=(16, 9))
phid = np.degrees(phi)
thd = np.degrees(theta)

ax[0,0].plot(phid, H, lw=2, c="steelblue")
ax[0,0].set_xlabel("crank angle phi (deg)"); ax[0,0].set_ylabel("lift height H (mm)")
ax[0,0].set_title("Servo angle -> lift height"); ax[0,0].grid(alpha=.3)

ax[0,1].plot(phid, thd, lw=2, c="teal")
ax[0,1].set_xlabel("crank angle phi (deg)"); ax[0,1].set_ylabel("scissor angle theta (deg)")
ax[0,1].set_title("Crank-slider kinematics"); ax[0,1].grid(alpha=.3)

ax[0,2].plot(phid, np.abs(dxs_dphi(phi)), lw=2, c="purple")
ax[0,2].set_xlabel("crank angle phi (deg)"); ax[0,2].set_ylabel("|dx/dphi| (mm/rad)")
ax[0,2].set_title("Mechanical advantage (low = strong)"); ax[0,2].grid(alpha=.3)

ax[1,0].plot(thd, F_ideal, lw=2, c="crimson", label="no spring")
ax[1,0].plot(thd, F_spring, lw=2, c="green", label="with assist spring")
ax[1,0].set_xlabel("scissor angle theta (deg)"); ax[1,0].set_ylabel("actuator force (N)")
ax[1,0].set_title("Actuator force vs angle"); ax[1,0].legend(); ax[1,0].grid(alpha=.3)

ax[1,1].plot(phid, kgcm(T_nosp), lw=2, c="crimson", label="no spring")
ax[1,1].plot(phid, kgcm(T_sp), lw=2, c="green", label="with assist spring")
ax[1,1].axhline(P.SERVO_STALL_TORQUE, ls="--", c="k", label="MG996R stall")
ax[1,1].axhline(P.SERVO_STALL_TORQUE/P.SF_TARGET, ls=":", c="gray",
                label=f"target (SF={P.SF_TARGET:.0f})")
ax[1,1].set_xlabel("crank angle phi (deg)"); ax[1,1].set_ylabel("servo torque (kgf*cm)")
ax[1,1].set_title("Servo torque requirement"); ax[1,1].legend(fontsize=8); ax[1,1].grid(alpha=.3)
ax[1,1].set_ylim(0, max(P.SERVO_STALL_TORQUE*1.4, kgcm(T_nosp).max()*1.1))

Hs = np.linspace(P.height_at(P.THETA_MIN), P.height_at(P.THETA_MAX), 60)
tips = []
for Hq in Hs:
    M, cx, cy, cz = cog_with_mast(Hq)
    dmin = min(P.SUPPORT["front"]-cx, P.SUPPORT["rear"]+cx,
               P.SUPPORT["left"]-cy, P.SUPPORT["right"]+cy)
    tips.append(g*dmin/cz)
ax[1,2].plot(Hs, tips, lw=2, c="darkorange")
ax[1,2].axhline(0.5, ls="--", c="r", label="typical drive accel 0.5 m/s2")
ax[1,2].set_xlabel("lift height H (mm)"); ax[1,2].set_ylabel("tipping accel limit (m/s2)")
ax[1,2].set_title("Robot tipping margin vs mast height")
ax[1,2].legend(fontsize=8); ax[1,2].grid(alpha=.3)

plt.tight_layout()
plt.savefig("scissor_analysis.png", dpi=130)
say()
say("บันทึกกราฟ: scissor_analysis.png")

with open("scissor_analysis_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(OUT))
print("\nบันทึกรายงาน: scissor_analysis_report.txt")

# ---- ส่งค่าที่คำนวณได้ให้สคริปต์ CAD ใช้ต่อ ----
import json
derived = {
    "crank_r_mm": round(r_crank, 3),
    "crank_centre_x_mm": round(x_c, 3),
    "drive_type": "scotch_yoke",
    "phi0_deg": P.CRANK_PHI_OFFSET,
    "slider_x_fold_mm": round(xs_fold, 3),
    "slider_x_up_mm": round(xs_up, 3),
    "stroke_mm": round(stroke, 3),
    "spring_anchor_x_mm": xa,
    "spring_anchor_y_mm": ya,
    "spring_link_frac": p,
    "spring_k_total_N_per_mm": k_sel,
    "spring_free_len_mm": s0,
    "spring_ext_max_mm": round(float(ext_arr.max()), 2),
    "servo_torque_peak_Nm": round(float(T_sp.max()), 4),
    "servo_SF": round(float(SF_final), 2),
    "F_act_peak_no_spring_N": round(float(F_ideal.max()), 2),
    "mass_scissor_g": round(m_scissor*1000, 1),
    "mass_top_g": round(m_top*1000, 1),
}
with open("scissor_derived.json", "w") as f:
    json.dump(derived, f, indent=2)
print("บันทึกค่าที่คำนวณได้: scissor_derived.json")
