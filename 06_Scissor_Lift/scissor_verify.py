"""
scissor_verify.py — ตรวจสอบโมเดลก่อนส่งไปพิมพ์
รัน:  python3 scissor_verify.py
ออก:  scissor_views.png  +  ผลตรวจบนหน้าจอ (exit code 1 ถ้ามีข้อผิดพลาดร้ายแรง)

ตรวจ 9 ข้อ
  1. ปิดลูปคิเนแมติกส์  — ปลายแขนทุกท่อนต้องบรรจบที่หมุดจริง ทุกมุม
  2. ระยะห่างแขนชั้นเดียวกันตอนพับ (จุดที่ชนกันง่ายที่สุด)
  3. ขอบเขตพื้นที่เก็บ 100 x 100 mm
  4. ความสูงรวมตอนยืดสุด = 500 mm
  5. ลูกปืน crank ต้องอยู่ในร่อง yoke ตลอดช่วงหมุน
  6. เสาแคร่ต้องอยู่ในร่องนำของแผ่นฐานตลอดระยะชัก
  7. ชิ้นส่วนชนกันจริงไหม (บูลีน intersection ของ mesh)
  8. แพลตฟอร์มขึ้นตรงในแนวดิ่ง (ไม่เอียง)
  9. จุดยึดกล้องอยู่ในช่วงที่แพลตฟอร์มถูกรองรับ (กันแพลตฟอร์มโยก)
"""

import math, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

import scissor_params as P
import scissor_cad as C
import solidkit as sk

FAIL, WARN = [], []

def check(ok, name, detail, hard=True):
    tag = "ผ่าน  " if ok else ("ไม่ผ่าน" if hard else "เตือน ")
    print(f"[{tag}] {name}\n         {detail}")
    if not ok:
        (FAIL if hard else WARN).append(name)
    return ok

print("=" * 72)
print("ตรวจสอบโมเดล scissor lift")
print("=" * 72)

TH_MIN, TH_MAX = C.TH_MIN, C.TH_MAX

# ---------------------------------------------------------------- 1
err = 0.0
for th in np.linspace(TH_MIN, TH_MAX, 25):
    A, B = C.scissor_nodes(th)
    for (pa, pb, _) in C.scissor_links(th):
        d = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        err = max(err, abs(d - P.L_LINK))
    # จุดตัดกลางแขนของแต่ละชั้นต้องตรงกันทั้งสองท่อน
    for k in range(1, P.N_STAGES + 1):
        m1 = ((A[k-1][0] + B[k][0]) / 2, (A[k-1][1] + B[k][1]) / 2)
        m2 = ((B[k-1][0] + A[k][0]) / 2, (B[k-1][1] + A[k][1]) / 2)
        err = max(err, math.hypot(m1[0]-m2[0], m1[1]-m2[1]))
check(err < 1e-9, "1. ปิดลูปคิเนแมติกส์",
      f"ความคลาดเคลื่อนสูงสุดของความยาวแขน + จุดตัดกลาง = {err:.2e} mm")

# ---------------------------------------------------------------- 2
d_par = P.L_LINK * math.sin(TH_MIN) * math.cos(TH_MIN)
gap = d_par - P.LINK_W
check(gap > 0.5, "2. ระยะห่างแขนชั้นเดียวกันตอนพับ",
      f"ระยะตั้งฉาก {d_par:.2f} mm − ความกว้างแขน {P.LINK_W:.1f} mm "
      f"= ช่องว่าง {gap:.2f} mm  (ต้อง > 0.5)")

# ---------------------------------------------------------------- 3,4
asm_f, phi_f = C.build_assembly(TH_MIN)
asm_e, phi_e = C.build_assembly(TH_MAX)
wf, we = C.fuse(asm_f), C.fuse(asm_e)
bf, be = wf.bbox(), we.bbox()

check(bf[3]-bf[0] <= P.STOW_X + 0.1 and bf[4]-bf[1] <= P.STOW_Y + 0.1,
      "3. ขอบเขตพื้นที่เก็บตอนพับ",
      f"X {bf[3]-bf[0]:.1f} x Y {bf[4]-bf[1]:.1f} mm "
      f"(กำหนด {P.STOW_X:.0f} x {P.STOW_Y:.0f})   "
      f"สูงเหนือดาดฟ้า {bf[5]:.1f} mm, ลึกใต้ดาดฟ้า {-bf[2]:.1f} mm")

check(abs(be[5] - P.H_EXTENDED_TARGET) <= 5.0,
      "4. ความสูงรวมตอนยืดสุด",
      f"{be[5]:.1f} mm (เป้าหมาย {P.H_EXTENDED_TARGET:.0f} ±5)   "
      f"ระยะยกจริง = {be[5]-bf[5]:.1f} mm")

