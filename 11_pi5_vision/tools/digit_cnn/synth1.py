import cv2,numpy as np,json,random,os
from PIL import Image,ImageDraw,ImageFont
random.seed(7); os.makedirs('synth',exist_ok=True)
B=json.load(open('boxes.json'))
SEG={'0':'abcdef','1':'bc','2':'abdeg','3':'abcdg','4':'bcfg','5':'acdfg','6':'acdefg','7':'abc','8':'abcdefg','9':'abcdfg'}
def tile_7seg(d,S=200):
    t=np.zeros((S,S,3),np.uint8); m=np.zeros((S,S),np.uint8)
    x0,x1,y0,y1,y2,w=50,150,25,100,175,16
    segs={'a':((x0,y0),(x1,y0)),'b':((x1,y0),(x1,y1)),'c':((x1,y1),(x1,y2)),'d':((x0,y2),(x1,y2)),
          'e':((x0,y1),(x0,y2)),'f':((x0,y0),(x0,y1)),'g':((x0,y1),(x1,y1))}
    for s in SEG[d]:
        (a,b),(c,e)=segs[s]; cv2.line(m,(a+(4 if a!=c else 0),b+(4 if b!=e else 0)),(c-(4 if a!=c else 0),e-(4 if b!=e else 0)),255,w)
    return m,(40,40,235)            # mask, colour BGR (red LED)
def tile_font(d,font,S=200,size=150):
    im=Image.new('L',(S,S),0); dr=ImageDraw.Draw(im); f=ImageFont.truetype(font,size)
    bb=dr.textbbox((0,0),d,font=f); w,h=bb[2]-bb[0],bb[3]-bb[1]
    dr.text(((S-w)/2-bb[0],(S-h)/2-bb[1]),d,255,font=f); return np.array(im)
STY={
 '7seg_red':lambda d:(tile_7seg(d)[0],(40,40,235),None),
 'print_card':lambda d:(tile_font(d,'/System/Library/Fonts/Supplemental/Arial Bold.ttf'),(25,25,25),(235,235,235)),
 'hand_red':lambda d:(tile_font(d,'/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf',size=165),(50,40,220),None),
}
gt={}
for src,quads in B.items():
    base=cv2.imread(src)
    for sty,fn in STY.items():
        for k in range(5):
            num=''.join(random.choice('0123456789') for _ in range(4))
            im=base.copy().astype(np.float32)
            for d,q in zip(num,quads):
                q=np.array(q,np.float32)
                # order corners tl,tr,br,bl
                s=q.sum(1); df=np.diff(q,axis=1).ravel()
                q=np.array([q[s.argmin()],q[df.argmin()],q[s.argmax()],q[df.argmax()]],np.float32)
                m,col,bg=fn(d); S=m.shape[0]
                H=cv2.getPerspectiveTransform(np.float32([[0,0],[S,0],[S,S],[0,S]]),q)
                if bg is not None:
                    full=cv2.warpPerspective(np.full((S,S),255,np.uint8),H,(im.shape[1],im.shape[0]))/255.
                    im=im*(1-full[...,None])+np.array(bg)*full[...,None]
                mm=cv2.warpPerspective(m,H,(im.shape[1],im.shape[0]))
                mm=cv2.GaussianBlur(mm,(3,3),0)/255.
                im=im*(1-mm[...,None])+np.array(col)*mm[...,None]
            im=np.clip(im+np.random.normal(0,3,im.shape),0,255).astype(np.uint8)
            name=f"synth/{os.path.basename(src)[:15]}_{sty}_{k}.jpg"
            cv2.imwrite(name,im,[cv2.IMWRITE_JPEG_QUALITY,90]); gt[name]=num
json.dump(gt,open('synth_gt.json','w'),indent=0); print(len(gt))
