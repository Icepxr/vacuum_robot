// ทดสอบ src/robot/comm_codec.h บน host (ไม่ต้องมี PlatformIO):
//   clang++ -std=c++17 -I src/robot test/host_comm_codec.cpp -o /tmp/codec && /tmp/codec
// vector ต้องตรงกับ 11_pi5_vision/tests/test_protocol.py
#include <cstdio>
#include "comm_codec.h"

static int fails = 0;
#define CHECK(c) do { if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

int main() {
  CHECK(mrc::crc8("123456789", 9) == 0xF4);
  CHECK(mrc::crc8("E,1000,CAPTURE_REQ,1", 20) == 0xE0);
  CHECK(mrc::crc8("", 0) == 0x00);

  char out[64];
  CHECK(mrc::appendCrc("E,1000,CAPTURE_REQ,1", out, sizeof out) == 23);
  CHECK(strcmp(out, "E,1000,CAPTURE_REQ,1*E0") == 0);

  char good[] = "$K,1,1*1E";   CHECK(mrc::checkFrame(good, strlen(good)) && strcmp(good, "$K,1,1") == 0);
  char badcrc[] = "$K,1,1*00"; CHECK(!mrc::checkFrame(badcrc, strlen(badcrc)));
  char lower[] = "$K,1,1*1e";  CHECK(mrc::checkFrame(lower, strlen(lower)));   // strtol รับ hex ตัวเล็กด้วย
  char nostar[] = "$K,1,1";    CHECK(!mrc::checkFrame(nostar, strlen(nostar)));
  char boot[] = "ESP-ROM:esp32s3-20210327"; CHECK(!mrc::checkFrame(boot, strlen(boot)));
  char shrt[] = "#E*";         CHECK(!mrc::checkFrame(shrt, strlen(shrt)));
  char zz[] = "$K,1,1*ZZ";     CHECK(!mrc::checkFrame(zz, strlen(zz)));
  char sp[] = "$K,1,1* 1";     CHECK(!mrc::checkFrame(sp, strlen(sp)));

  // round trip: ทุกอย่างที่ appendCrc สร้าง checkFrame ต้องรับ
  const char* bodies[] = { "K,7,1", "K,7,0", "E,4294967295,CAPTURE_REQ,99", "P" };
  for (const char* b : bodies) {
    char line[64] = "#";
    mrc::appendCrc(b, line + 1, sizeof line - 1);
    CHECK(mrc::checkFrame(line, strlen(line)) && strcmp(line + 1, b) == 0);
  }
  printf(fails ? "%d FAILED\n" : "all ok\n", fails);
  return fails ? 1 : 0;
}
