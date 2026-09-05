import math
G=9.81; RHO=1.27e-3
ETA=0.65*0.90; F_STIC=6.0
MG={'6V':11.0*0.0980665,'4.8V':9.4*0.0980665}

def analyze(n,L,th_min,th_max,W,T,m_pay,plat,k,p,xa,ya,s0,phi0=9.0,n_spring=2,kmul=1.0):
    n_links=4*n
    m_sc=(n_links*L*W*T*RHO+n_links*1.6+20.0)/1000
    m_top=(m_pay+plat)/1000
    W_eff=(m_top+m_sc/2)*G
    stroke=L*(math.cos(math.radians(th_min))-math.cos(math.radians(th_max)))
    r=stroke/(1+math.cos(math.radians(phi0)))
    xc=L*math.cos(math.radians(th_min))-r*math.cos(math.radians(phi0))
    K=k*kmul*n_spring   # N/mm total
    Tmax=0; Fmin=1e9; Fmax=-1e9; smax=0; det=None
    for i in range(241):
        th=th_min+(th_max-th_min)*i/240; tr=math.radians(th)
        # gravity term: dU/dth = n*W_eff*L*cos th  (U = n*W_eff*L*sin th), dxs/dth = -L sin th
        dUg = n*W_eff*L*math.cos(tr)          # N*mm per rad
        px=p*L*math.cos(tr); py=p*L*math.sin(tr)
        dpx=-p*L*math.sin(tr); dpy=p*L*math.cos(tr)
        s=math.hypot(px-xa,py-ya); smax=max(smax,s)
        ext=max(s-s0,0.0)
        dsdth=((px-xa)*dpx+(py-ya)*dpy)/s
        dUs=K*ext*dsdth
        F=(dUg+dUs)/(L*math.sin(tr))          # N  (actuator force at slider)
        Fmin=min(Fmin,F); Fmax=max(Fmax,F)
        xs=L*math.cos(tr); c=max(-1,min(1,(xs-xc)/r)); phi=math.acos(c)
        Tq=(abs(F)/ETA+F_STIC)*(r/1000)*abs(math.sin(phi))
        if Tq>Tmax: Tmax=Tq; det=(th,math.degrees(phi),F)
    return dict(Tmax=Tmax,Fmin=Fmin,Fmax=Fmax,smax=smax,r=r,m_sc=m_sc*1000,det=det,
                ext_max=smax-s0)

# grid search for C2: 7x90, th 15 -> 60.8, payload sweep
n,L,tmin,tmax,W,T,plat=7,90,15,60.8,10,3.2,35
for m_pay in (60,150,300):
    best=None
    for p in [0.7,0.8,0.9,1.0]:
        for xa in range(0,45,5):
            for ya in range(0,30,5):
                for s0 in range(30,90,5):
                    for k in [x/100 for x in range(50,600,15)]:
                        r=analyze(n,L,tmin,tmax,W,T,m_pay,plat,k,p,xa,ya,s0)
                        if r['Fmin']<0.25: continue
                        if r['ext_max']>0.8*s0: continue
                        # robustness: k +10%
                        r2=analyze(n,L,tmin,tmax,W,T,m_pay,plat,k,p,xa,ya,s0,kmul=1.10)
                        if r2['Fmin']<0.25: continue
                        if best is None or r['Tmax']<best[0]['Tmax']:
                            best=(r,dict(k=k,p=p,xa=xa,ya=ya,s0=s0),r2)
    if best:
        r,par,r2=best
        print(f"payload {m_pay} g : k_รวม={par['k']*2:.2f} N/mm (2 ตัว ตัวละ {par['k']:.2f}) p={par['p']} A=({par['xa']},{par['ya']}) s0={par['s0']} mm")
        print(f"   F_act {r['Fmin']:.2f}…{r['Fmax']:.1f} N · ยืดสปริงสูงสุด {r['ext_max']:.1f} mm · T พีค {r['Tmax']:.3f} N·m = {r['Tmax']/0.0980665:.2f} kgf·cm")
        print(f"   SF: {MG['6V']/r['Tmax']:.2f} @6V · {MG['4.8V']/r['Tmax']:.2f} @4.8V  |  k+10%: F_min {r2['Fmin']:.2f} N, T {r2['Tmax']/0.0980665:.2f} kgf·cm")
    else:
        print(f"payload {m_pay} g : ไม่พบคำตอบที่ผ่านเงื่อนไข")
