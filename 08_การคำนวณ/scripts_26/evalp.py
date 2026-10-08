import cv2,json,numpy as np,sys,collections
sys.path.insert(0,'/Users/daiyazwaehama/Documents/vacuum_project/11_pi5_vision/src')
from ultralytics import YOLO
import sevenseg
M='/Users/daiyazwaehama/Documents/vacuum_project/meter_model/'
cnt=YOLO(M+'counter.pt'); dig=YOLO(M+'digit.pt')
B=json.load(open('boxes.json')); G=json.load(open('synth_gt.json'))
def quads_for(k):
    return [v for s,v in B.items() if s.split('/')[-1][:15]==k.split('/')[-1][:15]][0]
def read_digits(crop,conf=0.25):
    r=dig.predict(crop,conf=conf,verbose=False)[0]
    d=sorted([(float(b.xyxy[0][0]),dig.names[int(b.cls)],float(b.conf)) for b in r.boxes])
    return ''.join(x[1] for x in d),[round(x[2],2) for x in d]
def pad(im,x0,y0,x1,y1,p):
    w,h=x1-x0,y1-y0; H,W=im.shape[:2]
    return im[max(int(y0-p*h),0):min(int(y1+p*h),H),max(int(x0-p*w),0):min(int(x1+p*w),W)]
def dacc(p,g): return sum(a==b for a,b in zip(p,g))
res=collections.defaultdict(lambda: collections.Counter())
rows=[]
for k,g in G.items():
    sty=k.split('_',2)[2].rsplit('_',1)[0]; im=cv2.imread(k)
    q=np.array(sum(quads_for(k),[])); x0,y0=q.min(0); x1,y1=q.max(0)
    oc=pad(im,x0,y0,x1,y1,0.25)
    # E1
    rc=cnt.predict(im,conf=0.25,verbose=False)[0]
    if len(rc.boxes):
        b=rc.boxes[int(rc.boxes.conf.argmax())]; bx=[float(v) for v in b.xyxy[0]]
        e1,c1=read_digits(pad(im,*bx,0.10)); cc=round(float(b.conf),2)
        # IoU with true strip
        ix=max(0,min(bx[2],x1)-max(bx[0],x0))*max(0,min(bx[3],y1)-max(bx[1],y0))
        iou=ix/((bx[2]-bx[0])*(bx[3]-bx[1])+(x1-x0)*(y1-y0)-ix)
    else: e1,c1,cc,iou='',[],None,0
    e2,c2=read_digits(oc)
    s3=sevenseg.read(oc,ink='red')['text'] if sty!='print_card' else sevenseg.read(oc,ink='dark')['text']
    rows.append((k.split('/')[-1],g,cc,round(iou,2),e1,e2,s3))
    for tag,p in (('E1',e1),('E2',e2),('E3_7seg',s3)):
        res[(tag,sty)]['n']+=1; res[(tag,sty)]['exact']+=(p==g); res[(tag,sty)]['dig']+=dacc(p,g) if len(p)==4 else 0
    res[('cnt',sty)]['n']+=1; res[('cnt',sty)]['found']+=cc is not None; res[('cnt',sty)]['iou50']+=iou>=0.5
for r in rows: print(r)
print()
for (tag,sty),c in sorted(res.items()): print(tag,sty,dict(c))
