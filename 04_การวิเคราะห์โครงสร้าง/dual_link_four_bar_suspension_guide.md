# ระบบกันสะเทือน Dual-Link Four-Bar สำหรับหุ่นทำความสะอาด
### รีวิวสิทธิบัตร + หลักการทำงาน + วิธีคำนวณ (พร้อมอ้างอิงงานวิจัย)

> อ้างอิงหลักจากสิทธิบัตร **GB 2611795 A — “A robotic vacuum cleaner”** (Dyson Technology Ltd., ยื่น 15.10.2021, เผยแพร่ 19.04.2023). ผู้ประดิษฐ์: Stuart Lloyd Genn, Vinod Mohana Das, Sharir Azfar Saupi, Nor Fazlinda Alias. IPC: A47L 9/00, A47L 11/40, **B60G 3/18, B60G 3/20** (คลาส B60G = ระบบกันสะเทือนยานพาหนะ)

---

## 1. สรุปการรีวิวเอกสารที่อัปโหลด

| ไฟล์ | เลขที่ | เป็นเรื่องช่วงล่างไหม? | เนื้อหาจริง |
|---|---|---|---|
| `GB2611795A.pdf` | GB 2611795 A | ✅ **ใช่** | หุ่นดูดฝุ่นที่มีระบบกันสะเทือน **four-bar / dual-link** ต่อล้อเข้ากับตัวถัง — คือระบบที่คุณเล็งไว้ |
| `US11658540.pdf` | US 11,658,540 B2 | ❌ **ไม่ใช่** | “Assembling method of a rotor to an electric motor frame” — เป็น *วิธีประกอบโรเตอร์เข้าเฟรมมอเตอร์ด้วยกาว 2 ชนิด* ไม่เกี่ยวกับช่วงล่างเลย (เป็นสิทธิบัตร Dyson เหมือนกันแต่คนละเรื่อง) |

**⚠️ ข้อควรทราบ:** US11658540 ที่แนบมาไม่ใช่ระบบช่วงล่าง หากต้องการคู่เทียบ (prior art) ของ four-bar suspension ในหุ่นดูดฝุ่น ตัวสิทธิบัตร GB อ้างถึงเอกสาร: **DE 102018117740 A1**, **DE 102008029445 A1**, **US 2019/0193499 A1** — สามชิ้นนี้คือ prior art ที่ควรไปตามอ่านต่อ

---

## 2. สถาปัตยกรรมกลไก — มองเป็น “four-bar linkage” ในระนาบข้าง

ระบบนี้คือ **four-bar linkage (กลไกสี่ชิ้นต่อ)** มองจากด้านข้างรถ โดยจับคู่ชิ้นส่วนจริงกับทฤษฎีกลไกได้ดังนี้:

| ชิ้นส่วนในทฤษฎี four-bar | ชิ้นส่วนจริงในสิทธิบัตร | บทบาท |
|---|---|---|
| **Ground / frame** (ชิ้นอยู่กับที่) | ตัวถังหลัก (main body 12) | ฐานอ้างอิง |
| **Coupler** (ชิ้นลอย ปลายทั้งสองต่อกับแขน) | ชุดล้อ + เกียร์บ็อกซ์ (wheel/gearbox 36) | ตัวพาล้อ (wheel carrier) |
| **Link 1 (แขนล่าง)** | แขนที่หนึ่ง (first arm 60) | ต่อ gearbox↔body |
| **Link 2 (แขนบน)** | แขนที่สอง (second arm 62) “overlie” แขนล่าง | ต่อ gearbox↔body |

**จุดหมุน (pivot) ทั้ง 4 จุด:**

- `70` = แขนล่างต่อ gearbox (ฝั่งล้อ, ล่าง)
- `74` = แขนล่างต่อ body (ฝั่งตัวถัง) — มี **มุม α** และจุดต่อสปริง `72` อยู่เลยออกไป
- `80` = แขนบนต่อ gearbox (ฝั่งล้อ, บน)
- `82` = แขนบนต่อ body (ฝั่งตัวถัง, บน)

**ระยะสำคัญ 2 ค่า (หัวใจของสิทธิบัตร):**

- **A = ระยะระหว่าง pivot 70↔80** (ฝั่งล้อ/coupler) — *แคบ*
- **B = ระยะระหว่าง pivot 74↔82** (ฝั่งตัวถัง/ground) — *กว้างกว่า*
- เงื่อนไขบังคับ: **B > A** เสมอ → ทำให้แขนบน–ล่างไม่ขนานกัน (เป็นรูป **สี่เหลี่ยมคางหมู / trapezoidal linkage** ไม่ใช่ parallelogram)

