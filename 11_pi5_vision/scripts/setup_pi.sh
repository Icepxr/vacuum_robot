#!/usr/bin/env bash
# setup_pi.sh — เตรียม Raspberry Pi 5 ให้พร้อมสำหรับ MRC-001
# อ้างอิง: 01_เอกสารโครงการ/software_architecture.md §2.6, §3 · system_architecture.md §3.7
#
# ใช้:  bash setup_pi.sh base      # apt + venv + UART0 + dialout  (รันซ้ำได้ ไม่พังของเดิม)
#       bash setup_pi.sh hotspot   # สร้างโปรไฟล์ hotspot MRC-001 (ยัง "ไม่" เปิดใช้ทันที)
#       bash setup_pi.sh hostname  # ตั้งชื่อเครื่องเป็น mrc → http://mrc.local
#       bash setup_pi.sh status    # ตรวจว่าอะไรพร้อม/ไม่พร้อม ไม่แก้อะไร
#
# ⚠ รองรับทั้ง Raspberry Pi OS Bookworm และ Ubuntu 24.04 — แต่บน Ubuntu ไม่มี picamera2 (ดู C22 ในไฟล์ 10)
# ⚠ ขั้น base แก้ /boot/firmware/config.txt และ cmdline.txt → ต้อง reboot ถึงจะได้ /dev/ttyAMA0
# ⚠ ขั้น hotspot: ถ้า Pi ต่อ LAN ผ่าน Wi-Fi อยู่ การ "เปิด" hotspot จะตัด SSH ทันที
#    สคริปต์นี้จึงแค่สร้างโปรไฟล์ (autoconnect=no) แล้วให้เปิดเองด้วย  sudo nmcli con up MRC-001
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

MRC_HOME="${MRC_HOME:-$HOME/mrc}"          # โค้ดจาก 11_pi5_vision/ ถูก rsync มาไว้ที่นี่
VENV="$MRC_HOME/.venv"
BOOT=/boot/firmware
HOTSPOT_SSID="${HOTSPOT_SSID:-MRC-001}"
HOTSPOT_PASS="${HOTSPOT_PASS:-}"           # ต้องตั้งเองตอนเรียก: HOTSPOT_PASS=xxxx bash setup_pi.sh hotspot

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
bad()  { printf '  \033[1;31m✗\033[0m %s\n' "$*"; }
warn() { printf '  \033[1;33m!\033[0m %s\n' "$*"; }

is_ubuntu() { . /etc/os-release; [[ "$ID" == "ubuntu" ]]; }
cpu_temp() {
    if command -v vcgencmd >/dev/null && [[ -w /dev/vcio ]]; then vcgencmd measure_temp
    else awk '{printf "temp=%.1f\x27C (sysfs)\n",$1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo n/a; fi
}

need_pi5() {
    local model; model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)
    if [[ "$model" != *"Raspberry Pi 5"* ]]; then
        warn "เครื่องนี้ไม่ใช่ Pi 5 ($model) — ชื่อพอร์ต UART อาจไม่ใช่ /dev/ttyAMA0"
    else
        ok "$model"
    fi
}

