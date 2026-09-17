# หน้า 4–5: ห้องและมิเตอร์ · ตั้งค่า — ใช้ shell/ชิ้นส่วนร่วมจาก gen.py (import แล้ว gen.py จะสร้าง 3 หน้าแรกซ้ำ ไม่มีผลข้างเคียง)
from gen import *
import json

def field(label, value, placeholder=False, w="100%", note=""):
    col = "#9AA79F" if placeholder else "#17231D"
    n = f'<div style="color:#64736B;font-size:11px">{note}</div>' if note else ""
    return f'''<div style="display:flex;flex-direction:column;gap:4px;width:{w}">
  <label style="color:#64736B;font-size:12px">{label}</label>
  <div style="border:1px solid #D5DDD6;border-radius:10px;padding:9px 12px;font-size:14px;color:{col};background:#FFFFFF;min-height:40px;display:flex;align-items:center">{value}</div>{n}
</div>'''

# ───────────────────────── ห้องและมิเตอร์ ─────────────────────────
def rrow(room, floor, tenant, mail, w_id, e_id, last, status, sk, sel=False):
    bg = "background:#F1F8F4;" if sel else ""
    mailhtml = f'<span style="color:#64736B;font-size:12px">{mail}</span>' if mail else chip("ไม่มีอีเมล","info")
    t = f'<div style="display:flex;flex-direction:column;line-height:1.25"><span>{tenant}</span>{mailhtml}</div>' if tenant else '<span style="color:#9AA79F">— ว่าง</span>'
    def m(mid, ic, ink, ok=True):
        return f'<td style="padding:11px 12px;white-space:nowrap"><div style="display:flex;align-items:center;gap:6px">{icon(ic,14,ink)}<span style="font-family:ui-monospace,Menlo,monospace;font-size:13px">{mid}</span></div></td>'
    return f'''<tr style="border-top:1px solid #EEF1EE;{bg}">
  <td style="padding:11px 12px;white-space:nowrap"><div style="display:flex;flex-direction:column;line-height:1.25"><span style="font-weight:600">ห้อง {room}</span><span style="color:#64736B;font-size:12px">ชั้น {floor}</span></div></td>
  <td style="padding:11px 12px">{t}</td>
  {m(w_id,"drop","#2F6FBF")}{m(e_id,"bolt","#B7791F", room!="301")}
  <td style="padding:11px 12px;color:#64736B;font-size:13px;white-space:nowrap">{last}</td>
  <td style="padding:11px 12px">{chip(status,sk)}</td>
</tr>'''

def meter_card(ic, ink, tint, name, mid, serial, wp, digits, start, last):
    return f'''<div style="border:1px solid #E3E8E3;border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:10px">
  <div style="display:flex;align-items:center;gap:8px"><div style="width:28px;height:28px;border-radius:8px;background:{tint};color:{ink};display:flex;align-items:center;justify-content:center">{icon(ic,15)}</div><div style="font-weight:700;font-size:14px">{name}</div><span style="margin-left:auto;font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#64736B">{mid}</span></div>
  <div style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:8px">
    {field("หมายเลขบนตัวมิเตอร์", serial, serial.startswith("["))}
    {field("จุดจอดหุ่น (waypoint)", wp)}
    {field("จำนวนหลัก", digits)}
    {field("ค่าตอนผูกมิเตอร์ (เริ่มนับ)", start)}
  </div>
  <div style="display:flex;align-items:center;gap:8px;font-size:12px;color:#64736B">{icon("clock",13)}ยืนยันล่าสุด {last}<a href="#" style="margin-left:auto;font-weight:600;text-decoration:none;font-size:12px">เปลี่ยนมิเตอร์ใหม่ →</a></div>
</div>'''

