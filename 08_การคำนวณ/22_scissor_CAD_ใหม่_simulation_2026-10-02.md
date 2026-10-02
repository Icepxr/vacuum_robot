# 22 — Simulation ชุด scissor CAD ใหม่ (2 ต.ค. 2026)

**ไฟล์ต้นทาง:** `05_CAD/scissorPart/assembly/arm assembly.f3z/.step/.stl` และ STL รายชิ้นทั้งหมด
**สคริปต์:** `05_CAD/simulation/cad_mesh_audit.py`, `step_bom.py`, `scissor_full_sim.py`
**ผลดิบ:** `05_CAD/simulation/results/`
**สถานะ:** ผลทั้งหมดเป็น **[คำนวณ]** จาก geometry ที่ export; ยังไม่มีผลใดเป็น **[วัดจริง]** และยังไม่ใช่ nonlinear/contact FEA

---

## 22.1 ขอบเขตและข้อจำกัด

ทำแล้ว:

1. ตรวจ STL ทุกไฟล์: bounding box, triangle count, ปริมาตร, mass proxy และ manifold health
2. ดึง BOM จาก STEP: 91 occurrences
3. จำลอง kinematics ของแขน 6 ชุด, ความสูง, มุมทำงาน และช่องว่างตอนพับ
4. คำนวณแรงบิด MG996R ด้วย virtual work สำหรับ 1/2 servo และมวลปลายบน 3 กรณี
5. ตรวจ link/pin แบบ first-order: bending, axial, bearing, Euler buckling
6. รัน beam proxy ฐานหุ่นด้วยมวลชุดยกใหม่
7. คำนวณ CoG/การพลิกแบบ sensitivity ต่อมวลชุดยก 0.50–0.90 kg

ยังทำเป็น FEA ไม่ได้จากไฟล์ export ชุดนี้:

- STL/STEP ไม่มี Fusion joint, contact, print orientation, infill/perimeter และ material assignment ของชิ้นพิมพ์
- 16 จาก 18 STL มี non-manifold/shared-intersection edges; assembly มี **7,860 non-manifold edges** แม้ไม่มี open boundary edge จึงต้อง repair ก่อน tetra mesh
- จุดที่ยังต้อง FEA: ขอบรู M3, รอยเปลี่ยนหน้าตัด, root ของแขน servo, ฟันเฟือง และจุดยึดฐาน

---

## 22.2 อินพุต

| อินพุต | ค่า | ป้าย |
|---|---:|---|
| แขน 74.2 mm | 3 ชุด | [CAD] จากชื่อ/geometry |
| แขน 85.0 mm | 3 ชุด | [CAD] จากชื่อ/geometry |
| ผลรวมระยะ link | **477.6 mm** | [คำนวณ] |
| ความกว้างแขน | **11.981 mm** | [CAD] จาก STL |
| ความหนา load path | **5.4 mm** | [CAD/ประมาณการ] จาก shell ใน assembly |
| มวลแขน 6 ชุด ถ้า PETG solid | **123.78 g** | [คำนวณ] ρ=1.27 g/cm³ |
| มวลฐาน+ฝาครอบกล้อง ถ้า PETG solid | **187.29 g** | [คำนวณ] |
| กล้อง | **60 g** | [ค่าที่โปรเจกต์ใช้เดิม] |
| มวลปลายบนกรณีอิง CAD | **247.29 g** | [คำนวณ] 187.29+60; ยังไม่รวมสาย/SG90 |
| มวล assembly แบบ PETG-equivalent | **698.51 g** | [ประมาณการ] ใช้เป็น proxy เท่านั้น |
| η ข้อต่อ+เฟือง | **0.65** | [ประมาณการ] ค่าระมัดระวังสำหรับ friction/loss; ยังต้องวัดจริง |
| MG996R ที่ราง 5 V | **0.922 N·m** (9.4 kgf·cm) | [ประมาณการ] datasheet ไม่มีค่า 5 V |
| MG996R ที่ 6 V | **1.079 N·m** (11 kgf·cm) | [สเปก] |
| PETG σ_allow / E | **15 MPa / 2,000 MPa** | [ประมาณการ] ยังไม่มี coupon ของงานพิมพ์จริง |

