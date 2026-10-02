// ประกอบอีเมล (MIME) เอง — denomailer 1.6.0 พับหัวข้อภาษาไทยด้วย soft line break ของ quoted-printable
// ทำให้ header ขาดกลางทาง (หัวข้อขึ้นรหัสดิบ + From/To/Content-Type หลุดไปอยู่ในเนื้อหา · ผู้ใช้เจอ 3 ต.ค. 2569)
// ที่นี่: หัวข้อ/ชื่อผู้ส่ง = RFC 2047 encoded-word แบบ base64 ท่อนละ ≤ 75 ตัวอักษร พับบรรทัดด้วย CRLF + ช่องว่าง (RFC 5322)
//         เนื้อหา = base64 บรรทัดละ 76 ตัวอักษร (RFC 2045)
const enc = new TextEncoder();

export function b64(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
const wrap76 = (s: string) => s.replace(/.{1,76}/g, "$&\r\n");

// แบ่งข้อความเป็น encoded-word ไม่ตัดกลางตัวอักษร: base64 ≤ 60 ตัว (= 45 ไบต์) + "=?UTF-8?B?" + "?=" = 72 ≤ 75
export function encodeWords(text: string): string {
  if (/^[\x20-\x7e]*$/.test(text)) return text;
  const words: number[][] = [];
  let cur: number[] = [];
  for (const ch of text) {
    const b = [...enc.encode(ch)];
    if (cur.length + b.length > 45) { words.push(cur); cur = []; }
    cur.push(...b);
  }
  if (cur.length) words.push(cur);
  return words.map((w) => `=?UTF-8?B?${b64(new Uint8Array(w))}?=`).join("\r\n ");
}

export interface Inline { cid: string; contentType: string; filename: string; bytes: Uint8Array }
export function buildMessage(o: { fromName: string; fromAddr: string; to: string; subject: string; text: string; html: string; inline?: Inline[]; domain: string }) {
  const id = `${crypto.randomUUID()}@${o.domain}`;
  const alt = `alt-${crypto.randomUUID()}`, rel = `rel-${crypto.randomUUID()}`;
  const part = (type: string, body: Uint8Array, extra = "") =>
    `Content-Type: ${type}\r\nContent-Transfer-Encoding: base64\r\n${extra}\r\n${wrap76(b64(body))}`;
  const textPart = part('text/plain; charset="UTF-8"', enc.encode(o.text));
  const htmlPart = part('text/html; charset="UTF-8"', enc.encode(o.html));
  const htmlBlock = o.inline?.length
    ? `Content-Type: multipart/related; boundary="${rel}"\r\n\r\n--${rel}\r\n${htmlPart}` +
      o.inline.map((f) => `--${rel}\r\n` + part(`${f.contentType}; name="${f.filename}"`, f.bytes, `Content-ID: <${f.cid}>\r\nContent-Disposition: inline; filename="${f.filename}"\r\n`)).join("") +
      `--${rel}--\r\n`
    : htmlPart;
  const headers = [
    `From: ${encodeWords(o.fromName)} <${o.fromAddr}>`,
    `To: <${o.to}>`,
    `Subject: ${encodeWords(o.subject)}`,
    `Date: ${new Date().toUTCString().replace("GMT", "+0000")}`,
    `Message-ID: <${id}>`,
    "MIME-Version: 1.0",
    `Content-Type: multipart/alternative; boundary="${alt}"`,
  ].join("\r\n");
  const raw = `${headers}\r\n\r\n--${alt}\r\n${textPart}--${alt}\r\n${htmlBlock}--${alt}--\r\n`;
  return { raw, messageId: id };
}
