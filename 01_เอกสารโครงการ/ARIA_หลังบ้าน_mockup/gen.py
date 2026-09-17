# สร้างไฟล์ artboard 3 หน้า (Main / Confirm / Bills) โดยใช้ shell + sidebar ร่วมกัน
import textwrap

FONT = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;500;600;700&display=swap">'

CSS = """
body{margin:0;background:#F4F6F3;color:#17231D;font-family:"IBM Plex Sans Thai","Noto Sans Thai",-apple-system,"Segoe UI",sans-serif;font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
a{color:#1F8A5B}a:hover{color:#166A45}
*{box-sizing:border-box}
"""

def icon(name, size=18, color="currentColor"):
    p = {
    "home":'<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "check":'<circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/>',
    "bill":'<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    "grid":'<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/>',
    "gear":'<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "drop":'<path d="M12 3s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11z"/>',
    "bolt":'<path d="M13 2L5 14h6l-1 8 8-12h-6z"/>',
    "alert":'<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    "camera":'<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13" r="3.5"/>',
    "mail":'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "robot":'<rect x="5" y="7" width="14" height="12" rx="2"/><path d="M12 3v4M9 12h.01M15 12h.01M9 16h6"/>',
    "arrow":'<path d="M5 12h14M13 6l6 6-6 6"/>',
    "chev":'<path d="M9 6l6 6-6 6"/>',
    "clock":'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "search":'<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "x":'<path d="M6 6l12 12M18 6L6 18"/>',
    "pen":'<path d="M4 20l4-1 10-10-3-3L5 16z"/>',
    "image":'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="16" cy="9" r="1.5"/>',
    "send":'<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>',
    }[name]
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="flex:none">{p}</svg>'

NAV = [("home","หน้าหลัก",None),("check","ยืนยันค่ามิเตอร์","21"),("bill","บิล",None),("grid","ห้องและมิเตอร์",None),("gear","ตั้งค่า",None)]

def sidebar(active):
    items = []
    for key,label,badge in NAV:
        on = key==active
        bg = "background:rgba(255,255,255,.14);color:#FFFFFF;" if on else "color:#C9DCD1;"
        b = f'<span style="margin-left:auto;background:#F3B54A;color:#2B1B00;font-size:11px;font-weight:700;padding:1px 7px;border-radius:10px">{badge}</span>' if badge else ""
        items.append(f'<div style="display:flex;align-items:center;gap:12px;padding:11px 14px;border-radius:10px;font-size:14px;font-weight:{600 if on else 500};{bg}">{icon(key,18)}<span>{label}</span>{b}</div>')
    return f'''
<aside style="width:232px;flex:none;background:#123D2C;display:flex;flex-direction:column;padding:22px 16px;gap:6px;min-height:100%">
  <div style="display:flex;align-items:center;gap:10px;padding:2px 6px 22px">
    <div style="width:34px;height:34px;border-radius:10px;background:#1F8A5B;display:flex;align-items:center;justify-content:center;color:#FFFFFF">{icon("robot",20)}</div>
    <div style="display:flex;flex-direction:column">
      <div style="color:#FFFFFF;font-weight:700;font-size:17px;letter-spacing:.04em">ARIA</div>
      <div style="color:#8FB3A1;font-size:11px">ระบบจัดการมิเตอร์และบิลหอพัก</div>
    </div>
  </div>
  {"".join(items)}
  <div style="margin-top:auto;background:rgba(255,255,255,.08);border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:3px">
    <div style="color:#FFFFFF;font-weight:600;font-size:13px">[ชื่อหอพัก]</div>
    <div style="color:#8FB3A1;font-size:12px">48 ห้อง · 96 มิเตอร์</div>
    <div style="color:#8FB3A1;font-size:12px;display:flex;align-items:center;gap:6px">{icon("robot",13,"#8FB3A1")}MRC-001 · ซิงก์ล่าสุด 20:12</div>
  </div>
</aside>'''

def topbar(title, sub, right=""):
    return f'''
<header style="display:flex;align-items:center;gap:16px;padding:0 0 18px">
  <div style="display:flex;flex-direction:column;gap:2px">
    <h1 style="margin:0;font-size:22px;font-weight:700;letter-spacing:-.01em">{title}</h1>
    <div style="color:#64736B;font-size:13px">{sub}</div>
  </div>
  <div style="margin-left:auto;display:flex;align-items:center;gap:12px">{right}
    <div style="display:flex;align-items:center;gap:10px;background:#FFFFFF;border:1px solid #E3E8E3;border-radius:12px;padding:6px 12px 6px 6px">
      <div style="width:30px;height:30px;border-radius:50%;background:#D7E9DE"></div>
      <div style="display:flex;flex-direction:column;line-height:1.2"><span style="font-size:13px;font-weight:600">[ชื่อผู้ให้เช่า]</span><span style="font-size:11px;color:#64736B">ผู้ให้เช่า</span></div>
    </div>
  </div>
</header>'''

