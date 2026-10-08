"""เทรน CNN จิ๋วจำแนกช่องตัวเลข (0–9, ว่าง) จาก ink_map 40×40 → export ONNX ให้ cv2.dnn บน Pi"""
import time, sys
import numpy as np, torch, torch.nn as nn

dev = 'mps' if torch.backends.mps.is_available() else 'cpu'
torch.manual_seed(0)
NC = int(sys.argv[2]) if len(sys.argv) > 2 else 11     # 11 = ตัวอ่าน (digitnet) · 12 = ตัวคัดกรอง มีคลาส "ไม่ใช่ตัวเลข" (digitcheck)


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        def blk(i, o):
            return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(),
                                 nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(), nn.MaxPool2d(2))
        self.f = nn.Sequential(blk(1, 16), blk(16, 32), blk(32, 64))           # 40→20→10→5
        self.h = nn.Sequential(nn.Flatten(), nn.Dropout(0.3), nn.Linear(64 * 5 * 5, 128), nn.ReLU(), nn.Linear(128, NC))

    def forward(self, x):
        return self.h(self.f(x))


def load(p):
    d = np.load(p)
    return torch.from_numpy(d['X'])[:, None], torch.from_numpy(d['y'])


if __name__ == '__main__':
    Xtr, ytr = load('train.npz'); Xva, yva = load('val.npz')
    net = Net().to(dev)
    print('params', sum(p.numel() for p in net.parameters()), 'device', dev)
    EP = int(sys.argv[1]) if len(sys.argv) > 1 else 18
    opt = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=EP * (len(Xtr) // 256 + 1))
    lossf = nn.CrossEntropyLoss(label_smoothing=0.05)
    Xva_d, yva_d = Xva.to(dev), yva.to(dev)
    for ep in range(EP):
        t = time.time(); net.train(); perm = torch.randperm(len(Xtr)); tl = 0
        for i in range(0, len(Xtr), 256):
            idx = perm[i:i + 256]
            x = Xtr[idx].to(dev); y = ytr[idx].to(dev)
            if torch.rand(1).item() < 0.5:                      # augment เบาๆ: ความเข้มหมึก
                x = (x * (0.7 + 0.6 * torch.rand(len(x), 1, 1, 1, device=dev))).clamp(0, 1)
            opt.zero_grad(); l = lossf(net(x), y); l.backward(); opt.step(); sched.step(); tl += l.item() * len(idx)
        net.eval()
        with torch.no_grad():
            pr = torch.cat([net(Xva_d[i:i + 2048]).argmax(1) for i in range(0, len(Xva_d), 2048)])
        acc = (pr == yva_d).float().mean().item()
        print(f'ep {ep + 1:2d} loss {tl / len(Xtr):.3f} val acc {acc * 100:.2f}% · {time.time() - t:.1f} s', flush=True)
    net.cpu().eval()
    torch.save(net.state_dict(), 'digitnet.pt')
    torch.onnx.export(net, torch.zeros(1, 1, 40, 40), 'digitnet.onnx', input_names=['x'], output_names=['logits'],
                      dynamic_axes={'x': {0: 'n'}, 'logits': {0: 'n'}}, opset_version=13, dynamo=False)
    with torch.no_grad():
        pr = torch.cat([net(Xva[i:i + 2048]).argmax(1) for i in range(0, len(Xva), 2048)])
    cm = np.zeros((NC, NC), int)
    for a, b in zip(yva.numpy(), pr.numpy()):
        cm[a, b] += 1
    print('confusion (rows=true 0..9,_,x):'); print(cm)
