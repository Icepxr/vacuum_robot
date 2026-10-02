// SMTP ขั้นต่ำผ่าน TLS ตรง (พอร์ต 465) — พอสำหรับ Gmail + App Password (AUTH LOGIN)
// Edge Functions ห้ามพอร์ต 25/587 จึงใช้ 465 (implicit TLS)
const te = new TextEncoder(), td = new TextDecoder();

export async function smtpSend(o: { host: string; port: number; user: string; pass: string; from: string; to: string; raw: string }) {
  const conn = await Deno.connectTls({ hostname: o.host, port: o.port });
  let buf = "";
  async function reply(): Promise<{ code: number; text: string }> {
    const chunk = new Uint8Array(4096);
    for (;;) {
      const lines = buf.split("\r\n");
      for (let i = 0; i < lines.length - 1; i++) {
        if (/^\d{3} /.test(lines[i])) {   // บรรทัดสุดท้ายของคำตอบ = "XYZ " (ไม่ใช่ "XYZ-")
          const text = lines.slice(0, i + 1).join("\n");
          buf = lines.slice(i + 1).join("\r\n");
          return { code: Number(lines[i].slice(0, 3)), text };
        }
      }
      const n = await conn.read(chunk);
      if (n === null) throw new Error("SMTP ปิดการเชื่อมต่อ");
      buf += td.decode(chunk.subarray(0, n));
    }
  }
  async function cmd(line: string, ok: number[]) {
    await conn.write(te.encode(line + "\r\n"));
    const r = await reply();
    if (!ok.includes(r.code)) throw new Error(`SMTP ${r.code}: ${r.text.slice(0, 200)}`);
    return r;
  }
  try {
    const hello = await reply(); if (hello.code !== 220) throw new Error(`SMTP ${hello.code}`);
    await cmd("EHLO aria-th.netlify.app", [250]);
    await cmd("AUTH LOGIN", [334]);
    await cmd(btoa(o.user), [334]);
    await cmd(btoa(o.pass), [235]);
    await cmd(`MAIL FROM:<${o.from}>`, [250]);
    await cmd(`RCPT TO:<${o.to}>`, [250, 251]);
    await cmd("DATA", [354]);
    // dot-stuffing: บรรทัดที่ขึ้นต้นด้วย "." ต้องเติมอีกจุด (base64/header ของเราไม่มี แต่กันไว้)
    const body = o.raw.replace(/\r\n\./g, "\r\n..");
    const r = await cmd(body + "\r\n.", [250]);
    await cmd("QUIT", [221]).catch(() => {});
    return r.text;
  } finally {
    try { conn.close(); } catch { /* ปิดแล้ว */ }
  }
}