def shell(active, title, sub, body, right=""):
    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  {FONT}
  <style>{CSS}</style>
</helmet>
<div style="display:flex;width:1440px;min-height:900px;background:#F4F6F3">
  {sidebar(active)}
  <main style="flex:1;display:flex;flex-direction:column;padding:24px 28px 28px;min-width:0">
    {topbar(title, sub, right)}
    {body}
  </main>
</div>
</x-dc>
</body>
</html>
'''

def chip(text, kind):
    c = {"ok":("#E6F4EC","#166A45"),"warn":("#FBF1DF","#8A5A12"),"bad":("#FBE7E7","#9B2C2C"),"info":("#E7EFFB","#28599B"),"mut":("#EEF1EE","#5B6A62")}[kind]
    return f'<span style="display:inline-flex;align-items:center;background:{c[0]};color:{c[1]};font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;white-space:nowrap">{text}</span>'

def card(inner, style=""):
    return f'<section style="background:#FFFFFF;border:1px solid #E3E8E3;border-radius:16px;padding:18px 20px;display:flex;flex-direction:column;gap:12px;{style}">{inner}</section>'

def btn(label, kind="primary", ic=None):
    s = {"primary":"background:#1F8A5B;color:#FFFFFF;border:1px solid #1F8A5B;",
         "ghost":"background:#FFFFFF;color:#17231D;border:1px solid #D5DDD6;",
         "danger":"background:#FFFFFF;color:#9B2C2C;border:1px solid #E8B4B4;"}[kind]
    i = icon(ic,16) if ic else ""
    return f'<button style="display:inline-flex;align-items:center;justify-content:center;gap:8px;height:40px;padding:0 16px;border-radius:10px;font:inherit;font-size:14px;font-weight:600;cursor:pointer;{s}">{i}{label}</button>'

# ───────────────────────── หน้าหลัก ─────────────────────────
def stat(label, big, sub, ic, tint, ink, extra=""):
    return f'''<div style="background:#FFFFFF;border:1px solid #E3E8E3;border-radius:16px;padding:16px 18px;display:flex;flex-direction:column;gap:8px">
  <div style="display:flex;align-items:center;gap:10px">
    <div style="width:34px;height:34px;border-radius:10px;background:{tint};color:{ink};display:flex;align-items:center;justify-content:center">{icon(ic,18)}</div>
    <div style="color:#64736B;font-size:13px">{label}</div>
  </div>
  <div style="font-size:30px;font-weight:700;letter-spacing:-.02em;line-height:1.1">{big}</div>
  {extra}
  <div style="color:#64736B;font-size:12px">{sub}</div>
</div>'''

progress = '<div style="height:6px;background:#EEF1EE;border-radius:4px;overflow:hidden"><div style="width:79%;height:100%;background:#1F8A5B;border-radius:4px"></div></div>'

def issue(ic, tint, ink, title, sub, chipk, chipt):
    return f'''<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #EEF1EE">
  <div style="width:34px;height:34px;border-radius:10px;background:{tint};color:{ink};display:flex;align-items:center;justify-content:center">{icon(ic,17)}</div>
  <div style="display:flex;flex-direction:column;flex:1;min-width:0"><div style="font-weight:600;font-size:14px">{title}</div><div style="color:#64736B;font-size:12px">{sub}</div></div>
  {chip(chipt,chipk)}{icon("chev",16,"#9AA79F")}
</div>'''

def step(n, label, count, done):
    bg = "#1F8A5B" if done else "#FFFFFF"; col = "#FFFFFF" if done else "#1F8A5B"
    return f'''<div style="display:flex;flex-direction:column;align-items:center;gap:6px;flex:1">
  <div style="width:36px;height:36px;border-radius:50%;background:{bg};color:{col};border:2px solid #1F8A5B;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px">{n}</div>
  <div style="font-size:13px;font-weight:600">{label}</div><div style="font-size:12px;color:#64736B">{count}</div>
