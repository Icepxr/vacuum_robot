import math
G=9.81
ETA_J=0.65          # ประสิทธิภาพข้อต่อ scissor
F_STIC_T=0.05       # N*m ความฝืดที่แกนขับตรง (ประมาณการ)
MG={'6V':11.0*0.0980665,'4.8V':9.4*0.0980665}

def direct(n,L,th_min,th_max,m_sc_g,m_top_g,k_tot,p,xa,ya,s0,kmul=1.0,N=241):
    """เซอร์โวขับ 'แขนล่าง' โดยตรงที่จุดหมุนตายตัว  T = (dUg/dθ + dUs/dθ)/η"""
    W_eff=((m_top_g/1000)+(m_sc_g/1000)/2)*G
    Tmax=0; Tmin=1e9; det=None; smax=0
    K=k_tot*kmul
    for i in range(N):
        th=th_min+(th_max-th_min)*i/(N-1); tr=math.radians(th)
        dUg=n*W_eff*L*math.cos(tr)                     # N*mm/rad
        px=p*L*math.cos(tr); py=p*L*math.sin(tr)
        dpx=-p*L*math.sin(tr); dpy=p*L*math.cos(tr)
        s=math.hypot(px-xa,py-ya); smax=max(smax,s)
        ext=max(s-s0,0.0)
        dUs=K*ext*((px-xa)*dpx+(py-ya)*dpy)/s
        net=(dUg+dUs)/1000.0                            # N*m/rad -> N*m
        Tmin=min(Tmin,net)
        Tq=abs(net)/ETA_J+F_STIC_T
        if Tq>Tmax: Tmax=Tq; det=(th,net)
    return dict(Tmax=Tmax,net_min=Tmin,smax=smax,ext=smax-s0,det=det,travel=th_max-th_min)

n,L,tmin,tmax=7,90.0,15.0,60.8
m_sc=167.0
print(f"=== ขับแขนล่างโดยตรง · n={n} L={L} θ {tmin}→{tmax}° (H=550 mm) · ช่วงหมุนเซอร์โว {tmax-tmin:.0f}° ===\n")
for pay in (60,150,300):
    m_top=pay+35
    r0=direct(n,L,tmin,tmax,m_sc,m_top,0,1.0,0,0,999)
    print(f"payload {pay} g : ไม่มีสปริง T พีค = {r0['Tmax']:.3f} N·m = {r0['Tmax']/0.0980665:.2f} kgf·cm  → SF@4.8V {MG['4.8V']/r0['Tmax']:.2f}")
    best=None
    for p in [0.6,0.7,0.8,0.9,1.0]:
        for xa in range(0,41,5):
            for ya in range(0,31,5):
                for s0 in range(25,90,5):
                    for kk in [x/50 for x in range(25,900,5)]:
                        r=direct(n,L,tmin,tmax,m_sc,m_top,kk,p,xa,ya,s0)
                        if r['net_min']<0.005: continue        # กันยกตัวเอง (ต้องเป็นบวกตลอด)
                        if r['ext']>0.8*s0: continue
                        r2=direct(n,L,tmin,tmax,m_sc,m_top,kk,p,xa,ya,s0,kmul=1.10)
                        if r2['net_min']<0.0: continue
                        if best is None or r['Tmax']<best[0]['Tmax']: best=(r,dict(k=kk,p=p,xa=xa,ya=ya,s0=s0),r2)
    if best:
        r,par,r2=best
        print(f"   + สปริง: k_รวม={par['k']:.2f} N/mm (2 ตัว × {par['k']/2:.2f}) · จุดบนแขน p={par['p']}·L={par['p']*L:.0f} mm · A=({par['xa']},{par['ya']}) · s0={par['s0']} mm · ยืดสูงสุด {r['ext']:.1f} mm")
        print(f"     T พีค = {r['Tmax']:.3f} N·m = {r['Tmax']/0.0980665:.2f} kgf·cm → SF {MG['6V']/r['Tmax']:.2f} @6V · {MG['4.8V']/r['Tmax']:.2f} @4.8V   (เกิดที่ θ={r['det'][0]:.1f}°)")
        print(f"     k+10%: T {r2['Tmax']/0.0980665:.2f} kgf·cm · โมเมนต์สุทธิต่ำสุด {r2['net_min']*1000:.1f} N·mm/rad (ต้อง>0)")
    print()