### ค่าตัวเลขอ้างอิงจากสิทธิบัตร (ใช้เป็น design target ได้)

| พารามิเตอร์ | ช่วง | ค่าตัวอย่าง Dyson |
|---|---|---|
| ระยะ A (ฝั่งล้อ) | 10.0–16.0 mm | ~14.3 mm |
| ระยะ B (ฝั่งตัวถัง) | 17.0–30.0 mm | ~21.3 mm |
| อัตราส่วน **B/A** | 1.1–3.0 (ดีที่สุด ~1.5) | **1.43** |
| เส้นผ่านศูนย์กลางล้อ | 75–125 mm | ~86 mm |
| มุม α (ระหว่าง pivot 74 กับจุดต่อสปริง 72) | 90°–120° | ~96° |
| ค่าคงที่สปริง k | 0.75–1.25 “N/m” | ~0.96 “N/m” |
| Threshold ของ distance sensor | 90–120 mm | — |
| เงื่อนไข: B ≤ 40% ของ Ø ล้อ, A ≤ ~25% ของ Ø ล้อ | — | — |

> **⚠️ หมายเหตุเรื่องหน่วยสปริง:** ค่า “0.96 N/m” ที่อ่านได้จากสิทธิบัตร ในทางฟิสิกส์อ่อนเกินจริงมากสำหรับหุ่นมวลระดับกิโลกรัม (0.96 N/m หมายถึงกดยุบ 20 mm ใช้แรงแค่ ~0.02 N) — เป็นไปได้สูงว่าตั้งใจหมายถึง **N/mm** (≈ 960 N/m) หรือเป็นค่าที่จุดต่อสปริงที่มี motion ratio สูง ตอนออกแบบจริง **ต้องยืนยันหน่วยจากตัว PDF ต้นฉบับก่อนใช้**

---

## 3. หลักการทำงาน — ทำไมต้องออกแบบแบบนี้

ระบบนี้ไม่ได้ออกแบบเพื่อ “ความนุ่มนวล” แบบรถยนต์ แต่แก้ 2 ปัญหาเฉพาะของหุ่นดูดฝุ่น:

### ปัญหาที่ 1 — “หน้าเชิด” (rearing up) แล้วเซ็นเซอร์ลวง
หุ่นมี **distance sensor (cliff sensor)** ใต้ท้องคอยวัดระยะพื้น ถ้าค่าเกิน threshold (90–120 mm) หุ่นจะคิดว่าเจอ “ขอบตก/บันได” แล้วหยุดหรือถอย ปัญหาคือ เวลาหุ่นพยายามข้ามธรณีประตูเตี้ย ๆ ล้อดันขึ้น ตัวถังส่วนหน้าเชยขึ้น (rear up) ทำให้เซ็นเซอร์ “ลวง” ว่าเจอขอบตก → หุ่นยกเลิกการข้าม → **ทำความสะอาดได้พื้นที่น้อยลง** ระบบ four-bar ที่ B>A ถูกออกแบบมาเพื่อ *กดหัวไม่ให้เชิด* ให้ล้อยุบตัวรับสิ่งกีดขวางแทนการงัดตัวถังขึ้น

### ปัญหาที่ 2 — downforce ไม่เท่ากันตอนเดินหน้า/ถอยหลัง
มอเตอร์ขับล้อทำให้เกิด **reaction torque** ที่แขนช่วงล่าง (แรงปฏิกิริยาตามกฎข้อ 3 ของนิวตัน):
- ขับ **เดินหน้า** → แขนถูกงัด *ขึ้น* → downforce ที่ล้อ *ลดลง* (ล้อลอย เสียแรงยึดเกาะ/เสียแรงดูด)
- ขับ **ถอยหลัง** → แขนถูกกด *ลง* → downforce *เพิ่มขึ้น*

การทำให้ **B > A** เป็นการปรับ “แขนโมเมนต์” ของแรงปฏิกิริยานี้ให้ไม่สมมาตร เพื่อ **หักล้าง** ความต่างของ downforce ระหว่างเดินหน้า/ถอยหลัง — ผลลัพธ์คือแรงกดล้อ *เท่ากันทั้งสองทิศ* (สิทธิบัตรระบุว่า B และอัตราส่วน B/A ถูกเลือกเพื่อให้ downforce เท่ากันสองทิศ — ดู Fig. 9 “ผลต่าง downforce หน้า/หลัง vs. ระยะยุบล้อ” และ Fig. 10 “downforce vs. moment”)

