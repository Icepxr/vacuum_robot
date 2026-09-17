# artboard 6: ผังการไหลของข้อมูล หุ่น → แดชบอร์ด (สรุปภาพจาก data_flow_หุ่นถึงแดชบอร์ด.md)
from gen import icon, chip, FONT, CSS
import json, gen2  # gen2 สร้าง canvas.json 5 หน้า — ไฟล์นี้เขียนทับด้วย 6 หน้า

def stage(n, title, where, lines, tag, tagk, ic, ink, tint, w=200):
    li = "".join(f'<li style="margin:0;padding:0">{l}</li>' for l in lines)
    return f'''<div style="width:{w}px;flex:none;background:#FFFFFF;border:1px solid #E3E8E3;border-radius:14px;padding:14px 14px 12px;display:flex;flex-direction:column;gap:8px">
  <div style="display:flex;align-items:center;gap:8px"><div style="width:26px;height:26px;border-radius:50%;background:#123D2C;color:#FFFFFF;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center">{n}</div><div style="width:28px;height:28px;border-radius:8px;background:{tint};color:{ink};display:flex;align-items:center;justify-content:center">{icon(ic,15)}</div></div>
  <div style="display:flex;flex-direction:column;line-height:1.25"><div style="font-weight:700;font-size:14px">{title}</div><div style="color:#64736B;font-size:11px">{where}</div></div>
  <ul style="margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:4px;font-size:12px;color:#17231D">{li}</ul>
  <div style="margin-top:auto">{chip(tag,tagk)}</div>
</div>'''

def arrow(label, w=54):
    return f'''<div style="width:{w}px;flex:none;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding-top:38px">
  {icon("arrow",22,"#1F8A5B")}<div style="font-size:10px;color:#64736B;text-align:center;line-height:1.2;font-family:ui-monospace,Menlo,monospace">{label}</div></div>'''

E="#B7791F"; ET="#FBF1DF"; G="#166A45"; GT="#E6F4EC"; B="#28599B"; BT="#E7EFFB"; M="#5B6A62"; MT="#EEF1EE"

field_box = f'''
<div style="position:absolute;left:236px;top:78px;width:706px;height:396px;border:2px dashed #C9DCD1;border-radius:18px;pointer-events:none"></div>
<div style="position:absolute;left:252px;top:66px;background:#F4F6F3;padding:0 8px;font-size:12px;font-weight:700;color:#64736B;display:flex;align-items:center;gap:6px">{icon("robot",14,"#64736B")}สนาม · hotspot MRC-001 · ไม่มีอินเทอร์เน็ต</div>
<div style="position:absolute;left:1000px;top:66px;background:#F4F6F3;padding:0 8px;font-size:12px;font-weight:700;color:#64736B">แล็บ / คลาวด์ · มีอินเทอร์เน็ต</div>
'''

