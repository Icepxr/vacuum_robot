import ncnn,cv2,numpy as np,time,sys,os
D=sys.argv[1]; img=sys.argv[2]
def load(p):
    n=ncnn.Net(); n.opt.num_threads=4; n.load_param(p+'/model.ncnn.param'); n.load_model(p+'/model.ncnn.bin'); return n
def letterbox(im,S=640):
    h,w=im.shape[:2]; r=S/max(h,w); nh,nw=int(round(h*r)),int(round(w*r))
    out=np.full((S,S,3),114,np.uint8); top,left=(S-nh)//2,(S-nw)//2
    out[top:top+nh,left:left+nw]=cv2.resize(im,(nw,nh)); return out,r,left,top
def infer(net,im,conf=0.25):
    lb,r,l,t=letterbox(im); x=cv2.cvtColor(lb,cv2.COLOR_BGR2RGB).transpose(2,0,1).astype(np.float32)/255.
    ex=net.create_extractor(); ex.input('in0',ncnn.Mat(np.ascontiguousarray(x)))
    _,o=ex.extract('out0'); o=np.array(o)          # (4+nc, 8400)
    sc=o[4:].max(0); cl=o[4:].argmax(0); k=sc>conf
    b=o[:4,k].T; b=np.c_[b[:,0]-b[:,2]/2,b[:,1]-b[:,3]/2,b[:,2],b[:,3]]
    idx=cv2.dnn.NMSBoxes(b.tolist(),sc[k].tolist(),conf,0.45)
    idx=np.array(idx).ravel() if len(idx) else []
    return [((b[i,0]-l)/r,(b[i,1]-t)/r,b[i,2]/r,b[i,3]/r,float(sc[k][i]),int(cl[k][i])) for i in idx]
im=cv2.imread(img); cn=load(D+'/counter_ncnn'); dg=load(D+'/digit_ncnn')
for _ in range(3): infer(cn,im); infer(dg,im)
N=20; t=time.perf_counter()
for _ in range(N): infer(cn,im)
tc=(time.perf_counter()-t)/N*1000; t=time.perf_counter()
for _ in range(N): r=infer(dg,im)
td=(time.perf_counter()-t)/N*1000
print(f'{os.uname().nodename}: counter {tc:.0f} ms/frame · digit {td:.0f} ms/frame · total {tc+td:.0f} ms (4 threads, 640x640)')
print('digit dets on this image:',''.join(str(d[5]) for d in sorted(r)), [round(d[4],2) for d in sorted(r)])