### บทบาทของสปริง + มุม α
สปริง `64` ต่อจากปลายแขนล่าง (จุด `72`) ไปยังตัวถัง ให้ **แรงกดล้อลงพื้น (downforce)** ส่วน **มุม α ~96°** ของแขนที่ดัดโค้ง เป็นตัวปรับให้แนวแรงสปริงคงที่ตลอดช่วงยุบ ทำให้ downforce “ค่อนข้างคงที่” ไม่ว่าล้อจะอยู่ตำแหน่งไหน — จุดนี้สำคัญเพราะหัวดูด (cleaner head) ต้องการแรงกดพื้นสม่ำเสมอ

### สรุปเป็นประโยคเดียว
> Trapezoidal four-bar (B>A) + สปริงมุม α = ล้อยุบตัวรับสิ่งกีดขวางโดยตัวถังไม่เชิด **และ** แรงกดล้อคงที่/สมมาตรทั้งเดินหน้า-ถอยหลัง → หุ่นข้ามธรณีได้ ไม่โดนเซ็นเซอร์ลวง และดูดฝุ่นได้สม่ำเสมอ

---

## 4. ทำไม “B > A” ถึงได้ผล — แนวคิด Instantaneous Center (จุดหมุนชั่วขณะ)

เพราะแขนบน–ล่างไม่ขนาน (A≠B) เส้นแนวแกนของแขนทั้งสอง เมื่อลากต่อออกไปจะ **ตัดกันที่จุดหนึ่ง** เรียกว่า **Instantaneous Center (IC)** หรือ virtual pivot — เป็น “จุดหมุนเสมือน” ที่ล้อหมุนรอบ ณ ขณะนั้น (ทฤษฎี **Aronhold–Kennedy**) [3]

- เพราะ B (ฝั่งตัวถัง) > A (ฝั่งล้อ) แขนจึง *ลู่เข้าหากันทางฝั่งล้อ* → IC ตกอยู่ **เลยล้อออกไป** (ฝั่งตรงข้ามตัวถัง)
- ตำแหน่ง IC = กำหนด **ความยาวแขนแกว่งประสิทธิผล (effective swing-arm length)** และ **มุม anti-rise geometry** (เทียบได้กับ anti-dive / anti-squat ในรถยนต์)
- เมื่อล้อชนสิ่งกีดขวาง แรงกระทำเยื้องศูนย์ (offset load) สร้าง **โมเมนต์ที่ pivot ฝั่งหน้า (70, 80)** มากขึ้น → แขนขยับง่ายขึ้น → ล้อ “ปีน” สิ่งกีดขวางแทนที่จะงัดตัวถังให้เชิด

การเลื่อนตำแหน่ง IC ด้วยการปรับ B/A จึงเป็นวิธี “จูน” พฤติกรรม anti-rear-up โดยตรง

---

## 5. วิธีคำนวณระบบช่วงล่างนี้ — สูตร + วิธีพิจารณาทีละขั้น

> ต่อไปนี้อธิบายว่า *แต่ละค่ามาจากหลักการไหน ใช้สูตรอะไร และพิจารณายังไง* (ยังไม่แทนตัวเลข) เมื่อมีสเปกหุ่นจริงแล้วค่อยแทนค่าตามลำดับนี้ได้เลย

### ขั้นที่ 1 — ตั้งแบบจำลองจลนศาสตร์ (Vector Loop / Position Analysis)
วางระบบพิกัด แล้วเขียนตำแหน่ง pivot ทั้ง 4 เป็นเวกเตอร์ ปิดลูป four-bar ด้วย **loop-closure equation**:

```
r_arm1 + r_coupler − r_arm2 − r_ground = 0
```

แยกเป็นแกน x, y ได้ 2 สมการ:

```
a·cosθ2 + c·cosθ3 − b·cosθ4 − d = 0
a·sinθ2 + c·sinθ3 − b·sinθ4     = 0
```

