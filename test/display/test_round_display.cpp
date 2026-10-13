// Host-only tests and preview of the real round-display renderer.
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
uint32_t displayTestNow = 10000;
bool testLink=true, testStop=false, testManual=false, testMission=false, testTripped=false;
bool manualActive(){return testManual;} bool manualTripped(){return testTripped;}
bool missionRunning(){return testMission;} bool commLinkAlive(){return testLink;} bool robotEstopped(){return testStop;}
#include "../../src/robot/tft.cpp"

void resetScene() {
  testLink=true; testStop=testManual=testMission=testTripped=false; info=TftInfo{};
  tftSetInfo("172.20.10.2","1509",539,23,2,290,550,1,"","","");
}
bool has(const lgfx::LovyanGFX& g,const char* text) { return std::find(g.texts.begin(),g.texts.end(),text)!=g.texts.end(); }
int checks=0;
void check(bool condition,const char* message) { ++checks; if(!condition) { std::cerr<<message<<'\n'; std::exit(1); } }
bool insideRoundScreen(const lgfx::LovyanGFX& g) {
  for (const auto& b:g.bounds) {
    const double dx=std::abs(b.x-120)+b.w/2.0, dy=std::abs(b.y-120)+b.h/2.0;
    if(dx*dx+dy*dy>119*119) return false;
  }
  return true;
}
struct Scene { const char* name; const char* group; const char* copy; };
const Scene scenes[] = {
  {"พร้อมใช้งาน","everyday","539"},
  {"ขับเอง / ไอคอนจอย","everyday","539"},
  {"ภารกิจ / ไอคอนเส้นทาง","everyday","539"},
  {"รอค่าคุณภาพอากาศ","everyday","--"},
  {"ค่า eCO2 ระดับสูง","everyday","1260"},
  {"ทักทาย / ยังไม่มีลิงก์","connection","Connecting"},
  {"ชวนเปิดหน้าควบคุม","connection",":8000/drive"},
  {"ลิงก์มาแล้วแต่ข้อมูลเก่า","connection","Data pending"},
  {"Pi หลุดหลังเคยเชื่อมต่อ","connection","Pi offline"},
  {"กำลังถ่ายภาพ","camera","Capturing"},
  {"บันทึกภาพแล้ว","camera","Photo saved"},
  {"อ่านมิเตอร์สำเร็จ","camera","Meter reading"},
  {"อ่านตัวเลขไม่ออก","camera","Try again"},
  {"ถ่ายภาพไม่สำเร็จ","camera","Camera error"},
  {"หยุดเพราะสัญญาณขับหมดเวลา","attention","Drive paused"},
  {"ไม่มี IP","attention","No IP"},
  {"Pi ร้อนเกินไป","attention","Pi too hot"},
  {"กล้องยังไม่พร้อม","attention","539"},
  {"พื้นที่เก็บข้อมูลใกล้เต็ม","attention","Storage low"},
  {"เซนเซอร์อากาศไม่พร้อม","attention","--"},
  {"หยุดฉุกเฉิน","attention","E-STOP"},
};
void setupScene(size_t i) {
  resetScene();
  switch(i) {
    case 1: testManual=true; break;
    case 2: testMission=true; break;
    case 3: info.co2=-1; info.tvoc=info.aqi=-1; break;
    case 4: info.co2=1260; info.tvoc=380; info.aqi=4; break;
    case 5: testLink=false; info=TftInfo{}; break;
    case 6: info.clients=0; break;
    case 7: info.rxMs=1; break;
    case 8: testLink=false; info.rxMs=displayTestNow-6000; break;
    case 9: strcpy(info.evt,"CAP"); break;
    case 10: strcpy(info.evt,"SAVED"); break;
    case 11: strcpy(info.evt,"READ"); strcpy(info.arg,"1509"); break;
    case 12: strcpy(info.evt,"NOREAD"); break;
    case 13: strcpy(info.evt,"CAPFAIL"); strcpy(info.arg,"No frame"); break;
    case 14: testTripped=true; break;
    case 15: strcpy(info.warn,"NOIP"); break;
    case 16: strcpy(info.warn,"HOT"); break;
    case 17: strcpy(info.warn,"NOCAM"); break;
    case 18: strcpy(info.warn,"DISK"); break;
    case 19: strcpy(info.warn,"NOAIR"); break;
    case 20: testStop=true; break;
  }
}