stages = [
  stage("0","ทะเบียนมิเตอร์","ARIA → Pi · scp ตอนอยู่แล็บ",
        ["<code>meters.json</code>","meter_id · room · type","digits · decimals","waypoint · lift_mm (auto)","<code>registry_version</code>"],
        "ต้องเพิ่ม","warn","grid",B,BT,w=180),
  arrow("ทางเดียวที่ข้อมูล<br>ไหลลงหุ่น"),
  stage("1","ESP32 → Pi","UART · หน้าต่าง 5 s",
        ["<code>#E CAPTURE_REQ,n</code>","→ <code>$K,n,1</code> ทันทีที่ภาพลง SD","หุ่นรู้แค่ 'ครั้งที่ n'","ไม่รู้/ไม่ต้องรู้ว่ามิเตอร์ไหน"],
        "มีแล้ว · ไม่แก้","ok","bolt",E,ET,w=190),
  arrow("$K ก่อน OCR"),
  stage("2","Pi ถ่าย → OCR → แถว","capture_daemon · meter_reader",
        ["<code>images/&lt;id&gt;.jpg</code> 316 kB (อยู่บน Pi)","OCR → <code>value · confidence</code>","<b>+ crop</b> <code>crops/&lt;id&gt;.jpg</code> ~30 kB","<b>+ meter_id</b> จากที่เลือกบน cockpit","<b>+ registry_version · device_id · retake_of</b>","→ <code>readings.jsonl</code> + fsync"],
        "มี 13 ฟิลด์ · เพิ่ม 4","warn","camera",G,GT,w=250),
  arrow("WS"),
  stage("3","cockpit /drive","เบราว์เซอร์คนขับ",
        ["เห็นค่า + crop ทันที","เลือก 'มิเตอร์ที่เลือกอยู่'","ปุ่ม <b>ถ่ายใหม่</b> → แถวใหม่ <code>retake_of</code>","ไม่แตะ status (ของผู้ให้เช่า)"],
        "มี WS · เพิ่มปุ่ม","warn","check",G,GT,w=190),
]
stages2 = [
  stage("4","sync_supabase.py","Pi · ตอนมีเน็ต (timer 5 นาที)",
        ["เฉพาะแถว <code>synced_at</code> ว่าง","<b>crop → Storage ก่อน</b> แล้ว upsert แถว","payload 8 ฟิลด์ <b>+ 6</b>","<b>ไม่ส่ง</b> status / confirmed_value","service key · idempotent ด้วย local_id"],
        "มี 8 ฟิลด์ · เพิ่ม","warn","send",B,BT,w=230),
  arrow("HTTPS upsert"),
  stage("5","Supabase","Postgres + Storage",
        ["<code>meter_readings</code> ← หุ่นเขียน","<code>reading_events</code> ← คนเขียน (append-only)","trigger → cache <code>status · confirmed_value</code>","<code>meters · tenants · rates · invoices</code>","constraint: ค่าใหม่ ≥ งวดก่อน"],
        "มี 1 ตาราง · เพิ่ม 7","warn","grid",M,MT,w=250),
  arrow("RLS · auth<br>ผู้ให้เช่า"),
  stage("6","ARIA web","เบราว์เซอร์ผู้ให้เช่า",
        ["อ่านผ่าน view ต่อหน้า","ยืนยัน → insert event","บิล = Δconfirmed × อัตราของงวด","ห้ามเขียน meter_readings ตรง"],
        "ต้องสร้าง","bad","home",G,GT,w=200),
  arrow("state=ready"),
  stage("7","ส่งอีเมล","Edge Function · server-side",
        ["ต่อฉบับ: ส่ง → log → หน่วง 2–5 s","แนบ crop 2 รูป ~60 kB","ล้มฉบับไหน log แล้วไปต่อ","auth Gmail [ยังไม่ตัดสินใจ]"],
        "ต้องสร้าง","bad","mail",B,BT,w=200),
]

legend = f'''<div style="display:flex;gap:18px;align-items:center;font-size:12px;color:#64736B;flex-wrap:wrap">
  {chip("มีแล้ว","ok")}<span>รันได้วันนี้ ไม่แก้</span>{chip("เพิ่ม","warn")}<span>ต่อจากของเดิม</span>{chip("ต้องสร้าง","bad")}<span>หลัง 22 ก.ย.</span>
  <span style="margin-left:auto;display:flex;align-items:center;gap:6px">{icon("alert",14,"#8A5A12")}รอตัดสิน D1 ใครแปะ meter_id · D2 ตัวเรียก sync · D3 append-only · D4 auth Gmail · D5 เวลาบน Pi</span>
</div>'''

