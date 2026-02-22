FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV QT_QPA_PLATFORM=offscreen
ENV PYTHONPATH=/usr/lib/python3/dist-packages

# Installation des dépendances via APT avec les bons noms (python3-openssl)
RUN apt-get update && apt-get install -y \
    build-essential \
    git hostapd dnsmasq iptables wireless-tools net-tools rfkill \
    python3-pyqt5 python3-sip python3-openssl python3-scapy \
    python3-netifaces python3-requests python3-psutil \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
# URL corrigée sans espace
RUN git clone https://github.com/P0cL4bs/wifipumpkin3.git /opt/wifipumpkin3

WORKDIR /opt/wifipumpkin3
# Installation sans re-télécharger PyQt5 (déjà installé via apt)
RUN pip3 install . --break-system-packages --no-deps

WORKDIR /app
ENTRYPOINT ["wifipumpkin3", "--cli"]
