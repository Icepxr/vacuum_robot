"""สถิตยศาสตร์ scissor n ชั้น (1 ระนาบ) — หาแรงในหมุดทุกจุด + โมเมนต์ดัดกลางแขน
พิกัด: ฐานที่ y=0 · แขน A_k จาก (0,y_k)->(Lc,y_k+Ls) · แขน B_k จาก (Lc,y_k)->(0,y_k+Ls)
หมุดกลางของทั้งคู่อยู่ที่ (Lc/2, y_k+Ls/2)
ฐาน: A_0 ล่าง = หมุดตายตัว · B_0 ล่าง = slider (แรงตั้งฉากอย่างเดียว) + แรง actuator แนวนอน
บน:  B_{n-1} บน = หมุดยึดแพลตฟอร์ม · A_{n-1} บน = ร่องเลื่อน (แรงตั้งฉากอย่างเดียว)
"""
import numpy as np, math

def solve(n,L,th,m_link_g,m_plat_g,m_pay_g,g=9.81):
    c,s=math.cos(math.radians(th)),math.sin(math.radians(th))
    Ls,Lc=L*s,L*c
    w=m_link_g/1000*g            # N ต่อแขน 1 ท่อน (1 ระนาบ)
    Wp=(m_plat_g+m_pay_g)/1000*g # N ทั้งแพลตฟอร์ม -> ครึ่งหนึ่งต่อระนาบ
    Wp/=2.0
    H=n*Ls
    # ตำแหน่ง
    def A_pts(k): y=k*Ls; return (0,y),(Lc/2,y+Ls/2),(Lc,y+Ls)
    def B_pts(k): y=k*Ls; return (Lc,y),(Lc/2,y+Ls/2),(0,y+Ls)
    # ดัชนีตัวแปร
    idx={}; nv=0
    def add(name,k=2):
        nonlocal nv
        idx[name]=nv; nv+=k
    for k in range(n): add(('mid',k))
    for k in range(n-1): add(('R',k)); add(('Lf',k))
    add('basepin'); add('slider',1); add('toppin'); add('topslot',1); add('Fact',1)
    NB=2*n+1   # 2n แขน + แพลตฟอร์ม 1
    Aeq=np.zeros((3*NB,nv)); b=np.zeros(3*NB)
    def put(row_body,pos,var,comps,sign):
        """ใส่แรงที่จุด pos จากตัวแปร var (comps = 'xy' หรือ 'y') คูณ sign"""
        r0=3*row_body; i=idx[var]
        if comps=='xy':
            Aeq[r0+0,i]+=sign;            Aeq[r0+1,i+1]+=sign
            Aeq[r0+2,i]  += -sign*pos[1]; Aeq[r0+2,i+1]+= sign*pos[0]
        elif comps=='y':
            Aeq[r0+1,i]+=sign;            Aeq[r0+2,i]+= sign*pos[0]
        elif comps=='x':
            Aeq[r0+0,i]+=sign;            Aeq[r0+2,i]+= -sign*pos[1]
    def load(row_body,pos,fx,fy):
        r0=3*row_body
        b[r0+0]-=fx; b[r0+1]-=fy; b[r0+2]-=(pos[0]*fy-pos[1]*fx)
    # ---- แขน A_k : body id = k
    for k in range(n):
        bid=k; p0,pm,p1=A_pts(k)
        put(bid,pm,('mid',k),'xy',+1)                     # จาก B_k
        if k==0: put(bid,p0,'basepin','xy',+1)
        else:    put(bid,p0,('Lf',k-1),'xy',-1)           # ปฏิกิริยาจาก B_{k-1}
        if k==n-1: put(bid,p1,'topslot','y',+1)
        else:      put(bid,p1,('R',k),'xy',+1)
        load(bid,pm,0,-w)
    # ---- แขน B_k : body id = n+k
    for k in range(n):
        bid=n+k; p0,pm,p1=B_pts(k)
        put(bid,pm,('mid',k),'xy',-1)
        if k==0:
            put(bid,p0,'slider','y',+1)
            Aeq[3*bid+0,idx['Fact']]+=-1.0                # แรง actuator ทิศ -x
            Aeq[3*bid+2,idx['Fact']]+= +p0[1]*1.0         # -(-1)*y = +y ... m=-Fx*y
        else:
            put(bid,p0,('R',k-1),'xy',-1)
        if k==n-1: put(bid,p1,'toppin','xy',+1)
        else:      put(bid,p1,('Lf',k),'xy',+1)
        load(bid,pm,0,-w)
    # ---- แพลตฟอร์ม : body id = 2n
    bid=2*n
    put(bid,(0,H),'toppin','xy',-1)
    put(bid,(Lc,H),'topslot','y',-1)
    load(bid,(Lc/2,H),0,-Wp)
    x,res,rank,sv=np.linalg.lstsq(Aeq,b,rcond=None)
    resid=np.linalg.norm(Aeq@x-b)
    out={'Fact':x[idx['Fact']],'resid':resid,'rank':rank,'nv':nv}
    # โมเมนต์ดัดกลางแขน: คิดจากด้านปลายล่างของแต่ละแขน
    Ms=[]
    for k in range(n):
        for tag,pts in (('A',A_pts(k)),('B',B_pts(k))):
            p0,pm,p1=pts
            if tag=='A':
                if k==0: F=np.array([x[idx['basepin']],x[idx['basepin']+1]])
                else:    F=-np.array([x[idx[('Lf',k-1)]],x[idx[('Lf',k-1)]+1]])
            else:
                if k==0: F=np.array([-x[idx['Fact']],x[idx['slider']]])
                else:    F=-np.array([x[idx[('R',k-1)]],x[idx[('R',k-1)]+1]])
            r=np.array([p0[0]-pm[0],p0[1]-pm[1]])
            M=abs(r[0]*F[1]-r[1]*F[0])
            # แรงตามแนวแขน (axial)
            u=np.array([p1[0]-p0[0],p1[1]-p0[1]]); u=u/np.linalg.norm(u)
            ax=abs(F@u)
            Ms.append((k,tag,M,ax))
    out['links']=Ms
    return out

if __name__=='__main__':
    n,L=7,90.0
    m_link=90*10*3.2*1.27e-3   # g ต่อแขน (PETG 10x3.2)
    for th in (15.0,30.0,45.0,60.8):
        r=solve(n,L,th,m_link,35/2,60/2)   # แพลตฟอร์ม+payload หารสองแล้วในฟังก์ชัน... (ส่งค่ารวม)
        Mmax=max(m[2] for m in r['links']); axmax=max(m[3] for m in r['links'])
        print(f"θ={th:5.1f}°  F_act={r['Fact']:7.2f} N (1 ระนาบ)  M_max={Mmax:7.0f} N·mm  แรงตามแกนสูงสุด={axmax:6.1f} N  resid={r['resid']:.2e}")
