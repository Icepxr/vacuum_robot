import math
exec(open('lock2.py').read().split("PS=[")[0])
PS=[0.8,0.9,1.0]; XA=[0,10,20]; YA=[0,5,10,15]; S0=range(35,80,5)
KK=[x/20 for x in range(40,200,1)]
m_sc=297.0
for mode,name in (('yoke','A) scotch yoke'),('direct','B) ขับก้านล่างตรง')):
    r0=curves(m_sc,95.0,0,1.0,0,0,9999,mode=mode)
    print(f"{name} ไม่มีสปริง: T {r0['Tmax']/0.0980665:.2f} kgf·cm → SF@4.8V {MG['4.8V']/r0['Tmax']:.2f}",flush=True)
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
         if best is None or r['Tmax']<best[0]['Tmax']: best=(r,dict(k=kk,p=p,xa=xa,ya=ya,s0=s0),r2)
    r,par,r2=best
    print(f"   +สปริง k รวม {par['k']:.2f} N/mm (2×{par['k']/2:.2f}) · p={par['p']}·L={par['p']*89:.0f} mm · A=({par['xa']},{par['ya']}) · s0={par['s0']} mm · ยืดสูงสุด {r['ext']:.1f} mm · แรงรวมสูงสุด {par['k']*r['ext']:.0f} N ({par['k']*r['ext']/2:.0f} N/ตัว)")
    print(f"   T พีค {r['Tmax']/0.0980665:.2f} kgf·cm → SF {MG['6V']/r['Tmax']:.2f}@6V · {MG['4.8V']/r['Tmax']:.2f}@4.8V"+(f" · r_crank {r['r']:.2f} mm · F_act {r['Fmin']:.2f}…{r['Fmax']:.1f} N" if mode=='yoke' else ""))
    print(f"   ทน k+10%: T {r2['Tmax']/0.0980665:.2f} kgf·cm · โมเมนต์สุทธิต่ำสุด {r2['netmin']:.1f} N·mm/rad (ต้อง>0)\n")
