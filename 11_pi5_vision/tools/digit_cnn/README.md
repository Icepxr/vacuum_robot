# digit_cnn — เทรน/ประเมินตัวอ่านเลขรายช่องของกล่อง REAI

ผลและเหตุผลทั้งหมด: `08_การคำนวณ/26_ทดสอบโมเดล_YOLO_อ่านมิเตอร์.md` §26.5–26.8
ใช้งานจริงบน Pi ไม่ต้องใช้ไฟล์ในโฟลเดอร์นี้ — ใช้แค่ `src/reai_strip.py` `src/cellread.py` `src/models/digitnet.onnx`

ต้องใช้ venv แยก (Python 3.11 · torch · onnx · pillow · opencv) ไม่ใช่ venv ของ Pi · รันในโฟลเดอร์นี้:

```
python fonts.py                         # ฟอนต์ระบบ macOS → fonts.json (train / holdout)
# ตัวอ่าน (0–9/ว่าง) → src/models/digitnet.onnx
python gen_train_reader.py 200000 0 train.npz && python gen_train_reader.py 20000 5000000 val.npz   # ~3 นาทีบน M2
python train.py 12 11                   # 12 epoch · 11 คลาส · ~13 นาที (MPS) → digitnet.onnx
# ตัวคัดกรองแถวขยะ (มีคลาส "ไม่ใช่ตัวเลข") → src/models/digitcheck.onnx
python gen_train_check.py 220000 0 train.npz && python gen_train_check.py 20000 5000000 val.npz
python train.py 12 12                   # → digitnet.onnx แล้วเปลี่ยนชื่อเป็น digitcheck.onnx
python eval_full.py                     # ต้องมี pi/images/ (รูปจาก ~/mrc/data/images) + synth*_gt.json + popup_crop.png
```

`synth1.py` / `synth2.py` สร้างชุดทดสอบโดยวาดเลขลงในช่องจริงของรูปจาก Pi (`pi/images/`)

ทำไมสองโมเดล (7 ต.ค.): ใส่คลาส "ไม่ใช่ตัวเลข" ในตัวอ่านตัวเดียวทำให้กล่อง REAI แย่ลง 92→83 % / 95→88 % (กินเลข 6/7 ลายมือและ 0/8 แบบ 7-seg)
แต่ช่วยตัดแถวขยะในทางสำรองได้หมด → ให้ตัวอ่านอ่าน · ตัวคัดกรองตัดสินแค่ว่า "แถวนี้เป็นตัวเลขจริงไหม" (ไฟล์ 26 §26.10)