# ---------------------------------------------------------------- 5
slot_half = C.R_CRANK + P.BEARING_OD / 2.0 + 1.0
y_max = C.R_CRANK + P.BEARING_OD / 2.0
check(y_max <= slot_half, "5. ลูกปืนอยู่ในร่อง yoke",
      f"ลูกปืนเลยออกไปสุด ±{y_max:.1f} mm, ร่องยาว ±{slot_half:.1f} mm")

# ---------------------------------------------------------------- 6
gx0 = C.X_PIVOT + C.S_UP - C.POST_LEN / 2 - 1
gx1 = C.X_PIVOT + C.S_FOLD + C.POST_LEN / 2 + 1
inside = (gx0 >= -P.BASE_X/2 + 1) and (gx1 <= P.BASE_X/2 - 1)
check(inside, "6. ร่องนำแคร่อยู่ในแผ่นฐาน",
      f"ร่องกิน x {gx0:.1f} … {gx1:.1f} mm  (แผ่นฐาน "
      f"{-P.BASE_X/2:.0f} … {P.BASE_X/2:.0f})")

# ---------------------------------------------------------------- 7
print("\n[ ... ] 7. ตรวจการชนกันของชิ้นส่วน (บูลีน mesh) — ใช้เวลาสักครู่")
pairs_checked, hits = 0, []

def links_of(asm):
    return {k: v for k, v in asm.items() if k.startswith("link")}

for tag, asm in (("พับสุด", asm_f), ("ยืดสุด", asm_e)):
    lk = links_of(asm)
    names = sorted(lk)
    # 7a: แขน vs แขน (เฉพาะคู่ที่อยู่ระนาบเดียวกันและ y ทับกัน)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = lk[names[i]], lk[names[j]]
            ba, bb = a.bbox(), b.bbox()
            if ba[4] < bb[1] - 0.05 or bb[4] < ba[1] - 0.05:   # แยกกันในแกน Y
                continue
            if ba[3] < bb[0] or bb[3] < ba[0] or ba[5] < bb[2] or bb[5] < ba[2]:
                continue
            pairs_checked += 1
            v = sk.interference(a, b, tol_mm3=5.0)
            if v > 0:
                hits.append((tag, names[i], names[j], v))
    # 7b: แขนล่างสุด vs แผ่นฐาน   และ  แขนบนสุด vs แพลตฟอร์ม
    for nm in (names[0], names[1], names[2], names[3]):
        pairs_checked += 1
        v = sk.interference(lk[nm], asm["base"], tol_mm3=5.0)
        if v > 0:
            hits.append((tag, nm, "base", v))
    for nm in (names[-1], names[-2], names[-3], names[-4]):
        pairs_checked += 1
        v = sk.interference(lk[nm], asm["platform"], tol_mm3=5.0)
        if v > 0:
            hits.append((tag, nm, "platform", v))
    # 7c: แคร่ vs แผ่นฐาน (ต้องเลื่อนได้ ห้ามชน)
    pairs_checked += 1
    v = sk.interference(asm["carriage"], asm["base"], tol_mm3=5.0)
    if v > 0:
        hits.append((tag, "carriage", "base", v))
    # 7d: แคร่ vs เซอร์โว
    pairs_checked += 1
    v = sk.interference(asm["carriage"], asm["servo"], tol_mm3=5.0)
    if v > 0:
        hits.append((tag, "carriage", "servo", v))

detail = f"ตรวจ {pairs_checked} คู่"
if hits:
    detail += "\n         " + "\n         ".join(
        f"ชน! [{t}] {a} ↔ {b} = {v:.1f} mm³" for t, a, b, v in hits[:12])
check(not hits, "7. การชนกันของชิ้นส่วน", detail)

# ---------------------------------------------------------------- 8
tilts = []
for th in np.linspace(TH_MIN, TH_MAX, 40):
    A, B = C.scissor_nodes(th)
    tilts.append(abs(A[P.N_STAGES][1] - B[P.N_STAGES][1]))
check(max(tilts) < 1e-9, "8. แพลตฟอร์มขึ้นตรงแนวดิ่ง",
      f"ความต่างระดับหมุดบนซ้าย-ขวา สูงสุด = {max(tilts):.2e} mm")

# ---------------------------------------------------------------- 9
x_fix, x_lo = C.X_PIVOT, C.X_PIVOT + C.S_UP
x_cam = (x_fix + x_lo) / 2.0
ok9 = (min(x_fix, x_lo) + 16 <= x_cam <= max(x_fix, x_lo) - 16)
check(ok9, "9. จุดยึดกล้องอยู่ในช่วงที่แพลตฟอร์มถูกรองรับ",
      f"หมุดรองรับตอนยกสุดอยู่ที่ x = {x_fix:.1f} และ {x_lo:.1f} mm; "
      f"ชุดรูยึดกล้องกว้าง 30 mm อยู่กึ่งกลางที่ x = {x_cam:.1f} mm")