</div>'''

def row(room, w_prev, w_now, e_prev, e_now, status, sk):
    def cell(prev, now, ic, ink):
        if now is None:
            return f'<td style="padding:11px 12px;color:#9AA79F">— ยังไม่ได้อ่าน</td>'
        return f'<td style="padding:11px 12px"><div style="display:flex;align-items:center;gap:8px">{icon(ic,15,ink)}<span style="color:#64736B">{prev}</span>{icon("arrow",13,"#9AA79F")}<span style="font-weight:600">{now}</span></div></td>'
    return f'''<tr style="border-top:1px solid #EEF1EE">
  <td style="padding:11px 12px;font-weight:600">ห้อง {room}</td>
  {cell(w_prev,w_now,"drop","#2F6FBF")}
  {cell(e_prev,e_now,"bolt","#B7791F")}
  <td style="padding:11px 12px">{chip(status,sk)}</td>
  <td style="padding:11px 12px;text-align:right">{icon("chev",16,"#9AA79F")}</td>
</tr>'''

main_body = f'''
<div style="display:grid;grid-template-columns:repeat(4, minmax(0, 1fr));gap:16px">
  {stat("อ่านมิเตอร์แล้ว","38 <span style='font-size:16px;color:#64736B;font-weight:500'>/ 48 ห้อง</span>","หุ่นวิ่งรอบล่าสุด 16 ก.ย. 19:40–20:12","camera","#E6F4EC","#166A45",progress)}
  {stat("รอยืนยันค่า","21 <span style='font-size:16px;color:#64736B;font-weight:500'>ค่า</span>","7 ค่าที่ OCR ไม่มั่นใจ (&lt; 0.7)","check","#FBF1DF","#8A5A12")}
  {stat("บิลพร้อมส่ง","17 <span style='font-size:16px;color:#64736B;font-weight:500'>ใบ</span>","ส่งแล้ว 0 · รอยืนยันค่า 21 ห้อง","bill","#E7EFFB","#28599B")}
  {stat("ยังไม่ได้อ่าน","10 <span style='font-size:16px;color:#64736B;font-weight:500'>ห้อง</span>","ชั้น 3 ทั้งชั้น · สั่งหุ่นวิ่งซ้ำได้จากแอปควบคุม","alert","#FBE7E7","#9B2C2C")}
</div>

<div style="display:grid;grid-template-columns:minmax(0, 1.35fr) minmax(0, 1fr);gap:16px;margin-top:16px">
  {card(f'''
    <div style="display:flex;align-items:center;gap:10px"><h2 style="margin:0;font-size:16px;font-weight:700">ต้องดูก่อน</h2><span style="color:#64736B;font-size:13px">สิ่งที่ถ้าไม่จัดการ บิลจะผิด</span><a href="#" style="margin-left:auto;font-size:13px;font-weight:600;text-decoration:none">ไปหน้ายืนยัน →</a></div>
    <div style="display:flex;flex-direction:column">
      {issue("alert","#FBE7E7","#9B2C2C","ค่าที่อ่านได้ น้อยกว่างวดก่อน","ห้อง 204 · ไฟ · OCR 4,812 แต่งวดก่อนยืนยัน 4,891 — น่าจะอ่านหลักผิด","bad","ต้องแก้")}
      {issue("check","#FBF1DF","#8A5A12","OCR ไม่มั่นใจ 7 ค่า","ห้อง 105, 108, 112, 201, 203, 207, 210 · ความมั่นใจ 0.41–0.68","warn","ดูรูปเทียบ")}
      {issue("camera","#EEF1EE","#5B6A62","ยังไม่มีรูป 10 ห้อง","ชั้น 3 (301–310) · หุ่นยังไม่ได้วิ่งชั้นนี้ในรอบนี้","mut","รอหุ่น")}
      {issue("mail","#E7EFFB","#28599B","ผู้เช่า 2 ห้องยังไม่มีอีเมล","ห้อง 110, 208 · ส่งบิลไม่ได้จนกว่าจะกรอก","info","กรอกในทะเบียน")}
    </div>
  ''')}
  {card(f'''
    <h2 style="margin:0;font-size:16px;font-weight:700">รอบบิล กันยายน 2569</h2>
    <div style="display:flex;align-items:flex-start;gap:4px;padding:8px 0 4px">
      {step(1,"หุ่นถ่าย","38/48 ห้อง",True)}
      <div style="height:2px;background:#1F8A5B;flex:1;margin-top:17px"></div>
      {step(2,"ยืนยันค่า","55/76 ค่า",False)}
      <div style="height:2px;background:#DCE3DD;flex:1;margin-top:17px"></div>
      {step(3,"ออกบิล","17 ใบ",False)}
      <div style="height:2px;background:#DCE3DD;flex:1;margin-top:17px"></div>
      {step(4,"ส่งอีเมล","0 ใบ",False)}
    </div>
    <div style="border-top:1px solid #EEF1EE;padding-top:12px;display:flex;flex-direction:column;gap:8px;font-size:13px">
      <div style="display:flex;justify-content:space-between"><span style="color:#64736B">อัตราที่ใช้งวดนี้</span><span style="font-weight:600">น้ำ 18 ฿/หน่วย · ไฟ 8 ฿/หน่วย</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:#64736B">มีผลตั้งแต่</span><span>1 ม.ค. 2569 · 1 มิ.ย. 2569</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:#64736B">รูปต้นฉบับบน Pi / crop บนคลาวด์</span><span>76 / 76 รูป</span></div>
    </div>
    <div style="display:flex;gap:10px;margin-top:4px">{btn("ยืนยันค่าที่ค้าง (21)","primary","check")}{btn("ดูบิลที่พร้อม","ghost","bill")}</div>
  ''')}
