# -*- coding: utf-8 -*-
"""
วิเคราะห์ความแข็งแรงเชิงวิเคราะห์ (first-order) ของฐาน/โครงหุ่นดูดฝุ่น
- โมเดล: แผ่นฐานเป็น "คานรับแรงดัด" พาดระหว่างล้อขับ 2 ข้าง (simply supported beam)
- ตอบคำถาม: ฐานรับแรงกดได้สูงสุดเท่าไรก่อนคราก (yield), แอ่นเท่าไร, safety factor
- ไล่ตามความหนาแผ่น t และวัสดุพิมพ์ 3D (PLA / PETG / ABS)
ทุกค่าเป็นการประเมินขั้นต้น มีสมมติฐานชัดเจนด้านล่าง — ค่าจริงต้องยืนยันด้วย FEA ใน Fusion 360
"""
import numpy as np

g = 9.81  # m/s^2

# ---------------------------------------------------------------
# 1) ข้อมูลจากไฟล์โปรเจกต์ (sim_CoG_scissor.ipynb + BOM)
# ---------------------------------------------------------------
M_total   = 2.47   # kg  มวลรวมทั้งหุ่น (จาก notebook)
M_chassis = 1.20   # kg  มวลของฐาน/โครงเอง
M_payload = M_total - M_chassis   # kg  อุปกรณ์ที่ "วางบน" ฐาน = โหลดที่ฐานต้องแบก
W_payload = M_payload * g          # N
W_total   = M_total   * g          # N

# ชิ้นหนักสุดที่กดเฉพาะจุด (localized) — ใช้เช็คเคสแรงกดจุดเดียว
heaviest_component = 0.45  # kg (แบตเตอรี่แพ็ค)

# ---------------------------------------------------------------
# 2) เรขาคณิตฐาน (จาก support polygon ใน notebook)
# ---------------------------------------------------------------
track   = 0.180    # m  ระยะระหว่างล้อขับซ้าย-ขวา (y = ±90mm) = ช่วงคาน (span)
b_plate = 0.200    # m  ความกว้างฐานเต็ม (y: ±100mm)
# ความกว้างประสิทธิผลที่รับแรงดัด (แรงกดจุดเดียวกระจายบางส่วน) — ประเมินแบบ conservative
b_eff   = 0.080    # m  (แถบกว้าง ~80mm รอบจุดกด; ปรับได้)

L = track          # ช่วงคาน (m)

thicknesses = np.array([2, 3, 4, 5, 6]) / 1000.0  # m

# ---------------------------------------------------------------
# 3) คุณสมบัติวัสดุพิมพ์ 3D (ค่าทั่วไป ทิศทางพิมพ์แนวนอน)
#    sigma_flex = กำลังดัดสูงสุด (ultimate), E = โมดูลัส
#    derate = ตัวลดค่าเผื่อความไม่สม่ำเสมอของงานพิมพ์ (layer adhesion/anisotropy/void)
#    sigma_allow = ค่าออกแบบที่ปลอดภัย = sigma_flex * derate
# ---------------------------------------------------------------
materials = {
    "PLA":  dict(E=3.5e9, sigma_flex=80e6, derate=0.50, rho=1240),
    "PETG": dict(E=2.1e9, sigma_flex=68e6, derate=0.45, rho=1270),
    "ABS":  dict(E=2.3e9, sigma_flex=60e6, derate=0.45, rho=1050),
}

def beam_section(b, t):
    I = b * t**3 / 12.0      # moment of inertia (m^4)
    c = t / 2.0              # ระยะจาก neutral axis ถึงผิว (m)
    return I, c

def max_central_point_force(sigma_allow, b, t, L):
    """แรงกดจุดกึ่งกลางสูงสุดก่อนถึง sigma_allow (คาน simply supported)
    M_max = F L/4 ;  sigma = M c / I  ->  F_max = sigma_allow * b t^2 / (1.5 L)"""
    I, c = beam_section(b, t)
    F_max = sigma_allow * I / (c * (L / 4.0))
    return F_max

def central_deflection(F, E, b, t, L):
    I, _ = beam_section(b, t)
    return F * L**3 / (48.0 * E * I)   # m

def stress_from_force(F, b, t, L):
    I, c = beam_section(b, t)
    M = F * L / 4.0
    return M * c / I

print("="*78)
print("โหลดพื้นฐาน")
print("="*78)
print(f"มวลรวมหุ่น           M_total  = {M_total:.2f} kg  -> น้ำหนัก {W_total:.1f} N")
print(f"มวลโครง/ฐานเอง       M_chassis= {M_chassis:.2f} kg")
print(f"โหลดที่ฐานแบก(payload) M_pay   = {M_payload:.2f} kg  -> {W_payload:.1f} N")
print(f"ช่วงคาน(ล้อถึงล้อ) L = {L*1000:.0f} mm,  กว้างประสิทธิผล b_eff = {b_eff*1000:.0f} mm")
print()

