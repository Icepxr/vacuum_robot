#!/usr/bin/env bash
# deploy_to_pi.sh — รันบนโน้ตบุ๊ก: ส่งโฟลเดอร์ 11_pi5_vision/ ไปที่ ~/mrc บน Pi แล้ว (ถ้าขอ) รัน setup
#   bash scripts/deploy_to_pi.sh                 # rsync อย่างเดียว
#   bash scripts/deploy_to_pi.sh --setup         # rsync + setup_pi.sh base
#   bash scripts/deploy_to_pi.sh --status        # rsync + setup_pi.sh status
# ตั้ง PI=user@ip เพื่อเปลี่ยนปลายทาง (default ด้านล่าง)
set -euo pipefail
PI="${PI:-uchida@uchida-pi5.local}"   # 17 ก.ย.: ชื่อ mDNS บน hotspot iPhone — IP เปลี่ยนได้ อย่าฝังเลข
SRC="$(cd "$(dirname "$0")/.." && pwd)/"
# src/roi_config.json = กรอบอ่านมิเตอร์ที่ผู้ใช้ลากตั้งจากหน้าเว็บบน Pi (POST /api/roi) → ห้ามเขียนทับตอน deploy (12 ต.ค.)
#   ส่งเฉพาะตอน Pi ยังไม่มีไฟล์ (เครื่องใหม่) · --delete ไม่ลบไฟล์ที่ exclude ไว้
rsync -az --delete \
    --exclude '.venv' --exclude 'data/' --exclude 'logs/' --exclude '__pycache__' --exclude '*.pyc' --exclude 'debug/' \
    --exclude '.pytest_cache/' --exclude 'src/roi_config.json' \
    "$SRC" "$PI:~/mrc/"
rsync -az --ignore-existing "${SRC}src/roi_config.json" "$PI:~/mrc/src/roi_config.json"
echo "rsync → $PI:~/mrc  เสร็จ"
case "${1:-}" in
    --setup)  ssh -t "$PI" 'bash ~/mrc/scripts/setup_pi.sh base' ;;
    --status) ssh    "$PI" 'bash ~/mrc/scripts/setup_pi.sh status' ;;
esac
