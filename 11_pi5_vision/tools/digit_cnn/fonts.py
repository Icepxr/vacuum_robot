import glob,numpy as np,json,os
from PIL import Image,ImageDraw,ImageFont
paths=sorted(set(glob.glob('/System/Library/Fonts/*.tt?')+glob.glob('/System/Library/Fonts/Supplemental/*.tt?')+glob.glob('/Library/Fonts/*.tt?')+glob.glob(os.path.expanduser('~/Library/Fonts/*.tt?'))))
good=[]
def render(f,d):
    im=Image.new('L',(64,64),0); dr=ImageDraw.Draw(im); bb=dr.textbbox((0,0),d,font=f)
    if bb[2]-bb[0]<3 or bb[3]-bb[1]<8: return None
    dr.text((32-(bb[0]+bb[2])/2,32-(bb[1]+bb[3])/2),d,255,font=f); return np.array(im)>0
w=lambda g: np.ptp(np.where(g.any(0))[0])
BAD=('Webdings','Wingdings','Symbol','Zapf Dingbats','Bodoni Ornaments','Emoji','LastResort','Apple Braille','Keyboard','Apple Symbols')
for p in paths:
    for idx in range(0,8):
        try: f=ImageFont.truetype(p,44,index=idx)
        except Exception: break
        try: gl=[render(f,str(d)) for d in range(10)]
        except Exception: continue
        if any(g is None for g in gl): continue
        flat=[g.ravel() for g in gl]
        dist=min((flat[i]!=flat[j]).mean() for i in range(10) for j in range(i+1,10))
        if dist<0.02: continue
        name=f.getname()
        if any(k in (name[0] or '') for k in BAD): continue
        good.append((p,idx,name[0],name[1]))
HOLD=('Arial','Bradley Hand','Chalkduster','Georgia','Courier New')
hold=[g for g in good if g[2].startswith(HOLD)]; train=[g for g in good if not g[2].startswith(HOLD)]
print(len(good),'faces · train',len(train),'holdout',len(hold),'· families',len(set(g[2] for g in train)))
json.dump({'train':train,'hold':hold},open('fonts.json','w'))
# contact sheet of '2','4','7' across random train fonts to eyeball oddities
import random; random.seed(1); smp=random.sample(train,min(60,len(train)))
rows=[]
for k in range(0,len(smp),12):
    row=[]
    for p,idx,n,s in smp[k:k+12]:
        f=ImageFont.truetype(p,40,index=idx); im=Image.new('L',(150,50),255); dr=ImageDraw.Draw(im); dr.text((4,2),'2479',0,font=f); row.append(np.array(im))
    while len(row)<12: row.append(np.full((50,150),255,np.uint8))
    rows.append(np.hstack(row))
Image.fromarray(np.vstack(rows)).save('fonts_peek.png')
