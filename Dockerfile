FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV QT_QPA_PLATFORM=offscreen

# Installation des dépendances via APT (Python système unique, pas de conflit)
RUN apt-get update && apt-get install -y \
    build-essential python3 python3-pip python3-setuptools python3-dev \
    git hostapd dnsmasq iptables wireless-tools net-tools rfkill \
    python3-pyqt5 python3-sip python3-openssl python3-scapy \
    python3-netifaces python3-requests python3-psutil \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
# URL corrigée sans espace
RUN git clone https://github.com/P0cL4bs/wifipumpkin3.git /opt/wifipumpkin3

WORKDIR /opt/wifipumpkin3
# Installation avec le Python système (pas de conflit setuptools)
RUN pip3 install . --break-system-packages --no-deps

WORKDIR /app
ENTRYPOINT ["wifipumpkin3", "--cli"]