</div>

{card(f'''
  <div style="display:flex;align-items:center;gap:10px"><h2 style="margin:0;font-size:16px;font-weight:700">ห้องในรอบนี้</h2><span style="color:#64736B;font-size:13px">ค่างวดก่อน → ค่าที่อ่านได้รอบนี้ (หน่วย)</span>
    <div style="margin-left:auto;display:flex;gap:8px">{chip("ทั้งหมด 48","mut")}{chip("รอยืนยัน 21","warn")}{chip("ยืนยันแล้ว 17","ok")}{chip("ยังไม่อ่าน 10","bad")}</div></div>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead><tr style="color:#64736B;font-size:12px;text-align:left"><th style="padding:6px 12px;font-weight:600">ห้อง</th><th style="padding:6px 12px;font-weight:600">มิเตอร์น้ำ</th><th style="padding:6px 12px;font-weight:600">มิเตอร์ไฟ</th><th style="padding:6px 12px;font-weight:600">สถานะ</th><th></th></tr></thead>
    <tbody>
      {row("101","1,231","1,244","3,502","3,611","ยืนยันแล้ว","ok")}
      {row("102","987","998","2,140","2,233","ยืนยันแล้ว","ok")}
      {row("105","1,402","1,4?7","5,012","5,096","OCR ไม่มั่นใจ (น้ำ)","warn")}
      {row("110","1,120","1,133","2,876","2,950","ไม่มีอีเมลผู้เช่า","info")}
      {row("204","1,010","1,021","4,891","4,812","ค่าน้อยกว่างวดก่อน","bad")}
      {row("301",None,None,None,None,"ยังไม่ได้อ่าน","mut")}
    </tbody>
  </table>
''',"margin-top:16px")}
'''
open("Main.dc.html","w").write(shell("home","สวัสดี [ชื่อผู้ให้เช่า]","วันนี้ 16 ก.ย. 2569 · รอบบิลกันยายน — เหลือ 21 ค่าที่ต้องยืนยันก่อนส่งบิลได้", main_body,
  f'<div style="display:flex;align-items:center;gap:8px;background:#E6F4EC;color:#166A45;border-radius:10px;padding:8px 12px;font-size:13px;font-weight:600">{icon("robot",16)}หุ่นซิงก์ล่าสุด 20:12 · 96 รูป</div>'))

# ───────────────────────── ยืนยันค่ามิเตอร์ ─────────────────────────
def qitem(room, mtype, val, conf, sel=False, ck="ok"):
    ic,ink = ("drop","#2F6FBF") if mtype=="น้ำ" else ("bolt","#B7791F")
    bg = "background:#E6F4EC;border:1px solid #BFE0CC;" if sel else "background:#FFFFFF;border:1px solid #EEF1EE;"
    return f'''<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:12px;{bg}">
  {icon(ic,16,ink)}
  <div style="display:flex;flex-direction:column;flex:1;min-width:0;line-height:1.25"><div style="font-weight:600;font-size:14px">ห้อง {room} · {mtype}</div><div style="color:#64736B;font-size:12px">OCR {val}</div></div>
  {chip(conf,ck)}
