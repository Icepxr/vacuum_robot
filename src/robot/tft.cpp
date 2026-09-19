// tft.cpp — ดู tft.h
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include "tft.h"

bool manualActive(); bool manualTripped(); bool missionRunning(); bool commLinkAlive(); bool robotEstopped();

namespace {
constexpr int PIN_SCK = 38, PIN_MOSI = 39, PIN_DC = 40, PIN_CS = 47;   // §3.2

class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_GC9A01 panel_;
  lgfx::Bus_SPI      bus_;
 public:
  LGFX() {
    auto b = bus_.config();
    b.spi_host = SPI2_HOST; b.spi_mode = 0; b.freq_write = 40000000; b.freq_read = 16000000;
    b.spi_3wire = true; b.use_lock = true; b.dma_channel = SPI_DMA_CH_AUTO;
    b.pin_sclk = PIN_SCK; b.pin_mosi = PIN_MOSI; b.pin_miso = -1; b.pin_dc = PIN_DC;
    bus_.config(b); panel_.setBus(&bus_);
    auto p = panel_.config();
    p.pin_cs = PIN_CS; p.pin_rst = -1; p.pin_busy = -1;         // RST ผูกกับ EN ของชิป — ซอฟต์แวร์ไม่คุม
    p.panel_width = 240; p.panel_height = 240; p.offset_x = 0; p.offset_y = 0;
    p.readable = false; p.invert = true; p.rgb_order = false; p.dlen_16bit = false; p.bus_shared = false;
    panel_.config(p); setPanel(&panel_);
  }
};

LGFX lcd;
LGFX_Sprite spr(&lcd);
bool ready = false, useSprite = false;
TftInfo info;
uint32_t lastDraw = 0;

constexpr uint16_t C_BG = 0x0000, C_INK = 0xFFFF, C_MUT = 0x8410, C_OK = 0x07E0, C_WARN = 0xFD20, C_BAD = 0xF800, C_ACC = 0x2E9F;

// ── หน้าอากาศแบบกราฟิก (C34 · mock ใน scratchpad 19 ก.ย.) ──
// เกจโค้ง 270° เปิดด้านล่าง = eCO2 400→2000 ppm แบ่งสีตาม ENS160 Table 5 (ส่วนที่ยังไม่ถึงเป็นสีจาง) + ขีดขาวที่ค่าปัจจุบัน
// บน: AQI 5 จุด · กลาง: ตัวเลข + ระดับ · ล่าง: แถบ TVOC (0–1000 ppb) · อุณหภูมิ · ความชื้น
struct Seg { int lo, hi; uint16_t c; };
const Seg SEGS[5] = { {400, 600, 0x05E8}, {600, 800, 0x7E27}, {800, 1000, 0xF5E0}, {1000, 1500, 0xFBC0}, {1500, 2000, 0xE924} };
uint16_t dim(uint16_t c) {                                  // สีจาง ~28 % (แยกช่อง RGB565)
  return ((((c >> 11) & 0x1F) * 7 / 25) << 11) | ((((c >> 5) & 0x3F) * 7 / 25) << 5) | ((c & 0x1F) * 7 / 25);
}
float co2Angle(int v) {                                     // 135° (ซ้ายล่าง) → 405° (ขวาล่าง) · ตามเข็ม · 0° = 3 นาฬิกา (LovyanGFX)
  float f = (v - 400) / 1600.0f; if (f < 0) f = 0; if (f > 1) f = 1;
  return 135.0f + 270.0f * f;
}
void drawAirPage(lgfx::LovyanGFX& g, bool fresh) {
  const bool have = fresh && info.co2 >= 0;
  const int co2 = have ? info.co2 : 400;
  for (int i = 0; i < 5; ++i) g.fillArc(120, 120, 107, 94, co2Angle(SEGS[i].lo), co2Angle(SEGS[i].hi), dim(SEGS[i].c));
  if (have) for (int i = 0; i < 5; ++i)
    if (co2 > SEGS[i].lo) g.fillArc(120, 120, 107, 94, co2Angle(SEGS[i].lo), co2Angle(co2 < SEGS[i].hi ? co2 : SEGS[i].hi), SEGS[i].c);
  if (have) { const float a = co2Angle(co2); g.fillArc(120, 120, 112, 90, a - 1.5f, a + 1.5f, C_INK); }
  int lvl = 0; while (lvl < 4 && co2 >= SEGS[lvl].hi) ++lvl;
  const uint16_t lc = SEGS[lvl].c;
  // AQI 5 จุด
  const int aqi = have ? info.aqi : 0;
  const uint16_t ac = aqi <= 2 ? SEGS[0].c : aqi <= 3 ? SEGS[2].c : SEGS[4].c;
  for (int i = 0; i < 5; ++i) g.fillCircle(92 + i * 14, 50, 5, i < aqi ? ac : 0x39E7);
  g.setTextDatum(textdatum_t::middle_center);
  g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG);
  char b[32];
  snprintf(b, sizeof b, have ? "AQI %d/5" : "AQI --", aqi); g.drawString(b, 120, 66);
  // ตัวเลขกลาง
  g.setFont(&fonts::FreeSansBold24pt7b); g.setTextColor(have ? C_INK : C_MUT, C_BG);
  if (have) { snprintf(b, sizeof b, "%d", co2); g.drawString(b, 120, 104); } else g.drawString("--", 120, 104);
  g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG); g.drawString("eCO2 ppm", 120, 128);
  static const char* NAMES[5] = {"EXCELLENT", "GOOD", "FAIR", "POOR", "BAD"};
  g.setFont(&fonts::FreeSansBold9pt7b); g.setTextColor(have ? lc : C_MUT, C_BG); g.drawString(have ? NAMES[lvl] : "waiting", 120, 148);
  // TVOC แถบ
  g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG);
  snprintf(b, sizeof b, have && info.tvoc >= 0 ? "TVOC %d ppb" : "TVOC --", info.tvoc); g.drawString(b, 120, 168);
  g.fillRoundRect(70, 176, 100, 6, 3, 0x2965);
  if (have && info.tvoc >= 0) { int w = info.tvoc * 100 / 1000; if (w > 100) w = 100; if (w > 0) g.fillRoundRect(70, 176, w, 6, 3, 0x7D9F); }
  // อุณหภูมิ / ความชื้น
  g.setFont(&fonts::FreeSansBold9pt7b); g.setTextColor(C_INK, C_BG);
  if (have && info.temp10 > -1000) { snprintf(b, sizeof b, "%.1fC", info.temp10 / 10.0f); g.drawString(b, 92, 196);
                                     snprintf(b, sizeof b, "%d%%", info.rh10 / 10); g.drawString(b, 150, 196); }
  else { g.setTextColor(C_MUT, C_BG); g.drawString("--", 92, 196); g.drawString("--", 150, 196); }
  g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG); g.drawString("temp", 92, 212); g.drawString("humid", 150, 212);
}

