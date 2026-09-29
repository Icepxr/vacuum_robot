# ARIA — เว็บหลังบ้านเจ้าของหอ (`aria/web`)

ไฟล์นิ่งล้วน (vanilla JS · ไม่มีขั้น build) ต่อจากต้นแบบ [`design/aria-prototype`](../../design/aria-prototype) · ข้อมูลอยู่ใน Supabase **`aria-mrc`** ผ่าน RLS
ขอบเขตรอบนี้ = ขั้น 3 ของ [แบบ v1 §7](../../design/aria-backoffice-v1.md): ล็อกอินเจ้าของ + 5 หน้า + `reading_events`

| หน้า | ทำอะไรได้ | ยังไม่ทำ |
|---|---|---|
| หน้าหลัก | อ่านครบกี่ห้อง · ค่ารอยืนยัน · บิลคำนวณได้กี่ห้อง · รายการ "ต้องดูก่อน" · heartbeat ล่าสุดของหุ่น ("ข้อมูลล่าสุดเมื่อ …") | ตัวนับอีเมล (ขั้น 5) |
| ยืนยันค่ามิเตอร์ | คิวเรียงตามความเสี่ยง · รูป crop (signed URL 5 นาที) · ยืนยัน / แก้ค่า (ต้องมีเหตุผล) / ปฏิเสธ / ผูกมิเตอร์ · ประวัติทุก event | — |
| บิล | **พรีวิว** คำนวณสดจากค่าที่ยืนยัน · อัตรา ณ วันตัดรอบ · เปิด/ปิดรวมค่าเช่ารายรอบ · เปลี่ยนมิเตอร์กลางรอบ = รวมสองช่วง | อนุมัติ/ตรึงยอด (ขั้น 4 ต้องมีตาราง `invoices`) · ส่งอีเมล (ขั้น 5) |
| ห้องและมิเตอร์ | เพิ่มห้อง · ผู้เช่าเข้า/ออก/แก้อีเมล-ค่าเช่า · เพิ่ม/ปลดมิเตอร์ (รหัส `-01 → -02` อัตโนมัติ) · ส่งออก `meters.json` ให้ Pi | นำเข้า CSV |
| ตั้งค่า | ชื่อหอ · วันตัดรอบเริ่มต้น (ค่าเริ่ม = สิ้นเดือน · F6) · อัตรา (append-only) · วันตัดรอบรายรอบ | เชื่อม Gmail ผู้ส่ง |

กติกาที่ **ฐานข้อมูลบังคับ** (เว็บแค่โชว์ล่วงหน้า): ค่ายืนยันห้ามต่ำกว่าค่าก่อนหน้าของมิเตอร์เดียวกัน · ต้องผูกมิเตอร์ก่อนยืนยัน · `corrected` ต้องมีเหตุผล · event/ค่าจากหุ่นแก้ไม่ได้ · ช่วงผู้เช่า/มิเตอร์ของห้องเดียวกันห้ามซ้อน · ไม่อยู่ใน `owners` = ไม่เห็นอะไรเลย

## ลองบนเครื่อง
```bash
python3 -m http.server 8766 --directory aria/web
```
- `http://localhost:8766/` → หน้าล็อกอินจริง (ต้องตั้ง Google ก่อน ↓)
- `http://localhost:8766/?mock` → ข้อมูลจำลองในหน่วยความจำ ไม่แตะคลาวด์ (เปิดได้เฉพาะ localhost)
- เทสต์ตรรกะ: `node --test aria/web/test/*.test.mjs`

## Deploy ขึ้น Netlify (Free)
1. Netlify › Add new site › Import from Git › เลือก repo `Icepxr/vacuum_robot` branch `main`
2. **Base directory = `aria/web`** · ช่องอื่นปล่อยว่าง (build/publish อ่านจาก `aria/web/netlify.toml`)
3. Deploy แล้วจด URL เช่น `https://<ชื่อ>.netlify.app`
- `netlify.toml` ตั้ง `ignore` ให้ build เฉพาะเมื่อ `aria/web` เปลี่ยน — Free มี 300 เครดิต/เดือน · deploy ละ 15 → ถ้า deploy ทุก push ของ repo นี้จะเกิน ([ไฟล์ 20 §20.9](../../08_การคำนวณ/20_ระบบจัดการข้อมูลหอพัก_ความจุและอีเมล.md)) · ยังไม่ยืนยันว่า build ที่ถูก ignore กินเครดิตไหม — ดูหน้า Usage หลัง push แรกๆ
- มี CSP จำกัดให้คุยกับ `brvlfwrmkoyjnrhvfesq.supabase.co` เท่านั้น

## เปิดล็อกอิน Google (ทำครั้งเดียว · ต้องใช้บัญชีคุณเอง)
1. Google Cloud Console › Google Auth Platform › Clients › **Create client** แบบ *Web application*
   - Authorized JavaScript origins: `https://<ชื่อ>.netlify.app` (และ `http://localhost:8766` ถ้าจะลองบนเครื่อง)
   - Authorized redirect URIs: `https://brvlfwrmkoyjnrhvfesq.supabase.co/auth/v1/callback`
   - Consent screen ขณะอยู่สถานะ *Testing* ต้องเพิ่มบัญชี Google ของเจ้าของหอเป็น test user
2. Supabase `aria-mrc` › Authentication › Providers › **Google** › ใส่ Client ID + Secret › Enable
3. Authentication › URL Configuration › Site URL = URL Netlify · Redirect URLs เพิ่ม URL Netlify (+ `http://localhost:8766/` ถ้าลองบนเครื่อง)
4. **ปิด Email sign-up** ใน Authentication › Providers › Email (ตาม [aria/README.md](../README.md))
5. ใส่อีเมลเจ้าของหอใน SQL Editor: `insert into public.owners(email) values ('ชื่อ@gmail.com');` (ตัวพิมพ์เล็ก)

## ข้อมูลตัวอย่าง
`aria-mrc` มีห้อง 101–110 + ค่าที่หุ่นอ่านตัวอย่างจากอุปกรณ์ `DEMO-01` (revoke แล้ว ส่งข้อมูลเข้าไม่ได้) ติดป้าย `is_demo` · ลบทั้งหมดก่อนใช้กับหอจริง: `select public.delete_demo_data();` ใน SQL Editor (ตั้งใจไม่ใส่ปุ่มในเว็บ)

## ไฟล์
- `js/logic.js` ตรรกะล้วน (รอบบิล · คิว · บิล · meters.json) มีเทสต์ใน `test/`
- `js/api.js` Supabase จริง · `js/mock.js` ข้อมูลจำลองหน้าตาเดียวกัน · `js/app.js` หน้าจอ
- `js/config.js` URL + publishable key (สาธารณะ ใส่ในเบราว์เซอร์ได้) — **ห้ามใส่ service_role/secret key ในโฟลเดอร์นี้**
- `vendor/supabase-2.117.2.js` supabase-js UMD (MIT) ฝังไว้ ไม่พึ่ง CDN ตอนเดโมที่เน็ตสนามไม่แน่นอน
- `css/styles.css` + `css/theme.css` คัดลอกจากต้นแบบ ARIA Orbit · `css/app.css` ส่วนเพิ่ม