# ---------------------------------------------------------------- base
do_base() {
    log "ตรวจรุ่นบอร์ดและ OS"
    need_pi5
    . /etc/os-release; ok "$PRETTY_NAME"
    local pyv; pyv=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
    if [[ "$pyv" != "3.11" && "$pyv" != "3.12" ]]; then
        bad "python3 เป็น $pyv — requirements.txt ล็อกไว้กับ 3.11/3.12 (numpy 1.26 / opencv 4.10 ไม่มี wheel cp313)"
        exit 1
    fi
    ok "python3 $pyv"

    log "apt: แพ็กเกจระบบ (picamera2 ต้องมาจาก apt เท่านั้น)"
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3-venv python3-pip python3-dev build-essential git rsync \
        tesseract-ocr \
        iperf3 \
        avahi-daemon v4l-utils
    if is_ubuntu; then
        # C22 (ไฟล์ 10): Ubuntu ไม่มี python3-picamera2/rpicam-apps และ libcamera ของ Ubuntu ไม่มี PiSP
        # → บน Ubuntu ใช้ได้เฉพาะกล้อง USB ผ่าน OpenCV/V4L2 · ถ้าต้องการ CSI ให้ flash Raspberry Pi OS
        warn "Ubuntu: ข้าม python3-picamera2/rpicam-apps (ไม่มีใน apt) — กล้อง CSI ใช้ไม่ได้บน OS นี้ ดู C22"
    else
        sudo apt-get install -y -qq python3-picamera2 rpicam-apps
    fi
    # ssocr สำหรับจอ 7-segment — ยังไม่รู้ชนิดมิเตอร์ (README ตาราง) ลงเผื่อไว้ เล็กมาก
    sudo apt-get install -y -qq ssocr || warn "ssocr ไม่มีใน repo นี้ — ค่อยลงทีหลังถ้ามิเตอร์เป็น 7-segment"

    log "VS Code (ผู้ใช้ขอ 11 ก.ย.) — apt repo ของ Microsoft (snap 'code' ไม่มี build arm64 — ลองแล้ว 11 ก.ย.)"
    if command -v code >/dev/null; then
        ok "code มีอยู่แล้ว: $(code --version 2>/dev/null | head -1)"
    else
        sudo apt-get install -y -qq wget gpg
        wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | sudo tee /usr/share/keyrings/packages.microsoft.gpg >/dev/null
        echo "deb [arch=arm64 signed-by=/usr/share/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" | sudo tee /etc/apt/sources.list.d/vscode.list >/dev/null
        sudo apt-get update -qq && sudo apt-get install -y -qq code && ok "apt install code"
    fi

    log "venv แบบ --system-site-packages ที่ $VENV (ให้ import picamera2 จาก apt เจอ)"
    mkdir -p "$MRC_HOME"
    if [[ ! -x "$VENV/bin/python" ]]; then
        python3 -m venv --system-site-packages "$VENV"
    fi
    "$VENV/bin/pip" install -q --upgrade pip
    if [[ -f "$MRC_HOME/requirements.txt" ]]; then
        "$VENV/bin/pip" install -q -r "$MRC_HOME/requirements.txt"
        ok "pip install -r requirements.txt"
    else
        warn "ยังไม่มี $MRC_HOME/requirements.txt — rsync โค้ดมาก่อนแล้วรัน base ซ้ำ"
    fi

    log "UART0 บน GPIO14/15 → /dev/ttyAMA0 (system_architecture.md §3.7 ข้อ 1)"
    sudo cp -n "$BOOT/config.txt"  "$BOOT/config.txt.bak-mrc"  2>/dev/null || true
    sudo cp -n "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.bak-mrc" 2>/dev/null || true
    if ! grep -qE '^\s*enable_uart=1' "$BOOT/config.txt"; then
        printf '\n# MRC-001: UART0 ไป ESP32-S3 (GPIO14 TX / GPIO15 RX)\nenable_uart=1\ndtparam=uart0=on\n' | sudo tee -a "$BOOT/config.txt" >/dev/null
        ok "เพิ่ม enable_uart=1 + dtparam=uart0=on"
    else
        ok "enable_uart=1 มีอยู่แล้ว"
    fi
    if grep -qE 'console=(serial0|ttyAMA0|ttyS0),[0-9]+' "$BOOT/cmdline.txt"; then
        sudo sed -i -E 's/console=(serial0|ttyAMA0|ttyS0),[0-9]+ ?//' "$BOOT/cmdline.txt"
        ok "ลบ console=serial0,115200 ออกจาก cmdline.txt (ไม่งั้น Linux ยิง log ใส่ ESP32)"
    else
        ok "cmdline.txt ไม่มี serial console อยู่แล้ว"
    fi
    for svc in serial-getty@ttyAMA0.service serial-getty@serial0.service; do
        if systemctl is-enabled "$svc" &>/dev/null; then
            sudo systemctl disable --now "$svc" && ok "ปิด $svc"
        fi
    done
    # raspi-config มี flag สำหรับเรื่องเดียวกัน ใช้ซ้ำเพื่อความชัวร์ (0 = enable)
    if command -v raspi-config >/dev/null; then
        sudo raspi-config nonint do_serial_cons 1 || true   # 1 = ปิด console บน serial
        sudo raspi-config nonint do_serial_hw   0 || true   # 0 = เปิด hardware UART
    fi

    log "สิทธิ์พอร์ต serial + กล้อง"
    sudo usermod -aG dialout,video "$USER"
    ok "เพิ่ม $USER เข้า dialout,video (มีผลหลัง login ใหม่)"

    log "โฟลเดอร์ข้อมูล"
    mkdir -p "$MRC_HOME/data/images" "$MRC_HOME/data/runs"
    ok "$MRC_HOME/data/{images,runs}"

    echo
    warn "ต้อง sudo reboot หนึ่งครั้ง แล้วรัน  bash setup_pi.sh status  เพื่อยืนยันว่า /dev/ttyAMA0 โผล่"
}

