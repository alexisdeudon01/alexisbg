FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System tools for network monitoring (iw, arp, ip, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    iw wireless-tools net-tools iproute2 procps \
    libpcap-dev tcpdump \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# DB stored on mounted volume
ENV DB_PATH=/data/network.db

EXPOSE 80

CMD ["python3", "main.py"]
