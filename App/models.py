from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, BigInteger, Float,
    DateTime, Text, JSON, ForeignKey
)
from sqlalchemy.orm import relationship
from database import Base


# ─── Devices ────────────────────────────────────────────────
class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(String(17), unique=True, nullable=False, index=True)
    ip = Column(String(45))
    hostname = Column(String(255))
    vendor = Column(String(255))
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    signal_dbm = Column(Integer)
    rx_bytes = Column(BigInteger, default=0)
    tx_bytes = Column(BigInteger, default=0)
    rx_packets = Column(BigInteger, default=0)
    tx_packets = Column(BigInteger, default=0)

    ap_connections = relationship("DeviceAPHistory", back_populates="device", lazy="selectin")
    flows = relationship("FlowBase", back_populates="device", lazy="selectin")


# ─── Access Points ──────────────────────────────────────────
class AccessPoint(Base):
    __tablename__ = "access_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(String(64), nullable=False)
    bssid = Column(String(17), unique=True, nullable=False)
    channel = Column(Integer)
    security = Column(String(32))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    connections = relationship("DeviceAPHistory", back_populates="ap", lazy="selectin")


# ─── Device ↔ AP History ────────────────────────────────────
class DeviceAPHistory(Base):
    __tablename__ = "device_ap_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    ap_id = Column(Integer, ForeignKey("access_points.id"), nullable=False, index=True)
    connected_at = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="ap_connections")
    ap = relationship("AccessPoint", back_populates="connections")


# ─── Protocol Schemas (JSON abstraction) ────────────────────
class ProtocolSchema(Base):
    __tablename__ = "protocol_schemas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    protocol = Column(String(16), nullable=False, index=True)
    schema_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    flows = relationship("FlowBase", back_populates="schema", lazy="selectin")


# ─── Flow Base (common fields) ──────────────────────────────
class FlowBase(Base):
    __tablename__ = "flows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    src_mac = Column(String(17))
    dst_mac = Column(String(17))
    src_ip = Column(String(45), index=True)
    dst_ip = Column(String(45), index=True)
    src_port = Column(Integer)
    dst_port = Column(Integer)
    protocol = Column(String(16), index=True)
    length = Column(Integer)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    schema_id = Column(Integer, ForeignKey("protocol_schemas.id"), nullable=True)

    device = relationship("Device", back_populates="flows")
    schema = relationship("ProtocolSchema", back_populates="flows")
    tcp_detail = relationship("TCPFlow", uselist=False, back_populates="flow", lazy="selectin")
    udp_detail = relationship("UDPFlow", uselist=False, back_populates="flow", lazy="selectin")
    dns_detail = relationship("DNSFlow", uselist=False, back_populates="flow", lazy="selectin")
    http_detail = relationship("HTTPFlow", uselist=False, back_populates="flow", lazy="selectin")


# ─── TCP Flows ──────────────────────────────────────────────
class TCPFlow(Base):
    __tablename__ = "tcp_flows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=False, index=True)
    flags = Column(String(32))
    seq_num = Column(BigInteger)
    ack_num = Column(BigInteger)
    window = Column(Integer)
    payload_hex = Column(Text)
    payload_text = Column(Text)

    flow = relationship("FlowBase", back_populates="tcp_detail")


# ─── UDP Flows ──────────────────────────────────────────────
class UDPFlow(Base):
    __tablename__ = "udp_flows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=False, index=True)
    udp_length = Column(Integer)
    payload_hex = Column(Text)
    payload_text = Column(Text)

    flow = relationship("FlowBase", back_populates="udp_detail")


# ─── DNS Flows ──────────────────────────────────────────────
class DNSFlow(Base):
    __tablename__ = "dns_flows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=False, index=True)
    query = Column(String(255), index=True)
    query_type = Column(String(10))
    response = Column(Text)

    flow = relationship("FlowBase", back_populates="dns_detail")


# ─── HTTP Flows ─────────────────────────────────────────────
class HTTPFlow(Base):
    __tablename__ = "http_flows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=False, index=True)
    method = Column(String(10))
    url = Column(Text)
    host = Column(String(255), index=True)
    status_code = Column(Integer)
    headers_json = Column(JSON)
    body = Column(Text)

    flow = relationship("FlowBase", back_populates="http_detail")