# ---------------------------------------------------------------- hotspot
do_hotspot() {
    if [[ -z "$HOTSPOT_PASS" ]]; then
        bad "ต้องตั้ง HOTSPOT_PASS (≥ 8 ตัวอักษร WPA2) เช่น  HOTSPOT_PASS=mrc12345 bash setup_pi.sh hotspot"
        exit 1
    fi
    if (( ${#HOTSPOT_PASS} < 8 )); then bad "WPA2 ต้องยาว ≥ 8 ตัวอักษร"; exit 1; fi
    log "สร้างโปรไฟล์ hotspot '$HOTSPOT_SSID' บน wlan0 (autoconnect=no · IP 10.42.0.1 ตาม NetworkManager default)"
    if nmcli -t -f NAME con show | grep -qx "$HOTSPOT_SSID"; then
        warn "โปรไฟล์ $HOTSPOT_SSID มีอยู่แล้ว — ลบก่อนถ้าจะเปลี่ยนรหัส: sudo nmcli con delete $HOTSPOT_SSID"
    else
        sudo nmcli con add type wifi ifname wlan0 con-name "$HOTSPOT_SSID" autoconnect no \
            ssid "$HOTSPOT_SSID" mode ap ipv4.method shared ipv6.method disabled \
            wifi.band bg wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$HOTSPOT_PASS" \
            wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp
        ok "สร้างแล้ว"
    fi
    echo
    warn "เปิดใช้:  sudo nmcli con up $HOTSPOT_SSID     (ถ้า SSH มาทาง Wi-Fi จะหลุดทันที — ให้ทำผ่าน Ethernet/จอ)"
    warn "ปิด:      sudo nmcli con down $HOTSPOT_SSID"
    warn "ให้เปิดเองตอนบูต (โหมดสนาม):  sudo nmcli con mod $HOTSPOT_SSID autoconnect yes connection.autoconnect-priority 100"
}

# ---------------------------------------------------------------- hostname
do_hostname() {
    local name="${1:-mrc}"
    log "ตั้ง hostname = $name → เข้าเว็บที่ http://$name.local"
    sudo hostnamectl set-hostname "$name"
    sudo sed -i -E "s/^127\.0\.1\.1\s+.*/127.0.1.1\t$name/" /etc/hosts
    grep -q '127.0.1.1' /etc/hosts || echo -e "127.0.1.1\t$name" | sudo tee -a /etc/hosts >/dev/null
    sudo systemctl enable --now avahi-daemon
    ok "เสร็จ — มีผลเต็มที่หลัง reboot"
}

# ---------------------------------------------------------------- status
do_status() {
    log "สถานะ Pi"
    need_pi5
    . /etc/os-release; ok "$PRETTY_NAME · kernel $(uname -r)"
    ok "python3 $(python3 -V 2>&1 | cut -d' ' -f2) · hostname $(hostname)"
    ok "อุณหภูมิ CPU: $(cpu_temp) · throttled: $( { command -v vcgencmd >/dev/null && [[ -w /dev/vcio ]] && vcgencmd get_throttled; } 2>/dev/null || echo n/a)"
    ok "SD ว่าง: $(df -h / | awk 'NR==2{print $4" / "$2}')"
    ok "RAM: $(free -h | awk '/Mem/{print $7" ว่าง / "$2}')"

    log "UART0 (§3.7)"
    [[ -e /dev/ttyAMA0 ]] && ok "/dev/ttyAMA0 มี" || bad "/dev/ttyAMA0 ไม่มี — ยังไม่ reboot หลัง base? หรือ config.txt ไม่ถูก"
    grep -qE '^\s*enable_uart=1' $BOOT/config.txt && ok "config.txt: enable_uart=1" || bad "config.txt ไม่มี enable_uart=1"
    grep -qE 'console=(serial0|ttyAMA0)' $BOOT/cmdline.txt && bad "cmdline.txt ยังมี serial console!" || ok "cmdline.txt ไม่มี serial console"
    id -nG | grep -qw dialout && ok "$USER อยู่ใน dialout" || bad "$USER ไม่อยู่ใน dialout (login ใหม่หรือยัง?)"

    log "กล้อง"
    if command -v rpicam-hello >/dev/null; then
        if rpicam-hello --list-cameras 2>/dev/null | grep -q ':'; then
            rpicam-hello --list-cameras 2>/dev/null | sed 's/^/  /'
        else
            warn "rpicam-hello ไม่เห็นกล้อง CSI — ยังไม่ต่อกล้อง? (ยังไม่เลือกรุ่น ไม่อยู่ใน BOM)"
        fi
    elif is_ubuntu; then
        warn "Ubuntu: ไม่มี rpicam-apps · ตรวจได้เฉพาะกล้อง USB (V4L2) ด้านล่าง — ดู C22"
    else
        bad "ไม่มี rpicam-apps"
    fi
    if command -v v4l2-ctl >/dev/null; then
        v4l2-ctl --list-devices 2>/dev/null | grep -B1 -A2 -iE "usb|uvc" | sed 's/^/  /' || warn "ไม่พบกล้อง USB (UVC)"
    else
        ls /dev/video* 2>/dev/null | head -3 | sed 's/^/  video node: /' || true
    fi

    log "Python venv + ไลบรารี"
    if [[ -x "$VENV/bin/python" ]]; then
        "$VENV/bin/python" - <<'PY' 2>&1 | sed 's/^/  /'
import importlib
for m in ("numpy","cv2","pytesseract","requests","picamera2","serial","fastapi","uvicorn"):
    try:
        mod = importlib.import_module(m)
        print(f"✓ {m:12s} {getattr(mod,'__version__','')}")
    except Exception as e:
        print(f"✗ {m:12s} {type(e).__name__}: {e}")
PY
    else
        bad "ยังไม่มี venv ที่ $VENV"
    fi
    command -v code >/dev/null && ok "VS Code $(code --version 2>/dev/null | head -1)" || warn "ยังไม่มี VS Code"
    command -v tesseract >/dev/null && ok "tesseract $(tesseract --version 2>&1 | head -1 | cut -d' ' -f2)" || bad "ไม่มี tesseract"
    command -v ssocr >/dev/null && ok "ssocr มี" || warn "ไม่มี ssocr (ต้องมีเฉพาะมิเตอร์ 7-segment)"

    log "เครือข่าย"
    nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev 2>/dev/null | sed 's/^/  /' || true
    nmcli -t -f NAME con show 2>/dev/null | grep -qx "$HOTSPOT_SSID" && ok "โปรไฟล์ hotspot $HOTSPOT_SSID มี" || warn "ยังไม่มีโปรไฟล์ hotspot (bash setup_pi.sh hotspot)"
}

case "${1:-}" in
    base)     do_base ;;
    hotspot)  do_hotspot ;;
    hostname) do_hostname "${2:-mrc}" ;;
    status)   do_status ;;
    *) sed -n '2,12p' "$0"; exit 1 ;;
esac

# I2C (ENS160/AHT21 · ไฟล์ 21): i2c-tools ทำให้ /dev/i2c-1 เป็น group i2c → ผู้ใช้ต้องอยู่ในกลุ่ม ไม่งั้น service อ่านไม่ได้ (19 ก.ย.)
# sudo apt-get install -y i2c-tools && sudo usermod -aG i2c "$USER"
