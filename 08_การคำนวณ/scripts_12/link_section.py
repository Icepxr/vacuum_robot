import math
E=2000.0; SIG_ALLOW=15.0; RHO=1.27e-3; PIN_D=3.0
n,L,tmin,tmax=7,90,15,60.8
track=62.0
def struct(W,T,F_slider,label):
    F_link=F_slider/math.cos(math.radians(tmin))/4      # 2 ระนาบ x 2 แขน
    A=W*T; sig=F_link/A
    I_weak=W*T**3/12; Pcr=math.pi**2*E*I_weak/L**2
    sig_b=F_link/(PIN_D*T)
    H=n*L*math.sin(math.radians(tmax))
    I_t=2*A*(track/2)**2; kb=3*E*I_t/H**3
    m=(4*n*L*W*T*RHO)/1000
    return dict(W=W,T=T,A=A,F_link=F_link,sig=sig,SF_sig=SIG_ALLOW/sig,Pcr=Pcr,SF_b=Pcr/F_link,
                sig_bear=sig_b,SF_bear=SIG_ALLOW/sig_b,kb=kb,m_links=m,H=H)
print(f"H ยกสุด = {n*L*math.sin(math.radians(tmax)):.0f} mm · L={L} · θ={tmin}→{tmax}° · ช่องว่างแขนตอนพับ = {L*math.sin(math.radians(tmin))*math.cos(math.radians(tmin)):.1f} mm")
for F_slider,tag in ((45.8,"ไม่มีสปริง pay60"),(107.3,"ไม่มีสปริง pay300"),(11.0,"มีสปริง pay300")):
    print(f"\n--- กรณีโหลด: {tag}  (F_slider={F_slider} N) ---")
    print(f"{'W':>4}{'T':>5}{'F_แขน':>8}{'σอัด':>7}{'SFσ':>7}{'P_cr':>8}{'SFโก่ง':>7}{'σแบริ่ง':>8}{'SFbrg':>7}{'k_ข้าง':>7}{'มวลแขน':>8}")
    for W in (10,14,18):
        for T in (3.2,4,5,6,8):
            r=struct(W,T,F_slider,tag)
            print(f"{W:>4}{T:>5.1f}{r['F_link']:>8.1f}{r['sig']:>7.2f}{r['SF_sig']:>7.1f}{r['Pcr']:>8.1f}{r['SF_b']:>7.2f}{r['sig_bear']:>8.2f}{r['SF_bear']:>7.1f}{r['kb']:>7.2f}{r['m_links']:>8.0f}")
