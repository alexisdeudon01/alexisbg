"""
24/7 Device monitoring service.
Polls iw station dump + arp table every few seconds.
Adds new devices, updates existing, marks disconnected as inactive.
"""
import asyncio
import subprocess
import re
import logging
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Device, AccessPoint, DeviceAPHistory

logger = logging.getLogger("monitor")

MAC_VENDOR = None
try:
    from mac_vendor_lookup import MacLookup
    MAC_VENDOR = MacLookup()
    MAC_VENDOR.update_vendors()
except Exception:
    pass


def _run(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout
    except Exception:
        return ""


def _parse_stations() -> list[dict]:
    """Parse iw dev wlan1 station dump."""
    raw = _run("iw dev wlan1 station dump")
    stations = []
    current = None
    for line in raw.splitlines():
        m = re.match(r"Station\s+([0-9a-f:]{17})", line, re.I)
        if m:
            if current:
                stations.append(current)
            current = {"mac": m.group(1).lower(), "signal": None,
                       "rx_bytes": 0, "tx_bytes": 0,
                       "rx_packets": 0, "tx_packets": 0,
                       "connected_time": 0, "authorized": False}
            continue
        if current is None:
            continue
        line = line.strip()
        if line.startswith("signal:"):
            m2 = re.search(r"(-?\d+)", line)
            if m2:
                current["signal"] = int(m2.group(1))
        elif line.startswith("rx bytes:"):
            m2 = re.search(r"(\d+)", line)
            if m2:
                current["rx_bytes"] = int(m2.group(1))
        elif line.startswith("tx bytes:"):
            m2 = re.search(r"(\d+)", line)
            if m2:
                current["tx_bytes"] = int(m2.group(1))
        elif line.startswith("rx packets:"):
            m2 = re.search(r"(\d+)", line)
            if m2:
                current["rx_packets"] = int(m2.group(1))
        elif line.startswith("tx packets:"):
            m2 = re.search(r"(\d+)", line)
            if m2:
                current["tx_packets"] = int(m2.group(1))
        elif line.startswith("connected time:"):
            m2 = re.search(r"(\d+)", line)
            if m2:
                current["connected_time"] = int(m2.group(1))
        elif line.startswith("authorized:"):
            current["authorized"] = "yes" in line
    if current:
        stations.append(current)
    return [s for s in stations if s["authorized"]]


def _get_arp_table() -> dict:
    """Return {mac: ip} from arp -n."""
    raw = _run("arp -n")
    table = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 3 and re.match(r"\d+\.\d+\.\d+\.\d+", parts[0]):
            ip = parts[0]
            mac = parts[2].lower() if len(parts) > 2 else None
            if mac and mac != "(incomplete)" and ":" in mac:
                table[mac] = ip
    return table


def _lookup_vendor(mac: str) -> str:
    if MAC_VENDOR:
        try:
            return MAC_VENDOR.lookup(mac)
        except Exception:
            pass
    return ""


async def _ensure_ap(session: AsyncSession) -> AccessPoint:
    """Make sure our fake AP is in the DB."""
    raw = _run("iw dev wlan1 info")
    ssid, bssid, channel = "Unknown", "00:00:00:00:00:00", 0
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("ssid"):
            ssid = line.split(" ", 1)[1] if " " in line else ssid
        elif line.startswith("addr"):
            bssid = line.split(" ", 1)[1].lower() if " " in line else bssid
        elif line.startswith("channel"):
            m = re.search(r"(\d+)", line)
            if m:
                channel = int(m.group(1))

    result = await session.execute(
        select(AccessPoint).where(AccessPoint.bssid == bssid)
    )
    ap = result.scalar_one_or_none()
    if not ap:
        ap = AccessPoint(ssid=ssid, bssid=bssid, channel=channel,
                         security="WPA2-PSK", is_active=True)
        session.add(ap)
        await session.commit()
        await session.refresh(ap)
        logger.info(f"AP registered: {ssid} ({bssid})")
    else:
        ap.ssid = ssid
        ap.channel = channel
        ap.is_active = True
        await session.commit()
    return ap


async def monitor_loop():
    """Main monitoring loop — runs forever."""
    logger.info("Monitor service started")
    while True:
        try:
            async with async_session() as session:
                ap = await _ensure_ap(session)
                stations = _parse_stations()
                arp = _get_arp_table()
                now = datetime.utcnow()
                seen_macs = set()

                for st in stations:
                    mac = st["mac"]
                    seen_macs.add(mac)
                    ip = arp.get(mac)

                    result = await session.execute(
                        select(Device).where(Device.mac == mac)
                    )
                    dev = result.scalar_one_or_none()

                    if dev is None:
                        vendor = _lookup_vendor(mac)
                        dev = Device(
                            mac=mac, ip=ip, vendor=vendor,
                            first_seen=now, last_seen=now, is_active=True,
                            signal_dbm=st["signal"],
                            rx_bytes=st["rx_bytes"], tx_bytes=st["tx_bytes"],
                            rx_packets=st["rx_packets"], tx_packets=st["tx_packets"],
                        )
                        session.add(dev)
                        await session.commit()
                        await session.refresh(dev)
                        logger.info(f"New device: {mac} ({ip}) vendor={vendor}")

                        hist = DeviceAPHistory(
                            device_id=dev.id, ap_id=ap.id, connected_at=now
                        )
                        session.add(hist)
                    else:
                        dev.ip = ip or dev.ip
                        dev.last_seen = now
                        dev.is_active = True
                        dev.signal_dbm = st["signal"]
                        dev.rx_bytes = st["rx_bytes"]
                        dev.tx_bytes = st["tx_bytes"]
                        dev.rx_packets = st["rx_packets"]
                        dev.tx_packets = st["tx_packets"]

                        result2 = await session.execute(
                            select(DeviceAPHistory).where(
                                DeviceAPHistory.device_id == dev.id,
                                DeviceAPHistory.disconnected_at.is_(None)
                            )
                        )
                        active_conn = result2.scalar_one_or_none()
                        if not active_conn:
                            hist = DeviceAPHistory(
                                device_id=dev.id, ap_id=ap.id, connected_at=now
                            )
                            session.add(hist)

                    await session.commit()

                # Mark devices that are no longer connected as inactive
                result = await session.execute(
                    select(Device).where(Device.is_active == True)  # noqa
                )
                all_active = result.scalars().all()
                for dev in all_active:
                    if dev.mac not in seen_macs:
                        dev.is_active = False
                        dev.last_seen = now
                        # Close open AP history
                        result3 = await session.execute(
                            select(DeviceAPHistory).where(
                                DeviceAPHistory.device_id == dev.id,
                                DeviceAPHistory.disconnected_at.is_(None)
                            )
                        )
                        for hist in result3.scalars().all():
                            hist.disconnected_at = now
                await session.commit()

        except Exception as e:
            logger.error(f"Monitor error: {e}")

        await asyncio.sleep(5)
