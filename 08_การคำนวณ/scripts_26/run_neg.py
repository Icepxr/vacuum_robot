import glob,cv2,time
from ultralytics import YOLO
M='/Users/daiyazwaehama/Documents/vacuum_project/meter_model/'
cnt=YOLO(M+'counter.pt'); dig=YOLO(M+'digit.pt')
print('counter names',cnt.names,'| digit names',dig.names)
fs=sorted(glob.glob('pi/images/*.jpg'))
for conf in (0.25,0.5):
  nc=nd=0
  print(f'--- conf {conf}')
  for i,f in enumerate(fs):
    im=cv2.imread(f)
    rc=cnt.predict(im,conf=conf,verbose=False)[0]; rd=dig.predict(im,conf=conf,verbose=False)[0]
    c=[(round(float(b.conf),2),[int(v) for v in b.xyxy[0]]) for b in rc.boxes]
    d=sorted([(int(b.xyxy[0][0]),dig.names[int(b.cls)],round(float(b.conf),2)) for b in rd.boxes])
    nc+=bool(c); nd+=bool(d)
    if c or d: print(i,f.split('/')[-1][:15],'counter:',c,'digits:',''.join(x[1] for x in d),[x[2] for x in d])
  print(f'images with counter FP {nc}/24, with digit FP {nd}/24')
