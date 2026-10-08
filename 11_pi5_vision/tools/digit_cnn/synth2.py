"""ชุดทดสอบที่ 2: ใช้ quad จาก strip.find_strip บนรูปจริงทั้ง 12 กล่อง · ฟอนต์ holdout เท่านั้น · หลายสี/หลายแบบ"""
import cv2,numpy as np,json,random,os,glob
from PIL import Image,ImageDraw,ImageFont
import sys; sys.path.insert(0,'../../src'); import reai_strip as strip
random.seed(11); os.makedirs('synth2',exist_ok=True)
SEG={'0':'abcdef','1':'bc','2':'abdeg','3':'abcdg','4':'bcfg','5':'acdfg','6':'acdefg','7':'abc','8':'abcdefg','9':'abcdfg'}
H=json.load(open('fonts.json'))['hold']
def fp(name): return [h for h in H if h[2].startswith(name)]
def tile_font(d,cands,size=150,S=200):
    p,idx,_,_=random.choice(cands); f=ImageFont.truetype(p,size,index=idx)
    im=Image.new('L',(S,S),0); dr=ImageDraw.Draw(im); bb=dr.textbbox((0,0),d,font=f)
    dr.text(((S-(bb[0]+bb[2]))/2,(S-(bb[1]+bb[3]))/2),d,255,font=f); return np.array(im)
def tile_7seg(d,S=200,w=18):
    m=np.zeros((S,S),np.uint8); x0,x1,y0,y1,y2=55,145,30,100,170
    segs={'a':((x0,y0),(x1,y0)),'b':((x1,y0),(x1,y1)),'c':((x1,y1),(x1,y2)),'d':((x0,y2),(x1,y2)),'e':((x0,y1),(x0,y2)),'f':((x0,y0),(x0,y1)),'g':((x0,y1),(x1,y1))}
    for s in SEG[d]:
        (a,b),(c,e)=segs[s]; cv2.line(m,(a+(5 if a!=c else 0)-int(0.12*(b-100)),b+(5 if b!=e else 0)),(c-(5 if a!=c else 0)-int(0.12*(e-100)),e-(5 if b!=e else 0)),255,w)
    return m
STY={  # name: (glyph fn, ink BGR, card BGR or None)
 'black_marker':  (lambda d: tile_font(d,fp('Arial'),160),(30,30,30),None),
 'white_chalk':   (lambda d: tile_font(d,fp('Chalkduster'),150),(245,245,245),None),
 'yellow_7seg':   (lambda d: tile_7seg(d),(40,230,250),None),
 'green_hand':    (lambda d: tile_font(d,fp('Bradley Hand'),170),(60,200,40),None),
 'georgia_card':  (lambda d: tile_font(d,fp('Georgia'),150),(20,20,20),(170,240,250)),
 'courier_card':  (lambda d: tile_font(d,fp('Courier New'),160),(160,30,30),(240,240,240)),
 'red_7seg_small':(lambda d: cv2.resize(tile_7seg(d,w=12),(200,200)),(40,40,230),None),
}
fs=sorted(glob.glob('pi/images/*.jpg')); gt={}
for f in fs:
    r=strip.find_strip(cv2.imread(f))
    if r is None: continue
    q=r['quad']; base=cv2.imread(f)
    # quad ของแต่ละช่อง: แบ่งแถบ 4 ส่วนในพิกัดที่ดัดแล้ว แล้วแปลงกลับ
    Hm=cv2.getPerspectiveTransform(np.float32([[0,0],[480,0],[480,120],[0,120]]),q)
    for sty,(fn,col,card) in STY.items():
        for k in range(3):
            num=''.join(random.choice('0123456789') for _ in range(4)); im=base.astype(np.float32)
            for i,d in enumerate(num):
                cq=cv2.perspectiveTransform(np.float32([[[i*120+8,8],[i*120+112,8],[i*120+112,112],[i*120+8,112]]]),Hm)[0]
                m=fn(d); S=m.shape[0]; T=cv2.getPerspectiveTransform(np.float32([[0,0],[S,0],[S,S],[0,S]]),cq)
                if card is not None:
                    c=cv2.warpPerspective(np.full((S,S),255,np.uint8),T,base.shape[1::-1])/255.; im=im*(1-c[...,None])+np.array(card)*c[...,None]
                mm=cv2.GaussianBlur(cv2.warpPerspective(m,T,base.shape[1::-1]),(3,3),0)/255.
                im=im*(1-mm[...,None])+np.array(col)*mm[...,None]
            im=np.clip(im+np.random.normal(0,3,im.shape),0,255).astype(np.uint8)
            n=f"synth2/{os.path.basename(f)[:15]}_{sty}_{k}.jpg"; cv2.imwrite(n,im,[cv2.IMWRITE_JPEG_QUALITY,88]); gt[n]=num
json.dump(gt,open('synth2_gt.json','w'),indent=0); print(len(gt),'images')
