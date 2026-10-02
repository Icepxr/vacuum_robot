// เนื้อหาอีเมลบิลแบบใบแจ้งหนี้ (HTML + ข้อความล้วน) · แยกไฟล์เพื่อพรีวิวได้โดยไม่ต้องส่งจริง
const TH_MONTH = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"];
const cycleTh = (c: string) => { const [y, m] = c.split("-").map(Number); return `${TH_MONTH[m - 1]} ${y + 543}`; };
const baht = (n: number) => "฿" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (n: number | null) => n == null ? "—" : Number(n).toLocaleString("en-US", { maximumFractionDigits: 3 });
const esc = (s: unknown) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));

const dateTh = (iso: string) => { const d = new Date(new Date(iso).getTime() + 7 * 3600e3); return `${d.getUTCDate()} ${TH_MONTH[d.getUTCMonth()]} ${d.getUTCFullYear() + 543}`; };
const maskPP = (id: string) => id.length === 13 ? `x-xxxx-xxxxx-${id.slice(10, 12)}-${id[12]}` : `xxx-xxx-${id.slice(6)}`;

// อีเมลแบบใบแจ้งหนี้ (ผู้ใช้: "ตกแต่งให้เหมือนบิล" 3 ต.ค.) · ตาราง + inline style เท่านั้น (Gmail ตัด <style>/CSS ภายนอก)
export function render(inv: Record<string, any>, dorm: string, promptpay: string | null, logo: string | null = "cid:aria-logo") {
  const C = { ink: "#1c1530", sub: "#6b6280", line: "#ece8f3", brand: "#4c1d95", brand2: "#7c3aed", soft: "#f6f3fc" };
  const no = `INV-${inv.cycle.replace("-", "")}-${inv.room_id}${inv.revision > 1 ? `-R${inv.revision}` : ""}`;
  const issued = dateTh(inv.approved_at ?? new Date().toISOString());
  const td = (v: string, extra = "") => `<td style="padding:12px 8px;border-bottom:1px solid ${C.line};font-size:14px;color:${C.ink};${extra}">${v}</td>`;
  const item = (label: string, prev: number | null, curr: number | null, units: number, rate: number, amt: number) => `<tr>
    ${td(`<b style="white-space:nowrap">${label}</b><div style="font-size:12px;color:${C.sub};margin-top:2px;white-space:nowrap">${num(prev)} → ${num(curr)}</div>`, "padding-left:0")}
    ${td(num(units), "text-align:right")}${td(baht(rate).replace("฿", ""), "text-align:right;color:" + C.sub)}${td(baht(amt), "text-align:right;padding-right:0;white-space:nowrap")}</tr>`;
  const rent = Number(inv.rent_baht) ? `<tr>${td('<b style="white-space:nowrap">ค่าเช่าห้อง</b>', "padding-left:0")}${td("", "")}${td("", "")}${td(baht(inv.rent_baht), "text-align:right;padding-right:0")}</tr>` : "";
  const th = (v: string, align = "right") => `<th style="padding:0 8px 8px;font-size:11px;font-weight:600;letter-spacing:.06em;color:${C.sub};text-align:${align};border-bottom:2px solid ${C.ink}">${v}</th>`;
  const pay = promptpay ? `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;border:1px solid ${C.line};border-radius:14px;background:${C.soft}">
      <tr><td style="padding:20px;text-align:center">
        <div style="display:inline-block;padding:4px 12px;border-radius:99px;background:#113566;color:#fff;font-size:12px;font-weight:700;letter-spacing:.08em">PromptPay</div>
        <div style="font-size:15px;font-weight:700;color:${C.ink};margin:10px 0 2px">สแกนจ่ายด้วยแอปธนาคาร</div>
        <div style="font-size:12px;color:${C.sub}">QR นี้ฝังยอด ${baht(inv.total_baht)} ไว้แล้ว · พร้อมเพย์ ${maskPP(promptpay)}</div>
        <img src="cid:promptpay-qr" width="200" height="200" alt="QR พร้อมเพย์ ${baht(inv.total_baht)}" style="display:block;margin:14px auto 0;border:8px solid #fff;border-radius:12px">
      </td></tr></table>` : "";
  const html = `<!doctype html><html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(no)}</title></head>
<body style="margin:0;padding:0;background:#eeebf4;font-family:'Sukhumvit Set','Noto Sans Thai',Tahoma,Arial,sans-serif;color:${C.ink}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eeebf4"><tr><td align="center" style="padding:20px 8px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:18px;overflow:hidden;box-shadow:0 8px 30px rgba(40,20,80,.08)">
  <tr><td style="background:${C.brand};background-image:linear-gradient(120deg,${C.brand},${C.brand2});padding:24px 22px;color:#fff">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="vertical-align:top">${logo ? `<img src="${logo}" width="96" height="50" alt="ARIA" style="display:block;border:0;margin:0 0 10px">` : ""}<div style="font-size:12px;letter-spacing:.14em;opacity:.8">ใบแจ้งค่าบริการ · INVOICE</div><div style="font-size:22px;font-weight:700;margin-top:4px">${esc(dorm)}</div></td>
      <td style="vertical-align:top;text-align:right;font-size:12px;line-height:1.7;opacity:.95">เลขที่<br><b>${esc(no)}</b><br>ออกวันที่ ${issued}<br>รอบบิล ${cycleTh(inv.cycle)}</td>
    </tr></table></td></tr>
  <tr><td style="padding:22px 22px 8px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="vertical-align:top"><div style="font-size:11px;letter-spacing:.08em;color:${C.sub}">เรียน</div><div style="font-size:16px;font-weight:700;margin-top:2px">${esc(inv.tenant_name)}</div><div style="font-size:13px;color:${C.sub}">${esc(inv.recipient_email ?? "")}</div></td>
      <td style="vertical-align:top;text-align:right"><div style="font-size:11px;letter-spacing:.08em;color:${C.sub}">ห้อง</div><div style="font-size:26px;font-weight:800;color:${C.brand};line-height:1.1">${esc(inv.room_id)}</div></td>
    </tr></table>
    ${inv.revision > 1 ? `<div style="margin-top:14px;padding:10px 12px;border-radius:10px;background:#fff7e6;color:#7a4a00;font-size:13px">ฉบับแก้ไขครั้งที่ ${inv.revision - 1} · ใช้ฉบับนี้แทนฉบับก่อนหน้า</div>` : ""}
  </td></tr>
  <tr><td style="padding:12px 22px 0">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
      <tr>${th("รายการ · เลขมิเตอร์", "left").replace("padding:0 8px", "padding:0 8px 8px 0")}${th("หน่วย")}${th("บาท/หน่วย")}${th("จำนวนเงิน").replace("padding:0 8px 8px", "padding:0 0 8px 8px")}</tr>
      ${item("ค่าน้ำประปา", inv.water_prev, inv.water_curr, inv.water_units, inv.water_rate, inv.water_amount)}
      ${item("ค่าไฟฟ้า", inv.electric_prev, inv.electric_curr, inv.electric_units, inv.electric_rate, inv.electric_amount)}
      ${rent}
    </table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:18px"><tr>
      <td></td>
      <td style="width:240px;background:${C.soft};border-radius:14px;padding:16px 18px">
        <div style="font-size:12px;color:${C.sub}">ยอดที่ต้องชำระ</div>
        <div style="font-size:30px;font-weight:800;color:${C.brand};letter-spacing:-.01em;margin-top:2px">${baht(inv.total_baht)}</div>
      </td></tr></table>
    ${pay}
  </td></tr>
  <tr><td style="padding:22px 22px 24px">
    <div style="border-top:1px solid ${C.line};padding-top:16px;font-size:12px;line-height:1.7;color:${C.sub}">
      เลขมิเตอร์อ่านด้วยหุ่น ARIA และตรวจยืนยันโดยเจ้าของหอก่อนออกบิล<br>หากมีข้อสงสัยเกี่ยวกับยอด ตอบกลับอีเมลนี้ได้เลย
    </div></td></tr>
</table>
<div style="font-size:11px;color:#9a93ab;margin-top:12px">ส่งจากระบบ ARIA · ${esc(dorm)}</div>
</td></tr></table></body></html>`;
  const text = `${dorm} · ใบแจ้งค่าบริการ ${no}\nรอบบิล ${cycleTh(inv.cycle)} · ห้อง ${inv.room_id} · ${inv.tenant_name}\n\nค่าน้ำ ${num(inv.water_prev)} → ${num(inv.water_curr)} = ${num(inv.water_units)} หน่วย × ${baht(inv.water_rate)} = ${baht(inv.water_amount)}\nค่าไฟ ${num(inv.electric_prev)} → ${num(inv.electric_curr)} = ${num(inv.electric_units)} หน่วย × ${baht(inv.electric_rate)} = ${baht(inv.electric_amount)}\n${Number(inv.rent_baht) ? `ค่าเช่า ${baht(inv.rent_baht)}\n` : ""}\nยอดที่ต้องชำระ ${baht(inv.total_baht)}${promptpay ? `\nพร้อมเพย์ ${maskPP(promptpay)} (QR ในอีเมลฉบับ HTML)` : ""}`;
  return { subject: `ใบแจ้งค่าน้ำค่าไฟ ห้อง ${inv.room_id} · รอบ${cycleTh(inv.cycle)} · ${dorm}`, html, text };
}

