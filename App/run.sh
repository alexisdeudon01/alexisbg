#!/bin/bash
# ============================================================
#  run.sh — Lance le CIA Network Monitor sur port 80
# ============================================================
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "[*] CIA Network Monitor — Démarrage"

# Install dependencies if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "[*] Installation des dépendances Python..."
    pip3 install --break-system-packages -r requirements.txt
fi

echo "[+] Dépendances OK"
echo "[*] Lancement sur http://0.0.0.0:80"
echo "[*] Accessible depuis le réseau : http://192.168.178.66"

sudo python3 main.py