โดย a,b = ความยาวแขน, c = ความยาว coupler (ฝั่งล้อ), d = ระยะ ground (ฝั่งตัวถัง), θ = มุมของแต่ละชิ้น
วิธีมาตรฐานคือใช้ **Freudenstein equation** แก้หามุมที่เหลือเมื่อกำหนดมุมขับ 1 ตัว [1][5]
**พิจารณาอะไร:** ตรวจว่ากลไกประกอบได้จริงตลอดช่วงยุบล้อ (ไม่ล็อก, ไม่ผ่าน dead point) และล้อเคลื่อน “เกือบตั้งฉากกับพื้น” ตามที่สิทธิบัตรต้องการ

### ขั้นที่ 2 — หาเส้นทางการเคลื่อนของล้อ (Wheel Travel Path)
ไล่แก้สมการขั้นที่ 1 หลาย ๆ ตำแหน่งมุม แล้ว plot ตำแหน่งจุดศูนย์ล้อ → ได้ **โค้งการเคลื่อนของล้อ** ในระนาบข้าง
**พิจารณาอะไร:** ระยะยุบ–ยืดของล้อ (jounce/rebound travel), การเปลี่ยน caster/การเลื่อนหน้า-หลังของล้อ (เพราะเป็น four-bar โค้ง ไม่ใช่แขนเดี่ยว) — ค่านี้กำหนด clearance ใต้ท้องและ threshold ที่ปลอดภัยของ cliff sensor

### ขั้นที่ 3 — หา Instantaneous Center และแขนแกว่งประสิทธิผล
ลากเส้นแนวแกนแขนล่าง (ผ่าน 70,74) และแขนบน (ผ่าน 80,82) → จุดตัด = **IC** [3]
- ระยะจากศูนย์ล้อถึง IC = **effective swing-arm length (L_eff)**
- ความสูง/ตำแหน่ง IC เทียบ contact patch = กำหนด **anti-rise ratio**

**พิจารณาอะไร:** IC เลื่อนเมื่อล้อยุบ (เพราะแขนไม่ขนาน) → จูน B/A เพื่อคุมว่าจะให้ anti-rear-up มาก/น้อยแค่ไหน (สิทธิบัตรบอก B/A ~1.5; ใหญ่ไปเสี่ยงคว่ำ เล็กไปยังเชิดอยู่)

### ขั้นที่ 4 — Motion Ratio / Installation Ratio → Wheel Rate
**Motion ratio (MR)** = อัตราส่วนการเคลื่อนของสปริงต่อการเคลื่อนของล้อ:

```
MR = δ(spring) / δ(wheel)
```

หาได้จากอนุพันธ์ของ position analysis (velocity ratio) หรือหลักการงานเสมือน จากนั้น **แปลงเป็นอัตราสปริงที่ล้อ (wheel rate):**

```
k_wheel = MR² · k_spring        (ถ้าสปริงแนวตรงกับการเคลื่อน)
k_wheel = MR² · k_spring · cos²φ (เมื่อสปริงเอียงทำมุม φ)
```

MR ยกกำลังสองเพราะสมดุลพลังงาน (energy/virtual work) [1][6][7]
**พิจารณาอะไร:** MR ของ four-bar ไม่คงที่ตลอดช่วงยุบ (ต่างจากสมมติ MR≈1 ของ McPherson) — ควร plot MR vs. wheel travel เพื่อดูว่าอัตราสปริงที่ล้อ “แข็งขึ้น/อ่อนลง” (progressive/regressive) อย่างที่ต้องการไหม การเลือก hardpoint (ตำแหน่ง pivot) คือสิ่งที่คุมค่านี้ [4][7]

### ขั้นที่ 5 — แรงกดล้อสถิต (Static Downforce) จากสปริง + มุม α
ใช้ **สมดุลโมเมนต์รอบ pivot ตัวถัง** หรือ **หลักงานเสมือน (virtual work)**:

```
F_downforce = (F_spring · d_spring) / d_wheel
```

โดย d_spring, d_wheel = แขนโมเมนต์ของแรงสปริงและแรงล้อ วัดรอบ pivot (หรือรอบ IC)
- แรงสปริง `F_spring = k·x + F_preload` (x = ระยะยุบ, มี preload)
- **มุม α** ปรับ d_spring ให้แนวแรงคงที่ → downforce คงที่ตลอด travel (นี่คือเหตุผลที่ Dyson ดัดแขนเป็น ~96°)

**พิจารณาอะไร:** ตั้ง downforce เป้าหมายจากความต้องการของหัวดูด + แรงยึดเกาะขั้นต่ำ แล้วย้อนหา k_spring, preload, และมุม α ที่ทำให้ downforce แทบไม่แกว่งตลอดช่วงยุบ

