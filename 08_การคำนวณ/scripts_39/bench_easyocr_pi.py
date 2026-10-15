"""เวลา EasyOCR บน Pi 5 (ไฟล์ 39 ข้อ 2) — อ่านแถบที่ textreader_meter ดัดตรงแล้ว แบบเดียวกับ E3 (allowlist ตัวเลข)
รันด้วย ~/mrc-models/venv-ocr: python bench_easyocr_pi.py <easyocr_dir> <รูป...>"""
import sys, time, statistics
sys.path.insert(0, "/home/uchida/mrc/src")
import cv2
import textreader_meter as T
t = time.perf_counter()
import easyocr
r = easyocr.Reader(["en"], gpu=False, verbose=False, model_storage_directory=sys.argv[1], download_enabled=False)
print(f"โหลด EasyOCR {time.perf_counter() - t:.1f} s")
ts = []
for f in sys.argv[2:]:
    im = cv2.imread(f); body = T.find_body(im)
    if body is None: continue
    cnt = T.find_strip(im, body)
    if cnt is None: continue
    strip = T.warp_quad(im, T.strip_quad(cnt))
    t = time.perf_counter(); out = r.readtext(strip, allowlist="0123456789", detail=1, paragraph=False); dt = (time.perf_counter() - t) * 1000
    ts.append(dt); out.sort(key=lambda z: z[0][0][0])
    print(f'{f.split("/")[-1][:15]} {"".join(z[1] for z in out):6s} {dt:.0f} ms')
if ts:
    print(f"EasyOCR ต่อแถบ: median {statistics.median(ts[1:] or ts):.0f} ms · ครั้งแรก {ts[0]:.0f} ms · n={len(ts)}")
