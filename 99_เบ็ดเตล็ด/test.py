"""
จำลองสนามแม่เหล็กแบบไดโพล (Magnetic Dipole Field)
เหมาะกับการอธิบายสนามแม่เหล็กโลก / แม่เหล็กแท่ง ให้เห็นภาพเส้นสนาม (field lines)
สมการอ้างอิงจากสูตรสนามไดโพล 3 มิติ ที่ตัดผ่านระนาบที่มีแกนไดโพลอยู่
"""

import numpy as np
import matplotlib.pyplot as plt


def dipole_field(X, Y, pole_pos=(0.0, 0.0), moment=(0.0, 1.0)):
    """คำนวณสนาม B ที่จุด (X, Y) จากไดโพลแม่เหล็กที่ตำแหน่ง pole_pos
    moment คือทิศทางและขนาดของโมเมนต์แม่เหล็ก (mx, my)
    """
    mx, my = moment
    rx = X - pole_pos[0]
    ry = Y - pole_pos[1]
    r = np.sqrt(rx**2 + ry**2)
    r = np.where(r < 1e-3, 1e-3, r)  # กันหารด้วยศูนย์ตรงใจกลาง

    m_dot_r = mx * rx + my * ry
    Bx = (3 * m_dot_r * rx) / r**5 - mx / r**3
    By = (3 * m_dot_r * ry) / r**5 - my / r**3
    return Bx, By


def sample_field_at(x, y, pole_pos=(0.0, 0.0), moment=(0.0, 1.0)):
    """จำลองการ 'อ่านค่า' จากเซนเซอร์แม่เหล็ก (เช่น ที่ ESP32 ต่อกับ magnetometer)
    คืนค่าความแรงสนาม และมุมทิศทางเป็นองศา
    """
    Bx, By = dipole_field(np.array([x]), np.array([y]), pole_pos, moment)
    strength = np.hypot(Bx, By)[0]
    angle_deg = np.degrees(np.arctan2(By, Bx))[0]
    return strength, angle_deg


# --- สร้างกริดของจุดในพื้นที่จำลอง ---
n = 300
lim = 4
x = np.linspace(-lim, lim, n)
y = np.linspace(-lim, lim, n)
X, Y = np.meshgrid(x, y)

# ไดโพลอยู่ตรงกลาง แกนแม่เหล็กชี้ขึ้น (แทนแกนเหนือ-ใต้ของโลก/แท่งแม่เหล็ก)
Bx, By = dipole_field(X, Y, pole_pos=(0, 0), moment=(0, 1))
strength = np.hypot(Bx, By)
log_strength = np.log10(strength)

# --- วาดกราฟ ---
fig, ax = plt.subplots(figsize=(7, 7))

strm = ax.streamplot(
    X, Y, Bx, By,
    color=log_strength,
    cmap="plasma",
    density=1.8,
    linewidth=1,
    arrowsize=1.2,
)

# วาดตำแหน่งขั้วแม่เหล็ก (N อยู่บน, S อยู่ล่าง) เหมือนแท่งแม่เหล็ก/แกนโลก
ax.plot(0, 0.15, marker="o", color="white", markersize=14,
        markeredgecolor="black", zorder=5)
ax.text(0, 0.15, "N", ha="center", va="center", fontsize=9, fontweight="bold", zorder=6)
ax.plot(0, -0.15, marker="o", color="black", markersize=14, zorder=5)
ax.text(0, -0.15, "S", ha="center", va="center", fontsize=9, fontweight="bold",
        color="white", zorder=6)

ax.set_title("Magnetic Dipole Field Simulation", fontsize=13)
ax.set_xlabel("x")
ax.set_ylabel("y")
ax.set_xlim(-lim, lim)
ax.set_ylim(-lim, lim)
ax.set_aspect("equal")

cbar = fig.colorbar(strm.lines, ax=ax, shrink=0.8)
cbar.set_label("log10(field strength)")

plt.tight_layout()
plt.savefig("/home/claude/magnetic_field_sim.png", dpi=150)
print("บันทึกภาพเรียบร้อย")

# --- ตัวอย่าง: จำลองการอ่านค่าจากเซนเซอร์ที่ตำแหน่งต่างๆ (เหมือนต่อ magnetometer กับ ESP32) ---
sample_points = [(1, 0), (0, 2), (-1.5, -1), (2, 2)]
print("\nตัวอย่างค่าที่ 'เซนเซอร์' อ่านได้ ณ ตำแหน่งต่างๆ:")
for px, py in sample_points:
    s, ang = sample_field_at(px, py)
    print(f"  ตำแหน่ง ({px:>4}, {py:>4}) -> ความแรง B = {s:.4f}, ทิศทาง = {ang:6.1f} องศา")