> Mass proxy จาก STL คิดเหมือนเนื้อแน่น 100% ทุกชิ้น แต่ assembly จริงมีทั้ง PETG, เหล็ก, servo และช่องว่างจาก infill จึงห้ามเรียกว่า “มวลจริง” จนกว่าจะชั่ง

---

## 22.3 Kinematics และความสูง

### สมมติฐาน

แขนทั้ง 6 ชุดทำมุมร่วม `θ` และเรียงเป็น serial equal-angle linkage:

```text
H_link(θ) = ΣL_i · sinθ
H_total   = H_fixed + H_link
```

จาก PCA ของ link shells ในท่า CAD ได้มุมจากแนวดิ่งประมาณ 22.88° → `θ_CAD = 67.12°` จากแนวนอน

### แทนค่า

```text
ΣL = 3(74.2) + 3(85.0) = 477.6 mm
H_link,CAD = 477.6 sin(67.12°) = 440.02 mm
H_fixed    = 461.73 − 440.02 = 21.71 mm
H_max      = 21.71 + 477.6 sin(90°) = 499.31 mm
```

### ผล

| รายการ | ผล | ตัดสิน |
|---|---:|---|
| ความสูง CAD pose | 461.73 mm | [CAD] |
| ความสูงสูงสุดเชิงเรขาคณิต | **499.31 mm** | [คำนวณ] |
| requirement ก่อนรับ CAD ชุดปัจจุบัน | 550.00 mm | requirement |
| ส่วนที่ขาด | **50.69 mm (9.2%)** | **ไม่ผ่าน** |

ดีไซน์นี้สอดคล้องกับเป้ารุ่นเก่า ~500 mm มากกว่าเป้าใหม่ ≥550 mm จึงบันทึกเป็น C46 ในไฟล์ 10

---

## 22.4 ช่องว่างตอนพับ

ใช้ข้อจำกัดเชิงระนาบเดียวกับงานเดิมสำหรับแขนสั้นสุด:

```text
gap_raw = L_min sinθ cosθ
clearance = gap_raw − W_link
```

ที่ความสูงรวม 100 mm:

```text
θ_stow = asin((100 − 21.71)/477.6) = 9.435°
clearance = 74.2 sin(9.435°)cos(9.435°) − 11.981
          = 0.017 mm
```

**ผล:** เชิงคณิตศาสตร์ไม่ชน แต่ clearance **0.017 mm ใช้ผลิตจริงไม่ได้** [คำนวณ]
ถ้ากำหนด clearance ขั้นต่ำ 0.40 mm → ต้องพับสูง **102.57 mm** หรือทำแขนแคบลงอย่างน้อย ~0.38 mm

---

## 22.5 แรงบิด servo

### สูตร

ใช้ virtual work โดยรวมมวลแขนแต่ละท่อนที่กึ่งกลางท่อน:

```text
C = m_payload ΣL + Σ[m_i(s_i + L_i/2)]                 [kg·m]
T_gravity(θ) = g C cosθ                                [N·m]
T_servo = T_gravity/(N_servo η_joint) + T_stiction
T_stiction = 0.05 N·m/servo
```

ลำดับมวลแขนเลือกกรณีที่ทำให้โมเมนต์สูงสุด (conservative) และกวาดตั้งแต่ท่าพับ 100 mm ถึง 90°

### ผลพีคที่ท่าพับ

| มวลปลายบน | จำนวน servo ยก | T พีค/ตัว | SF @5 V | SF @6 V | ตัดสินที่ 5 V |
|---:|---:|---:|---:|---:|---|
| 95 g | 1 | 1.204 N·m | 0.77 | 0.90 | ไม่ผ่าน |
| 95 g | 2 | 0.627 N·m | 1.47 | 1.72 | ต่ำกว่าเป้า 2 |
| **247.29 g (CAD solid proxy+กล้อง)** | 1 | 2.287 N·m | 0.40 | 0.47 | ไม่ผ่านมาก |
| **247.29 g** | **2** | **1.169 N·m** | **0.79** | **0.92** | **ไม่ผ่าน** |
| 300 g | 1 | 2.662 N·m | 0.35 | 0.41 | ไม่ผ่าน |
| 300 g | 2 | 1.356 N·m | 0.68 | 0.80 | ไม่ผ่าน |