</div>'''

confirm_body = f'''
<div style="display:grid;grid-template-columns:300px minmax(0, 1fr) 340px;gap:16px;flex:1;min-height:0">

  {card(f'''
    <div style="display:flex;align-items:center;gap:8px"><h2 style="margin:0;font-size:15px;font-weight:700">คิวรอยืนยัน</h2><span style="color:#64736B;font-size:13px">21 ค่า</span></div>
    <div style="display:flex;gap:6px">{chip("ทั้งหมด","ok")}{chip("ไม่มั่นใจ 7","warn")}{chip("ผิดปกติ 1","bad")}</div>
    <div style="display:flex;align-items:center;gap:8px;border:1px solid #D5DDD6;border-radius:10px;padding:8px 10px;color:#9AA79F;font-size:13px">{icon("search",15)}ค้นหาห้อง</div>
    <div style="display:flex;flex-direction:column;gap:6px">
      {qitem("204","ไฟ","4,812","น้อยกว่าเดิม",True,"bad")}
      {qitem("105","น้ำ","1,4?7","0.41",False,"warn")}
      {qitem("108","ไฟ","3,204","0.55",False,"warn")}
      {qitem("112","น้ำ","880","0.62",False,"warn")}
      {qitem("201","ไฟ","6,118","0.68",False,"warn")}
      {qitem("103","น้ำ","1,532","0.94",False,"ok")}
      {qitem("103","ไฟ","2,977","0.97",False,"ok")}
      {qitem("104","น้ำ","1,205","0.91",False,"ok")}
    </div>
    <div style="color:#64736B;font-size:12px;margin-top:auto">เรียงตาม: ผิดปกติ → ไม่มั่นใจ → ปกติ</div>
  ''',"padding:16px")}

  {card(f'''
    <div style="display:flex;align-items:center;gap:10px"><h2 style="margin:0;font-size:16px;font-weight:700">ห้อง 204 · มิเตอร์ไฟ</h2>{chip("meter_id E-204","mut")}<span style="margin-left:auto;color:#64736B;font-size:13px;display:flex;align-items:center;gap:6px">{icon("clock",14)}ถ่าย 16 ก.ย. 20:04:31 · run 2569-09-16-A</span></div>
    <div style="position:relative;background:#2A2F2C;border-radius:12px;height:392px;display:flex;align-items:center;justify-content:center;overflow:hidden">
      <div style="position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(255,255,255,.03) 0 1px,transparent 1px 24px)"></div>
      <div style="width:540px;height:150px;background:#1E2320;border:2px solid #5EE1B5;border-radius:6px;display:flex;align-items:center;justify-content:center;gap:10px;color:#F2F6FF;font-family:ui-monospace,Menlo,monospace;font-size:56px;letter-spacing:.18em;font-weight:600">
        <span>4</span><span>8</span><span style="color:#FFB27A;border-bottom:3px solid #FFB27A">1</span><span>2</span><span style="color:#8FA3C7;font-size:32px">.7</span>
      </div>
      <div style="position:absolute;left:14px;top:12px;color:#C9DCD1;font-size:12px;display:flex;align-items:center;gap:6px">{icon("image",14,"#C9DCD1")}crop ROI · 30 kB · ต้นฉบับ 1080p อยู่บน Pi</div>
      <div style="position:absolute;right:14px;bottom:12px;display:flex;gap:8px">
        <span style="background:rgba(255,255,255,.12);color:#F2F6FF;border-radius:8px;padding:5px 10px;font-size:12px">ดูรูปเต็ม</span>
        <span style="background:rgba(255,255,255,.12);color:#F2F6FF;border-radius:8px;padding:5px 10px;font-size:12px">ซูมหลักที่ไม่มั่นใจ</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:12px">
      <div style="background:#F4F6F3;border-radius:12px;padding:12px 14px"><div style="color:#64736B;font-size:12px">งวดก่อน (ยืนยันแล้ว 15 ส.ค.)</div><div style="font-size:22px;font-weight:700">4,891</div></div>
      <div style="background:#FBE7E7;border-radius:12px;padding:12px 14px"><div style="color:#9B2C2C;font-size:12px">OCR รอบนี้ · ความมั่นใจ 0.83</div><div style="font-size:22px;font-weight:700;color:#9B2C2C">4,812</div></div>
      <div style="background:#F4F6F3;border-radius:12px;padding:12px 14px"><div style="color:#64736B;font-size:12px">หน่วยที่ใช้ (ถ้ารับค่า OCR)</div><div style="font-size:22px;font-weight:700;color:#9B2C2C">−79 ✕</div></div>
    </div>
    <div style="display:flex;align-items:flex-start;gap:10px;background:#FBF1DF;border-radius:12px;padding:12px 14px;color:#8A5A12;font-size:13px">{icon("alert",18)}<div>มิเตอร์ไฟย้อนกลับไม่ได้ — ค่าใหม่ต้อง ≥ 4,891 ระบบจะ<b>ไม่ให้ยืนยัน</b>ค่าที่น้อยกว่างวดก่อน · หลักที่น่าสงสัยคือหลักร้อย (8 กับ 9 ใน 7-segment ต่างกันขีดเดียว) — ถ้าอ่านเป็น 4,912 จะได้ 21 หน่วย ใกล้ค่าเฉลี่ยห้องนี้ (24 หน่วย/เดือน)</div></div>
  ''')}

  {card(f'''
    <h2 style="margin:0;font-size:15px;font-weight:700">ค่าที่จะยืนยัน</h2>
    <div style="display:flex;flex-direction:column;gap:6px">
      <label style="color:#64736B;font-size:12px">confirmed_value (แยกจากค่า OCR เสมอ)</label>
      <div style="display:flex;align-items:center;border:2px solid #1F8A5B;border-radius:12px;padding:10px 14px;font-size:28px;font-weight:700;font-family:ui-monospace,Menlo,monospace;letter-spacing:.06em">4,912<span style="margin-left:auto;color:#9AA79F;font-size:13px;font-family:inherit;letter-spacing:0;font-weight:500">หน่วย</span></div>
      <div style="color:#64736B;font-size:12px">ใช้จริง = 4,912 − 4,891 = <b style="color:#17231D">21 หน่วย</b> × 8 ฿ = <b style="color:#17231D">168 ฿</b></div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;margin-top:4px">
      {btn("ยืนยันค่า 4,912","primary","check").replace("height:40px","height:46px")}
      {btn("ปฏิเสธ · ให้หุ่นถ่ายใหม่","danger","camera")}
      {btn("ข้ามไปก่อน","ghost")}
    </div>
    <div style="color:#9AA79F;font-size:12px">Enter = ยืนยัน · Esc = ข้าม · ยืนยันแล้วเปลี่ยนใจได้ แต่จะเป็นแถวใหม่ ไม่ทับของเดิม</div>
    <div style="border-top:1px solid #EEF1EE;padding-top:12px;display:flex;flex-direction:column;gap:8px">
      <div style="font-size:13px;font-weight:700">ประวัติค่านี้ (append-only)</div>
      <div style="display:flex;flex-direction:column;gap:6px;font-size:12px;color:#64736B">
        <div style="display:flex;gap:8px"><span style="width:96px;flex:none">16 ก.ย. 20:04</span><span>หุ่น OCR → <b style="color:#17231D">4,812</b> · conf 0.83 · raw "4812.7"</span></div>
        <div style="display:flex;gap:8px"><span style="width:96px;flex:none">16 ก.ย. 20:04</span><span>ระบบ flag: น้อยกว่างวดก่อน</span></div>
        <div style="display:flex;gap:8px"><span style="width:96px;flex:none">15 ส.ค. 21:10</span><span>[ชื่อผู้ให้เช่า] ยืนยัน <b style="color:#17231D">4,891</b> (OCR 4,891 · conf 0.96)</span></div>
      </div>
    </div>
    <div style="border-top:1px solid #EEF1EE;padding-top:12px;display:flex;flex-direction:column;gap:4px;font-size:12px;color:#64736B">
      <div style="font-size:13px;font-weight:700;color:#17231D">ห้อง 204</div>
      <div>ผู้เช่า: สมชาย ใจดี · somchai@example.com</div>
      <div>ค่าเฉลี่ย 6 เดือน: ไฟ 24 หน่วย · น้ำ 11 หน่วย</div>
    </div>
  ''',"padding:16px 18px")}
