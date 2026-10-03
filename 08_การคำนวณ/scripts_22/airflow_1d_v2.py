"""ไฟล์ 22 §22.10 — แบบจำลองทางลม 1 มิติ v2 (ทิศที่ผู้ใช้ยืนยัน 1 ต.ค. 2026)
ช่องใต้พื้น+แปรง (ขวา) → กล่องท้าย (รู Ø36 = จอ ถือว่าปิด) → ช่องตรง 25×50 → ถังขยะซ้ายสุด → รู Ø80 → blower ชั้นบน
v1 (airflow_1d.py) ผิดทิศ — เก็บไว้เป็นประวัติ ห้ามใช้
"""
import math
from airflow_1d import RHO, MU, CFM, Q_FREE, P_MAX_CASES, fan_dp, f_darcy

mm2 = 1e-6
# --- เรขาคณิต [วัดจาก CAD Newassembly] -------------------------------------
A_SLOT = 40e-3 * 196e-3                 # ช่องใต้พื้น 40 × 196 = 7,840 mm²
EDGE = {  # ขอบรอบช่องใต้พื้น: ยาว (m), ความสูงจากพื้น (mm) — พื้นประมาณ z −35.4 จากล้อใน Asembly2 [ประมาณการ]
    'หน้า (x≈224)': (196e-3, 8.2), 'ข้าง y≈3': (40e-3, 8.2),
    'หลัง (x≈270)': (196e-3, 27.2), 'ข้าง y≈−193': (40e-3, 27.2)}
A_CH = 25e-3 * 50e-3; DH_CH = 33.3e-3; L_CH = 165e-3
A_BAY = 84.9e-3 * 50e-3                 # หน้าตัดช่องใส่ถัง 84.9 × 50 mm
A_80 = math.pi / 4 * 79.9e-3 ** 2       # รู Ø80 (พื้นที่วัดได้ 5,017 mm²)

# --- K [ประมาณการ ค่าตำรา] ---------------------------------------------------
K_GAP = 1.5      # ลอดใต้ขอบแล้วเลี้ยวขึ้น (อ้าง v ใต้ขอบ)
K_CH_IN = 0.5    # กล่องท้าย → ช่องตรง ขอบคม (อ้าง v ช่อง)
K_DUMP = 1.0     # ช่องตรง → ถัง ขยายตัวทันที (อ้าง v ช่อง)
K_80 = 1.0       # ถัง → รู Ø80 → ตา blower (อ้าง v รู)

def dp_series(q, filt_pa_at_10ls):
    v_ch = q / A_CH; v80 = q / A_80
    k_f = f_darcy(v_ch, DH_CH) * L_CH / DH_CH if q > 0 else 0
    dp = (K_CH_IN + k_f + K_DUMP) * 0.5 * RHO * v_ch ** 2 + K_80 * 0.5 * RHO * v80 ** 2
    dp += filt_pa_at_10ls * q / 0.010    # ไส้กรอง: ΔP ∝ Q (สื่อกรองไหลแบบ laminar) [ประมาณการ]
    return dp

def dp_inlet(q, edges):
    a = sum(l * h * 1e-3 for l, h in edges.values())
    return K_GAP * 0.5 * RHO * (q / a) ** 2, a

def solve(p0, shape, edges, filt=0.0):
    lo, hi = 0.0, Q_FREE
    for _ in range(100):
        q = (lo + hi) / 2
        r = fan_dp(q, p0, shape) - dp_inlet(q, edges)[0] - dp_series(q, filt)
        (lo, hi) = (q, hi) if r > 0 else (lo, q)
    dpi, a = dp_inlet(q, edges)
    return dict(Q=q, a_gap=a, v_gap=q / a, v_slot=q / A_SLOT, v_ch=q / A_CH, v_bay=q / A_BAY, v80=q / A_80,
                dp_in=dpi, dp_ser=dp_series(q, filt), dp_fan=fan_dp(q, p0, shape))

def show(tag, r):
    print(f"{tag:<40} Q={r['Q']*1e3:5.2f} L/s  ΔP_fan {r['dp_fan']:4.0f} Pa (เข้า {r['dp_in']:4.1f} · ช่อง+ถัง+Ø80 {r['dp_ser']:4.0f}) | "
          f"v ใต้ขอบ {r['v_gap']:4.1f} · v ช่องใต้พื้น {r['v_slot']:4.2f} · v ช่องตรง {r['v_ch']:4.1f} · v ถัง {r['v_bay']:4.2f} · v Ø80 {r['v80']:4.1f} m/s")

if __name__ == '__main__':
    p0 = P_MAX_CASES['กลาง 423 Pa']
    print(f"A ใต้ขอบรวม = {sum(l*h for l,h in EDGE.values())*1e3:.0f} mm² · A ช่องใต้พื้น {A_SLOT/mm2:.0f} · A ช่องตรง {A_CH/mm2:.0f} · A Ø80 {A_80/mm2:.0f} mm²")
    print('\n== R1 ตาม CAD ไม่มีไส้กรอง')
    for sh in ('lin', 'quad'):
        show(f'R1 {sh}', solve(p0, sh, EDGE))
    print('\n== R2 ใส่ขอบยาง/แปรงขนลดช่องใต้ขอบเหลือ 3 mm ทุกด้าน')
    sealed = {k: (l, 3.0) for k, (l, h) in EDGE.items()}
    show('R2 lin', solve(p0, 'lin', sealed))
    print('\n== ไส้กรองในถัง (ΔP ที่ 10 L/s)')
    for fp in (0, 50, 100, 200):
        show(f'R1 lin กรอง {fp} Pa@10L/s', solve(p0, 'lin', EDGE, fp))
    print('\n== ความไว ΔP_max / curve (R1 ไม่มีกรอง)')
    for n, pv in P_MAX_CASES.items():
        for sh in ('lin', 'quad'):
            show(f'{n} {sh}', solve(pv, sh, EDGE))