### ขั้นที่ 6 — ⭐ เงื่อนไข downforce สมมาตร หน้า/หลัง (หัวใจของ B>A)
โมเมนต์จาก reaction torque ของมอเตอร์กระจายลงแขนผ่าน pivot ฝั่งล้อ (spacing A) และฝั่งตัวถัง (spacing B) เขียนสมดุลโมเมนต์ของ coupler (ตัวพาล้อ):

```
ΔF_downforce ∝ T_reaction · f(B, A, geometry)
```

- เดินหน้า: reaction torque ทำให้แขนถูกงัดขึ้น → −ΔF
- ถอยหลัง: reaction torque กดแขนลง → +ΔF
- เมื่อ **A = B (parallelogram)** ความไม่สมมาตรนี้จะเหลือค้าง (downforce หน้า≠หลัง)
- **เลือก B > A** ให้แขนโมเมนต์สองฝั่งชดเชยกัน → ตั้งเป้า **ΔF_forward = ΔF_backward**

**พิจารณาอะไร:** นี่คือสมการที่ใช้ *เลือกค่า B/A* จริง ๆ — plot “ผลต่าง downforce หน้า-หลัง” เทียบกับ B/A (เหมือน Fig. 9–10 ของสิทธิบัตร) แล้วเลือกจุดที่ผลต่าง ≈ 0 ซึ่งมักตกราว B/A ≈ 1.4–1.5 [2][4]

### ขั้นที่ 7 — เงื่อนไข Anti-Rear-Up ตอนชนสิ่งกีดขวาง
จำลองแรงที่ล้อชนขอบ (แรงแนวราบ + แนวดิ่งที่ contact point เยื้องจากศูนย์ล้อ) เขียน **สมดุลโมเมนต์รอบ pivot ฝั่งหน้า (70, 80)**:

```
M_obstacle = F_contact × (แขนโมเมนต์เยื้องศูนย์)
```

เทียบว่าโมเมนต์นี้ “ดันแขนให้ยุบ” มากกว่า “งัดตัวถังให้เชิด” หรือไม่
**พิจารณาอะไร:** ถ้าใช้แขนเดี่ยว (single-arm) โมเมนต์นี้มักงัดตัวถังขึ้น; four-bar ที่ B>A เพิ่มโมเมนต์ที่ pivot หน้า ทำให้แขนยุบก่อน → ตัวถังไม่เชิด → cliff sensor ไม่ลวง เปรียบเทียบสองแบบด้วยสมการนี้เพื่อพิสูจน์ข้อได้เปรียบ

### ขั้นที่ 8 — ความถี่ธรรมชาติ / การสั่น (Ride Frequency)
ตรวจความนุ่ม-แข็งของช่วงล่างด้วย:

```
f_n = (1 / 2π) · √(k_wheel / m_sprung_per_wheel)
```

**พิจารณาอะไร:** สำหรับหุ่นดูดฝุ่นไม่ได้เน้น ride comfort แต่ f_n ช่วยเช็คว่าล้อ “ตามพื้น” ทันไหมและไม่เด้งจนหัวดูดลอย — เลือก k_wheel (จากขั้น 4) และ damping ให้เหมาะ [3][8]

### ขั้นที่ 9 — การตรวจสอบ (Verification)
1. **Loop-equation / analytic** ใน Python (numpy) หรือ MATLAB — ยืนยัน position, MR, IC [5]
2. **Multibody dynamics (MBD)** — MSC ADAMS หรือ ADAMS/Car จำลอง reaction torque + obstacle จริง (งานวิจัยส่วนใหญ่ตรวจด้วย ADAMS) [2][4][6]
3. เทียบผล analytic vs. MBD เพื่อจับ error ทางเรขาคณิต [10 → Ziemba et al.]

---

## 6. เอกสารอ้างอิง (References)

**สิทธิบัตรหลัก**
- GB 2611795 A — *A robotic vacuum cleaner*, Dyson Technology Ltd., 2023. (ต้นฉบับที่รีวิว)
- Prior art ที่ควรอ่านต่อ: DE 102018117740 A1, DE 102008029445 A1, US 2019/0193499 A1

**งานวิจัย (ค้นจากฐานข้อมูล peer-reviewed)**

