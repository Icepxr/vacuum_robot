# CAD simulation — scissor assembly 2026-10-02

ชุดนี้ตรวจ CAD ที่ export อยู่ใน `05_CAD/` โดยไม่แก้ไฟล์ต้นฉบับ `.f3d/.f3z/.step/.stl`

## วิธีรัน

```powershell
python 05_CAD\simulation\cad_mesh_audit.py
python 05_CAD\simulation\step_bom.py "05_CAD\scissorPart\assembly\arm assembly.step" --output "05_CAD\simulation\results\step_bom.csv"
python 05_CAD\simulation\scissor_full_sim.py
```

ไฟล์ผลอยู่ใน `05_CAD/simulation/results/`:

- `mesh_audit.csv/json` — ขนาด, ปริมาตร, solid PETG mass proxy และ mesh health ของ STL ทุกไฟล์
- `arm_assembly_components.csv` — 143 connected shells ของ assembly
- `step_bom.csv` — BOM 91 occurrences จาก STEP
- `scissor_simulation_summary.json` — ผลรวมที่โปรแกรมอ่านต่อได้
- `servo_torque_cases.csv` — แรงบิดกรณี 1/2 servo และมวลปลายบน 3 กรณี
- `base_plate_beam_check.csv` — beam proxy ของฐานหนา 2–6 mm
- `stability_sensitivity.csv` — ความไวของ CoG/การพลิกต่อมวลเสา 0.50–0.90 kg
- PNG — ภาพตรวจ geometry และกราฟผล simulation

## ขอบเขต

เป็น analytical simulation ที่ผูกกับขนาดและปริมาตรจาก CAD export จริง แต่ไม่ใช่ nonlinear/contact FEA ไฟล์ STL/STEP ไม่มี print settings, Fusion joints, contact set และวัสดุชิ้นพิมพ์ จึงยังต้องยืนยันรูหมุด, รอยเทเปอร์, ฟันเฟือง และฐานยึดใน Fusion/solver หลังแก้ mesh non-manifold และกำหนด boundary conditions แล้ว
