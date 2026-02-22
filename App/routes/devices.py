from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Device, DeviceAPHistory, AccessPoint

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("")
async def list_devices(active_only: bool = False, db: AsyncSession = Depends(get_db)):
    q = select(Device).order_by(Device.last_seen.desc())
    if active_only:
        q = q.where(Device.is_active == True)  # noqa
    result = await db.execute(q)
    devices = result.scalars().all()

    out = []
    for d in devices:
        # Get current AP
        ap_ssid = None
        res2 = await db.execute(
            select(AccessPoint.ssid)
            .join(DeviceAPHistory, DeviceAPHistory.ap_id == AccessPoint.id)
            .where(
                DeviceAPHistory.device_id == d.id,
                DeviceAPHistory.disconnected_at.is_(None)
            )
            .limit(1)
        )
        row = res2.scalar_one_or_none()
        if row:
            ap_ssid = row

        out.append({
            "id": d.id, "mac": d.mac, "ip": d.ip,
            "hostname": d.hostname, "vendor": d.vendor,
            "first_seen": d.first_seen.isoformat() if d.first_seen else None,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "is_active": d.is_active,
            "signal_dbm": d.signal_dbm,
            "rx_bytes": d.rx_bytes, "tx_bytes": d.tx_bytes,
            "rx_packets": d.rx_packets, "tx_packets": d.tx_packets,
            "current_ap_ssid": ap_ssid,
        })
    return out


@router.get("/{device_id}")
async def get_device(device_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device).where(Device.id == device_id))
    dev = result.scalar_one_or_none()
    if not dev:
        return {"error": "Device not found"}

    # AP history
    res2 = await db.execute(
        select(DeviceAPHistory, AccessPoint)
        .join(AccessPoint, DeviceAPHistory.ap_id == AccessPoint.id)
        .where(DeviceAPHistory.device_id == device_id)
        .order_by(DeviceAPHistory.connected_at.desc())
        .limit(20)
    )
    ap_history = []
    for hist, ap in res2.all():
        ap_history.append({
            "ssid": ap.ssid, "bssid": ap.bssid,
            "connected_at": hist.connected_at.isoformat() if hist.connected_at else None,
            "disconnected_at": hist.disconnected_at.isoformat() if hist.disconnected_at else None,
        })

    return {
        "id": dev.id, "mac": dev.mac, "ip": dev.ip,
        "hostname": dev.hostname, "vendor": dev.vendor,
        "first_seen": dev.first_seen.isoformat() if dev.first_seen else None,
        "last_seen": dev.last_seen.isoformat() if dev.last_seen else None,
        "is_active": dev.is_active,
        "signal_dbm": dev.signal_dbm,
        "rx_bytes": dev.rx_bytes, "tx_bytes": dev.tx_bytes,
        "rx_packets": dev.rx_packets, "tx_packets": dev.tx_packets,
        "ap_history": ap_history,
    }