</div>
'''
open("Confirm.dc.html","w").write(shell("check","ยืนยันค่ามิเตอร์","รอบบิลกันยายน 2569 · ยืนยันแล้ว 55 จาก 76 ค่า · เหลือ 21", confirm_body,
  f'<div style="display:flex;align-items:center;gap:8px;color:#64736B;font-size:13px">{icon("check",16,"#1F8A5B")}วันนี้ยืนยันไปแล้ว 12 ค่า</div>'))

# ───────────────────────── บิล ─────────────────────────
def brow(room, tenant, mail, wu, eu, status, sk, dim=False):
    wb = "" if wu is None else f"{wu*18:,}"
    eb = "" if eu is None else f"{eu*8:,}"
    tot = f"{wu*18+eu*8:,}" if (wu is not None and eu is not None) else "—"
    c = "color:#9AA79F;" if dim else ""
    mailhtml = f'<span style="color:#64736B;font-size:12px">{mail}</span>' if mail else chip("ไม่มีอีเมล","info")
    def u(v,b,ic,ink):
        if v is None: return '<td style="padding:11px 12px;color:#9AA79F">—</td>'
        return f'<td style="padding:11px 12px"><div style="display:flex;align-items:baseline;gap:6px">{icon(ic,14,ink)}<span style="font-weight:600">{v}</span><span style="color:#64736B;font-size:12px">หน่วย</span><span style="margin-left:auto;font-weight:600">{b}</span></div></td>'
    return f'''<tr style="border-top:1px solid #EEF1EE;{c}">
  <td style="padding:11px 12px"><input type="checkbox" style="width:16px;height:16px;accent-color:#1F8A5B" {"checked" if sk=="ok" else ""}></td>
  <td style="padding:11px 12px;font-weight:600">ห้อง {room}</td>
  <td style="padding:11px 12px"><div style="display:flex;flex-direction:column;line-height:1.25"><span>{tenant}</span>{mailhtml}</div></td>
  {u(wu,wb,"drop","#2F6FBF")}{u(eu,eb,"bolt","#B7791F")}
  <td style="padding:11px 12px;font-weight:700;text-align:right">{tot}</td>
  <td style="padding:11px 12px">{chip(status,sk)}</td>