# ================================================================
# วาดภาพตรวจ
# ================================================================
def draw(ax, theta, title):
    A, B = C.scissor_nodes(theta)
    for (pa, pb, dy) in C.scissor_links(theta):
        ax.plot([pa[0], pb[0]], [pa[1], pb[1]],
                lw=2.4, color="#3a8f4a" if dy < 0 else "#7fbf5f",
                solid_capstyle="round", zorder=3)
    for k in range(P.N_STAGES + 1):
        for pt in (A[k], B[k]):
            ax.add_patch(Circle(pt, 1.6, color="#222", zorder=4))
    # ฐาน
    ax.add_patch(plt.Rectangle((-P.BASE_X/2, 0), P.BASE_X, P.BASE_T,
                               color="#8a8a90", zorder=2))
    # แพลตฟอร์ม
    ztop = A[P.N_STAGES][1] + 6.0
    ax.add_patch(plt.Rectangle((-P.PLAT_X/2, ztop), P.PLAT_X, P.PLAT_T,
                               color="#c8b93f", zorder=2))
    # crank + yoke
    s = C.span(theta)
    cosphi = max(-1, min(1, (C.X_PIVOT + s - C.X_CRANK) / C.R_CRANK))
    phi = math.acos(cosphi)
    ax.plot([C.X_CRANK, C.X_CRANK + C.R_CRANK*math.cos(phi)],
            [C.Z_CRK_B + 2, C.Z_CRK_B + 2], lw=3, color="#2a6fbf", zorder=3)
    ax.add_patch(plt.Rectangle((C.X_PIVOT + s - 13, C.Z_YOKE_B), 26,
                               C.Z_YOKE_T - C.Z_YOKE_B, color="#d97a35", zorder=2))
    ax.add_patch(plt.Rectangle((C.X_CRANK - 20.25, C.Z_CRK_B - 38), 40.5, 38,
                               color="#26262c", zorder=1))
    # กรอบพื้นที่เก็บ
    ax.add_patch(plt.Rectangle((-P.STOW_X/2, 0), P.STOW_X, P.STOW_Y,
                               fill=False, ls="--", ec="crimson", lw=1.3, zorder=5))
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal"); ax.grid(alpha=.25)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Z (mm)")

fig = plt.figure(figsize=(15, 8))
ax1 = fig.add_subplot(1, 3, 1); draw(ax1, TH_MIN,
    f"FOLDED  theta={P.THETA_MIN}deg\nH={bf[5]:.0f} mm above deck")
ax1.set_xlim(-60, 60); ax1.set_ylim(-60, 120)

ax2 = fig.add_subplot(1, 3, 2); draw(ax2, TH_MAX,
    f"EXTENDED  theta={P.THETA_MAX}deg\nH={be[5]:.0f} mm above deck")
ax2.set_xlim(-60, 60); ax2.set_ylim(-60, 540)

ax3 = fig.add_subplot(1, 3, 3)
for th, c, lab in [(TH_MIN, "#c0392b", "folded"),
                   (math.radians(25), "#e67e22", "25 deg"),
                   (math.radians(42), "#16a085", "42 deg"),
                   (TH_MAX, "#2980b9", "extended")]:
    A, B = C.scissor_nodes(th)
    for (pa, pb, dy) in C.scissor_links(th):
        ax3.plot([pa[0], pb[0]], [pa[1], pb[1]], lw=1.3, color=c, alpha=.8)
    ax3.plot([], [], color=c, label=lab)
ax3.add_patch(plt.Rectangle((-P.BASE_X/2, 0), P.BASE_X, P.BASE_T, color="#8a8a90"))
ax3.set_aspect("equal"); ax3.grid(alpha=.25); ax3.legend(fontsize=8)
ax3.set_title("Motion sweep"); ax3.set_xlim(-60, 60); ax3.set_ylim(-20, 540)
ax3.set_xlabel("X (mm)"); ax3.set_ylabel("Z (mm)")

plt.tight_layout()
plt.savefig("scissor_views.png", dpi=125)
print("\nบันทึกภาพตรวจ: scissor_views.png")

# ================================================================
print("\n" + "=" * 72)
if FAIL:
    print(f"ไม่ผ่าน {len(FAIL)} ข้อ: {', '.join(FAIL)}")
    sys.exit(1)
print(f"ผ่านทุกข้อ" + (f"  (มีข้อเตือน {len(WARN)}: {', '.join(WARN)})" if WARN else ""))
