// ทดสอบ: deno test promptpay_test.ts
import { crc16, promptpayPayload } from "./promptpay.ts";
Deno.test("crc16 ccitt-false check value", () => { if (crc16("123456789") !== "29B1") throw new Error(crc16("123456789")); });
Deno.test("payload = ไลบรารีอ้างอิง promptpay-qr", () => {
  const want = "00020101021229370016A000000677010111011300668123456785802TH530376454044.226304"; // + CRC
  const p = promptpayPayload("0812345678", 4.22);
  if (!p.startsWith(want)) throw new Error(p);
});
