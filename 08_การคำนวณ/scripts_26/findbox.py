import glob,cv2,numpy as np,json
fs=sorted(glob.glob('pi/images/*.jpg'))
def boxes(im):
    b,g,r=[x.astype(int) for x in cv2.split(im)]
    m=((r>165)&(r-g>22)&(b-r<45)).astype(np.uint8)*255
    m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    cs,hier=cv2.findContours(m,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    holes=[]
    if hier is None: return []
    for c,hh in zip(cs,hier[0]):
        if hh[3]<0: continue
        a=cv2.contourArea(c)
        if a<600: continue
        ap=cv2.approxPolyDP(c,0.06*cv2.arcLength(c,True),True)
        x,y,w,h=cv2.boundingRect(c)
        if len(ap)==4 and 0.5<w/h<2.2: holes.append((x,a,ap.reshape(4,2).tolist()))
    holes.sort(key=lambda t:t[0])
    # keep a run of 4 similar-area holes
    if len(holes)>=4:
        best=None
        for k in range(len(holes)-3):
            g4=holes[k:k+4]; ar=[t[1] for t in g4]
            sc=max(ar)/min(ar)
            if best is None or sc<best[0]: best=(sc,g4)
        if best[0]<2.5: return [t[2] for t in best[1]]
    return []
if __name__=='__main__':
    out={}
    for i in range(12,24):
        if i==17: continue
        q=boxes(cv2.imread(fs[i])); print(i,len(q)); 
        if q: out[fs[i]]=q
    json.dump(out,open('boxes.json','w'))