# ---------------------------------------------------------------
# 4) ผลลัพธ์หลัก: แรงกดจุดสูงสุดที่รับได้ + FoS ที่โหลดใช้งานจริง
# ---------------------------------------------------------------
# โหลดใช้งานอ้างอิง: สมมติแรงกดเฉพาะจุดจากชิ้นหนักสุด + แรงกระแทกเผื่อ (impact factor 2x)
F_service = heaviest_component * g          # แรงสถิตจากชิ้นหนักสุด
impact_factor = 2.0                         # เผื่อสะเทือน/ตกกระแทกตอนข้ามธรณี
F_service_dyn = F_service * impact_factor

results = {}
for mat, p in materials.items():
    sa = p["sigma_flex"] * p["derate"]
    rows = []
    for t in thicknesses:
        F_max = max_central_point_force(sa, b_eff, t, L)      # N ก่อนคราก
        # FoS ที่โหลดใช้งาน (dynamic)
        sig_service = stress_from_force(F_service_dyn, b_eff, t, L)
        FoS = sa / sig_service
        defl = central_deflection(F_service_dyn, p["E"], b_eff, t, L) * 1000  # mm
        mass_equiv = F_max / g   # kg เทียบเท่าที่กดจุดกลางได้
        rows.append((t*1000, F_max, mass_equiv, FoS, defl))
    results[mat] = rows

for mat, rows in results.items():
    p = materials[mat]
    sa = p["sigma_flex"]*p["derate"]/1e6
    print("="*78)
    print(f"วัสดุ {mat}:  E={p['E']/1e9:.1f} GPa | กำลังดัด {p['sigma_flex']/1e6:.0f} MPa"
          f" | ค่าออกแบบ(allow) {sa:.0f} MPa")
    print("-"*78)
    print(f"{'หนา(mm)':>8} {'แรงจุดสูงสุด(N)':>16} {'~เทียบ kg':>10} "
          f"{'FoS@ใช้งาน':>12} {'แอ่น(mm)':>10}")
    for t_mm, F_max, meq, FoS, defl in rows:
        print(f"{t_mm:>8.0f} {F_max:>16.0f} {meq:>10.1f} {FoS:>12.1f} {defl:>10.3f}")
    print()

print("="*78)
print(f"หมายเหตุ: โหลดใช้งานอ้างอิง = ชิ้นหนักสุด {heaviest_component} kg "
      f"x impact {impact_factor:.0f} = {F_service_dyn:.1f} N (แรงกดจุดกลางคาน)")
print("FoS>2 ถือว่าปลอดภัยดีสำหรับงานพิมพ์ 3D | FoS<1.5 ควรเพิ่มความหนา/ครีบเสริม")
print("="*78)

# ---------------------------------------------------------------
# 5) กราฟ
# ---------------------------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(1, 2, figsize=(13, 5))
colors = {"PLA":"#c0392b", "PETG":"#2980b9", "ABS":"#27ae60"}

# Plot 1: max central point load (kg-equivalent) vs thickness
for mat, rows in results.items():
    t_mm = [r[0] for r in rows]
    meq  = [r[2] for r in rows]
    ax[0].plot(t_mm, meq, "o-", color=colors[mat], label=mat, lw=2)
ax[0].axhline(M_total, ls="--", color="gray", label=f"whole robot {M_total} kg")
ax[0].set_xlabel("Base plate thickness (mm)")
ax[0].set_ylabel("Max central point load before yield (~kg equiv.)")
ax[0].set_title("Point-load capacity vs thickness")
ax[0].grid(alpha=0.3); ax[0].legend()

# Plot 2: FoS at service load vs thickness
for mat, rows in results.items():
    t_mm = [r[0] for r in rows]
    fos  = [r[3] for r in rows]
    ax[1].plot(t_mm, fos, "s-", color=colors[mat], label=mat, lw=2)
ax[1].axhline(2.0, ls="--", color="green", alpha=0.7, label="FoS=2 (good)")
ax[1].axhline(1.0, ls="--", color="red", alpha=0.7, label="FoS=1 (yield)")
ax[1].set_xlabel("Base plate thickness (mm)")
ax[1].set_ylabel("Safety Factor at service load")
ax[1].set_title(f"FoS at {F_service_dyn:.0f} N (heaviest part x impact 2)")
ax[1].grid(alpha=0.3); ax[1].legend()

plt.tight_layout()
out = "/sessions/fervent-wonderful-ptolemy/mnt/outputs/base_strength_result.png"
plt.savefig(out, dpi=140)
print("saved:", out)
