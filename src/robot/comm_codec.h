#pragma once
// comm_codec.h — ส่วนที่ไม่ขึ้นกับ Arduino ของลิงก์ Pi 5: CRC8 + ตรวจเฟรม
// แยกออกมาเพื่อคอมไพล์ทดสอบบน host ได้ (test/host_comm_codec.cpp) ด้วย vector เดียวกับ
// 11_pi5_vision/src/mrc_protocol.py — ถ้าสองฝั่งได้ค่าต่างกัน ลิงก์จะเงียบสนิทโดยไม่มี error
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

namespace mrc {

// poly 0x07 · init 0x00 · ไม่ reflect · ไม่ xor-out  →  crc8("123456789") == 0xF4
inline uint8_t crc8(const char* s, size_t n) {
  uint8_t crc = 0;
  for (size_t i = 0; i < n; ++i) {
    crc ^= (uint8_t)s[i];
    for (int b = 0; b < 8; ++b)
      crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x07) : (uint8_t)(crc << 1);
  }
  return crc;
}

// รับบรรทัดที่ตัด \r\n แล้ว (line[len]=='\0') · คืน true ถ้า <$|#><body>*CC และ CRC ตรง
// ผลข้างเคียงเมื่อ true: เขียน '\0' ทับ '*' → line กลายเป็น "<sentinel><body>"
inline bool checkFrame(char* line, size_t len) {
  if (len < 4 || (line[0] != '$' && line[0] != '#')) return false;
  if (line[len - 3] != '*') return false;
  char* end;
  const long want = strtol(line + len - 2, &end, 16);
  if (end != line + len || want < 0 || want > 0xFF) return false;
  if (crc8(line + 1, len - 4) != (uint8_t)want) return false;
  line[len - 3] = '\0';
  return true;
}

// เขียน "<body>*CC" ลง out (ไม่รวม sentinel/\n) · คืนความยาว · out ต้องมีที่ ≥ bodyLen+4
inline size_t appendCrc(const char* body, char* out, size_t outMax) {
  const size_t n = strlen(body);
  if (n + 4 > outMax) return 0;
  memcpy(out, body, n);
  out[n] = '*';
  static const char hex[] = "0123456789ABCDEF";
  const uint8_t c = crc8(body, n);
  out[n + 1] = hex[c >> 4];
  out[n + 2] = hex[c & 0xF];
  out[n + 3] = '\0';
  return n + 3;
}

}  // namespace mrc
