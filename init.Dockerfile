FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    iptables iproute2 network-manager \
    && rm -rf /var/lib/apt/lists/*
COPY init-iptables.sh /init-iptables.sh
RUN chmod +x /init-iptables.sh
CMD ["/bin/bash", "/init-iptables.sh"]