rooms_body = f'''
<div style="display:grid;grid-template-columns:minmax(0, 1fr) 380px;gap:16px;flex:1;min-height:0">
  {card(f'''
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <div style="display:flex;align-items:center;gap:8px;border:1px solid #D5DDD6;border-radius:10px;padding:8px 10px;color:#9AA79F;font-size:13px;width:220px">{icon("search",15)}ค้นหาห้อง / ผู้เช่า / meter_id</div>
      <div style="display:flex;gap:8px">{chip("ทั้งหมด 48","mut")}{chip("มีผู้เช่า 46","ok")}{chip("ว่าง 2","mut")}{chip("ไม่มีอีเมล 2","info")}{chip("มิเตอร์ยังไม่เคยอ่านสำเร็จ 3","warn")}</div>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead><tr style="color:#64736B;font-size:12px;text-align:left">
        <th style="padding:6px 12px;font-weight:600">ห้อง</th><th style="padding:6px 12px;font-weight:600">ผู้เช่า</th>
        <th style="padding:6px 12px;font-weight:600">น้ำ</th><th style="padding:6px 12px;font-weight:600">ไฟ</th><th style="padding:6px 12px;font-weight:600">อ่านล่าสุด</th><th style="padding:6px 12px;font-weight:600">สถานะ</th></tr></thead>
      <tbody>
        {rrow("101","1","วราภรณ์ ใจดี","waraporn@example.com","W-101","E-101","16 ก.ย. 19:41","พร้อมออกบิล","ok")}
        {rrow("102","1","ศักดิ์ชัย แสนสุข","sakchai@example.com","W-102","E-102","16 ก.ย. 19:43","พร้อมออกบิล","ok")}
        {rrow("103","1","ธนพร พรมมา","thanaporn@example.com","W-103","E-103","16 ก.ย. 19:44","พร้อมออกบิล","ok")}
        {rrow("106","1",None,None,"W-106","E-106","16 ก.ย. 19:48","ว่าง · อ่านต่อแต่ไม่ออกบิล","mut")}
        {rrow("110","1","สุรเชษฐ์ จันทร์ดี",None,"W-110","E-110","16 ก.ย. 19:52","ต้องกรอกอีเมล","info")}
        {rrow("204","2","สมชาย ใจดี","somchai@example.com","W-204","E-204","16 ก.ย. 20:04","พร้อมออกบิล","ok",True)}
        {rrow("208","2","อรทัย บุญมี",None,"W-208","E-208","16 ก.ย. 20:08","ต้องกรอกอีเมล","info")}
        {rrow("301","3","ปรีชา วงศ์ดี","preecha@example.com","W-301","E-301","ผูกใหม่ 10 ก.ย.","รอหุ่นอ่านครั้งแรก","warn")}
      </tbody>
    </table>
    <div style="color:#64736B;font-size:12px;margin-top:auto">แสดง 8 จาก 48 ห้อง · ห้องว่างยังให้หุ่นอ่านต่อ เพื่อไม่ให้ค่างวดก่อนขาดตอนเวลามีผู้เช่าใหม่</div>
  ''')}

  {card(f'''
    <div style="display:flex;align-items:center;gap:10px"><h2 style="margin:0;font-size:16px;font-weight:700">ห้อง 204</h2>{chip("ชั้น 2","mut")}<span style="margin-left:auto">{icon("x",18,"#9AA79F")}</span></div>
    <div style="display:flex;flex-direction:column;gap:8px">
      <div style="font-size:13px;font-weight:700">ผู้เช่า</div>
      {field("ชื่อ","สมชาย ใจดี")}
      {field("อีเมลรับบิล","somchai@example.com", note="ระบบส่งบิลไปที่นี่เท่านั้น ไม่มี = ออกบิลได้แต่ส่งไม่ได้")}
      <div style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:8px">{field("เข้าอยู่","1 มี.ค. 2568")}{field("ค่ามิเตอร์วันเข้าอยู่ (น้ำ/ไฟ)","1,180 / 4,102")}</div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px">
      <div style="font-size:13px;font-weight:700">มิเตอร์ 2 ตัว</div>
      {meter_card("drop","#2F6FBF","#E7EFFB","น้ำ","W-204","[หมายเลขบนตัวมิเตอร์]","WP-24 · เสายก 1,120 mm","5 หลัก + 3 ทศนิยม","1,180 (1 มี.ค. 2568)","16 ก.ย. 20:04 · 1,021")}
      {meter_card("bolt","#B7791F","#FBF1DF","ไฟ","E-204","[หมายเลขบนตัวมิเตอร์]","WP-25 · เสายก 1,650 mm","5 หลัก + 1 ทศนิยม","4,102 (1 มี.ค. 2568)","15 ส.ค. 21:10 · 4,891")}
    </div>
    <div style="display:flex;gap:10px;margin-top:auto">{btn("บันทึก","primary")}{btn("ย้ายออก / ห้องว่าง","ghost")}</div>
  ''',"padding:16px 18px")}
</div>
'''
open("Rooms.dc.html","w").write(shell("grid","ห้องและมิเตอร์","ทะเบียนที่ผูก meter_id ↔ ห้อง ↔ อีเมลผู้เช่า · 48 ห้อง · 96 มิเตอร์", rooms_body,
  f'{btn("นำเข้า CSV","ghost")}{btn("เพิ่มห้อง","primary")}'))

