"""
24/7 Packet capture service on wlan1.
Captures each flow, identifies protocol, stores in DB with protocol-specific tables.
Uses scapy for packet sniffing.
"""
import asyncio
import json
import logging
import threading
from datetime import datetime
from scapy.all import sniff, IP, TCP, UDP, DNS, DNSQR, DNSRR, Raw, Ether
from sqlalchemy import select

from database import async_session
from models import (
    Device, FlowBase, TCPFlow, UDPFlow, DNSFlow, HTTPFlow,
    ProtocolSchema
)

logger = logging.getLogger("capture")

# Packet queue: scapy runs in a thread, DB writes happen async
_packet_queue: asyncio.Queue = None
_loop = None


def _extract_http(payload_bytes: bytes) -> dict | None:
    """Try to parse HTTP from raw payload."""
    try:
        text = payload_bytes.decode("utf-8", errors="replace")
        lines = text.split("\r\n")
        if not lines:
            return None
        first = lines[0]
        # Request: GET /path HTTP/1.1
        if any(first.startswith(m) for m in ("GET ", "POST ", "PUT ", "DELETE ", "HEAD ", "OPTIONS ", "PATCH ")):
            parts = first.split(" ")
            method = parts[0]
            url = parts[1] if len(parts) > 1 else ""
            host = ""
            headers = {}
            for l in lines[1:]:
                if ":" in l:
                    k, v = l.split(":", 1)
                    headers[k.strip()] = v.strip()
                    if k.strip().lower() == "host":
                        host = v.strip()
            body_idx = text.find("\r\n\r\n")
            body = text[body_idx + 4:] if body_idx >= 0 else ""
            return {"method": method, "url": url, "host": host,
                    "headers": headers, "body": body[:2000], "status_code": None}
        # Response: HTTP/1.1 200 OK
        if first.startswith("HTTP/"):
            parts = first.split(" ")
            status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            return {"method": None, "url": None, "host": None,
                    "headers": {}, "body": "", "status_code": status}
    except Exception:
        pass
    return None


