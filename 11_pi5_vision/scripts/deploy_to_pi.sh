#!/usr/bin/env bash
# deploy_to_pi.sh — รันบนโน้ตบุ๊ก: ส่งโฟลเดอร์ 11_pi5_vision/ ไปที่ ~/mrc บน Pi แล้ว (ถ้าขอ) รัน setup
#   bash scripts/deploy_to_pi.sh                 # rsync อย่างเดียว
#   bash scripts/deploy_to_pi.sh --setup         # rsync + setup_pi.sh base
#   bash scripts/deploy_to_pi.sh --status        # rsync + setup_pi.sh status
# ตั้ง PI=user@ip เพื่อเปลี่ยนปลายทาง (default ด้านล่าง)
set -euo pipefail
PI="${PI:-uchida@10.137.154.184}"
SRC="$(cd "$(dirname "$0")/.." && pwd)/"
rsync -az --delete \
    --exclude '.venv' --exclude 'data/' --exclude '__pycache__' --exclude '*.pyc' --exclude 'debug/' \
    "$SRC" "$PI:~/mrc/"
echo "rsync → $PI:~/mrc  เสร็จ"
case "${1:-}" in
    --setup)  ssh -t "$PI" 'bash ~/mrc/scripts/setup_pi.sh base' ;;
    --status) ssh    "$PI" 'bash ~/mrc/scripts/setup_pi.sh status' ;;
esac