// วงแหวนรอบนอก = สถานะรวม (เขียว/เหลือง/แดง) · กลาง = หน้าสลับ IP / ค่าอ่าน / CO2 · ล่าง = โหมด
void draw(lgfx::LovyanGFX& g) {
  const uint32_t now = millis();
  const bool link = commLinkAlive();
  const bool estop = robotEstopped();
  const bool infoFresh = info.rxMs && now - info.rxMs < 5000;
  uint16_t ring = estop ? C_BAD : !link ? C_BAD : (manualTripped() ? C_WARN : C_OK);
  g.fillScreen(C_BG);
  g.fillArc(120, 120, 119, 113, 0, 360, ring);          // บาง 6 px — ให้เกจอากาศด้านในเด่น
  g.setTextColor(C_INK, C_BG);
  g.setTextDatum(textdatum_t::middle_center);
  const uint32_t ph = now % 12000;                          // รอบ 12 s: IP 3 s · ค่าอ่าน 3 s · อากาศ 6 s (หน้ากราฟิกให้เวลาอ่านนานกว่า)
  const int page = ph < 3000 ? 0 : ph < 6000 ? 1 : 2;
  if (estop) {
    g.setFont(&fonts::FreeSansBold18pt7b); g.drawString("E-STOP", 120, 110);
  } else if (!link) {
    g.setFont(&fonts::FreeSansBold12pt7b); g.drawString("NO LINK", 120, 100);
    g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG); g.drawString("waiting for Pi", 120, 130);
  } else if (page == 0) {
    g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG); g.drawString("open in browser", 120, 78);
    g.setFont(&fonts::FreeSansBold12pt7b); g.setTextColor(C_ACC, C_BG);
    g.drawString(infoFresh && info.ip[0] ? info.ip : "no IP yet", 120, 110);
    g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG); g.drawString(":8000/drive", 120, 138);
  } else if (page == 1) {
    g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG); g.drawString("last meter reading", 120, 78);
    g.setFont(&fonts::FreeSansBold24pt7b); g.setTextColor(C_INK, C_BG);
    g.drawString(infoFresh && info.reading[0] ? info.reading : "--", 120, 115);
  } else {
    drawAirPage(g, infoFresh);
  }
  // โหมด (ล่าง)
  if (page != 2 || estop || !link) {
    g.setFont(&fonts::FreeSansBold9pt7b); g.setTextColor(C_INK, C_BG);
    g.drawString(estop ? "stopped" : missionRunning() ? "MISSION" : manualActive() ? "DRIVING" : "READY", 120, 178);
  }
  // จุดหน้า
  if (page != 2) for (int i = 0; i < 3; ++i) g.fillCircle(108 + i * 12, 200, 3, i == page && link && !estop ? C_INK : C_MUT);
}
}  // namespace

void tftSetup() {
  lcd.init();
  lcd.setRotation(0);
  lcd.setBrightness(255);
  spr.setPsram(true);
  spr.setColorDepth(16);
  useSprite = spr.createSprite(240, 240) != nullptr;   // 115 kB ใน PSRAM (N16R8) · ไม่ได้ก็วาดตรง (กะพริบนิดหน่อย)
  ready = true;
  Serial.printf("[tft] GC9A01 SCK%d MOSI%d DC%d CS%d · sprite %s\n", PIN_SCK, PIN_MOSI, PIN_DC, PIN_CS, useSprite ? "PSRAM" : "ไม่มี (วาดตรง)");
}

void tftTick() {
  if (!ready) return;
  const uint32_t now = millis();
  if (now - lastDraw < 200) return;
  lastDraw = now;
  if (useSprite) { draw(spr); spr.pushSprite(0, 0); }
  else draw(lcd);
}

void tftSetInfo(const char* ip, const char* reading, int co2, int tvoc, int aqi, int temp10, int rh10) {
  strncpy(info.ip, ip, sizeof info.ip - 1);
  strncpy(info.reading, reading, sizeof info.reading - 1);
  info.co2 = co2; info.tvoc = tvoc; info.aqi = aqi; info.temp10 = temp10; info.rh10 = rh10; info.rxMs = millis();
}
bool tftReady() { return ready; }
