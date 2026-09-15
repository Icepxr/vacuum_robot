#!/usr/bin/env bash
# start_web.sh — รันบน Pi: (รี)สตาร์ทแอปควบคุมเบื้องหลัง · log ที่ ~/mrc/logs/web.log
#   bash ~/mrc/scripts/start_web.sh            # กล้อง USB index 0 + /dev/ttyAMA0
#   bash ~/mrc/scripts/start_web.sh --image    # ไม่มีกล้อง: ใช้รูปล่าสุดใน data/images แทน
#   bash ~/mrc/scripts/start_web.sh --stop
# หมายเหตุ: ใช้ pgrep กับ path ของสคริปต์ python ไม่ใช่ pkill -f ชื่อสั้นๆ — ไม่งั้นฆ่า ssh session ที่พิมพ์คำสั่งเอง
set -u
cd "$(dirname "$0")/.."
mkdir -p logs
for p in $(pgrep -f "src/capture_daemon.py"; pgrep -f "src/mrc_web.py"); do kill "$p" 2>/dev/null; done
sleep 3
# ถ้ายังอยู่ (เช่น uvicorn รุ่นเก่ารอ stream ปิด) ยิงแรง — สองตัวถือ /dev/ttyAMA0 พร้อมกันไม่ได้
for p in $(pgrep -f "src/capture_daemon.py"; pgrep -f "src/mrc_web.py"); do kill -9 "$p" 2>/dev/null && echo "kill -9 $p (ไม่ยอมตายใน 3 s)"; done
sleep 0.5
if pgrep -f "src/mrc_web.py|src/capture_daemon.py" >/dev/null; then echo "ยังมี process เก่าอยู่ — หยุด"; exit 1; fi
[[ "${1:-}" == "--stop" ]] && { echo "หยุดแล้ว"; exit 0; }
ARGS=(--serial /dev/ttyAMA0 --camera 0 --port 8000)
if [[ "${1:-}" == "--image" ]]; then
    IMG=$(ls -t data/images/*.jpg 2>/dev/null | head -1)
    [[ -z "$IMG" ]] && { echo "ไม่มีรูปใน data/images ให้ใช้แทนกล้อง"; exit 1; }
    ARGS+=(--image "$IMG"); echo "โหมดไม่มีกล้อง: ใช้ $IMG"
fi
setsid nohup .venv/bin/python src/mrc_web.py "${ARGS[@]}" > logs/web.log 2>&1 < /dev/null &
sleep 4
if pgrep -f "src/mrc_web.py" >/dev/null; then
    echo "รันอยู่ · http://$(hostname -I | awk '{print $1}'):8000"; grep -E "ฟัง|เว็บ|Error|error" logs/web.log | tail -3
else
    echo "ไม่ขึ้น — ดู logs/web.log:"; tail -20 logs/web.log; exit 1
fi
