// tft.cpp — ดู tft.h
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include "tft.h"
#include "../pins.h"
#include <math.h>

bool manualActive(); bool manualTripped(); bool missionRunning(); bool commLinkAlive(); bool robotEstopped();

#ifndef TFT_SPI_HZ
#define TFT_SPI_HZ 40000000      // ค่าเดิม C32 · env robot_tftdiag ลดเป็น 10 MHz ไว้ตัดปัญหาสายยาว (10 ต.ค. จอไม่ขึ้นภาพ)
#endif

namespace {
#ifndef TFT_PIN_SCK
#define TFT_PIN_SCK PIN_TFT_SCK   // ../pins.h · env robot_tftdiag ย้ายไป 41 ชั่วคราว (10 ต.ค.)
#endif
#ifndef TFT_PIN_MOSI
#define TFT_PIN_MOSI PIN_TFT_MOSI // ../pins.h · env robot_tftdiag ย้ายไป 42 ชั่วคราว
#endif
constexpr int PIN_SCK = TFT_PIN_SCK, PIN_MOSI = TFT_PIN_MOSI, PIN_DC = PIN_TFT_DC, PIN_CS = PIN_TFT_CS;

// จอที่ใช้: ค่าเริ่ม = GC9A01 กลม 240×240 (C32) · -D TFT_ST7735 = 1.8" ST7735S 128×160 บอร์ดแดง V1.1 (C64 · 12 ต.ค. จอกลมเสีย)
#ifdef TFT_ST7735
constexpr int PANEL_W = 128, PANEL_H = 160;   // ขนาดชิป (แนวตั้ง)
constexpr int SCR_W = 160, SCR_H = 128;       // ใช้งานแนวนอน — แบบ B "Signal split" (design/aria-st7735-landscape-prototype)
#ifndef TFT_ROTATION
#define TFT_ROTATION 1                        // 1 / 3 = แนวนอนสองทิศ · ติดตั้งกลับหัวให้ใช้ 3
#endif
#else
constexpr int PANEL_W = 240, PANEL_H = 240;
constexpr int SCR_W = 240, SCR_H = 240;
#define TFT_ROTATION 0
#endif

class LGFX : public lgfx::LGFX_Device {
#ifdef TFT_ST7735
  lgfx::Panel_ST7735S panel_;
#else
  lgfx::Panel_GC9A01 panel_;
#endif
  lgfx::Bus_SPI      bus_;
 public:
  LGFX() {
    auto b = bus_.config();
    b.spi_host = SPI2_HOST; b.spi_mode = 0; b.freq_write = TFT_SPI_HZ; b.freq_read = 16000000;
    b.spi_3wire = true; b.use_lock = true; b.dma_channel = SPI_DMA_CH_AUTO;
    b.pin_sclk = PIN_SCK; b.pin_mosi = PIN_MOSI; b.pin_miso = -1; b.pin_dc = PIN_DC;
    bus_.config(b); panel_.setBus(&bus_);
    auto p = panel_.config();
    p.pin_cs = PIN_CS; p.pin_rst = -1; p.pin_busy = -1;         // RST ผูกกับ EN ของชิป — ซอฟต์แวร์ไม่คุม (ST7735S ส่ง SWRESET ตอน init อยู่แล้ว)
#ifdef TFT_ST7735
    // บอร์ดแดง 1.8" มีหลายล็อต (red/black/green tab) — ถ้าขอบจอมีแถบขยะ ปรับ offset · สีแดง↔น้ำเงินสลับ ให้กลับ rgb_order
    p.memory_width = 132; p.memory_height = 162;
    p.panel_width = PANEL_W; p.panel_height = PANEL_H;
// ล็อตที่ใช้อยู่ (12 ต.ค. รูปจริง): offset (2,1) เหลือแถบขยะขอบบน/ซ้าย → (0,0) · พื้นม่วงออกชมพู (แดง↔น้ำเงินสลับ) → rgb_order = true
#ifndef TFT_OFS_X
#define TFT_OFS_X 0
#endif
#ifndef TFT_OFS_Y
#define TFT_OFS_Y 0
#endif
#ifndef TFT_RGB_ORDER
#define TFT_RGB_ORDER true
#endif
    p.offset_x = TFT_OFS_X; p.offset_y = TFT_OFS_Y;
    p.readable = false; p.invert = false; p.rgb_order = TFT_RGB_ORDER; p.dlen_16bit = false; p.bus_shared = false;
#else
    p.panel_width = 240; p.panel_height = 240; p.offset_x = 0; p.offset_y = 0;
    p.readable = false; p.invert = true; p.rgb_order = false; p.dlen_16bit = false; p.bus_shared = false;
#endif
    panel_.config(p); setPanel(&panel_);
  }
};

LGFX lcd;
LGFX_Sprite spr(&lcd);
bool ready = false, useSprite = false;
TftInfo info;
uint32_t lastDraw = 0;

// Approved outer-ring identity: no wordmark, faces or mode text.
constexpr uint16_t rgb(int r,int g,int b) { return ((r>>3)<<11)|((g>>2)<<5)|(b>>3); }
// 29 ก.ย. 2026 ผู้ใช้ (2 รอบ): ม่วงเดิมมืด/หม่น → พื้นสว่างขึ้น + สีวงแหวนทุก state สดขึ้น (แทนโทนนุ่มที่เคยอนุมัติ)
// พื้น L_hsl 7 % → 33 % · รางวงแหวนเปลี่ยนเป็น "ร่อง" เข้มกว่าพื้น ให้สีสดเด่นบนราง
// คอนทราสต์ (หลังปัด RGB565 · ไฟล์ 19 §19.11): ตัวอักษรบนพื้น INK 11.9 · MUT 8.4 · UNKNOWN 5.7 · ACC 7.1 · OK 8.3 · WARN 8.1 · BAD 4.5
//   สีวงแหวนบนราง ≥ 6.3 · รางเทียบพื้น 1.4
// ค่าเดิม (ก่อน 29 ก.ย.): BG (16,11,27) · PANEL (52,38,63) · INK (245,239,255) · MUT (166,154,182) · UNKNOWN (113,103,127)
//   ACC (182,160,207) · OK (158,217,189) · WARN (230,207,148) · BAD (237,150,164) · STOP_BG 0x3803
constexpr uint16_t C_BG=rgb(70,34,132), C_PANEL=rgb(40,14,86), C_INK=rgb(255,255,255);
constexpr uint16_t C_MUT=rgb(222,210,250), C_UNKNOWN=rgb(186,168,228), C_ACC=rgb(232,178,255);
constexpr uint16_t C_OK=rgb(64,240,170), C_WARN=rgb(255,204,64), C_BAD=rgb(255,112,146), C_STOP_BG=rgb(128,16,44);

// ── ตำแหน่ง/ขนาดของจอกลม (ตัวเลขเดิมทุกตัว · วงแหวน) — จอเหลี่ยมแนวนอนใช้ชุดฟังก์ชัน rect* ด้านล่าง ──
// ข้อมูล ลำดับหน้า (selectPage) สถานะ HUD สี สัญลักษณ์ ใช้ร่วมกันทั้งสองจอ
struct Layout {
  int cx;
  int hudX0, hudStep, hudY;
  int symCy;
  const lgfx::IFont* labelFont; int labelY, labelW, hintY, hintW;
  const lgfx::IFont* bigFont; const lgfx::IFont* bigFontLong; int bigY, bigW;
  int unitY, tvocY, tvocW, envIconY, envTextY, tIconX, tTextX, hIconX, hTextX;
  const lgfx::IFont* estopFont; int estopY, estopHintY;
  const lgfx::IFont* ipFont; int ipY, ipW, urlY;
  int readLabelY, readSavedY;
};
const Layout L = { 120, 72, 26, 43,  102,
  &fonts::FreeSansBold12pt7b, 164, 196, 191, 164,
  &fonts::FreeSansBold24pt7b, &fonts::FreeSansBold18pt7b, 115, 196,
  145, 174, 170, 197, 207, 65, 94, 129, 157,
  &fonts::FreeSansBold18pt7b, 159, 191,
  &fonts::FreeSansBold9pt7b, 161, 196, 190,
  162, 190 };
#ifdef TFT_ST7735
constexpr bool RECT = true;
#else
constexpr bool RECT = false;
#endif

// Clip only display copy, never the underlying IP / telemetry / protocol data.
void drawFitted(lgfx::LovyanGFX& g, const char* text, int y, int width, int x = L.cx) {
  char out[64]; snprintf(out, sizeof out, "%s", text ? text : "");
  if (g.textWidth(out) > width) {
    size_t n = strlen(out);
    while (n > 0) {
      out[--n] = '\0';
      char candidate[68]; snprintf(candidate, sizeof candidate, "%s...", out);
      if (n + 3 < sizeof out && g.textWidth(candidate) <= width) { memcpy(out + n, "...", 4); break; }
    }
  }
  g.drawString(out, x, y);
}

// Abstract symbols only: no eyes, mouth or mascot face.
enum class Symbol { Orbit, Camera, Check, Retry, Link, Heat, Pause, Stop };
void drawSymbol(lgfx::LovyanGFX& g, Symbol symbol, uint16_t tint, int cx = L.cx, int cy = L.symCy, float sc = 1.0f) {
  const uint16_t background = symbol == Symbol::Stop ? C_STOP_BG : C_BG;
  // พิกัดต้นฉบับของจอกลม (กลาง 120,102 · กว้าง 64 px) → แปลงไปจุดกลาง cx,cy และย่อด้วย sc (จอเหลี่ยม ≈ 0.55 = 34 px ตามต้นแบบ B)
  auto X=[&](int v){ return cx + (int)lroundf((v-120)*sc); };
  auto Y=[&](int v){ return cy + (int)lroundf((v-102)*sc); };
  auto S=[&](int v){ int r=(int)lroundf(v*sc); return r<1 ? 1 : r; };
  auto T=[&](int v){ int r=(int)lroundf(v*sc); return r<2 ? 2 : r; };     // ความหนาเส้น/ขอบ ไม่บางกว่า 2 px
  auto ring=[&](int x,int y,int ro,int ri,float a0,float a1,uint16_t c){ int o=S(ro); g.fillArc(X(x),Y(y),o,o-T(ro-ri),a0,a1,c); };
  // Shared outer frame carries the state; no extra inner rings or boxed cards.
  switch (symbol) {
    case Symbol::Camera: {
      const int t=T(2);
      g.fillRoundRect(X(88), Y(80), S(64), S(45), S(12), tint);
      g.fillRoundRect(X(88)+t, Y(80)+t, S(64)-2*t, S(45)-2*t, S(10), background);
      g.fillRoundRect(X(104), Y(75), S(32), T(9), S(4), tint);
      ring(120,103,15,11,0,360,tint);
      break; }
    case Symbol::Check: {
      const int k=(int)lroundf(2*sc);
      for (int d=-k; d<=k; ++d) {
        g.drawLine(X(99), Y(103)+d, X(115), Y(118)+d, tint);
        g.drawLine(X(115), Y(118)+d, X(144), Y(86)+d, tint);
      }
      break; }
    case Symbol::Retry:
      ring(120,102,26,23,35,325,tint);
      g.drawLine(X(140), Y(86), X(148), Y(89), tint); g.drawLine(X(148), Y(89), X(147), Y(78), tint);
      break;
    case Symbol::Link:
      ring(120,118,33,30,220,320,tint);
      ring(120,118,21,18,220,320,tint);
      g.fillCircle(X(120), Y(116), T(4), tint);
      break;
    case Symbol::Heat: {
      const int t=T(4);
      g.fillRoundRect(X(114), Y(74), T(12), S(45), S(6), tint);
      g.fillRoundRect(X(114)+t, Y(74)+t, T(12)-2*t>0 ? T(12)-2*t : 1, S(29), S(2), background);
      g.fillCircle(X(120), Y(119), S(12), tint);
      g.drawLine(X(141), Y(81), X(149), Y(81), tint); g.drawLine(X(141), Y(94), X(149), Y(94), tint);
      break; }
    case Symbol::Pause:
      g.fillRoundRect(X(105), Y(83), T(10), S(38), S(5), tint);
      g.fillRoundRect(X(125), Y(83), T(10), S(38), S(5), tint);
      break;
    case Symbol::Stop:
      ring(120,102,32,28,0,360,tint);
      g.fillRoundRect(X(109), Y(91), S(22), S(22), S(4), C_INK);
      break;
    case Symbol::Orbit:
      ring(120,102,28,25,195,315,tint);
      ring(120,102,28,25,15,125,tint);
      g.fillCircle(X(144), Y(88), T(4), tint);
      g.fillCircle(X(120), Y(102), T(5), C_INK);
      break;
  }
}

enum class Page {
  Ready, Driving, Mission, AirWaiting, Welcome, DataWaiting,
  Connecting, Offline, Capturing, Saved, Reading, Unreadable, CaptureFailed,
  Deadman, NoWifi, Hot, NoCamera, Disk, NoAir, OtherWarning, OtherEvent, Estop
};
bool is(const char* a, const char* b) { return strcmp(a, b) == 0; }

Page selectPage(bool fresh) {
  // Existing priority retained; local deadman also has explicit presentation.
  if (robotEstopped()) return Page::Estop;
  if (!commLinkAlive()) return info.rxMs ? Page::Offline : Page::Connecting;
  const char* evt = fresh ? info.evt : "";
  const char* warn = fresh ? info.warn : "";
  if (is(evt, "CAP")) return Page::Capturing;
  if (is(evt, "SAVED")) return Page::Saved;
  if (is(evt, "READ")) return Page::Reading;
  if (is(evt, "NOREAD")) return Page::Unreadable;
  if (is(evt, "CAPFAIL")) return Page::CaptureFailed;
  if (is(evt, "DEADMAN")) return Page::Deadman;
  if (evt[0]) return Page::OtherEvent;
  if (is(warn, "NOIP")) return Page::NoWifi;
  if (is(warn, "HOT")) return Page::Hot;
  if (manualTripped()) return Page::Deadman;
  if (!fresh) return Page::DataWaiting;
  if (info.clients == 0) return Page::Welcome;
  if (is(warn, "NOCAM")) return Page::NoCamera;
  if (is(warn, "DISK")) return Page::Disk;
  if (is(warn, "NOAIR")) return Page::NoAir;
  if (warn[0]) return Page::OtherWarning;
  if (missionRunning()) return Page::Mission;
  if (manualActive()) return Page::Driving;
  return info.co2 < 0 ? Page::AirWaiting : Page::Ready;
}


enum class Health { Unknown, Ready, Bad, Warning, Idle };
enum class Mode { Idle, Manual, Mission, Paused };
struct Hud { Health link, camera, network, modeHealth; Mode mode; };
Hud hudState(bool fresh) {
  Hud h{commLinkAlive() ? (fresh ? Health::Ready : Health::Warning) : Health::Bad,
        Health::Unknown, Health::Unknown, Health::Idle, Mode::Idle};
  // Network glyph means Pi has an IP; it does not assert Wi-Fi or internet access.
  if(fresh) h.network = is(info.warn,"NOIP") || !info.ip[0] ? Health::Bad : Health::Ready;
  // $D has one priority warning, not independently reported subsystem health.
  // A newer frame with no earlier warning confirms the camera-fallback check ran.
  if(fresh && info.clients>=0) {
    if(is(info.warn,"NOCAM") || is(info.evt,"CAPFAIL")) h.camera=Health::Bad;
    else if(!info.warn[0] || is(info.warn,"DISK") || is(info.warn,"NOAIR")) h.camera=Health::Ready;
  }
  if(robotEstopped() || manualTripped() || (fresh && is(info.evt,"DEADMAN"))) {
    h.mode=Mode::Paused; h.modeHealth=robotEstopped() ? Health::Bad : Health::Warning;
  } else if(missionRunning()) { h.mode=Mode::Mission; h.modeHealth=Health::Ready; }
  else if(manualActive()) { h.mode=Mode::Manual; h.modeHealth=Health::Ready; }
  return h;
}
uint16_t healthColor(Health health) {
  return health==Health::Bad ? C_BAD : health==Health::Warning ? C_WARN
    : health==Health::Ready ? C_ACC : C_UNKNOWN;
}
enum class SmallIcon { Link, Camera, Network, Joystick, Route, Pause, Thermo, Drop };
void smallIcon(lgfx::LovyanGFX& g, SmallIcon icon, int x,int y,uint16_t c,uint16_t bg) {
  switch(icon) {
    case SmallIcon::Link:
      g.fillRoundRect(x+1,y+5,10,8,4,c); g.fillRoundRect(x+3,y+7,6,4,2,bg);
      g.fillRoundRect(x+8,y+5,10,8,4,c); g.fillRoundRect(x+10,y+7,6,4,2,bg);
      g.fillRect(x+6,y+8,7,2,c); break;
    case SmallIcon::Camera:
      g.fillRoundRect(x+1,y+5,16,11,3,c); g.fillRoundRect(x+3,y+7,12,7,2,bg);
      g.fillRoundRect(x+6,y+3,6,3,1,c); g.fillCircle(x+9,y+10,3,c); g.fillCircle(x+9,y+10,1,bg); break;
    case SmallIcon::Network:
      g.fillArc(x+9,y+14,9,7,220,320,c); g.fillArc(x+9,y+14,5,3,220,320,c);
      g.fillCircle(x+9,y+15,1,c); break;
    case SmallIcon::Joystick:
      g.fillRoundRect(x+2,y+12,14,5,2,c); g.fillRoundRect(x+4,y+13,10,2,1,bg);
      g.fillRect(x+8,y+6,2,7,c); g.fillCircle(x+9,y+4,3,c); g.fillCircle(x+9,y+4,1,bg); break;
    case SmallIcon::Route:
      g.fillCircle(x+3,y+15,2,c); g.fillCircle(x+15,y+4,2,c);
      g.drawLine(x+5,y+15,x+12,y+15,c); g.drawLine(x+12,y+15,x+12,y+9,c);
      g.drawLine(x+12,y+9,x+7,y+9,c); g.drawLine(x+7,y+9,x+7,y+4,c);
      g.drawLine(x+7,y+4,x+13,y+4,c); break;
    case SmallIcon::Pause:
      g.fillRoundRect(x+4,y+5,3,10,1,c); g.fillRoundRect(x+11,y+5,3,10,1,c); break;
    case SmallIcon::Thermo:
      g.fillRoundRect(x+4,y+1,5,9,2,c); g.fillRoundRect(x+6,y+3,1,5,0,bg);
      g.fillCircle(x+6,y+10,3,c); g.fillCircle(x+6,y+10,1,bg); break;
    case SmallIcon::Drop:
      g.drawLine(x+6,y+1,x+2,y+8,c); g.drawLine(x+6,y+1,x+10,y+8,c);
      g.fillArc(x+6,y+8,4,3,0,180,c); break;
  }
}
void drawHudIcon(lgfx::LovyanGFX& g,SmallIcon icon,int x,Health health,int y=L.hudY,uint16_t bg=C_BG) {
  const uint16_t c=healthColor(health);
  smallIcon(g,icon,x,y,c,bg);
  if(health==Health::Bad) {
    g.drawLine(x+2,y+16,x+17,y+1,c); g.drawLine(x+2,y+17,x+17,y+2,c);
  }
}
void drawHud(lgfx::LovyanGFX& g,bool fresh) {
  const Hud h=hudState(fresh);
  const int x=L.hudX0, d=L.hudStep;
  drawHudIcon(g,SmallIcon::Link,x,h.link); drawHudIcon(g,SmallIcon::Camera,x+d,h.camera);
  drawHudIcon(g,SmallIcon::Network,x+2*d,h.network);
  drawHudIcon(g,h.mode==Mode::Mission ? SmallIcon::Route : h.mode==Mode::Manual ? SmallIcon::Joystick : SmallIcon::Pause,x+3*d,h.modeHealth);
}

// Same 400–2000 ppm mapping and band boundaries, with the approved softer colors.
struct Seg { int lo, hi; uint16_t c; };
// แถบ eCO2 สดขึ้น (29 ก.ย.) · เดิม (158,217,189) (195,215,154) (230,207,148) (235,173,134) (237,150,164)
const Seg SEGS[5]={{400,600,C_OK},{600,800,rgb(184,240,80)},{800,1000,C_WARN},
  {1000,1500,rgb(255,150,72)},{1500,2000,C_BAD}};
int airLevel() { int level=0; while(level<4 && info.co2>=SEGS[level].hi) ++level; return level; }
float airAngle(int value) {
  float f=(value-400)/1600.0f; if(f<0) f=0; if(f>1) f=1; return 135.0f+270.0f*f;
}
void ringCap(lgfx::LovyanGFX& g,float angle,uint16_t color) {
  const float a=angle*0.01745329252f;
  g.fillCircle((int)roundf(120+116*cosf(a)),(int)roundf(120+116*sinf(a)),4,color);
}
void ringArc(lgfx::LovyanGFX& g,float start,float end,uint16_t color) {
  if(end<=start) return;
  g.fillArc(120,120,120,112,start,end,color);
  if(end-start<360) { ringCap(g,start,color); ringCap(g,end,color); }
}
void frame(lgfx::LovyanGFX& g,uint16_t color,bool full=false) {
  if(full) ringArc(g,0,360,color); else ringArc(g,135,405,color);
}
void airGauge(lgfx::LovyanGFX& g,bool gas) {
  ringArc(g,135,405,C_PANEL);
  if(gas && info.co2>400) ringArc(g,135,airAngle(info.co2),SEGS[airLevel()].c);
}
void drawAirPage(lgfx::LovyanGFX& g,Page page) {
  const bool noAir=page==Page::NoAir, gas=info.co2>=0 && !noAir;
  airGauge(g,gas);
  g.setFont(L.bigFont); g.setTextColor(gas ? C_INK : C_MUT,C_BG);
  char b[40]; if(gas) snprintf(b,sizeof b,"%d",info.co2); else snprintf(b,sizeof b,"--");
  drawFitted(g,b,L.bigY,L.bigW);
  g.setFont(&fonts::Font0); g.setTextColor(C_MUT,C_BG); g.drawString("eCO2 ppm",L.cx,L.unitY);
  if(page==Page::Disk || noAir || page==Page::OtherWarning) {
    g.setTextColor(C_WARN,C_BG); drawFitted(g,page==Page::Disk ? "Storage low" : noAir ? "No air sensor" : info.warn,L.tvocY,L.tvocW);
  } else {
    if(info.tvoc>=0) snprintf(b,sizeof b,"TVOC %d ppb",info.tvoc); else snprintf(b,sizeof b,"TVOC -- ppb");
    drawFitted(g,b,L.tvocY,L.tvocW);
  }
  smallIcon(g,SmallIcon::Thermo,L.tIconX,L.envIconY,C_MUT,C_BG); smallIcon(g,SmallIcon::Drop,L.hIconX,L.envIconY,C_MUT,C_BG);
  g.setFont(&fonts::Font2); g.setTextColor(C_INK,C_BG);
  if(info.temp10>-1000) snprintf(b,sizeof b,"%.1fC",info.temp10/10.0f); else snprintf(b,sizeof b,"--C");
  g.drawString(b,L.tTextX,L.envTextY);
  if(info.rh10>=0) snprintf(b,sizeof b,"%d%%",info.rh10/10); else snprintf(b,sizeof b,"--%%");
  g.drawString(b,L.hTextX,L.envTextY);
}
void drawMessage(lgfx::LovyanGFX& g,Symbol symbol,uint16_t tint,const char* label,const char* hint=nullptr) {
  // A uniform status frame, NOT a fabricated task-progress percentage.
  frame(g,tint);
  drawSymbol(g,symbol,tint);
  g.setFont(L.labelFont); g.setTextColor(tint,C_BG); drawFitted(g,label,L.labelY,L.labelW);
  if(hint && hint[0]) { g.setFont(&fonts::Font2); g.setTextColor(C_MUT,C_BG); drawFitted(g,hint,L.hintY,L.hintW); }
}
// ═══ จอเหลี่ยมแนวนอน 160×128 · แบบ B "Signal split" (12 ต.ค. · design/aria-st7735-landscape-prototype ?variant=B) ═══
// ซ้าย = rail 25 px ไอคอน HUD เรียงลง · ขวา = ข้อมูล · หน้าเหตุการณ์มีเส้นสีสถานะบน (แทนวงแหวน) · E-STOP พื้นแดงทั้งจอ ไม่มี HUD
constexpr int RAIL_W = 25, RCX = 92, RW = 126;       // กลางพื้นที่ข้อมูล x = 92 · กว้างใช้ได้ ≈ 126 px
void rectRail(lgfx::LovyanGFX& g,bool fresh) {
  g.fillRect(0,0,RAIL_W,SCR_H,C_PANEL);
  const Hud h=hudState(fresh);
  drawHudIcon(g,SmallIcon::Link,3,h.link,18,C_PANEL);
  drawHudIcon(g,SmallIcon::Camera,3,h.camera,43,C_PANEL);
  drawHudIcon(g,SmallIcon::Network,3,h.network,68,C_PANEL);
  drawHudIcon(g,h.mode==Mode::Mission ? SmallIcon::Route : h.mode==Mode::Manual ? SmallIcon::Joystick : SmallIcon::Pause,3,h.modeHealth,93,C_PANEL);
}
void rectTopLine(lgfx::LovyanGFX& g,uint16_t tone,int y=17,int t=3) { g.fillRect(35,y,113,t,tone); }
void rectGauge(lgfx::LovyanGFX& g,bool gas) {
  const int x0=38, w=106, y=74, h=5;
  auto xAt=[&](int v){ float f=(v-400)/1600.0f; if(f<0) f=0; if(f>1) f=1; return x0+(int)roundf(w*f); };
  g.fillRoundRect(x0,y,w,h,2,C_PANEL);
  if(gas && info.co2>400) g.fillRoundRect(x0,y,xAt(info.co2)-x0,h,2,SEGS[airLevel()].c);
  for(int i=1;i<5;++i) g.drawFastVLine(xAt(SEGS[i].lo),y+h+1,2,C_UNKNOWN);     // 600 / 800 / 1000 / 1500
}
void rectAir(lgfx::LovyanGFX& g,Page page) {
  const bool noAir=page==Page::NoAir, gas=info.co2>=0 && !noAir;
  char b[40];
  g.setTextDatum(textdatum_t::middle_center);
  g.setFont(&fonts::FreeSansBold18pt7b); g.setTextColor(gas ? C_INK : C_UNKNOWN,C_BG);
  if(gas) snprintf(b,sizeof b,"%d",info.co2); else snprintf(b,sizeof b,"--");
  drawFitted(g,b,44,RW,RCX);
  g.setFont(&fonts::Font0); g.setTextColor(C_MUT,C_BG); g.drawString("eCO2 ppm",RCX,63);
  rectGauge(g,gas);
  g.setTextDatum(textdatum_t::top_left);
  if(page==Page::Disk || noAir || page==Page::OtherWarning) {
    g.setTextColor(C_WARN,C_BG); g.drawString(page==Page::Disk ? "Storage low" : noAir ? "No air sensor" : info.warn,39,86);
  } else {
    if(info.tvoc>=0) snprintf(b,sizeof b,"TVOC %d ppb",info.tvoc); else snprintf(b,sizeof b,"TVOC -- ppb");
    g.setTextColor(C_MUT,C_BG); g.drawString(b,39,86);
  }
  smallIcon(g,SmallIcon::Thermo,37,101,C_MUT,C_BG); smallIcon(g,SmallIcon::Drop,95,101,C_MUT,C_BG);
  g.setFont(&fonts::Font2); g.setTextColor(C_INK,C_BG);
  if(info.temp10>-1000) snprintf(b,sizeof b,"%.1fC",info.temp10/10.0f); else snprintf(b,sizeof b,"--C");
  g.drawString(b,53,101);
  if(info.rh10>=0) snprintf(b,sizeof b,"%d%%",info.rh10/10); else snprintf(b,sizeof b,"--%%");
  g.drawString(b,110,101);
  g.setTextDatum(textdatum_t::middle_center);
}
void rectMessage(lgfx::LovyanGFX& g,Symbol symbol,uint16_t tone,const char* label,const char* hint=nullptr) {
  rectTopLine(g,tone);
  drawSymbol(g,symbol,tone,RCX,50,0.55f);
  g.setFont(&fonts::FreeSansBold9pt7b); g.setTextColor(tone,C_BG); drawFitted(g,label,82,RW,RCX);
  if(hint && hint[0]) { g.setFont(&fonts::Font2); g.setTextColor(C_MUT,C_BG); drawFitted(g,hint,101,RW,RCX); }
}
void drawRect(lgfx::LovyanGFX& g,Page page,bool fresh) {
  if(page==Page::Estop) {
    g.fillScreen(C_STOP_BG); g.fillRect(0,0,RAIL_W,SCR_H,rgb(79,6,25));
    rectTopLine(g,C_BAD,15,4);
    drawSymbol(g,Symbol::Stop,C_BAD,RCX,46,0.5f);
    g.setFont(&fonts::FreeSansBold12pt7b); g.setTextColor(C_INK,C_STOP_BG); g.drawString("E-STOP",RCX,82);
    g.setFont(&fonts::Font2); g.drawString("Motors off",RCX,101);
    return;
  }
  g.fillScreen(C_BG);
  rectRail(g,fresh);
  switch(page) {
    case Page::Connecting: rectMessage(g,Symbol::Orbit,C_MUT,"Connecting"); break;
    case Page::Offline: rectMessage(g,Symbol::Link,C_BAD,"Pi offline","Check USB"); break;
    case Page::DataWaiting: rectMessage(g,Symbol::Orbit,C_WARN,"Data pending"); break;
    case Page::Welcome:
      drawSymbol(g,Symbol::Link,C_ACC,RCX,36,0.5f);
      g.setFont(&fonts::Font2); g.setTextColor(C_INK,C_BG);         // IP ห้ามถูกตัด → Font2 (≈ 7 px/ตัว · 15 ตัว = 105 px)
      g.drawString(info.ip[0] ? info.ip : "No IP yet",RCX,74);
      g.setTextColor(C_MUT,C_BG); g.drawString(":8000/drive",RCX,94); break;
    case Page::Capturing: rectMessage(g,Symbol::Camera,C_ACC,"Capturing"); break;
    case Page::Saved: rectMessage(g,Symbol::Check,C_OK,"Photo saved","Reading..."); break;
    case Page::Reading:
      g.setFont(strlen(info.arg)>6 ? &fonts::FreeSansBold12pt7b : &fonts::FreeSansBold18pt7b);
      g.setTextColor(C_INK,C_BG); drawFitted(g,info.arg[0] ? info.arg : "?",50,RW,RCX);
      g.setFont(&fonts::Font2); g.setTextColor(C_OK,C_BG); g.drawString("Meter reading",RCX,77);
      g.setFont(&fonts::Font0); g.setTextColor(C_MUT,C_BG); g.drawString("Saved",RCX,95); break;
    case Page::Unreadable: rectMessage(g,Symbol::Retry,C_WARN,"Try again","Adjust framing"); break;
    case Page::CaptureFailed: rectMessage(g,Symbol::Camera,C_BAD,"Camera error",info.arg[0] ? info.arg : "No frame"); break;
    case Page::Deadman: rectMessage(g,Symbol::Pause,C_WARN,"Drive paused","Reconnect"); break;
    case Page::NoWifi: rectMessage(g,Symbol::Link,C_BAD,"No IP","Check network"); break;
    case Page::Hot: rectMessage(g,Symbol::Heat,C_BAD,"Pi too hot","Let it cool"); break;
    case Page::OtherEvent: rectMessage(g,Symbol::Orbit,C_ACC,info.evt,info.arg); break;
    default: rectAir(g,page); break;
  }
}

void draw(lgfx::LovyanGFX& g) {
  const bool fresh=info.rxMs && millis()-info.rxMs<5000;
  const Page page=selectPage(fresh);
  g.setTextDatum(textdatum_t::middle_center);
  if(RECT) { drawRect(g,page,fresh); return; }
  const bool emergency=page==Page::Estop;
  g.fillScreen(emergency ? C_STOP_BG : C_BG);
  if(!emergency) drawHud(g,fresh);
  switch(page) {
    case Page::Estop:
      frame(g,C_BAD,true); drawSymbol(g,Symbol::Stop,C_BAD);
      g.setFont(L.estopFont); g.setTextColor(C_INK,C_STOP_BG); g.drawString("E-STOP",L.cx,L.estopY);
      g.setFont(&fonts::Font2); g.drawString("Motors off",L.cx,L.estopHintY); break;
    case Page::Connecting: drawMessage(g,Symbol::Orbit,C_MUT,"Connecting"); break;
    case Page::Offline: drawMessage(g,Symbol::Link,C_BAD,"Pi offline","Check USB"); break;
    case Page::DataWaiting: drawMessage(g,Symbol::Orbit,C_WARN,"Data pending"); break;
    case Page::Welcome:
      frame(g,C_ACC); drawSymbol(g,Symbol::Link,C_ACC);
      g.setFont(L.ipFont); g.setTextColor(C_INK,C_BG);
      drawFitted(g,info.ip[0] ? info.ip : "No IP yet",L.ipY,L.ipW);
      g.setFont(&fonts::Font2); g.setTextColor(C_MUT,C_BG); g.drawString(":8000/drive",L.cx,L.urlY); break;
    case Page::Capturing: drawMessage(g,Symbol::Camera,C_ACC,"Capturing"); break;
    case Page::Saved: drawMessage(g,Symbol::Check,C_OK,"Photo saved","Reading..."); break;
    case Page::Reading:
      frame(g,C_OK);
      g.setFont(strlen(info.arg)>7 ? L.bigFontLong : L.bigFont);
      g.setTextColor(C_INK,C_BG); drawFitted(g,info.arg[0] ? info.arg : "?",L.bigY,L.bigW);
      g.setFont(&fonts::Font2); g.setTextColor(C_OK,C_BG); g.drawString("Meter reading",L.cx,L.readLabelY);
      g.setFont(&fonts::Font0); g.setTextColor(C_MUT,C_BG); g.drawString("Saved",L.cx,L.readSavedY); break;
    case Page::Unreadable: drawMessage(g,Symbol::Retry,C_WARN,"Try again","Adjust framing"); break;
    case Page::CaptureFailed: drawMessage(g,Symbol::Camera,C_BAD,"Camera error",info.arg[0] ? info.arg : "No frame"); break;
    case Page::Deadman: drawMessage(g,Symbol::Pause,C_WARN,"Drive paused","Reconnect"); break;
    case Page::NoWifi: drawMessage(g,Symbol::Link,C_BAD,"No IP","Check network"); break;
    case Page::Hot: drawMessage(g,Symbol::Heat,C_BAD,"Pi too hot","Let it cool"); break;
    case Page::OtherEvent: drawMessage(g,Symbol::Orbit,C_ACC,info.evt,info.arg); break;
    default: drawAirPage(g,page); break;
  }
}
}  // namespace

