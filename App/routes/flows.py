from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import FlowBase, TCPFlow, UDPFlow, DNSFlow, HTTPFlow

router = APIRouter(prefix="/api/flows", tags=["flows"])


@router.get("")
async def list_flows(
    protocol: str = None,
    device_id: int = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(FlowBase).order_by(desc(FlowBase.timestamp))
    if protocol:
        q = q.where(FlowBase.protocol == protocol.upper())
    if device_id:
        q = q.where(FlowBase.device_id == device_id)
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    flows = result.scalars().all()

    out = []
    for f in flows:
        detail = None
        if f.tcp_detail:
            detail = {"flags": f.tcp_detail.flags, "seq": f.tcp_detail.seq_num,
                       "ack": f.tcp_detail.ack_num, "window": f.tcp_detail.window,
                       "payload_text": (f.tcp_detail.payload_text or "")[:200]}
        elif f.udp_detail:
            detail = {"length": f.udp_detail.udp_length,
                       "payload_text": (f.udp_detail.payload_text or "")[:200]}
        elif f.dns_detail:
            detail = {"query": f.dns_detail.query,
                       "type": f.dns_detail.query_type,
                       "response": f.dns_detail.response}
        elif f.http_detail:
            detail = {"method": f.http_detail.method,
                       "url": f.http_detail.url,
                       "host": f.http_detail.host,
                       "status": f.http_detail.status_code}
        out.append({
            "id": f.id,
            "timestamp": f.timestamp.isoformat() if f.timestamp else None,
            "src_ip": f.src_ip, "dst_ip": f.dst_ip,
            "src_port": f.src_port, "dst_port": f.dst_port,
            "protocol": f.protocol, "length": f.length,
            "detail": detail,
        })
    return out


@router.get("/stats")
async def flow_stats(db: AsyncSession = Depends(get_db)):
    # Protocol distribution
    result = await db.execute(
        select(FlowBase.protocol, func.count(FlowBase.id))
        .group_by(FlowBase.protocol)
        .order_by(desc(func.count(FlowBase.id)))
        .limit(10)
    )
    protocols = [{"protocol": r[0], "count": r[1]} for r in result.all()]

    # Top DNS domains
    result2 = await db.execute(
        select(DNSFlow.query, func.count(DNSFlow.id))
        .group_by(DNSFlow.query)
        .order_by(desc(func.count(DNSFlow.id)))
        .limit(15)
    )
    domains = [{"domain": r[0], "count": r[1]} for r in result2.all()]

    # Top HTTP hosts
    result3 = await db.execute(
        select(HTTPFlow.host, func.count(HTTPFlow.id))
        .group_by(HTTPFlow.host)
        .order_by(desc(func.count(HTTPFlow.id)))
        .limit(15)
    )
    http_hosts = [{"host": r[0], "count": r[1]} for r in result3.all()]

    # Total flows
    result4 = await db.execute(select(func.count(FlowBase.id)))
    total = result4.scalar() or 0

    # Total bytes
    result5 = await db.execute(select(func.sum(FlowBase.length)))
    total_bytes = result5.scalar() or 0

    return {
        "total_flows": total,
        "total_bytes": total_bytes,
        "protocols": protocols,
        "top_domains": domains,
        "top_http_hosts": http_hosts,
    }


@router.get("/live")
async def live_flows(
    seconds: int = Query(default=10, le=60),
    db: AsyncSession = Depends(get_db),
):
    """Get flows from the last N seconds."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(seconds=seconds)
    result = await db.execute(
        select(FlowBase)
        .where(FlowBase.timestamp >= cutoff)
        .order_by(desc(FlowBase.timestamp))
        .limit(200)
    )
    flows = result.scalars().all()
    return [
        {
            "id": f.id,
            "timestamp": f.timestamp.isoformat() if f.timestamp else None,
            "src_ip": f.src_ip, "dst_ip": f.dst_ip,
            "protocol": f.protocol, "length": f.length,
        }
        for f in flows
    ]
