#pragma once
// Host-only recording double. This is not the hardware library or a pixel-perfect font emulator.
#include "Arduino.h"
#include <cmath>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
#define SPI2_HOST 2
#define SPI_DMA_CH_AUTO 0
namespace textdatum_t { constexpr int middle_center = 0; }
namespace fonts {
struct TestFont { int height, advance; bool bold; };
inline TestFont Font0{8,6,false}, Font2{16,8,false}, FreeSansBold9pt7b{18,10,true};
inline TestFont FreeSansBold12pt7b{24,13,true}, FreeSansBold18pt7b{36,20,true}, FreeSansBold24pt7b{48,27,true};
}
namespace lgfx {
struct BusConfig { int spi_host,spi_mode,freq_write,freq_read,dma_channel,pin_sclk,pin_mosi,pin_miso,pin_dc; bool spi_3wire,use_lock; };
struct PanelConfig { int pin_cs,pin_rst,pin_busy,panel_width,panel_height,offset_x,offset_y; bool readable,invert,rgb_order,dlen_16bit,bus_shared; };
struct Bus_SPI { BusConfig config() { return {}; } void config(BusConfig) {} };
struct Panel_GC9A01 { PanelConfig config() { return {}; } void config(PanelConfig) {} void setBus(Bus_SPI*) {} };
inline std::string color(uint16_t c) {
  std::ostringstream s; s << '#' << std::hex << std::setfill('0')
    << std::setw(2) << (((c>>11)&31)*255/31) << std::setw(2) << (((c>>5)&63)*255/63) << std::setw(2) << ((c&31)*255/31); return s.str();
}
inline std::string escaped(std::string s) {
  std::string out; for(char c:s) out += c=='&'?"&amp;":c=='<'?"&lt;":c=='>'?"&gt;":c=='\"'?"&quot;":std::string(1,c); return out;
}
class LovyanGFX {
 public:
  struct TextBounds { int x,y,w,h; };
  struct Arc { int x,y,outer,inner; float start,end; uint16_t color; };
  std::vector<std::string> ops, texts;
  std::vector<TextBounds> bounds;
  std::vector<Arc> arcs;
  const fonts::TestFont* font = &fonts::Font0; uint16_t ink=0xffff;
  void setTextDatum(int) {} void setFont(const fonts::TestFont* f) { font=f; }
  void setTextColor(uint16_t c,uint16_t) { ink=c; }
  int textWidth(const char* s) {
    int width=0; for(;*s;++s) width += (*s=='.'||*s==':'||*s==' ')?font->advance/2:font->advance; return width;
  }
  void fillScreen(uint16_t c) { ops.clear(); texts.clear(); bounds.clear(); arcs.clear(); fillRect(0,0,240,240,c); }
  void fillRect(int x,int y,int w,int h,uint16_t c) { fillRoundRect(x,y,w,h,0,c); }
  void fillRoundRect(int x,int y,int w,int h,int r,uint16_t c) {
    std::ostringstream s; s<<"<rect x='"<<x<<"' y='"<<y<<"' width='"<<w<<"' height='"<<h<<"' rx='"<<r<<"' fill='"<<color(c)<<"'/>"; ops.push_back(s.str());
  }
  void fillCircle(int x,int y,int r,uint16_t c) {
    std::ostringstream s; s<<"<circle cx='"<<x<<"' cy='"<<y<<"' r='"<<r<<"' fill='"<<color(c)<<"'/>"; ops.push_back(s.str());
  }
  void drawLine(int x,int y,int x2,int y2,uint16_t c) {
    std::ostringstream s; s<<"<path d='M"<<x<<','<<y<<" L"<<x2<<','<<y2<<"' stroke='"<<color(c)<<"'/>"; ops.push_back(s.str());
  }
  void fillArc(int x,int y,int outer,int inner,float start,float end,uint16_t c) {
    arcs.push_back({x,y,outer,inner,start,end,c});
    std::ostringstream s;
    if(end-start>=359.9f) s<<"<circle cx='"<<x<<"' cy='"<<y<<"' r='"<<(outer+inner)/2.0<<"' fill='none' stroke='"<<color(c)<<"' stroke-width='"<<outer-inner<<"'/>";
    else {
      const double a=start*3.141592653589793/180, b=end*3.141592653589793/180; const int large=end-start>180;
      s<<"<path d='M"<<x+outer*cos(a)<<','<<y+outer*sin(a)<<" A"<<outer<<','<<outer<<" 0 "<<large<<" 1 "<<x+outer*cos(b)<<','<<y+outer*sin(b)
        <<" L"<<x+inner*cos(b)<<','<<y+inner*sin(b)<<" A"<<inner<<','<<inner<<" 0 "<<large<<" 0 "<<x+inner*cos(a)<<','<<y+inner*sin(a)<<" Z' fill='"<<color(c)<<"'/>";
    }
    ops.push_back(s.str());
  }
  void drawString(const char* text,int x,int y) {
    bounds.push_back({x,y,textWidth(text),font->height});
    texts.emplace_back(text); std::ostringstream s;
    s<<"<text x='"<<x<<"' y='"<<y<<"' text-anchor='middle' dominant-baseline='central' font-family='Arial,sans-serif' font-size='"<<font->height
      <<"' font-weight='"<<(font->bold?700:400)<<"' fill='"<<color(ink)<<"' textLength='"<<textWidth(text)<<"' lengthAdjust='spacingAndGlyphs'>"<<escaped(text)<<"</text>"; ops.push_back(s.str());
  }
};
struct LGFX_Device:LovyanGFX { void setPanel(Panel_GC9A01*) {} void init() {} void setRotation(int) {} void setBrightness(int) {} };
struct LGFX_Sprite:LovyanGFX { explicit LGFX_Sprite(LGFX_Device*) {} void setPsram(bool) {} void setColorDepth(int) {} void* createSprite(int,int) { return this; } void pushSprite(int,int) {} };
}
using LGFX_Sprite = lgfx::LGFX_Sprite;
