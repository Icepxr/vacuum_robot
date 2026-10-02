// QR พร้อมเพย์ (มาตรฐาน EMVCo QR / Thai QR Payment) แบบฝังยอด · ไม่พึ่งบริการภายนอก
// id = เบอร์มือถือ 10 หลัก (0812345678) หรือเลขบัตร/ผู้เสียภาษี 13 หลัก
const tlv = (id: string, v: string) => id + String(v.length).padStart(2, "0") + v;

export function crc16(s: string): string {   // CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) ตามสเปก EMVCo
  let crc = 0xffff;
  for (const b of new TextEncoder().encode(s)) {
    crc ^= b << 8;
    for (let i = 0; i < 8; i++) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
  }
  return crc.toString(16).toUpperCase().padStart(4, "0");
}

export function promptpayPayload(id: string, amount: number): string {
  const acct = id.length === 13 ? tlv("02", id) : tlv("01", "0066" + id.slice(1));   // มือถือ: 0066 + ตัด 0 หน้า
  const body = tlv("00", "01") + tlv("01", "12")                                    // 12 = ใช้ครั้งเดียว (มียอด)
    + tlv("29", tlv("00", "A000000677010111") + acct)
    + tlv("58", "TH") + tlv("53", "764") + tlv("54", amount.toFixed(2)) + "6304";
  return body + crc16(body);
}
