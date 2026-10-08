"""ประเมินทั้งไปป์ไลน์: ภาพเต็ม → find_strip → 4 ช่อง → DigitNet"""
import cv2,json,glob,time,sys,collections,numpy as np
import sys; sys.path.insert(0,'../../src')
import reai_strip as strip; from cellread import DigitNet
net=DigitNet(sys.argv[1] if len(sys.argv)>1 else 'digitnet.onnx')
def read(im):
    r=strip.find_strip(im)
    if r is None: return None,[]
    out=net.predict(strip.cells(r['strip'],inset=0.08))
    return ''.join(o[0] for o in out),[round(o[1],2) for o in out]
def run(gtfile,tag):
    G=json.load(open(gtfile)); st=collections.defaultdict(lambda:[0,0,0,0,0]); bad=[]
    t=time.perf_counter()
    for k,g in G.items():
        sty=k.split('_',2)[2].rsplit('_',1)[0]; p,c=read(cv2.imread(k)); s=st[sty]
        s[0]+=1; s[1]+=p is not None; s[2]+=p==g; s[3]+=sum(a==b for a,b in zip(p or '',g)); s[4]+=4
        if p!=g: bad.append((k.split('/')[-1],g,p,c))
    dt=(time.perf_counter()-t)/len(G)*1000
    print(f'== {tag}  ({dt:.0f} ms/ภาพ บน Mac)  [n, เจอแถบ, ถูกครบ 4 หลัก, หลักถูก/หลักทั้งหมด]')
    tot=[0]*5
    for sty,s in sorted(st.items()):
        print(f'  {sty:15s} {s[0]:3d} {s[1]:3d} {s[2]:3d}  {s[3]}/{s[4]}'); tot=[a+b for a,b in zip(tot,s)]
    print(f'  {"รวม":15s} {tot[0]:3d} {tot[1]:3d} {tot[2]:3d}  {tot[3]}/{tot[4]}  → ถูกครบ {tot[2]/tot[0]*100:.1f}% · รายหลัก {tot[3]/tot[4]*100:.1f}%')
    for b in bad[:12]: print('   ✗',b)
    return bad
run('synth_gt.json','ชุด 1 (75 ภาพ · 7seg แดง/การ์ด Arial/ลายมือ Bradley)')
run('synth2_gt.json','ชุด 2 (231 ภาพ · ฟอนต์ holdout · หลายสี)')
# ชุดลบจริง: 12 กล่องช่องว่าง → ต้องได้ "____" · 12 รูปไม่มีกล่อง → ต้องไม่เจอแถบ
fs=sorted(glob.glob('pi/images/*.jpg')); blank_ok=cells_ok=nostrip_ok=0; nb=0
for i,f in enumerate(fs):
    p,c=read(cv2.imread(f)); box=12<=i<=23 and i!=17
    if box: nb+=1; blank_ok+=p=='____'; cells_ok+=(p or '').count('_'); print('  กล่องว่าง',i,p,c) if p!='____' else None
    else: nostrip_ok+=p is None
print(f'== รูปจริง: กล่องช่องว่างอ่านเป็น ____ ครบ {blank_ok}/{nb} กล่อง ({cells_ok}/{nb*4} ช่อง) · รูปไม่มีกล่องไม่เจอแถบ {nostrip_ok}/{24-nb}')
