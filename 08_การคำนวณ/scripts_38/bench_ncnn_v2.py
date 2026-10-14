"""เวลา NCNN บน Pi 5: counter (seg · 1280) + digit (640) จาก weights/ ชุด 13 ต.ค. — ใช้ ncnn ตรง ไม่ต้องมี ultralytics
python bench_ncnn_v2.py <weights_dir> <รูป.jpg> [threads]"""
import ncnn, cv2, numpy as np, time, sys, os
D, IMG = sys.argv[1], sys.argv[2]; TH = int(sys.argv[3]) if len(sys.argv) > 3 else 4

def load(p):
    n = ncnn.Net(); n.opt.num_threads = TH; n.load_param(p + '/model.ncnn.param'); n.load_model(p + '/model.ncnn.bin'); return n

def letterbox(im, S):
    h, w = im.shape[:2]; r = S / max(h, w); nh, nw = int(round(h * r)), int(round(w * r))
    out = np.full((S, S, 3), 114, np.uint8); top, left = (S - nh) // 2, (S - nw) // 2
    out[top:top + nh, left:left + nw] = cv2.resize(im, (nw, nh)); return out, r, left, top

def infer(net, im, S, nc, conf=0.25):
    lb, r, l, t = letterbox(im, S); x = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB).transpose(2, 0, 1).astype(np.float32) / 255.
    ex = net.create_extractor(); ex.input('in0', ncnn.Mat(np.ascontiguousarray(x)))
    _, o = ex.extract('out0'); o = np.array(o)          # (4+nc[+32 mask], N)
    sc = o[4:4 + nc].max(0); cl = o[4:4 + nc].argmax(0); k = sc > conf
    b = o[:4, k].T; b = np.c_[b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2, b[:, 2], b[:, 3]]
    idx = cv2.dnn.NMSBoxes(b.tolist(), sc[k].tolist(), conf, 0.45); idx = np.array(idx).ravel() if len(idx) else []
    return [((b[i, 0] - l) / r, (b[i, 1] - t) / r, b[i, 2] / r, b[i, 3] / r, round(float(sc[k][i]), 2), int(cl[k][i])) for i in idx]

im = cv2.imread(IMG); cn = load(D + '/counter_ncnn_model'); dg = load(D + '/digit_ncnn_model')
for _ in range(2): infer(cn, im, 1280, 2); infer(dg, im, 640, 10)
N = 10; t = time.perf_counter()
for _ in range(N): rc = infer(cn, im, 1280, 2)
tc = (time.perf_counter() - t) / N * 1000
crop = im
if rc:
    x, y, w, h = max(rc, key=lambda d: d[4])[:4]; crop = im[max(int(y - .1 * h), 0):int(y + 1.1 * h), max(int(x - .1 * w), 0):int(x + 1.1 * w)]
t = time.perf_counter()
for _ in range(N): rd = infer(dg, crop, 640, 10)
td = (time.perf_counter() - t) / N * 1000
print(f'{os.uname().nodename} threads={TH}: counter@1280 {tc:.0f} ms · digit@640 {td:.0f} ms · รวม {tc + td:.0f} ms')
print('counter:', [(d[4], ['water', 'elec'][d[5]]) for d in rc], '· digit:', ''.join(str(d[5]) for d in sorted(rd)))
