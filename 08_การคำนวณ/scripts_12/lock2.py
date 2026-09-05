import math
G=9.81; RHO=1.27e-3
ETA=0.65*0.90; F_STIC=6.0; ETA_J=0.65; T_STIC=0.05
MG={'6V':11.0*0.0980665,'4.8V':9.4*0.0980665}
n,L,tmin,tmax=7,89.0,7.19,62.0

def curves(m_sc_g,m_top_g,k_tot,p,xa,ya,s0,kmul=1.0,N=161,mode='yoke',phi0=9.0):
    W_eff=((m_top_g/1000)+(m_sc_g/1000)/2)*G
    stroke=L*(math.cos(math.radians(tmin))-math.cos(math.radians(tmax)))
    r=stroke/(1+math.cos(math.radians(phi0)))
    xc=L*math.cos(math.radians(tmin))-r*math.cos(math.radians(phi0))
    K=k_tot*kmul
    Tmax=0; Fmin=1e9; Fmax=-1e9; smax=0; netmin=1e9
    for i in range(N):
        th=tmin+(tmax-tmin)*i/(N-1); tr=math.radians(th)
        dUg=n*W_eff*L*math.cos(tr)
        px=p*L*math.cos(tr); py=p*L*math.sin(tr)
        dpx=-p*L*math.sin(tr); dpy=p*L*math.cos(tr)
        s=math.hypot(px-xa,py-ya); smax=max(smax,s)
        dUs=K*max(s-s0,0.0)*((px-xa)*dpx+(py-ya)*dpy)/s
        net=dUg+dUs                       # N*mm/rad
        netmin=min(netmin,net)
        if mode=='yoke':
            F=net/(L*math.sin(tr))
            Fmin=min(Fmin,F); Fmax=max(Fmax,F)
            xs=L*math.cos(tr); c=max(-1,min(1,(xs-xc)/r)); phi=math.acos(c)
            Tq=(abs(F)/ETA+F_STIC)*(r/1000)*abs(math.sin(phi))
        else:
            Tq=abs(net/1000.0)/ETA_J+T_STIC
        Tmax=max(Tmax,Tq)
    return dict(Tmax=Tmax,Fmin=Fmin,Fmax=Fmax,ext=smax-s0,netmin=netmin,r=r)

PS=[0.7,0.8,0.9,1.0]; XA=range(0,41,10); YA=range(0,31,10); S0=range(30,90,10)
KK=[x/10 for x in range(20,400,4)]
for tag,m_sc in {"ก้าน 10x8.0 mm (ระนาบเดียว)":318.0,"ก้าน 16x5.0 mm (เหลื่อมระนาบ)":318.0,"ก้าน 10x3.2 mm (ค่าเดิม)":166.0}.items():
    print(f"\n===== {tag} · m_เสา {m_sc:.0f} g · m_top 95 g =====",flush=True)
    for mode,name in (('yoke','A) scotch yoke'),('direct','B) ขับก้านล่างตรง')):
        r0=curves(m_sc,95.0,0,1.0,0,0,9999,mode=mode)
        extra=f" · F พีค {r0['Fmax']:.0f} N" if mode=='yoke' else f" · ช่วงหมุน {tmax-tmin:.1f}°"
        print(f"  {name} ไม่มีสปริง: T {r0['Tmax']/0.0980665:.2f} kgf·cm → SF@4.8V {MG['4.8V']/r0['Tmax']:.2f}{extra}",flush=True)
        best=None
        for p in PS:
            for xa in XA:
                for ya in YA:
                    for s0 in S0:
                        for kk in KK:
                            r=curves(m_sc,95.0,kk,p,xa,ya,s0,mode=mode)
                            if r['netmin']<5.0 or r['ext']>0.8*s0: continue
                            r2=curves(m_sc,95.0,kk,p,xa,ya,s0,kmul=1.10,mode=mode)
                            if r2['netmin']<0.0: continue
                            if best is None or r['Tmax']<best[0]['Tmax']: best=(r,dict(k=kk,p=p,xa=xa,ya=ya,s0=s0))
        if best:
            r,par=best
            print(f"     +สปริง k รวม {par['k']:.1f} N/mm (2×{par['k']/2:.2f}) · p={par['p']} A=({par['xa']},{par['ya']}) s0={par['s0']} mm · ยืด {r['ext']:.0f} mm · แรงสปริงรวมสูงสุด {par['k']*r['ext']:.0f} N",flush=True)
            print(f"     T พีค {r['Tmax']/0.0980665:.2f} kgf·cm → SF {MG['6V']/r['Tmax']:.2f}@6V · {MG['4.8V']/r['Tmax']:.2f}@4.8V"+(f" · r_crank {r['r']:.1f} mm" if mode=='yoke' else ""),flush=True)
        else:
            print("     +สปริง: ไม่พบคำตอบที่ผ่านเงื่อนไข",flush=True)
