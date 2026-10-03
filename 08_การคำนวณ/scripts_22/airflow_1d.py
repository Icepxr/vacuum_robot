"""ไฟล์ 22 — แบบจำลองทางลม 1 มิติ: blower AVC BA10033B12U + ทางลม Newassembly
ทุกค่าที่เป็นสมมติฐานอยู่ใน CFG ด้านบน · รัน: python3 airflow_1d.py
เครือข่าย:  [ปากหน้า → กรวย → ช่องตรง]  ┐
            [ช่องใต้พื้น (แปรง)]         ├→ กล่องเก็บฝุ่น → รู Ø36 หลังคา → blower
            [รั่ว: รู Ø80 ชั้นบน → กรวย] ┘ (เฉพาะกรณีรูนี้ไม่ได้ปิด)
"""
import math, json, sys

RHO = 1.2            # kg/m³ อากาศ 25–30 °C
MU = 1.81e-5         # Pa·s
CFM = 0.000471947    # m³/s

# --- blower -------------------------------------------------------------
Q_FREE = 38.68 * CFM            # [สเปก-ร้าน] 18.25 L/s
# ΔP_max ไม่มีในสเปก · เทียบ Delta BFB1012VH (97×94×33, 38.0 CFM, 486.2 Pa @4500 rpm) [สเปก Digi-Key]
# ปรับด้วยกฎพัดลม ΔP ∝ n² ไปที่ 4200 rpm → 423 Pa [ประมาณการ]
P_MAX_CASES = {'ต่ำ 300 Pa': 300.0, 'กลาง 423 Pa': 486.2 * (4200 / 4500) ** 2, 'สูง 486 Pa': 486.2}

def fan_dp(q, p0, shape):
    """shape='lin' : ΔP = P0(1-Q/Qf)  (มองโลกร้าย)  ·  'quad' : ΔP = P0(1-(Q/Qf)²) (มองโลกดี)"""
    r = q / Q_FREE
    return p0 * (1 - r) if shape == 'lin' else p0 * (1 - r * r)

# --- เรขาคณิต [วัดจาก CAD Newassembly 1 ต.ค. 2026] ---------------------------
mm2 = 1e-6
A_MOUTH = 84.9e-3 * 50.0e-3          # ปากหน้า กว้าง 84.9 × สูง 50.0 mm
A_CH = 25.0e-3 * 50.0e-3             # ช่องตรง 25.0 × 50.0 mm
DH_CH = 2 * 25.0 * 50.0 / (25.0 + 50.0) * 1e-3   # 33.3 mm
L_CH = 165e-3                        # x ≈ 30 → 195 mm
A_HOLE = math.pi / 4 * 36.0e-3 ** 2  # รูหลังคา Ø36 (ส่วนแคบสุดของ keyhole) = 1018 mm²
A_LEAK80 = math.pi / 4 * 80e-3 ** 2  # รู Ø80 พื้นชั้นบน เหนือกรวย
SLOT_PERIM = 2 * (40 + 196) * 1e-3  # เส้นรอบช่องใต้พื้น 40 × 196 mm

# --- สัมประสิทธิ์การสูญเสีย [ประมาณการ จากค่าตำรา] -----------------------------
K_MOUTH = 0.5      # ทางเข้าขอบคม (อ้างความเร็วที่ปาก)
K_FUNNEL = 0.10    # กรวยลดขนาด 85→25 mm ยาว ~30 mm (อ้างความเร็วช่อง)
K_DUMP = 1.0       # ช่องตรงเปิดเข้ากล่อง = เสียหัวความเร็วทั้งหมด
K_GAP = 1.5        # ลมลอดใต้ขอบหุ่นแล้วเลี้ยวขึ้นช่อง (อ้างความเร็วในช่องว่าง)
K_LEAK = 1.5       # รู Ø80 → กรวย
K_HOLE = {'ต่ำ': 0.8, 'กลาง': 1.0, 'สูง': 1.5}   # รูขอบคม Ø36 + ขยายตัวเข้าตา blower

def f_darcy(v, dh, eps=0.05e-3):
    re = RHO * v * dh / MU
    if re < 2300: return 64 / max(re, 1)
    return 0.25 / math.log10(eps / (3.7 * dh) + 5.74 / re ** 0.9) ** 2  # Swamee–Jain (ε 0.05 mm ~ ชิ้นพิมพ์ 3D)

def dp_front(q):
    v_ch = q / A_CH; v_m = q / A_MOUTH
    k_f = f_darcy(v_ch, DH_CH) * L_CH / DH_CH if q > 0 else 0
    return K_MOUTH * 0.5 * RHO * v_m ** 2 + (K_FUNNEL + k_f + K_DUMP) * 0.5 * RHO * v_ch ** 2

def q_from_dp(dp_fn, dp):
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        (lo, hi) = (mid, hi) if dp_fn(mid) < dp else (lo, mid)
    return lo