# ───────────────────────── ตั้งค่า ─────────────────────────
def subnav(active):
    items = [("อัตราค่าน้ำ-ไฟ","rate"),("อีเมล","mail"),("ข้อมูลหอพัก","home"),("พื้นที่เก็บรูป","image")]
    out = []
    for label,key in items:
        on = key==active
        out.append(f'<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;font-size:14px;font-weight:{600 if on else 500};{"background:#E6F4EC;color:#166A45;" if on else "color:#17231D;"}">{icon("bill" if key=="rate" else key,17)}{label}</div>')
    return f'<nav style="display:flex;flex-direction:column;gap:4px;width:220px;flex:none">{"".join(out)}</nav>'

def rate_row(ic, ink, name, rate, since, until, status, sk, dim=False):
    c = "color:#9AA79F;" if dim else ""
    return f'''<tr style="border-top:1px solid #EEF1EE;{c}">
  <td style="padding:11px 12px"><div style="display:flex;align-items:center;gap:8px">{icon(ic,15,ink)}<span style="font-weight:600">{name}</span></div></td>
  <td style="padding:11px 12px;font-weight:700;font-size:16px">{rate} <span style="font-size:12px;font-weight:500;color:#64736B">฿/หน่วย</span></td>
  <td style="padding:11px 12px">{since}</td><td style="padding:11px 12px;color:#64736B">{until}</td>
  <td style="padding:11px 12px">{chip(status,sk)}</td>
</tr>'''

