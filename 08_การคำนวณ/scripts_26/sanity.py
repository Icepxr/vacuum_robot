import cv2,json,numpy as np,random
from PIL import Image,ImageDraw,ImageFont
from ultralytics import YOLO
M='/Users/daiyazwaehama/Documents/vacuum_project/meter_model/'
cnt=YOLO(M+'counter.pt'); dig=YOLO(M+'digit.pt')
B=json.load(open('boxes.json')); G=json.load(open('synth_gt.json'))
def rd(crop,conf=0.25):
    r=dig.predict(crop,conf=conf,verbose=False)[0]
    return ''.join(dig.names[int(b.cls)] for b in sorted(r.boxes,key=lambda b:float(b.xyxy[0][0])))
# 1) tighter oracle crop, conf variants
for p,conf in ((0.05,0.25),(0.05,0.5),(0.25,0.5)):
  ex=collections=0; tot={}
  for k,g in G.items():
    sty=k.split('_',2)[2].rsplit('_',1)[0]
    q=np.array(sum([v for s,v in B.items() if s.split('/')[-1][:15]==k.split('/')[-1][:15]][0],[]))
    x0,y0=q.min(0); x1,y1=q.max(0); w,h=x1-x0,y1-y0; im=cv2.imread(k)
    c=im[int(y0-p*h):int(y1+p*h),int(x0-p*w):int(x1+p*w)]
    t=tot.setdefault(sty,[0,0]); t[0]+=1; t[1]+=rd(c,conf)==g
  print('pad',p,'conf',conf,tot)
# 2) mechanical-register synth (white digits in black windows, last red) on a light meter plate
random.seed(3); f=ImageFont.truetype('/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf',90)
wall=cv2.imread(sorted(B)[0]); ok_c=ok_d=n=0; out=[]
for i in range(20):
    num=''.join(random.choice('0123456789') for _ in range(5))
    pl=Image.new('RGB',(560,300),(225,228,230)); dr=ImageDraw.Draw(pl)
    dr.rectangle((40,90,520,210),fill=(20,20,20))
    for j,d in enumerate(num):
        x=50+j*94; dr.rectangle((x,100,x+84,200),fill=(10,10,10) if j<4 else (150,20,20))
        bb=dr.textbbox((0,0),d,font=f); dr.text((x+42-(bb[2]-bb[0])/2-bb[0],150-(bb[3]-bb[1])/2-bb[1]),d,fill=(240,240,240),font=f)
    dr.text((200,30),"kWh",fill=(30,30,30),font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',48))
    plate=cv2.cvtColor(np.array(pl),cv2.COLOR_RGB2BGR)
    s=random.uniform(0.5,1.0); plate=cv2.resize(plate,None,fx=s,fy=s)
    im=wall.copy(); y,x=300+random.randint(0,200),600+random.randint(0,300)
    im[y:y+plate.shape[0],x:x+plate.shape[1]]=plate
    rc=cnt.predict(im,conf=0.25,verbose=False)[0]; n+=1
    if len(rc.boxes):
        ok_c+=1; b=[int(v) for v in rc.boxes[int(rc.boxes.conf.argmax())].xyxy[0]]
        r=rd(im[b[1]:b[3],b[0]:b[2]]); ok_d+=r==num; out.append((num,r,round(float(rc.boxes.conf.max()),2)))
    else: out.append((num,'-no counter-',None))
    if i<2: cv2.imwrite(f'mech_{i}.jpg',im)
print('mech register: counter found',ok_c,'/',n,' exact read',ok_d,'/',n); print(out)
