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

// วงแหวนรอบนอก = สถานะรวม (เขียว/เหลือง/แดง) · กลาง = หน้าสลับ IP / ค่าอ่าน / CO2 · ล่าง = โหมด
void draw(lgfx::LovyanGFX& g) {
  const uint32_t now = millis();
  const bool link = commLinkAlive();
  const bool estop = robotEstopped();
  const bool infoFresh = info.rxMs && now - info.rxMs < 5000;
  uint16_t ring = estop ? C_BAD : !link ? C_BAD : (manualTripped() ? C_WARN : C_OK);
  g.fillScreen(C_BG);
  g.fillArc(120, 120, 119, 110, 0, 360, ring);
  g.setTextColor(C_INK, C_BG);
  g.setTextDatum(textdatum_t::middle_center);
  const int page = (now / 3000) % 3;                       // 0 IP · 1 ค่าอ่าน · 2 CO2
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
    g.setFont(&fonts::Font2); g.setTextColor(C_MUT, C_BG); g.drawString("eCO2 ppm", 120, 78);
    g.setFont(&fonts::FreeSansBold24pt7b);
    if (infoFresh && info.co2 >= 0) { char b[12]; snprintf(b, sizeof b, "%d", info.co2);
      g.setTextColor(info.co2 >= 1000 ? C_WARN : C_INK, C_BG); g.drawString(b, 120, 115); }
    else { g.setTextColor(C_MUT, C_BG); g.drawString("--", 120, 115); }
  }
  // โหมด (ล่าง)
  g.setFont(&fonts::FreeSansBold9pt7b); g.setTextColor(C_INK, C_BG);
  g.drawString(estop ? "stopped" : missionRunning() ? "MISSION" : manualActive() ? "DRIVING" : "READY", 120, 178);
  // จุดหน้า
  for (int i = 0; i < 3; ++i) g.fillCircle(108 + i * 12, 200, 3, i == page && link && !estop ? C_INK : C_MUT);
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

void tftSetInfo(const char* ip, const char* reading, int co2) {
  strncpy(info.ip, ip, sizeof info.ip - 1);
  strncpy(info.reading, reading, sizeof info.reading - 1);
  info.co2 = co2; info.rxMs = millis();
}
bool tftReady() { return ready; }
