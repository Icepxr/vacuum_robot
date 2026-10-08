import cv2,json,numpy as np
from ultralytics import YOLO
M='/Users/daiyazwaehama/Documents/vacuum_project/meter_model/'
cnt=YOLO(M+'counter.pt'); dig=YOLO(M+'digit.pt')
B=json.load(open('boxes.json')); G=json.load(open('synth_gt.json'))
def rd(c):
    r=dig.predict(c,conf=0.25,verbose=False)[0]
    return ''.join(dig.names[int(b.cls)] for b in sorted(r.boxes,key=lambda b:float(b.xyxy[0][0])))
for z in (1.0,2.0,3.5):     # context around the 4-box strip, multiples of strip width
  st={}
  for k,g in G.items():
    sty=k.split('_',2)[2].rsplit('_',1)[0]; im=cv2.imread(k)
    q=np.array(sum([v for s,v in B.items() if s.split('/')[-1][:15]==k.split('/')[-1][:15]][0],[]))
    cx,cy=q.mean(0); w=(q[:,0].max()-q[:,0].min())*z
    x0,y0=int(max(cx-w/2,0)),int(max(cy-w*0.5625/2,0)); c=im[y0:int(cy+w*0.5625/2),x0:int(cx+w/2)]
    rc=cnt.predict(c,conf=0.25,verbose=False)[0]
    t=st.setdefault(sty,[0,0,0]); t[0]+=1
    if len(rc.boxes):
        t[1]+=1; b=[int(v) for v in rc.boxes[int(rc.boxes.conf.argmax())].xyxy[0]]
        t[2]+=rd(c[b[1]:b[3],b[0]:b[2]])==g
    if k.endswith('print_card_0.jpg') and z==2.0: cv2.imwrite('zoom_peek.jpg',c)
  print('zoom ctx',z,'x strip: [n, counter found, exact]',st)