rule = f'''<div style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:12px">
  <div style="background:#FFFFFF;border:1px solid #E3E8E3;border-radius:12px;padding:12px 14px;font-size:12px"><div style="font-weight:700;font-size:13px;margin-bottom:4px">หุ่นเขียนได้แค่ "สิ่งที่มันเห็น"</div><code>value · confidence · raw_text · รูป · meter_id ที่คนขับเลือก</code> — ห้ามเขียน <code>status</code>/<code>confirmed_value</code> เป็นอย่างอื่นนอกจาก default</div>
  <div style="background:#FFFFFF;border:1px solid #E3E8E3;border-radius:12px;padding:12px 14px;font-size:12px"><div style="font-weight:700;font-size:13px;margin-bottom:4px">คนเขียน "สิ่งที่ยืนยัน" เป็น event ใหม่เสมอ</div>ยืนยัน / แก้ / ปฏิเสธ / ผูกห้อง = 1 แถวใน <code>reading_events</code> · ไม่มีการเขียนทับ · บิลอ้าง event ล่าสุด</div>
  <div style="background:#FFFFFF;border:1px solid #E3E8E3;border-radius:12px;padding:12px 14px;font-size:12px"><div style="font-weight:700;font-size:13px;margin-bottom:4px">พังตรงไหน ข้อมูลอยู่บน SD</div>ไม่มีเน็ต = กองไว้ · sync ซ้ำไม่ซ้ำแถว (upsert) · crop ล้ม = แถวไปก่อน <code>crop_path=null</code> · ต้นฉบับ 36 MB/รอบ อยู่บน Pi · crop 3.4 MB/รอบ ขึ้นคลาวด์ (ไฟล์ 20 §20.7)</div>
</div>'''

html = f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  {FONT}
  <style>{CSS} code{{font-family:ui-monospace,Menlo,monospace;font-size:11px;background:#F4F6F3;padding:1px 4px;border-radius:4px}}</style>
</helmet>
<div style="position:relative;width:1440px;min-height:900px;background:#F4F6F3;padding:24px 28px 28px;display:flex;flex-direction:column;gap:18px">
  <header style="display:flex;flex-direction:column;gap:2px"><h1 style="margin:0;font-size:22px;font-weight:700">ผังการไหลของข้อมูล — หุ่น MRC-001 → แดชบอร์ด ARIA</h1><div style="color:#64736B;font-size:13px">ทางเดียว หุ่น → คลาวด์ · ยกเว้นทะเบียนมิเตอร์ที่ copy ลงหุ่นด้วยมือ · รายละเอียดใน <code>01_เอกสารโครงการ/data_flow_หุ่นถึงแดชบอร์ด.md</code></div></header>
  <div style="display:flex;gap:0;align-items:stretch">
    {"".join(stages[:2])}
    <div style="position:relative;display:flex;gap:0;align-items:stretch;border:2px dashed #C9DCD1;border-radius:18px;padding:22px 14px 14px">
      <div style="position:absolute;left:14px;top:-9px;background:#F4F6F3;padding:0 8px;font-size:12px;font-weight:700;color:#64736B;display:flex;align-items:center;gap:6px">{icon("robot",14,"#64736B")}สนาม · hotspot MRC-001 · ไม่มีอินเทอร์เน็ต</div>
      {"".join(stages[2:])}
    </div>
  </div>
  <div style="display:flex;gap:0;align-items:stretch;margin-left:250px;position:relative;border:2px dashed #C9DCD1;border-radius:18px;padding:22px 14px 14px;align-self:flex-start">
    <div style="position:absolute;left:14px;top:-9px;background:#F4F6F3;padding:0 8px;font-size:12px;font-weight:700;color:#64736B">แล็บ / คลาวด์ · มีอินเทอร์เน็ต · Pi กลับมาต่อ Ethernet</div>
    {"".join(stages2)}
  </div>
  {rule}
  {legend}
</div>
</x-dc>
</body>
</html>
'''
open("DataFlow.dc.html","w").write(html)

c = json.load(open("canvas.json"))
c["artboards"].append({"file":"DataFlow.dc.html","title":"6 · ผังการไหลของข้อมูล หุ่น → แดชบอร์ด","x":0,"y":2360,"w":1440,"h":900})
c["annotations"].append({"id":"flow-note","x":1560,"y":2360,"w":560,"text":"ผังนี้สรุปจาก data_flow_หุ่นถึงแดชบอร์ด.md §0–§2\nสีป้าย: เขียว = โค้ดที่รันได้วันนี้ · เหลือง = ต่อจากของเดิม (ควรทำก่อนแข่งเพื่อไม่ต้อง migrate) · แดง = สร้างใหม่หลัง 22 ก.ย.\nD1–D5 รอผู้ใช้ตัดสิน — อยู่ใน §4 ของเอกสาร"})
json.dump(c, open("canvas.json","w"), ensure_ascii=False, indent=2)
print("ok3")
