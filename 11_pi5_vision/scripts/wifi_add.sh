#!/usr/bin/env bash
# wifi_add.sh — เพิ่ม Wi-Fi ใหม่ให้ Pi (เช่น hotspot มือถือ) ให้ต่อเองอัตโนมัติ และ "ชอบ" วงนี้มากกว่า Wi-Fi อาคาร
#   รันบน Pi:  bash ~/mrc/scripts/wifi_add.sh
#   ถามชื่อ Wi-Fi + รหัส (พิมพ์เองบนจอ ไม่ต้องส่งรหัสให้ใคร) · ใช้ NetworkManager (nmcli) ของ Ubuntu
# หลังต่อได้: หา Pi ด้วย  ping uchida-pi5.local  หรือ IP ที่สคริปต์พิมพ์ · หน้าเว็บ http://uchida-pi5.local:8000/drive
set -u
read -rp "ชื่อ Wi-Fi (SSID) ของมือถือ: " SSID
read -rsp "รหัสผ่าน: " PSK; echo
[[ -z "$SSID" || ${#PSK} -lt 8 ]] && { echo "SSID ว่างหรือรหัสสั้นกว่า 8 ตัว — ยกเลิก"; exit 1; }

CON="hotspot-${SSID// /_}"
nmcli connection delete "$CON" >/dev/null 2>&1 || true
# autoconnect-priority สูงกว่า Wi-Fi อาคาร (ค่าเริ่มต้น 0) → ถ้าเห็นทั้งสองวง จะเลือกมือถือก่อน
nmcli connection add type wifi ifname wlan0 con-name "$CON" ssid "$SSID" \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" \
    connection.autoconnect yes connection.autoconnect-priority 10 \
    ipv4.method auto ipv6.method auto >/dev/null || { echo "เพิ่มไม่สำเร็จ"; exit 1; }
unset PSK
echo "เพิ่มแล้ว: $CON · กำลังต่อ… (SSH จะหลุดถ้าคุณต่ออยู่ผ่าน Wi-Fi อาคาร — ปกติ)"
nmcli connection up "$CON" 2>&1 | tail -1
sleep 3
IP=$(nmcli -g IP4.ADDRESS device show wlan0 | head -1)
echo "Pi ตอนนี้: SSID=$(nmcli -g GENERAL.CONNECTION device show wlan0) · IP=${IP:-ยังไม่ได้} · ชื่อ mDNS=$(hostname).local"
echo "$(date '+%F %T') $SSID ${IP:-none}" >> ~/mrc/logs/ip.txt 2>/dev/null || true