แม้ใช้ 2 servo ที่ 6 V กรณี CAD ก็ยังมี SF <1 จึงห้ามทดสอบยกพร้อม payload นี้โดยไม่มี counterbalance/ตัวขับใหม่/การวัดมวลจริง

ถ้าใช้เฟืองทดอย่างเดียวเพื่อให้ **SF=2 @5 V** ต้องได้อัตราทดอย่างน้อย:

```text
i = 1.169 / (0.922/2) = 2.54 : 1
ช่วงหมุน servo = (90 − 9.435) × 2.54 = 204.3°
```

แต่ datasheet ในโปรเจกต์ระบุประมาณ 120° → เฟืองทดอย่างเดียวแก้แรงบิดแล้วทำให้ช่วงหมุนไม่พอ ต้องใช้สปริง/แก๊สสปริง/lead screw/winch หรือ servo แบบหลายรอบแทน

---

## 22.6 แขนและหมุด — first-order

### สมมติฐาน

- 2 load paths
- หน้าตัด `W×T = 11.981×5.4 mm`, รู M3, link ยาวสุด 85 mm
- กรณี payload 247.29 g, effective lift mass 314.64 g
- `θ=9.435°`, `η=0.65`
- โมเมนต์ที่รูใช้ first-order `M≈F_horizontal,path L/4`

### แทนค่าและผล

```text
F_horizontal,total = 28.58 N
F_axial/path        = 9.41 N
M/path              = 303.63 N·mm
σ_bending           = 2.388 MPa
σ_axial             = 0.194 MPa
σ_combined          = 2.582 MPa
```

| Check | ผล | SF |
|---|---:|---:|
| PETG static | 2.582 MPa | **5.81** |
| impact ×2 | 5.164 MPa | **2.90** |
| impact ×2 + Kt≈2 ที่ขอบรู | 10.327 MPa | **1.45** ⚠ |
| bearing ที่รู | 0.581 MPa | 25.81 (เทียบ 15 MPa) |
| Euler buckling | Pcr 429.53 N vs 9.41 N | 45.62 |

**สรุป:** แขนไม่ติด axial/buckling แต่ขอบรู/รอยเปลี่ยนหน้าตัดเหลือ SF 1.45 เมื่อรวม impact และ stress concentration จึงยังไม่ผ่านเป้า SF≥2 จนกว่า FEA/coupon test จะยืนยัน

---

## 22.7 ฐานหุ่นรับชุดยกใหม่

ใช้ beam proxy เดิม: simply supported span 180 mm, effective width 80 mm, PETG `E=2.1 GPa`, flexural allowable `68×0.45=30.6 MPa` และโหลดจุดกลางจาก mast proxy 0.6985 kg × impact 2 = **13.70 N**

| ฐานหนา | σ | SF | การแอ่น |
|---:|---:|---:|---:|
| 2 mm | 11.56 MPa | 2.65 | 14.87 mm |
| 3 mm | 5.14 MPa | **5.95** | **4.41 mm** ⚠ |
| 4 mm | 2.89 MPa | 10.59 | 1.86 mm |
| 5 mm | 1.85 MPa | 16.54 | 0.95 mm |
| 6 mm | 1.28 MPa | 23.82 | 0.55 mm |

**สรุป:** 3 mm ไม่ครากแต่ beam proxy คาดว่าแอ่นมาก ต้องอาศัยครีบ/รูปทรงจริงและ FEA ยืนยัน; ถ้าเป็นแผ่นเรียบล้วนควร ≥5 mm เพื่อกดการแอ่นต่ำกว่า 1 mm