</tr>'''

bills_body = f'''
<div style="display:grid;grid-template-columns:repeat(4, minmax(0, 1fr));gap:16px">
  {stat("พร้อมส่ง","17 <span style='font-size:16px;color:#64736B;font-weight:500'>ใบ</span>","ค่าน้ำ-ไฟยืนยันครบทั้ง 2 มิเตอร์ + มีอีเมล","send","#E6F4EC","#166A45")}
  {stat("รอยืนยันค่า","21 <span style='font-size:16px;color:#64736B;font-weight:500'>ห้อง</span>","ออกบิลไม่ได้จนกว่าจะยืนยัน","check","#FBF1DF","#8A5A12")}
  {stat("ยอดรวมที่พร้อมส่ง","฿ 9,864","เฉลี่ย 580 ฿/ห้อง · น้ำ 3,024 · ไฟ 6,840","bill","#E7EFFB","#28599B")}
  {stat("ส่งแล้วงวดนี้","0 <span style='font-size:16px;color:#64736B;font-weight:500'>ใบ</span>","งวดก่อนส่ง 48 ใบใน 2 นาที 24 วิ · ตีกลับ 0","mail","#EEF1EE","#5B6A62")}
</div>

{card(f'''
  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <h2 style="margin:0;font-size:16px;font-weight:700">บิลงวดกันยายน 2569</h2>
    <span style="color:#64736B;font-size:13px">อัตรางวดนี้: น้ำ 18 ฿/หน่วย (มีผล 1 ม.ค. 2569) · ไฟ 8 ฿/หน่วย (มีผล 1 มิ.ย. 2569)</span>
    <div style="margin-left:auto;display:flex;gap:8px">{chip("ทั้งหมด 48","mut")}{chip("พร้อมส่ง 17","ok")}{chip("รอยืนยัน 21","warn")}{chip("ไม่มีอีเมล 2","info")}{chip("ยังไม่อ่าน 10","bad")}</div>
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead><tr style="color:#64736B;font-size:12px;text-align:left">
      <th style="padding:6px 12px;width:40px"></th><th style="padding:6px 12px;font-weight:600">ห้อง</th><th style="padding:6px 12px;font-weight:600">ผู้เช่า</th>
      <th style="padding:6px 12px;font-weight:600;width:190px">น้ำ · บาท</th><th style="padding:6px 12px;font-weight:600;width:190px">ไฟ · บาท</th>
      <th style="padding:6px 12px;font-weight:600;text-align:right">รวม (฿)</th><th style="padding:6px 12px;font-weight:600">สถานะ</th></tr></thead>
    <tbody>
      {brow("101","วราภรณ์ ใจดี","waraporn@example.com",13,109,"พร้อมส่ง","ok")}
      {brow("102","ศักดิ์ชัย แสนสุข","sakchai@example.com",11,93,"พร้อมส่ง","ok")}
      {brow("103","ธนพร พรมมา","thanaporn@example.com",9,71,"พร้อมส่ง","ok")}
      {brow("105","กิตติพงษ์ รัตนวงศ์","kittipong@example.com",None,84,"รอยืนยันค่าน้ำ","warn")}
      {brow("110","สุรเชษฐ์ จันทร์ดี",None,13,74,"ไม่มีอีเมล","info")}
      {brow("204","สมชาย ใจดี","somchai@example.com",11,None,"รอยืนยันค่าไฟ","warn")}
      {brow("301","—",None,None,None,"ยังไม่ได้อ่าน","mut",True)}
    </tbody>
  </table>
''',"margin-top:16px")}