void tftSetup() {
  lcd.init();
  lcd.setRotation(TFT_ROTATION);
  lcd.setBrightness(255);
  spr.setPsram(true);
  spr.setColorDepth(16);
  useSprite = spr.createSprite(SCR_W, SCR_H) != nullptr;   // กลม 115 kB / เหลี่ยม 40 kB ใน PSRAM (N16R8) · ไม่ได้ก็วาดตรง (กะพริบนิดหน่อย)
  ready = true;
#ifdef TFT_ST7735
  const char* panelName = "ST7735S 160x128 แนวนอน (แบบ B)";
#else
  const char* panelName = "GC9A01";
#endif
  Serial.printf("[tft] %s SCK%d MOSI%d DC%d CS%d · SPI %d MHz · sprite %s\n", panelName, PIN_SCK, PIN_MOSI, PIN_DC, PIN_CS,
                (int)(TFT_SPI_HZ / 1000000), useSprite ? "PSRAM" : "ไม่มี (วาดตรง)");
#ifdef TFT_BOOT_TEST
  // ทดสอบจอ (env robot_tftdiag): สีพื้นเต็มจอ แดง → เขียว → น้ำเงิน → ขาว ช่วงละ 0.5 s · เห็นสี = จอรับคำสั่ง SPI ได้
  const uint16_t cols[] = {TFT_RED, TFT_GREEN, TFT_BLUE, TFT_WHITE};
  const char* names[] = {"แดง", "เขียว", "น้ำเงิน", "ขาว"};
  for (int i = 0; i < 4; ++i) { lcd.fillScreen(cols[i]); Serial.printf("[tft] ทดสอบสี %s\n", names[i]); delay(500); }
  // กรอบขอบจอ + ป้ายมุม: เห็นเส้นครบ 4 ด้านชิดขอบ = offset ถูก · ตัวหนังสือ R/G/B ตรงสี = rgb_order ถูก
  lcd.fillScreen(TFT_BLACK);
  lcd.drawRect(0, 0, SCR_W, SCR_H, TFT_WHITE);
  lcd.drawRect(2, 2, SCR_W - 4, SCR_H - 4, TFT_YELLOW);
  lcd.setTextDatum(lgfx::top_left); lcd.setTextSize(1);
  lcd.setTextColor(TFT_RED);   lcd.drawString("R red",   6, 8);
  lcd.setTextColor(TFT_GREEN); lcd.drawString("G green", 6, 20);
  lcd.setTextColor(TFT_BLUE);  lcd.drawString("B blue",  6, 32);
  lcd.setTextColor(TFT_WHITE); lcd.drawString(panelName, 6, 48);
  lcd.drawString("MRC-001", 6, 60);
  Serial.printf("[tft] ทดสอบกรอบ %dx%d + ป้าย R/G/B (ค้าง 3 s)\n", SCR_W, SCR_H);
  delay(3000);
#endif

}

void tftTick() {
  if (!ready) return;
  const uint32_t now = millis();
  if (now - lastDraw < 200) return;
  lastDraw = now;
  if (useSprite) { draw(spr); spr.pushSprite(0, 0); }
  else draw(lcd);
}

void tftSetInfo(const char* ip, const char* reading, int co2, int tvoc, int aqi, int temp10, int rh10,
                int clients, const char* warn, const char* evt, const char* arg) {
  strncpy(info.ip, ip, sizeof info.ip - 1);
  strncpy(info.reading, reading, sizeof info.reading - 1);
  strncpy(info.warn, warn, sizeof info.warn - 1);
  strncpy(info.evt, evt, sizeof info.evt - 1);
  strncpy(info.arg, arg, sizeof info.arg - 1);
  info.co2 = co2; info.tvoc = tvoc; info.aqi = aqi; info.temp10 = temp10; info.rh10 = rh10; info.clients = clients; info.rxMs = millis();
}
bool tftReady() { return ready; }