---

## 22.8 CoG และเสถียรภาพ

### สมมติฐาน

เริ่มจากค่ากลางเดิม 2.342 kg, `z_CoG=51.74 mm` แล้วหัก lift เก่า 0.351 kg ออก ได้ฐานหุ่น `1.991 kg`, `z≈36.26 mm` [คำนวณจากข้อมูลเดิมที่ยังมี C3/C4]
วาง assembly ใหม่บนดาดฟ้าที่ z=100 mm; volume centroid จาก STL อยู่สูง 229.83 mm → mast CoG ≈329.83 mm

### กรณี mass proxy 0.70 kg

```text
M_total = 1.991 + 0.700 = 2.691 kg
z_CoG   = 112.62 mm
a_tip   = 9.81(0.100)/0.11262 = 8.71 m/s²
guard SF2.5 = 3.48 m/s²
θ_tip   = atan(0.100/0.11262) = 41.60°
```

กวาดมวล mast 0.50–0.90 kg ได้ `a_tip=10.31…7.68 m/s²` และ guard SF2.5 = `4.12…3.07 m/s²`
ดังนั้น guard เดิม 7.58 m/s² ใช้กับเสาใหม่นี้ไม่ได้; ค่าเริ่มต้นชั่วคราวควรไม่เกิน **3.5 m/s²** จนกว่าจะชั่งมวลและวัด CoG จริง

---

## 22.9 สรุปผ่าน/ไม่ผ่าน

| หัวข้อ | ผล |
|---|---|
| STEP assembly/BOM | ผ่านการอ่าน: 91 occurrences, MG996R 2 ตัว, hardware ครบในไฟล์ |
| Mesh พร้อมเข้า FEA | **ไม่ผ่าน:** 16/18 STL non-manifold; assembly 7,860 edges |
| ความสูง ≥550 mm | **ไม่ผ่าน:** สูงสุด 499.31 mm |
| พับ ≤100 mm พร้อม tolerance ผลิต | **ไม่ผ่าน:** clearance 0.017 mm; ต้อง ~102.57 mm สำหรับ 0.4 mm |
| MG996R 1 ตัว | **ไม่ผ่านทุกกรณี** |
| MG996R 2 ตัว @5 V, payload CAD | **ไม่ผ่าน:** SF 0.79 |
| แขน static | ผ่าน first-order SF 5.81 |
| แขน impact+Kt | **ต่ำกว่าเป้า:** SF 1.45 |
| pin bearing / buckling | ผ่าน first-order |
| ฐาน 3 mm ไม่คราก | ผ่าน SF 5.95 แต่แอ่น proxy 4.41 mm ต้อง FEA |
| เสถียรภาพ | ต้องลด acceleration guard จากค่าเก่า; provisional 3.5 m/s² |

---

## 22.10 ต้องวัด/ยืนยันก่อนล็อกแบบ

1. ชั่ง assembly รวม และชั่งเฉพาะชุดบนสุดจริง
2. ยืนยันว่า MG996R ทั้ง 2 ตัวใช้ยก หรือ `SERVO_B` ยังเป็นแกนกล้องตาม `system_architecture.md` บรรทัด 171 (C45)
3. วัดช่วงหมุนจริงและกระแส MG996R ที่ราง 5.0 V
4. ระบุ filament, orientation, wall/perimeter และ infill ของทุกชิ้น
5. repair mesh หรือใช้ body ต้นฉบับใน Fusion แล้วกำหนด joints/contact/material
6. รัน FEA mesh convergence ที่รู M3, taper, gear root และฐานยึด
7. วัด backlash/การแกว่ง และทดสอบตัดไฟโดยมี safety tether

**ข้อแนะนำก่อนทดลองจริง:** อย่ายก payload ด้วยชุดนี้ตามตัวเลข CAD proxy จนกว่าจะเพิ่ม counterbalance หรือเปลี่ยน actuator และผ่าน torque SF≥2; การทดลอง motion เปล่าต้องมี current limit, mechanical stop และสายกันตก