def _build_schema_signature(protocol: str, src_port: int, dst_port: int,
                            payload_len: int) -> dict:
    """Build a JSON schema signature for a flow."""
    return {
        "protocol": protocol,
        "src_port": src_port,
        "dst_port": dst_port,
        "payload_size_bucket": (payload_len // 100) * 100 if payload_len else 0,
    }


def _packet_callback(pkt):
    """Called by scapy for each captured packet. Pushes to async queue."""
    if _packet_queue is None or _loop is None:
        return
    try:
        info = _dissect(pkt)
        if info:
            asyncio.run_coroutine_threadsafe(
                _packet_queue.put(info), _loop
            )
    except Exception:
        pass


def _dissect(pkt) -> dict | None:
    """Dissect a packet into a dict for DB storage."""
    if not pkt.haslayer(IP):
        return None

    ip = pkt[IP]
    info = {
        "timestamp": datetime.utcnow(),
        "src_mac": pkt[Ether].src.lower() if pkt.haslayer(Ether) else None,
        "dst_mac": pkt[Ether].dst.lower() if pkt.haslayer(Ether) else None,
        "src_ip": ip.src,
        "dst_ip": ip.dst,
        "src_port": None,
        "dst_port": None,
        "protocol": "OTHER",
        "length": len(pkt),
        "detail_type": None,
        "detail": {},
    }

    # DNS
    if pkt.haslayer(DNS):
        info["protocol"] = "DNS"
        dns = pkt[DNS]
        query = ""
        qtype = ""
        response = ""
        if dns.qd and hasattr(dns.qd, "qname"):
            query = dns.qd.qname.decode(errors="replace").rstrip(".")
            qtype = str(dns.qd.qtype)
        if dns.an:
            answers = []
            for i in range(dns.ancount):
                try:
                    rr = dns.an[i]
                    answers.append(str(rr.rdata))
                except Exception:
                    break
            response = ", ".join(answers)
        info["detail_type"] = "dns"
        info["detail"] = {"query": query[:255], "query_type": qtype, "response": response[:500]}
        if pkt.haslayer(UDP):
            info["src_port"] = pkt[UDP].sport
            info["dst_port"] = pkt[UDP].dport
        return info

    # TCP
    if pkt.haslayer(TCP):
        tcp = pkt[TCP]
        info["src_port"] = tcp.sport
        info["dst_port"] = tcp.dport
        info["protocol"] = "TCP"

        payload = bytes(tcp.payload) if tcp.payload else b""
        payload_hex = payload[:500].hex() if payload else ""
        payload_text = payload[:500].decode("utf-8", errors="replace") if payload else ""

        # Check for HTTP
        http = _extract_http(payload) if payload else None
        if http and http["method"]:
            info["protocol"] = "HTTP"
            info["detail_type"] = "http"
            info["detail"] = http
        else:
            flags = str(tcp.flags)
            info["detail_type"] = "tcp"
            info["detail"] = {
                "flags": flags,
                "seq_num": tcp.seq,
                "ack_num": tcp.ack,
                "window": tcp.window,
                "payload_hex": payload_hex,
                "payload_text": payload_text[:1000],
            }
        return info

    # UDP
    if pkt.haslayer(UDP):
        udp = pkt[UDP]
        info["src_port"] = udp.sport
        info["dst_port"] = udp.dport
        info["protocol"] = "UDP"

        payload = bytes(udp.payload) if udp.payload else b""
        info["detail_type"] = "udp"
        info["detail"] = {
            "udp_length": udp.len,
            "payload_hex": payload[:500].hex() if payload else "",
            "payload_text": payload[:500].decode("utf-8", errors="replace") if payload else "",
        }
        return info

    return info


async def _find_or_create_schema(session, protocol: str, src_port: int,
                                  dst_port: int, length: int) -> int | None:
    """Find an existing schema or create one."""
    sig = _build_schema_signature(protocol, src_port or 0, dst_port or 0, length or 0)
    result = await session.execute(
        select(ProtocolSchema).where(
            ProtocolSchema.protocol == protocol,
            ProtocolSchema.schema_json == sig
        )
    )
    schema = result.scalar_one_or_none()
    if schema:
        return schema.id

    schema = ProtocolSchema(protocol=protocol, schema_json=sig)
    session.add(schema)
    await session.commit()
    await session.refresh(schema)
    return schema.id


async def _store_packet(info: dict):
    """Store a dissected packet into the DB."""
    try:
        async with async_session() as session:
            # Find device by MAC
            device_id = None
            if info["src_mac"]:
                result = await session.execute(
                    select(Device.id).where(Device.mac == info["src_mac"])
                )
                row = result.scalar_one_or_none()
                if row:
                    device_id = row

            # Find or create schema
            schema_id = await _find_or_create_schema(
                session, info["protocol"],
                info["src_port"], info["dst_port"], info["length"]
            )

            # Insert base flow
            flow = FlowBase(
                timestamp=info["timestamp"],
                src_mac=info["src_mac"],
                dst_mac=info["dst_mac"],
                src_ip=info["src_ip"],
                dst_ip=info["dst_ip"],
                src_port=info["src_port"],
                dst_port=info["dst_port"],
                protocol=info["protocol"],
                length=info["length"],
                device_id=device_id,
                schema_id=schema_id,
            )
            session.add(flow)
            await session.commit()
            await session.refresh(flow)

            # Insert protocol-specific detail
            dt = info.get("detail_type")
            d = info.get("detail", {})

            if dt == "tcp":
                session.add(TCPFlow(
                    flow_id=flow.id, flags=d.get("flags"),
                    seq_num=d.get("seq_num"), ack_num=d.get("ack_num"),
                    window=d.get("window"),
                    payload_hex=d.get("payload_hex"),
                    payload_text=d.get("payload_text"),
                ))
            elif dt == "udp":
                session.add(UDPFlow(
                    flow_id=flow.id, udp_length=d.get("udp_length"),
                    payload_hex=d.get("payload_hex"),
                    payload_text=d.get("payload_text"),
                ))
            elif dt == "dns":
                session.add(DNSFlow(
                    flow_id=flow.id, query=d.get("query"),
                    query_type=d.get("query_type"),
                    response=d.get("response"),
                ))
            elif dt == "http":
                session.add(HTTPFlow(
                    flow_id=flow.id, method=d.get("method"),
                    url=d.get("url"), host=d.get("host"),
                    status_code=d.get("status_code"),
                    headers_json=d.get("headers"),
                    body=d.get("body"),
                ))
            await session.commit()
    except Exception as e:
        logger.error(f"Store error: {e}")


async def _consumer_loop():
    """Consume packets from queue and store in DB."""
    while True:
        info = await _packet_queue.get()
        await _store_packet(info)


def _sniffer_thread():
    """Scapy sniffer in a dedicated thread."""
    logger.info("Sniffer thread started on wlan1")
    try:
        sniff(iface="wlan1", prn=_packet_callback, store=0,
              filter="ip", count=0)
    except Exception as e:
        logger.error(f"Sniffer error: {e}")


async def capture_loop():
    """Main capture entry point."""
    global _packet_queue, _loop
    _loop = asyncio.get_event_loop()
    _packet_queue = asyncio.Queue(maxsize=10000)

    logger.info("Capture service started")

    # Start scapy in a background thread
    t = threading.Thread(target=_sniffer_thread, daemon=True)
    t.start()

    # Run consumer
    await _consumer_loop()