[1] [Analytical Derivation and Analysis of Vertical and Lateral Installation Ratios for Swing Axle, McPherson and Double Wishbone Suspension Architectures](https://consensus.app/papers/details/2daf0c15c36a547e9781d16cd9a1a836/?utm_source=claude_desktop) (Bucchi et al., 2022, Actuators) — ที่มาของสูตร installation/motion ratio จากเรขาคณิต + instant center/roll center

[2] [Dynamic modeling and analysis of a four-bar mechanism for automobile applications](https://consensus.app/papers/details/ca742b4a499c59a6b1d7f2ec7b4c5482/?utm_source=claude_desktop) (Khan et al., 2020, ICECCE) — จำลอง four-bar สำหรับช่วงล่างรถ (MATLAB + ADAMS)

[3] [Instant Center Identification of Single-Loop Multi-DOF Planar Linkage Using Virtual Link](https://consensus.app/papers/details/9d73c7f89b735687be7895d88ed197af/?utm_source=claude_desktop) (Nie et al., 2021, Applied Sciences) — วิธีหา instant center (Aronhold–Kennedy)

[4] [A new method of identification of equivalent suspension and damping rates of full-vehicle model](https://consensus.app/papers/details/6f096a2233e754cdb4c91eab778f1c1a/?utm_source=claude_desktop) (Zhou et al., 2018, Vehicle System Dynamics) — แปลงกลไกช่วงล่างเป็น equivalent spring/damper rate ด้วย screw theory

[5] [Computer Grafoanalytic Kinematical Analysis for Four-Bar Linkage Mechanism](https://consensus.app/papers/details/91de2ef9acb95e80a6128bdd0bc65062/?utm_source=claude_desktop) (Marinov, 2025) — จลนศาสตร์ four-bar (ความเร็ว/ความเร่ง) เชิงคำนวณ

[6] [Derivation of the Three-Dimensional Installation Ratio for Dual A-Arm Suspensions](https://consensus.app/papers/details/4118c0fcdba8590c9f751fdfb3c7f4da/?utm_source=claude_desktop) (Manes et al., 2004) — installation ratio 3 มิติ + wheel rate จาก geometry

[7] [Design, modeling and simulation of suspension geometry for formula student vehicles](https://consensus.app/papers/details/07b16324480156239a716017b060163f/?utm_source=claude_desktop) (Chauhan et al., 2020, Materials Today: Proceedings) — ตัวอย่างการคำนวณ motion ratio → spring travel เชิงปฏิบัติ

**ตำราอ้างอิงพื้นฐาน (แนะนำสำหรับลงมือคำนวณ)**
- R. L. Norton, *Design of Machinery* — four-bar position/velocity analysis, Freudenstein equation
- Uicker, Pennock & Shigley, *Theory of Machines and Mechanisms* — instant center, Aronhold–Kennedy
- W. & D. Milliken, *Race Car Vehicle Dynamics* — motion ratio, wheel rate, anti-features (anti-dive/squat)
- T. Gillespie, *Fundamentals of Vehicle Dynamics* — ride frequency, suspension basics

---

## 7. ข้อควรระวัง / ขั้นต่อไปสำหรับงานออกแบบจริง

1. **ยืนยันหน่วยค่าสปริง** (0.96 “N/m” น่าจะเป็น N/mm) จาก PDF ต้นฉบับก่อนคำนวณ downforce
2. **ปรับสเกลตามมวลหุ่นของคุณ** — ค่า Dyson (ล้อ 86 mm) เหมาะกับหุ่นบางเตี้ย ถ้าหุ่นคุณหนัก/ล้อใหญ่กว่า ต้อง scale k_spring, preload และ B, A ใหม่ (คงอัตราส่วน B/A ~1.4–1.5 ไว้เป็นจุดตั้งต้น)
3. **เริ่มจาก B/A ≈ 1.43** แล้วค่อย optimize ด้วยขั้นที่ 6 (downforce สมมาตร) และขั้นที่ 7 (anti-rear-up) ให้เข้ากับ reaction torque ของมอเตอร์+เกียร์จริงของคุณ
4. **ตรวจ 2 ทิศทางเสมอ** (เดินหน้า/ถอยหลัง) เพราะจุดขายของกลไกนี้คือความสมมาตรของ downforce
5. ถ้าต้องการ ผมช่วยต่อได้: (ก) สร้างสคริปต์ Python คำนวณ position/MR/IC ของ four-bar, (ข) แทนค่าตัวเลขจริงเมื่อคุณให้สเปกหุ่น, หรือ (ค) วาดไดอะแกรมกลไกอธิบายจุดหมุน
