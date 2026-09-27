// tft.cpp — ดู tft.h
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include "tft.h"
#include "../pins.h"
#include <math.h>

bool manualActive(); bool manualTripped(); bool missionRunning(); bool commLinkAlive(); bool robotEstopped();

namespace {
constexpr int PIN_SCK = PIN_TFT_SCK, PIN_MOSI = PIN_TFT_MOSI, PIN_DC = PIN_TFT_DC, PIN_CS = PIN_TFT_CS;   // ../pins.h

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

// Approved outer-ring identity: no wordmark, faces or mode text.
constexpr uint16_t rgb(int r,int g,int b) { return ((r>>3)<<11)|((g>>2)<<5)|(b>>3); }
constexpr uint16_t C_BG=rgb(16,11,27), C_PANEL=rgb(52,38,63), C_INK=rgb(245,239,255);
constexpr uint16_t C_MUT=rgb(166,154,182), C_UNKNOWN=rgb(113,103,127), C_ACC=rgb(182,160,207);
constexpr uint16_t C_OK=rgb(158,217,189), C_WARN=rgb(230,207,148), C_BAD=rgb(237,150,164), C_STOP_BG=0x3803;

// Clip only display copy, never the underlying IP / telemetry / protocol data.
void drawFitted(lgfx::LovyanGFX& g, const char* text, int y, int width) {
  char out[64]; snprintf(out, sizeof out, "%s", text ? text : "");
  if (g.textWidth(out) > width) {
    size_t n = strlen(out);
    while (n > 0) {
      out[--n] = '\0';
      char candidate[68]; snprintf(candidate, sizeof candidate, "%s...", out);
      if (n + 3 < sizeof out && g.textWidth(candidate) <= width) { memcpy(out + n, "...", 4); break; }
    }
  }
  g.drawString(out, 120, y);
}

// Abstract symbols only: no eyes, mouth or mascot face.
enum class Symbol { Orbit, Camera, Check, Retry, Link, Heat, Pause, Stop };
void drawSymbol(lgfx::LovyanGFX& g, Symbol symbol, uint16_t tint) {
  const uint16_t background = symbol == Symbol::Stop ? C_STOP_BG : C_BG;
  // Shared outer frame carries the state; no extra inner rings or boxed cards.
  switch (symbol) {
    case Symbol::Camera:
      g.fillRoundRect(88, 80, 64, 45, 12, tint);
      g.fillRoundRect(90, 82, 60, 41, 10, background);
      g.fillRoundRect(104, 75, 32, 9, 4, tint);
      g.fillCircle(120, 103, 15, tint); g.fillCircle(120, 103, 11, background);
      break;
    case Symbol::Check:
      for (int d=-2; d<=2; ++d) {
        g.drawLine(99, 103+d, 115, 118+d, tint);
        g.drawLine(115, 118+d, 144, 86+d, tint);
      }
      break;
    case Symbol::Retry:
      g.fillArc(120, 102, 26, 23, 35, 325, tint);
      g.drawLine(140, 86, 148, 89, tint); g.drawLine(148, 89, 147, 78, tint);
      break;
    case Symbol::Link:
      g.fillArc(120, 118, 33, 30, 220, 320, tint);
      g.fillArc(120, 118, 21, 18, 220, 320, tint);
      g.fillCircle(120, 116, 4, tint);
      break;
    case Symbol::Heat:
      g.fillRoundRect(114, 74, 12, 45, 6, tint);
      g.fillRoundRect(118, 78, 4, 29, 2, background);
      g.fillCircle(120, 119, 12, tint);
      g.drawLine(141, 81, 149, 81, tint); g.drawLine(141, 94, 149, 94, tint);
      break;
    case Symbol::Pause:
      g.fillRoundRect(105, 83, 10, 38, 5, tint);
      g.fillRoundRect(125, 83, 10, 38, 5, tint);
      break;
    case Symbol::Stop:
      g.fillArc(120, 102, 32, 28, 0, 360, tint);
      g.fillRoundRect(109, 91, 22, 22, 4, C_INK);
      break;
    case Symbol::Orbit:
      g.fillArc(120, 102, 28, 25, 195, 315, tint);
      g.fillArc(120, 102, 28, 25, 15, 125, tint);
      g.fillCircle(144, 88, 4, tint);
      g.fillCircle(120, 102, 5, C_INK);
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
void drawHudIcon(lgfx::LovyanGFX& g,SmallIcon icon,int x,Health health) {
  const uint16_t c=healthColor(health);
  smallIcon(g,icon,x,43,c,C_BG);
  if(health==Health::Bad) {
    g.drawLine(x+2,59,x+17,44,c); g.drawLine(x+2,60,x+17,45,c);
  }
}
void drawHud(lgfx::LovyanGFX& g,bool fresh) {
  const Hud h=hudState(fresh);
  drawHudIcon(g,SmallIcon::Link,72,h.link); drawHudIcon(g,SmallIcon::Camera,98,h.camera);
  drawHudIcon(g,SmallIcon::Network,124,h.network);
  drawHudIcon(g,h.mode==Mode::Mission ? SmallIcon::Route : h.mode==Mode::Manual ? SmallIcon::Joystick : SmallIcon::Pause,150,h.modeHealth);
}

// Same 400–2000 ppm mapping and band boundaries, with the approved softer colors.
struct Seg { int lo, hi; uint16_t c; };
const Seg SEGS[5]={{400,600,rgb(158,217,189)},{600,800,rgb(195,215,154)},{800,1000,rgb(230,207,148)},
  {1000,1500,rgb(235,173,134)},{1500,2000,rgb(237,150,164)}};
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
void drawAirPage(lgfx::LovyanGFX& g,Page page) {
  const bool noAir=page==Page::NoAir, gas=info.co2>=0 && !noAir;
  ringArc(g,135,405,C_PANEL);
  if(gas && info.co2>400) ringArc(g,135,airAngle(info.co2),SEGS[airLevel()].c);
  g.setFont(&fonts::FreeSansBold24pt7b); g.setTextColor(gas ? C_INK : C_MUT,C_BG);
  char b[40]; if(gas) snprintf(b,sizeof b,"%d",info.co2); else snprintf(b,sizeof b,"--");
  drawFitted(g,b,115,196);
  g.setFont(&fonts::Font0); g.setTextColor(C_MUT,C_BG); g.drawString("eCO2 ppm",120,145);
  if(page==Page::Disk || noAir || page==Page::OtherWarning) {
    g.setTextColor(C_WARN,C_BG); drawFitted(g,page==Page::Disk ? "Storage low" : noAir ? "No air sensor" : info.warn,174,170);
  } else {
    if(info.tvoc>=0) snprintf(b,sizeof b,"TVOC %d ppb",info.tvoc); else snprintf(b,sizeof b,"TVOC -- ppb");
    drawFitted(g,b,174,170);
  }
  smallIcon(g,SmallIcon::Thermo,65,197,C_MUT,C_BG); smallIcon(g,SmallIcon::Drop,129,197,C_MUT,C_BG);
  g.setFont(&fonts::Font2); g.setTextColor(C_INK,C_BG);
  if(info.temp10>-1000) snprintf(b,sizeof b,"%.1fC",info.temp10/10.0f); else snprintf(b,sizeof b,"--C");
  g.drawString(b,94,207);
  if(info.rh10>=0) snprintf(b,sizeof b,"%d%%",info.rh10/10); else snprintf(b,sizeof b,"--%%");
  g.drawString(b,157,207);
}
void drawMessage(lgfx::LovyanGFX& g,Symbol symbol,uint16_t tint,const char* label,const char* hint=nullptr) {
  // A uniform status frame, NOT a fabricated task-progress percentage.
  ringArc(g,135,405,tint);
  drawSymbol(g,symbol,tint);
  g.setFont(&fonts::FreeSansBold12pt7b); g.setTextColor(tint,C_BG); drawFitted(g,label,164,196);
  if(hint && hint[0]) { g.setFont(&fonts::Font2); g.setTextColor(C_MUT,C_BG); drawFitted(g,hint,191,164); }
}
void draw(lgfx::LovyanGFX& g) {
  const bool fresh=info.rxMs && millis()-info.rxMs<5000;
  const Page page=selectPage(fresh);
  const bool emergency=page==Page::Estop;
  g.fillScreen(emergency ? C_STOP_BG : C_BG);
  g.setTextDatum(textdatum_t::middle_center);
  if(!emergency) drawHud(g,fresh);
  switch(page) {
    case Page::Estop:
      ringArc(g,0,360,C_BAD); drawSymbol(g,Symbol::Stop,C_BAD);
      g.setFont(&fonts::FreeSansBold18pt7b); g.setTextColor(C_INK,C_STOP_BG); g.drawString("E-STOP",120,159);
      g.setFont(&fonts::Font2); g.drawString("Motors off",120,191); break;
    case Page::Connecting: drawMessage(g,Symbol::Orbit,C_MUT,"Connecting"); break;
    case Page::Offline: drawMessage(g,Symbol::Link,C_BAD,"Pi offline","Check USB"); break;
    case Page::DataWaiting: drawMessage(g,Symbol::Orbit,C_WARN,"Data pending"); break;
    case Page::Welcome:
      ringArc(g,135,405,C_ACC); drawSymbol(g,Symbol::Link,C_ACC);
      g.setFont(&fonts::FreeSansBold9pt7b); g.setTextColor(C_INK,C_BG);
      drawFitted(g,info.ip[0] ? info.ip : "No IP yet",161,196);
      g.setFont(&fonts::Font2); g.setTextColor(C_MUT,C_BG); g.drawString(":8000/drive",120,190); break;
    case Page::Capturing: drawMessage(g,Symbol::Camera,C_ACC,"Capturing"); break;
    case Page::Saved: drawMessage(g,Symbol::Check,C_OK,"Photo saved","Reading..."); break;
    case Page::Reading:
      ringArc(g,135,405,C_OK);
      g.setFont(strlen(info.arg)>7 ? &fonts::FreeSansBold18pt7b : &fonts::FreeSansBold24pt7b);
      g.setTextColor(C_INK,C_BG); drawFitted(g,info.arg[0] ? info.arg : "?",115,196);
      g.setFont(&fonts::Font2); g.setTextColor(C_OK,C_BG); g.drawString("Meter reading",120,162);
      g.setFont(&fonts::Font0); g.setTextColor(C_MUT,C_BG); g.drawString("Saved",120,190); break;
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
