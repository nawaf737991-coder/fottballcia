#!/usr/bin/env bash
# تثبيت سيرفر Fottballcia على Ubuntu/Debian (شغّله كـ root)
set -e
[ "$(id -u)" = 0 ] || { echo "شغّل الأمر كمستخدم root"; exit 1; }
REPO_RAW="https://raw.githubusercontent.com/nawaf737991-coder/fottballcia/main/server"

apt-get update -y
apt-get install -y python3 curl caddy

mkdir -p /opt/fottballcia /var/lib/fottballcia
curl -fsSL "$REPO_RAW/site_server.py" -o /opt/fottballcia/site_server.py
curl -fsSL "$REPO_RAW/match_center.py" -o /opt/fottballcia/match_center.py

read -rsp "الصق مفتاح API-Football (ما يظهر وانت تكتب) ثم Enter: " KEY </dev/tty
echo
[ -n "$KEY" ] || { echo "ما أدخلت مفتاح"; exit 1; }
(umask 077; printf 'API_FOOTBALL_KEY=%s\nLIVE_INTERVAL=30\n' "$KEY" > /etc/fottballcia.env)

cat > /etc/systemd/system/fottballcia.service <<UNIT
[Unit]
Description=Fottballcia live server
After=network-online.target
[Service]
EnvironmentFile=/etc/fottballcia.env
ExecStart=/usr/bin/python3 /opt/fottballcia/site_server.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT

IP=$(curl -4fsS https://api.ipify.org)
HOST="$(echo "$IP" | tr . -).sslip.io"
cat > /etc/caddy/Caddyfile <<CADDY
$HOST {
    reverse_proxy 127.0.0.1:8080
}
CADDY

systemctl daemon-reload
systemctl enable --now fottballcia
systemctl restart caddy
sleep 8
echo
echo "تم. رابط السيرفر (انسخه وأرسله لي):"
echo "https://$HOST"
echo "تجربة: https://$HOST/today.json"