<div style="display:flex;align-items:center;gap:14px;background:#FFFFFF;border:1px solid #E3E8E3;border-radius:16px;padding:14px 20px;margin-top:16px">
  <div style="display:flex;flex-direction:column;gap:2px">
    <div style="font-weight:700;font-size:15px">เลือกแล้ว 17 บิล · ฿ 9,864</div>
    <div style="color:#64736B;font-size:13px">ส่งจาก [อีเมลผู้ให้เช่า] · หน่วง 3 s/ฉบับ → ใช้เวลา ~51 s · แนบรูป crop มิเตอร์ 2 รูป/ฉบับ (~60 kB) · ส่งได้เฉพาะบิลที่ยืนยันค่าครบแล้วเท่านั้น</div>
  </div>
  <div style="margin-left:auto;display:flex;gap:10px">{btn("ดูตัวอย่างอีเมล","ghost","mail")}{btn("ส่ง 17 บิลทางอีเมล","primary","send")}</div>
</div>
'''
open("Bills.dc.html","w").write(shell("bill","บิล","รอบบิลกันยายน 2569 · คิดจาก confirmed_value เท่านั้น ไม่ใช้ค่า OCR ดิบ", bills_body))

import json
json.dump({
  "artboards":[
    {"file":"Main.dc.html","title":"1 · หน้าหลัก — สถานะรอบบิล","x":0,"y":0,"w":1440,"h":1000},
    {"file":"Confirm.dc.html","title":"2 · ยืนยันค่ามิเตอร์ (หน้าที่ใช้ทุกเดือน)","x":1560,"y":0,"w":1440,"h":1000},
    {"file":"Bills.dc.html","title":"3 · บิล + ส่งอีเมล","x":3120,"y":0,"w":1440,"h":1000}
  ],
  "annotations":[
    {"id":"scope","x":0,"y":-260,"w":700,"text":"ARIA หลังบ้าน (ฝั่งคลาวด์ · C23) — mockup นิ่ง 3 หน้า\nเก็บ: หน้าหลัก · ยืนยันค่ามิเตอร์ · บิล · ห้องและมิเตอร์ · ตั้งค่า (อัตรา+วันมีผล / อีเมล)\nตัดจาก DormPlus: สัญญาเช่า · แจ้งซ่อม · ข้อความ · รายงาน · การเงินรวม · เมนูด่วน · Premium · แบนเนอร์\nตัวเลขทั้งหมดในภาพเป็นตัวอย่าง (sample) — [วงเล็บ] คือค่าที่ต้องกรอกจริง"},
    {"id":"rule-confirm","x":1560,"y":-160,"w":600,"text":"กติกาในหน้านี้ที่มาจาก schema ที่ล็อกไว้:\n• value (OCR) กับ confirmed_value คนละคอลัมน์ · ประวัติ append-only\n• มิเตอร์ย้อนกลับไม่ได้ → ห้ามยืนยันค่าที่น้อยกว่างวดก่อน\n• คิวเรียง ผิดปกติ → ไม่มั่นใจ → ปกติ ให้เจอของที่ทำให้บิลผิดก่อน"},
    {"id":"rule-bills","x":3120,"y":-160,"w":600,"text":"บิลคิดจาก confirmed_value × อัตราที่มีผล ณ งวดนั้น (ไม่ใช่อัตราวันนี้)\nส่งได้เฉพาะแถวที่ยืนยันครบ 2 มิเตอร์ + มีอีเมล · หน่วง 2–5 s/ฉบับ ตามไฟล์ 20 §20.4"}
  ],
  "launch":{"view":"canvas"}
}, open("canvas.json","w"), ensure_ascii=False, indent=2)
print("ok")
