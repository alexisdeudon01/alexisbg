#!/bin/bash
# ============================================================
#  init-iptables.sh — Applique les règles NAT/forwarding
#  Exécuté comme container oneshot au démarrage de la stack
# ============================================================
set -e

echo "[*] Activation IP forwarding..."
echo 1 > /proc/sys/net/ipv4/ip_forward

echo "[*] Configuration iptables-nft (NAT wlan1 → eth0)..."

# FORWARD: wlan1 (fake AP) <-> eth0 (internet)
iptables -C FORWARD -i wlan1 -o eth0 -j ACCEPT 2>/dev/null || \
    iptables -I FORWARD 1 -i wlan1 -o eth0 -j ACCEPT
iptables -C FORWARD -i eth0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
    iptables -I FORWARD 2 -i eth0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT

# NAT: masquerade le trafic du fake AP vers internet
iptables -t nat -C POSTROUTING -o eth0 -s 10.0.0.0/8 -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -o eth0 -s 10.0.0.0/8 -j MASQUERADE

# SSH toujours accessible sur eth0
iptables -C INPUT -i eth0 -p tcp --dport 22 -j ACCEPT 2>/dev/null || \
    iptables -I INPUT 1 -i eth0 -p tcp --dport 22 -j ACCEPT

# Protéger wlan0 (ne pas se connecter au fake AP)
nmcli device disconnect wlan0 2>/dev/null || true
nmcli device set wlan0 autoconnect no 2>/dev/null || true

echo "[+] iptables + forwarding OK"