settings_body = f'''
<div style="display:flex;gap:16px;flex:1;min-height:0">
  {subnav("rate")}
  <div style="display:flex;flex-direction:column;gap:16px;flex:1;min-width:0">
    {card(f'''
      <div style="display:flex;align-items:center;gap:10px"><h2 style="margin:0;font-size:16px;font-weight:700">อัตราค่าน้ำ-ไฟ พร้อมวันมีผล</h2><span style="color:#64736B;font-size:13px">บิลของงวดไหนใช้อัตราที่มีผล ณ วันตัดรอบของงวดนั้น · แถวเก่าแก้ไม่ได้ เพิ่มแถวใหม่แทน</span></div>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <thead><tr style="color:#64736B;font-size:12px;text-align:left"><th style="padding:6px 12px;font-weight:600">ประเภท</th><th style="padding:6px 12px;font-weight:600">อัตรา</th><th style="padding:6px 12px;font-weight:600">มีผลตั้งแต่</th><th style="padding:6px 12px;font-weight:600">สิ้นผล</th><th style="padding:6px 12px;font-weight:600">สถานะ</th></tr></thead>
        <tbody>
          {rate_row("bolt","#B7791F","ไฟ","8","1 มิ.ย. 2569","—","ใช้อยู่","ok")}
          {rate_row("drop","#2F6FBF","น้ำ","18","1 ม.ค. 2569","—","ใช้อยู่","ok")}
          {rate_row("bolt","#B7791F","ไฟ","7","1 ม.ค. 2568","31 พ.ค. 2569","สิ้นผลแล้ว · ใช้กับบิล ม.ค. 68–พ.ค. 69","mut",True)}
          {rate_row("drop","#2F6FBF","น้ำ","16","1 ม.ค. 2568","31 ธ.ค. 2568","สิ้นผลแล้ว","mut",True)}
        </tbody>
      </table>
    ''')}
    {card(f'''
      <h2 style="margin:0;font-size:15px;font-weight:700">เพิ่มอัตราใหม่</h2>
      <div style="display:grid;grid-template-columns:160px 160px 200px minmax(0, 1fr);gap:12px;align-items:end">
        {field("ประเภท","ไฟ")}
        {field("อัตรา (฿/หน่วย)","8.50")}
        {field("มีผลตั้งแต่","1 ต.ค. 2569", note="ต้องเป็นวันตัดรอบในอนาคต")}
        <div style="display:flex;gap:10px">{btn("เพิ่มอัตรา","primary")}</div>
      </div>
      <div style="display:flex;align-items:flex-start;gap:10px;background:#FBF1DF;border-radius:12px;padding:12px 14px;color:#8A5A12;font-size:13px">{icon("alert",18)}<div>อัตรานี้จะใช้กับบิลงวด <b>ตุลาคม 2569</b> เป็นต้นไป · บิลกันยายนที่ยังไม่ส่ง<b>ยังคิดที่ 8 ฿</b> · ระบบจะแจ้งผู้เช่าในอีเมลบิลงวดถัดไปว่าอัตราเปลี่ยน</div></div>
    ''')}
    <div style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:16px">
      {card(f'''
        <div style="display:flex;align-items:center;gap:8px"><h2 style="margin:0;font-size:15px;font-weight:700">อีเมลผู้ส่ง</h2>{chip("ยังไม่ยืนยันวิธีล็อกอิน","warn")}</div>
        {field("ส่งจาก","[อีเมลผู้ให้เช่า]@gmail.com",True)}
        {field("วิธียืนยันตัวตน","[ยังไม่ตัดสินใจ: App Password (ต้องเปิด 2FA) / OAuth2]",True, note="ห้ามใช้รหัสผ่านบัญชีตรงๆ — ต้องเช็คเอกสาร Google ก่อนเขียนโค้ด (ไฟล์ 20 §20.4)")}
        <div style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:8px">{field("หน่วงระหว่างฉบับ","3 วินาที", note="48 ห้อง ≈ 2 นาที 24 วิ")}{field("แนบรูป crop มิเตอร์","เปิด · 2 รูป/ฉบับ")}</div>
        {field("หัวข้ออีเมล","ค่าน้ำ-ค่าไฟ ห้อง {ห้อง} งวด {เดือน} — [ชื่อหอพัก]")}
        <div style="display:flex;gap:10px">{btn("ส่งทดสอบถึงตัวเอง","ghost","mail")}{btn("บันทึก","primary")}</div>
      ''')}
      <div style="display:flex;flex-direction:column;gap:16px">
        {card(f'''
          <h2 style="margin:0;font-size:15px;font-weight:700">ข้อมูลหอพัก</h2>
          {field("ชื่อหอพัก","[ชื่อหอพัก]",True)}
          <div style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:8px">{field("วันตัดรอบบิล","วันที่ 1 ของเดือน")}{field("จำนวนห้อง","48 (จากทะเบียน)")}</div>
        ''')}
        {card(f'''
          <div style="display:flex;align-items:center;gap:8px"><h2 style="margin:0;font-size:15px;font-weight:700">พื้นที่เก็บรูป</h2><span style="color:#64736B;font-size:12px">ตัวจำกัดจริงของระบบ (ไฟล์ 20)</span></div>
          <div style="display:flex;flex-direction:column;gap:6px">
            <div style="display:flex;justify-content:space-between;font-size:13px"><span>crop บนคลาวด์</span><span style="font-weight:600">61 MB / 1 GB</span></div>
            <div style="height:6px;background:#EEF1EE;border-radius:4px;overflow:hidden"><div style="width:6%;height:100%;background:#1F8A5B;border-radius:4px"></div></div>
            <div style="display:flex;justify-content:space-between;font-size:13px;margin-top:6px"><span>ต้นฉบับ 1080p บน Pi</span><span style="font-weight:600">2.3 GB / 20 GB</span></div>
            <div style="height:6px;background:#EEF1EE;border-radius:4px;overflow:hidden"><div style="width:12%;height:100%;background:#1F8A5B;border-radius:4px"></div></div>
            <div style="color:#64736B;font-size:12px;margin-top:4px">ที่อัตรานี้ คลาวด์พอ ~12 ปี · Pi พอ ~23 ปี (48 ห้อง)</div>
          </div>
        ''')}
      </div>
    </div>
  </div>
</div>
'''
open("Settings.dc.html","w").write(shell("gear","ตั้งค่า","อัตรา (พร้อมวันมีผล) · อีเมลผู้ส่ง · ข้อมูลหอพัก · พื้นที่เก็บรูป", settings_body))

