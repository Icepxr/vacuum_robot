import cv2,json,glob,time,collections,numpy as np,sys
sys.path.insert(0,'../../src')
import cellread
cellread._net=cellread.DigitNet(); cellread._check=cellread.DigitNet(cellread.CHECK_MODEL)
def run(gtfile,tag):
    G=json.load(open(gtfile)); ok=dig=tot=0; flag=0; wrong_unflagged=0
    for k,g in G.items():
        r=cellread.read_meter(cv2.imread(k)); p=r['text'] if r['ok'] else None
        ok+=p==g; dig+=sum(a==b for a,b in zip(p or '',g)); tot+=4
        if p is not None and p!=g and r['conf']>=0.8: wrong_unflagged+=1
    print(f'{tag}: ถูกครบ {ok}/{len(G)} ({ok/len(G)*100:.1f}%) · รายหลัก {dig/tot*100:.1f}% · ผิดแต่มั่นใจ ≥0.8: {wrong_unflagged}')
run('synth_gt.json','ชุด 1'); run('synth2_gt.json','ชุด 2')
fs=sorted(glob.glob('pi/images/*.jpg')); fp=[]; blank=0; t=[]
for i,f in enumerate(fs):
    t0=time.perf_counter(); r=cellread.read_meter(cv2.imread(f)); t.append(time.perf_counter()-t0)
    box=12<=i<=23 and i!=17
    if box: blank+= (r['source']=='reai' and not r['ok'])
    elif r['ok']: fp.append((i,r['text'],r['conf'],r['source']))
print(f'กล่องว่างจริง: ไม่ให้ค่า {blank}/11 · รูปไม่มีมิเตอร์ที่ถูกอ่านเป็นเลข: {len(fp)}/13 {fp} · เวลาเฉลี่ย {np.mean(t)*1e3:.0f} ms (Mac)')
c=cv2.imread('popup_crop.png'); big=np.full((720,1280,3),90,np.uint8); big[300:444,400:845]=c
for n,im in (('มิเตอร์น้ำ (ครอปป๊อปอัพ)',c),('มิเตอร์น้ำในเฟรม 1280×720',big)):
    r=cellread.read_meter(im); print(n,'→',r['text'],r['conf'],r['source'],r['why'],'(ค่าจริง 0521893)')