int main(int argc,char**) {
  lgfx::LovyanGFX g;
  for(size_t i=0;i<std::size(scenes);++i) {
    setupScene(i); draw(g);
    check(has(g,scenes[i].copy),scenes[i].name);
    check(insideRoundScreen(g),"text fits circular screen (approximate host fonts)");
    check(g.texts.size() <= (i<5 || (i>=17 && i<=19) ? 5u : 3u),"minimal text budget per screen");
    check(!has(g,"ARIA")&&!has(g,"Manual")&&!has(g,"Mission"),"no wordmark or mode text");
    check(std::any_of(g.arcs.begin(),g.arcs.end(),[](const lgfx::LovyanGFX::Arc& a){ return a.x==120&&a.y==120&&a.outer==120&&a.inner==112; }),"outermost frame across states");
  }
  resetScene(); draw(g);
  check(has(g,"539")&&has(g,"29.0C")&&has(g,"55%")&&has(g,"TVOC 23 ppb"),"approved air summary");
  testManual=testMission=true; draw(g); check(hudState(true).mode==Mode::Mission&&!has(g,"Mission")&&!has(g,"Manual"),"mission mode icon wins without mode text");
  resetScene(); strcpy(info.evt,"CAP"); testLink=false; draw(g);
  check(has(g,"Pi offline")&&!has(g,"Capturing")&&!has(g,"Ready"),"offline wins over events and never says ready");
  testStop=true; draw(g); check(has(g,"E-STOP")&&!has(g,"Pi offline"),"E-stop wins over offline");
  resetScene(); strcpy(info.warn,"HOT"); strcpy(info.evt,"CAP"); draw(g);
  check(has(g,"Capturing")&&!has(g,"Pi too hot"),"existing event priority retained");
  resetScene(); info.rxMs=1; strcpy(info.evt,"READ"); strcpy(info.arg,"9999"); draw(g);
  check(has(g,"Data pending")&&!has(g,"9999")&&!has(g,"539"),"stale event and air data hidden");
  resetScene(); info.clients=0; strcpy(info.warn,"HOT"); draw(g);
  check(has(g,"Pi too hot")&&!has(g,":8000/drive"),"severe fault wins over welcome");
  resetScene(); strcpy(info.warn,"NOAIR"); draw(g);
  check(has(g,"--")&&!has(g,"539")&&has(g,"29.0C")&&has(g,"55%"),"no-air warning hides gas, not environment");
  resetScene(); info.co2=-1; info.rh10=-1; info.aqi=-1; draw(g);
  check(has(g,"29.0C")&&has(g,"--%")&&has(g,"TVOC 23 ppb"),"independent field sentinels");
  resetScene(); strcpy(info.evt,"DEADMAN"); draw(g); check(has(g,"Drive paused"),"Pi deadman event");
  resetScene(); testTripped=true; strcpy(info.warn,"HOT"); draw(g);
  check(has(g,"Pi too hot"),"local trip does not hide severe warning");
  resetScene(); strcpy(info.evt,"READ"); strcpy(info.arg,"12345678"); draw(g);
  check(has(g,"12345678")&&insideRoundScreen(g),"eight-digit reading preserved");
  resetScene(); strcpy(info.evt,"READ"); draw(g); check(has(g,"?"),"empty reading not fabricated");
  resetScene(); strcpy(info.warn,"NOCAM"); draw(g); check(has(g,"539"),"minor fault retains air");
  resetScene(); info.clients=-1; draw(g); check(has(g,"539"),"legacy client sentinel supported");
  g.setFont(&fonts::Font2); drawFitted(g,"a very long diagnostic message that cannot fit",165,198);
  check(g.textWidth(g.texts.back().c_str())<=198,"long copy fitted");
  resetScene(); tftSetup(); tftTick(); check(has(spr,"539"),"ticker draws sprite");
  const auto oldOps=spr.ops; displayTestNow+=100; testStop=true; tftTick();
  check(spr.ops==oldOps,"200ms cadence retained");
  displayTestNow+=100; tftTick(); check(has(spr,"E-STOP"),"next tick reflects emergency");

  // Telemetry health is conservative: one priority warning cannot describe all subsystems.
  resetScene(); check(hudState(true).camera==Health::Ready&&hudState(true).network==Health::Ready,"modern normal HUD");
  testLink=false; auto h=hudState(false);
  check(h.link==Health::Bad&&h.camera==Health::Unknown&&h.network==Health::Unknown,"offline HUD never claims subsystem health");
  resetScene(); strcpy(info.warn,"HOT"); check(hudState(true).camera==Health::Unknown,"higher priority HOT masks camera health");
  strcpy(info.warn,"NOIP"); check(hudState(true).camera==Health::Unknown&&hudState(true).network==Health::Bad,"NOIP overrides retained IP and masks camera health");
  strcpy(info.warn,"NOCAM"); check(hudState(true).camera==Health::Bad,"camera failure icon");
  strcpy(info.warn,"DISK"); check(hudState(true).camera==Health::Ready,"later-priority disk warning confirms camera check");
  resetScene(); info.clients=-1; check(hudState(true).camera==Health::Unknown,"legacy frame camera health unknown");
  resetScene(); strcpy(info.evt,"CAPFAIL"); check(hudState(true).camera==Health::Bad,"capture failure icon");
  resetScene(); check(hudState(false).camera==Health::Unknown&&hudState(false).network==Health::Unknown,"stale HUD unknown");
  testManual=true; check(hudState(true).mode==Mode::Manual,"joystick mode");
  testTripped=true; check(hudState(true).mode==Mode::Paused,"deadman pause icon");
  check(airAngle(400)==135&&airAngle(2000)==405&&airAngle(0)==135&&airAngle(9999)==405,"same clamped eCO2 scale");
  resetScene(); draw(g);
  check(std::any_of(g.arcs.begin(),g.arcs.end(),[](const lgfx::LovyanGFX::Arc& a){ return a.outer==120&&a.inner==112&&a.color==SEGS[0].c&&a.end>135&&a.end<405; }),"low eCO2 fills small part of perimeter");
  info.co2=1680; draw(g);
  check(std::any_of(g.arcs.begin(),g.arcs.end(),[](const lgfx::LovyanGFX::Arc& a){ return a.outer==120&&a.inner==112&&a.color==SEGS[4].c&&a.end>315; }),"high eCO2 fills more of perimeter");
  info.co2=-1; draw(g);
  check(std::count_if(g.arcs.begin(),g.arcs.end(),[](const lgfx::LovyanGFX::Arc& a){ return a.outer==120&&a.inner==112; })==1,"unknown eCO2 shows track only");
  resetScene(); info.co2=400; draw(g);
  check(std::count_if(g.arcs.begin(),g.arcs.end(),[](const lgfx::LovyanGFX::Arc& a){ return a.outer==120&&a.inner==112; })==1,"baseline eCO2 has no invented fill");
  resetScene(); strcpy(info.evt,"CAP"); draw(g);
  check(std::count_if(g.arcs.begin(),g.arcs.end(),[](const lgfx::LovyanGFX::Arc& a){ return a.outer==120&&a.inner==112&&a.start==135&&a.end==405; })==1,"capture frame is uniform, not percentage progress");
  testStop=true; draw(g);
  check(std::any_of(g.arcs.begin(),g.arcs.end(),[](const lgfx::LovyanGFX::Arc& a){ return a.outer==120&&a.inner==112&&a.start==0&&a.end==360&&a.color==C_BAD; }),"emergency continuous red perimeter");
  resetScene(); strcpy(info.warn,"NEW"); draw(g); check(has(g,"NEW"),"unknown warning fitted fallback");
  resetScene(); strcpy(info.evt,"NEW"); strcpy(info.arg,"note"); draw(g); check(has(g,"NEW")&&has(g,"note"),"unknown event fitted fallback");
  if(argc==1) { std::cout<<checks<<" round-display checks passed (host double, no hardware)\n"; return 0; }
  std::cout<<R"HTML(<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Round display · outer ring states</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f1fa;color:#312343;font:14px system-ui,sans-serif;padding:36px 24px}header,nav,main,footer{max-width:1100px;margin:auto}header{padding:8px 0 24px}.eyebrow{font-size:11px;letter-spacing:2px;color:#78628e}h1{font-size:clamp(26px,5vw,38px);font-weight:650;letter-spacing:-1px;margin:10px 0}p{line-height:1.8;color:#756385;margin:0;max-width:780px}nav{display:flex;gap:8px;flex-wrap:wrap;padding-bottom:28px}button{font:inherit;background:transparent;border:1px solid #dfd4e9;border-radius:22px;padding:10px 16px;cursor:pointer;color:#655077}button[aria-pressed=true]{background:#6c438e;color:white;border-color:#6c438e}button:focus-visible{outline:3px solid #ba88d5;outline-offset:3px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:34px 24px}figure{margin:0;text-align:center}figure[hidden]{display:none}svg{display:block;width:240px;height:240px;margin:auto;border-radius:50%;box-shadow:0 12px 30px #3d235a24}figcaption{margin-top:15px;font-size:14px}figcaption span{display:block;font-size:11px;color:#96809f;margin-top:4px}footer{margin-top:38px;padding-top:20px;border-top:1px solid #e4dceb;font-size:12px;line-height:1.8;color:#85718e}@media(max-width:540px){body{padding:22px 16px}.grid{grid-template-columns:1fr;gap:30px}}
</style><header><div class="eyebrow">ROUND DISPLAY / APPROVED DIRECTION</div><h1>วงแหวนขอบนอก · ทุกสถานะ</h1><p>21 ฉากจากโค้ดวาดจอจริง · ไม่มี ARIA หรือข้อความโหมดบนจอ<br>ข้อมูลตัวอย่างและฟอนต์จำลอง ยังไม่ได้ตรวจบนจอจริง</p></header>
<nav aria-label="เลือกกลุ่มสถานะ"><button aria-pressed="true" data-filter="all">ทั้งหมด · 21</button><button aria-pressed="false" data-filter="everyday">อยู่ด้วยกัน · 5</button><button aria-pressed="false" data-filter="connection">เชื่อมต่อ · 4</button><button aria-pressed="false" data-filter="camera">กล้องและมิเตอร์ · 5</button><button aria-pressed="false" data-filter="attention">ต้องดูแล · 7</button></nav><main class="grid">
)HTML";
  for(size_t i=0;i<std::size(scenes);++i) {
    setupScene(i); draw(g);
    std::cout<<"<figure data-group='"<<scenes[i].group<<"'><svg viewBox='0 0 240 240' role='img' aria-label='"<<scenes[i].name<<"'>";
    for(const auto& op:g.ops) std::cout<<op;
    std::cout<<"</svg><figcaption>"<<scenes[i].name<<"<span>STATE "<<(i+1)<<" / 21</span></figcaption></figure>\n";
  }
  std::cout<<R"HTML(</main><footer>Host preview · Approximate fonts · No hardware commands</footer>
<script>document.querySelectorAll('button[data-filter]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('button[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelectorAll('figure[data-group]').forEach(f=>f.hidden=button.dataset.filter!=='all'&&f.dataset.group!==button.dataset.filter)}));</script></html>)HTML";
}
