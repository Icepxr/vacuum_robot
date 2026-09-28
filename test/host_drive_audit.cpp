// host_drive_audit.cpp — จำลองโซ่ขับจริง drive.js pump() → Pi clamp → manual_core.h · ผลอยู่ไฟล์ 19 §19.9
// c++ -std=c++17 -I src/robot test/host_drive_audit.cpp -o /tmp/drive_audit && /tmp/drive_audit
#include <cstdio>
#include <cmath>
#include <algorithm>
#include "manual_core.h"
// จำลองโซ่จริง: drive.js pump() (สูตรเดียวกับไฟล์) → Pi clamp → manual_core (โค้ดจริง)
const int VMAX=716, WMAX=7950, TURNGAIN=7950;
struct VW{int v,w;};
VW client(double x,double y,int pct,bool step,bool turnScale=true,int curve=50,int spinMin=70){
  double tv=y*VMAX*pct/100.0, turnW=std::min(TURNGAIN,WMAX);
  double tw=-x*turnW*(turnScale?(1-0.5*fabs(y)):1);
  if(step) tw=-x*turnW*(y? curve/100.0 : std::max(pct,spinMin)/100.0);
  return {(int)lround(tv),(int)lround(tw)};
}
mrc::WheelCmd steady(VW c){ mrc::Manual m; m.configure(mrc::ManualCfg{}); m.setLimits(VMAX,WMAX);
  uint32_t t=0; mrc::WheelCmd o; for(int i=0;i<200;i++){ m.setpoint(c.v,c.w,t); o=m.tick(t); t+=10;} return o; }
int main(){
  printf("== A. เดินตรงด้วยจอย/สไลเดอร์ (y=1) ==\n");
  for(int pct: {10,15,20,25,30,50,75,100}){ VW c=client(0,1,pct,false); auto o=steady(c);
    printf("  %3d%%  v=%4d mm/s  → ล้อ %4d/%4d ‰  (ถ้าไม่มีพื้น 250 ‰ จะได้ %d ‰)\n",pct,c.v,o.l,o.r,(int)(c.v*1.4)); }
  printf("== B. เดินตรงจอยครึ่งทาง (y=0.3) ที่ปุ่ม 50%% ==\n");
  { VW c=client(0,0.3,50,false); auto o=steady(c); printf("  v=%d → ล้อ %d/%d ‰ (ควรเป็น %d)\n",c.v,o.l,o.r,(int)(c.v*1.4)); }
  printf("== C. แก้ทิศเล็กน้อยระหว่างเดิน (จอย x=0.15,y=1) ==\n");
  for(int pct:{50,100}){ VW c=client(0.15,1,pct,false); auto o=steady(c); printf("  %3d%%: v=%d w=%d → ซ้าย %d ขวา %d ‰\n",pct,c.v,c.w,o.l,o.r);}
  printf("== D. เลี้ยวโค้งด้วยจอย (x=0.5,y=1) ==\n");
  for(int pct:{50,100}){ VW c=client(0.5,1,pct,false); auto o=steady(c); printf("  %3d%%: v=%d w=%d → ซ้าย %d ขวา %d ‰ (อัตราส่วน %.2f)\n",pct,c.v,c.w,o.l,o.r,(double)o.r/o.l);}
  printf("== E. แตะจอยหมุนเบาๆ อยู่กับที่ (x=0.1,y=0) ==\n");
  { VW c=client(0.1,0,50,false); auto o=steady(c); printf("  w=%d → ซ้าย %d ขวา %d ‰\n",c.w,o.l,o.r); }
  printf("== F. ปล่อยจอยจากความเร็วคงที่ → ล้อ 0 ==\n");
  for(int pct:{50,75,100}){ mrc::Manual m; m.configure(mrc::ManualCfg{}); m.setLimits(VMAX,WMAX); VW c=client(0,1,pct,false);
    uint32_t t=0; for(int i=0;i<200;i++){m.setpoint(c.v,c.w,t); m.tick(t); t+=10;} int start=m.out().l; m.stop();
    int n=0; while(m.tick(t).l!=0){t+=10;n++;} double tr=n*0.01, d=c.v*tr/2;
    printf("  %3d%%: %d ‰ → 0 ใช้ %.2f s · ระยะไหลระหว่าง ramp ≈ %.0f mm (ความเร็ว∝duty)\n",pct,start,tr,d);}
  printf("== G. ออกตัว 0 → เต็ม (เฉพาะ slew เฟิร์มแวร์) ==\n");
  for(int pct:{50,100}){ mrc::Manual m; m.configure(mrc::ManualCfg{}); m.setLimits(VMAX,WMAX); VW c=client(0,1,pct,false);
    uint32_t t=0; int n=0; int tgt=steady(c).l; while(true){m.setpoint(c.v,c.w,t); if(m.tick(t).l>=tgt)break; t+=10;n++;}
    printf("  %3d%%: ถึง %d ‰ ใน %d ms\n",pct,tgt,n*10);}
  printf("== H. deadband + พื้น: คำสั่งล้อ 0–300 mm/s → ‰ ==\n  ");
  for(int v=0;v<=300;v+=25){ auto o=steady({v,0}); printf("%d→%d ",v,o.l);} printf("\n");
}
