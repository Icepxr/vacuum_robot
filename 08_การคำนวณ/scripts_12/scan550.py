import math, itertools
G=9.81; RHO=1.27e-3  # g/mm^3 PETG
def cot(d): return 1/math.tan(math.radians(d))

def eval_cfg(n,L,th_min,th_max,W,T,base,m_pay_g,plat_g,track=62.0,pin_hw=16.0,clear=1.0):
    H = n*L*math.sin(math.radians(th_max))
    Hs= n*L*math.sin(math.radians(th_min))
    span_stow = L*math.cos(math.radians(th_min))
    d_gap = L*math.sin(math.radians(th_min))*math.cos(math.radians(th_min))
    # masses
    n_links = 4*n            # 2 links/stage/plane x 2 planes
    v_link = L*W*T           # mm^3 (approx, ignoring end radii vs hole)
    m_links = n_links*v_link*RHO
    m_hw    = n_links*1.6 + 20.0   # screws/bushes/spacers ~1.6 g per link joint + slider
    m_sc = m_links+m_hw
    m_top = m_pay_g+plat_g
    W_eff = (m_top/1000 + (m_sc/1000)/2)*G
    F_min = n*W_eff*cot(th_min)     # peak, no spring
    F_max_th = n*W_eff*cot(th_max)
    # link axial force at th_min (worst)
    F_link = F_min/math.cos(math.radians(th_min))/4
    A = W*T
    sig = F_link/A
    I = W*T**3/12
    Pcr = math.pi**2*2000*I/L**2
    # tower lateral stiffness
    I_t = 2*(W*T)*(track/2)**2
    kb = 3*2000*I_t/H**3
    # wander from pin clearance 0.15mm
    clr=0.15; tilt=2*clr/track
    wander = sum(tilt*(H - (k*H/n) + H/n) for k in range(1,n+1))
    stroke = L*(math.cos(math.radians(th_min))-math.cos(math.radians(th_max)))
    return dict(H=H,Hs=Hs,span=span_stow,gap=d_gap,m_sc=m_sc,m_top=m_top,W_eff=W_eff,
                F_min=F_min,F_max=F_max_th,F_link=F_link,sig=sig,Pcr=Pcr,SFb=Pcr/F_link,
                kb=kb,wander=wander,stroke=stroke,n_links=n_links)

print("=== A) เทียบทางเลือกเรขาคณิตให้ H>=550 mm (payload 60g + platform 35g, PETG 10x3.2) ===")
print(f"{'n':>2} {'L':>5} {'θmin':>5} {'θmax':>5} {'H':>6} {'Hพับ':>6} {'span':>6} {'ช่องว่าง':>7} {'m_sc':>6} {'Fพีค':>7} {'SFโก่ง':>6} {'k_ข้าง':>6} {'แกว่ง':>6} {'ชัก':>6}")
cands=[]
for n in (7,8,9,10):
    for L in (70,80,90,100):
        for th_min in (8,10,12,15,20):
            # find th_max needed for 550
            s=550/(n*L)
            if s>=0.95: continue
            th_max=math.degrees(math.asin(s))
            if th_max<=th_min+10: continue
            r=eval_cfg(n,L,th_min,th_max,10.0,3.2,100,60,35)
            if r['gap']<11.0: continue   # link width 10 + 1 clearance
            cands.append((n,L,th_min,th_max,r))
for n,L,tmin,tmax,r in cands:
    print(f"{n:>2} {L:>5.0f} {tmin:>5.0f} {tmax:>5.1f} {r['H']:>6.0f} {r['Hs']:>6.0f} {r['span']:>6.1f} {r['gap']:>7.1f} {r['m_sc']:>6.0f} {r['F_min']:>7.1f} {r['SFb']:>6.2f} {r['kb']:>6.2f} {r['wander']:>6.1f} {r['stroke']:>6.1f}")