json.dump({
  "artboards":[
    {"file":"Main.dc.html","title":"1 · หน้าหลัก — สถานะรอบบิล","x":0,"y":0,"w":1440,"h":1000},
    {"file":"Confirm.dc.html","title":"2 · ยืนยันค่ามิเตอร์ (หน้าที่ใช้ทุกเดือน)","x":1560,"y":0,"w":1440,"h":1000},
    {"file":"Bills.dc.html","title":"3 · บิล + ส่งอีเมล","x":3120,"y":0,"w":1440,"h":1000},
    {"file":"Rooms.dc.html","title":"4 · ห้องและมิเตอร์ (ทะเบียน meter_id)","x":0,"y":1180,"w":1440,"h":1000},
    {"file":"Settings.dc.html","title":"5 · ตั้งค่า — อัตราพร้อมวันมีผล / อีเมล","x":1560,"y":1180,"w":1440,"h":1000}
  ],
  "annotations":[
    {"id":"scope","x":0,"y":-260,"w":700,"text":"ARIA หลังบ้าน (ฝั่งคลาวด์ · C23) — mockup นิ่ง 5 หน้า\nเก็บ: หน้าหลัก · ยืนยันค่ามิเตอร์ · บิล · ห้องและมิเตอร์ · ตั้งค่า (อัตรา+วันมีผล / อีเมล)\nตัดจาก DormPlus: สัญญาเช่า · แจ้งซ่อม · ข้อความ · รายงาน · การเงินรวม · เมนูด่วน · Premium · แบนเนอร์\nตัวเลขทั้งหมดในภาพเป็นตัวอย่าง (sample) — [วงเล็บ] คือค่าที่ต้องกรอกจริง"},
    {"id":"rule-confirm","x":1560,"y":-160,"w":600,"text":"กติกาในหน้านี้ที่มาจาก schema ที่ล็อกไว้:\n• value (OCR) กับ confirmed_value คนละคอลัมน์ · ประวัติ append-only\n• มิเตอร์ย้อนกลับไม่ได้ → ห้ามยืนยันค่าที่น้อยกว่างวดก่อน\n• คิวเรียง ผิดปกติ → ไม่มั่นใจ → ปกติ ให้เจอของที่ทำให้บิลผิดก่อน"},
    {"id":"rule-bills","x":3120,"y":-160,"w":600,"text":"บิลคิดจาก confirmed_value × อัตราที่มีผล ณ งวดนั้น (ไม่ใช่อัตราวันนี้)\nส่งได้เฉพาะแถวที่ยืนยันครบ 2 มิเตอร์ + มีอีเมล · หน่วง 2–5 s/ฉบับ ตามไฟล์ 20 §20.4"},
    {"id":"rule-rooms","x":0,"y":1020,"w":700,"text":"ทะเบียนมิเตอร์: 1 ห้อง = 2 meter_id (W-xxx / E-xxx) · เก็บ waypoint + ความสูงเสายก ต่อมิเตอร์ ให้หุ่นใช้\n\"เปลี่ยนมิเตอร์ใหม่\" = ปิด meter_id เดิมด้วยค่าสุดท้าย แล้วเปิด meter_id ใหม่ด้วยค่าเริ่มนับ → บิลเดือนนั้น = (เดิมสุดท้าย − เดิมงวดก่อน) + (ใหม่ตอนนี้ − ใหม่เริ่มนับ)\nนี่คือข้อยกเว้นเดียวของกติกา \"ค่าใหม่ต้อง ≥ งวดก่อน\"\nห้องว่างยังให้หุ่นอ่านต่อ (ไม่ออกบิล) เพื่อไม่ให้ค่างวดก่อนขาดตอน"},
    {"id":"rule-settings","x":1560,"y":1060,"w":600,"text":"อัตรา = ตาราง append-only มีวันมีผล/สิ้นผล (ข้อ 3 ของ C23) · เพิ่มได้เฉพาะวันตัดรอบในอนาคต\nวิธีล็อกอิน Gmail [ยังไม่ตัดสินใจ] — ต้องเช็คเอกสาร Google ก่อนเขียนโค้ด"}
  ],
  "launch":{"view":"canvas"}
}, open("canvas.json","w"), ensure_ascii=False, indent=2)
print("ok2")
