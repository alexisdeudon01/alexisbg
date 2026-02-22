from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Device, FlowBase, AccessPoint, DeviceAPHistory

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/topology")
async def topology(db: AsyncSession = Depends(get_db)):
    """Return nodes and edges for vis.js network diagram."""
    nodes = []
    edges = []

    # Get all APs
    result = await db.execute(select(AccessPoint).where(AccessPoint.is_active == True))  # noqa
    aps = result.scalars().all()
    for ap in aps:
        nodes.append({
            "id": f"ap_{ap.id}",
            "label": ap.ssid,
            "group": "ap",
            "title": f"BSSID: {ap.bssid}\nChannel: {ap.channel}\nSecurity: {ap.security}",
        })

    # Internet node
    nodes.append({
        "id": "internet",
        "label": "Internet",
        "group": "internet",
        "title": "via eth0 → Fritz!Box",
    })

    # Router node
    nodes.append({
        "id": "router",
        "label": "Fritz!Box",
        "group": "router",
        "title": "192.168.178.1\nGateway",
    })

    # Link AP → router → internet
    for ap in aps:
        edges.append({"from": f"ap_{ap.id}", "to": "router", "label": "NAT", "width": 3})
    edges.append({"from": "router", "to": "internet", "label": "eth0", "width": 4})

    # Get active devices
    result2 = await db.execute(
        select(Device).where(Device.is_active == True).order_by(Device.last_seen.desc())  # noqa
    )
    devices = result2.scalars().all()

    for dev in devices:
        speed_rx = dev.rx_bytes / max(1, 1)  # absolute value
        speed_tx = dev.tx_bytes / max(1, 1)
        label = dev.hostname or dev.vendor or dev.mac[-8:]
        nodes.append({
            "id": f"dev_{dev.id}",
            "label": label,
            "group": "device",
            "title": (f"MAC: {dev.mac}\nIP: {dev.ip}\n"
                      f"Signal: {dev.signal_dbm} dBm\n"
                      f"RX: {_fmt_bytes(dev.rx_bytes)}\n"
                      f"TX: {_fmt_bytes(dev.tx_bytes)}"),
            "rx_bytes": dev.rx_bytes,
            "tx_bytes": dev.tx_bytes,
            "signal_dbm": dev.signal_dbm,
        })

        # Find which AP this device is connected to
        res3 = await db.execute(
            select(DeviceAPHistory.ap_id).where(
                DeviceAPHistory.device_id == dev.id,
                DeviceAPHistory.disconnected_at.is_(None)
            ).limit(1)
        )
        ap_id = res3.scalar_one_or_none()
        if ap_id:
            bw = max(1, min(8, dev.rx_bytes // 100000))
            edges.append({
                "from": f"dev_{dev.id}",
                "to": f"ap_{ap_id}",
                "width": bw,
                "label": f"↑{_fmt_bytes(dev.tx_bytes)} ↓{_fmt_bytes(dev.rx_bytes)}",
            })

    return {"nodes": nodes, "edges": edges}


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    # Device counts
    res_total = await db.execute(select(func.count(Device.id)))
    res_active = await db.execute(
        select(func.count(Device.id)).where(Device.is_active == True)  # noqa
    )
    # Flow counts
    res_flows = await db.execute(select(func.count(FlowBase.id)))
    res_bytes = await db.execute(select(func.sum(FlowBase.length)))

    # RX/TX totals from devices
    res_rx = await db.execute(select(func.sum(Device.rx_bytes)))
    res_tx = await db.execute(select(func.sum(Device.tx_bytes)))

    return {
        "total_devices": res_total.scalar() or 0,
        "active_devices": res_active.scalar() or 0,
        "total_flows": res_flows.scalar() or 0,
        "total_flow_bytes": res_bytes.scalar() or 0,
        "total_rx": res_rx.scalar() or 0,
        "total_tx": res_tx.scalar() or 0,
    }


def _fmt_bytes(b: int) -> str:
    if b is None:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"
