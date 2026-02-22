from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


# ─── Device ─────────────────────────────────────────────────
class DeviceOut(BaseModel):
    id: int
    mac: str
    ip: Optional[str] = None
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    is_active: bool
    signal_dbm: Optional[int] = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    current_ap_ssid: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Access Point ───────────────────────────────────────────
class APOut(BaseModel):
    id: int
    ssid: str
    bssid: str
    channel: Optional[int] = None
    security: Optional[str] = None
    is_active: bool
    created_at: datetime
    connected_devices: int = 0

    class Config:
        from_attributes = True


class APUpdate(BaseModel):
    ssid: Optional[str] = None
    password: Optional[str] = None


# ─── Flow ───────────────────────────────────────────────────
class FlowOut(BaseModel):
    id: int
    timestamp: datetime
    src_mac: Optional[str] = None
    dst_mac: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None
    length: Optional[int] = None
    detail: Optional[dict] = None

    class Config:
        from_attributes = True


# ─── Dashboard Stats ────────────────────────────────────────
class DashboardStats(BaseModel):
    total_devices: int = 0
    active_devices: int = 0
    total_flows: int = 0
    total_bytes_rx: int = 0
    total_bytes_tx: int = 0
    top_protocols: List[dict] = []
    top_domains: List[dict] = []


# ─── Network Topology Node / Edge ───────────────────────────
class TopoNode(BaseModel):
    id: str
    label: str
    group: str
    title: Optional[str] = None
    rx_rate: float = 0.0
    tx_rate: float = 0.0


class TopoEdge(BaseModel):
    from_id: str
    to_id: str
    label: Optional[str] = None
    width: float = 1.0