def solve(p0, shape, gap_mm, k_hole, leak80):
    a_gap = SLOT_PERIM * gap_mm * 1e-3
    def branches(p_bin):
        qf = q_from_dp(dp_front, p_bin)
        qu = a_gap * math.sqrt(2 * p_bin / (K_GAP * RHO)) if gap_mm > 0 else 0
        ql = A_LEAK80 * math.sqrt(2 * p_bin / (K_LEAK * RHO)) if leak80 else 0
        return qf, qu, ql
    # หา p_bin ที่ fan_dp(Q) = p_bin + ΔP_hole(Q)
    lo, hi = 0.0, p0
    for _ in range(100):
        pb = (lo + hi) / 2
        q = sum(branches(pb))
        resid = fan_dp(q, p0, shape) - (pb + k_hole * 0.5 * RHO * (q / A_HOLE) ** 2)
        (lo, hi) = (pb, hi) if resid > 0 else (lo, pb)
    qf, qu, ql = branches(pb); q = qf + qu + ql
    return dict(Q=q, Qf=qf, Qu=qu, Ql=ql, P_bin=pb, dP_hole=k_hole * 0.5 * RHO * (q / A_HOLE) ** 2,
                v_hole=q / A_HOLE, v_ch=qf / A_CH, v_mouth=qf / A_MOUTH,
                v_gap=(qu / a_gap if gap_mm > 0 else 0))

def show(tag, r):
    print(f"{tag:<44} Q={r['Q']*1e3:5.2f} L/s | หน้า {r['Qf']*1e3:5.2f} ({100*r['Qf']/r['Q']:3.0f}%) "
          f"ใต้พื้น {r['Qu']*1e3:5.2f} รั่ว80 {r['Ql']*1e3:5.2f} | P_กล่อง {r['P_bin']:5.0f} Pa  ΔP_รู {r['dP_hole']:4.0f} | "
          f"v_รู {r['v_hole']:4.1f} v_ช่อง {r['v_ch']:4.1f} v_ปาก {r['v_mouth']:4.1f} v_ใต้ {r['v_gap']:4.1f} m/s")

if __name__ == '__main__':
    print(f"Q_free = {Q_FREE*1e3:.2f} L/s · ΔP_max กลาง = {P_MAX_CASES['กลาง 423 Pa']:.1f} Pa · "
          f"A_รู = {A_HOLE/mm2:.0f} mm² · A_ช่อง = {A_CH/mm2:.0f} mm² · A_ปาก = {A_MOUTH/mm2:.0f} mm² · Dh = {DH_CH*1e3:.1f} mm")
    p0 = P_MAX_CASES['กลาง 423 Pa']
    print('\n== S1 ปิดสนิทยกเว้นปากหน้า (ไม่มีช่องใต้พื้น ไม่รั่ว) — ขอบบนของปากหน้า')
    for sh in ('lin', 'quad'):
        show(f'S1 {sh}', solve(p0, sh, 0, K_HOLE['กลาง'], False))
    print('\n== S2 ปากหน้า + ช่องใต้พื้น (แปรง) · กวาดระยะห่างพื้น h')
    for g in (3, 5, 9, 15, 27):
        show(f'S2 h={g} mm lin', solve(p0, 'lin', g, K_HOLE['กลาง'], False))
    print('\n== S3 เหมือน S2 (h=9) + รู Ø80 ชั้นบนเปิดโล่ง')
    show('S3 h=9 lin', solve(p0, 'lin', 9, K_HOLE['กลาง'], True))
    print('\n== ความไวต่อ ΔP_max, รูปร่าง curve, K_รู (S2 h=9)')
    for pn, pv in P_MAX_CASES.items():
        for kn, kv in K_HOLE.items():
            for sh in ('lin', 'quad'):
                show(f'{pn} K_รู {kn} {sh}', solve(pv, sh, 9, kv, False))

    print('\n== ถ้าขยายรูหลังคา (K_รู กลาง, ΔP_max กลาง, lin)')
    for d in (36, 45, 50, 60):
        A_HOLE = math.pi / 4 * (d * 1e-3) ** 2
        show(f'Ø{d} S1 ปิดสนิท', solve(p0, 'lin', 0, K_HOLE['กลาง'], False))
        show(f'Ø{d} S2 h=9', solve(p0, 'lin', 9, K_HOLE['กลาง'], False))
    A_HOLE = math.pi / 4 * 36.0e-3 ** 2

    print('\n== ความเร็วปลาย (terminal) ของเศษ PLA ทรงกลม · ρ_p 1240 kg/m³ · Cd 0.44 (Re > 1000)')
    for d in (1, 2, 3, 5, 8, 10):
        dm = d * 1e-3
        vt = math.sqrt(4 * 9.81 * dm * 1240 / (3 * 0.44 * RHO))
        re = RHO * vt * dm / MU
        print(f'd = {d:>2} mm : v_t = {vt:5.1f} m/s  (Re = {re:,.0f})')

    print('\n== ความเร็วลมที่พื้นหน้าปากหน้า (Dallavalle, ช่องเปิดไม่มีปีก: v = Q/(10x²+A))')
    for qf in (0.0032, 0.0118, 0.0135):
        for x in (0.032, 0.057):
            print(f'Q_หน้า {qf*1e3:4.1f} L/s · x = {x*1e3:.0f} mm : v = {qf/(10*x*x + A_MOUTH):4.2f} m/s')
