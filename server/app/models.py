"""ORM 数据模型。

- Agent: 每台被监控机器的注册信息与最新快照（便于 Dashboard 快速读取）。
- Metric: 时序指标历史，转换为 TimescaleDB hypertable。
"""

from datetime import datetime

from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    # agent_id 由客户端生成（machine-id / 主机名派生），全局唯一
    agent_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    os: Mapped[str] = mapped_column(String(64), default="")
    kernel: Mapped[str] = mapped_column(String(255), default="")
    arch: Mapped[str] = mapped_column(String(32), default="")

    # 外网 IP 与所属国家
    public_ip: Mapped[str] = mapped_column(String(64), default="")
    country_code: Mapped[str] = mapped_column(String(8), default="")
    country: Mapped[str] = mapped_column(String(64), default="")

    cpu_count: Mapped[int] = mapped_column(Integer, default=0)
    mem_total: Mapped[int] = mapped_column(BigInteger, default=0)

    # 最新快照
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    mem_percent: Mapped[float] = mapped_column(Float, default=0.0)
    mem_used: Mapped[int] = mapped_column(BigInteger, default=0)
    process_count: Mapped[int] = mapped_column(Integer, default=0)
    load1: Mapped[float] = mapped_column(Float, default=0.0)
    uptime_seconds: Mapped[int] = mapped_column(BigInteger, default=0)

    # 磁盘
    disk_total: Mapped[int] = mapped_column(BigInteger, default=0)
    disk_used: Mapped[int] = mapped_column(BigInteger, default=0)
    disk_percent: Mapped[float] = mapped_column(Float, default=0.0)

    # 网络 IO
    net_sent_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_recv_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_bytes_sent: Mapped[int] = mapped_column(BigInteger, default=0)
    net_bytes_recv: Mapped[int] = mapped_column(BigInteger, default=0)

    # 网络质量（错误 / 丢包 / TCP 重传）
    net_errin: Mapped[int] = mapped_column(BigInteger, default=0)
    net_errout: Mapped[int] = mapped_column(BigInteger, default=0)
    net_dropin: Mapped[int] = mapped_column(BigInteger, default=0)
    net_dropout: Mapped[int] = mapped_column(BigInteger, default=0)
    net_errin_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_errout_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_dropin_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_dropout_rate: Mapped[float] = mapped_column(Float, default=0.0)
    tcp_retrans: Mapped[int] = mapped_column(BigInteger, default=0)
    tcp_retrans_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # TCP 连接
    tcp_connections: Mapped[int] = mapped_column(Integer, default=0)
    tcp_established: Mapped[int] = mapped_column(Integer, default=0)

    # Top 进程（最新快照，JSON 列表）
    top_processes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Metric(Base):
    __tablename__ = "metrics"

    # 复合主键：hypertable 分区列必须包含在主键内
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("agents.agent_id"), primary_key=True, index=True
    )

    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    mem_percent: Mapped[float] = mapped_column(Float, default=0.0)
    mem_used: Mapped[int] = mapped_column(BigInteger, default=0)
    process_count: Mapped[int] = mapped_column(Integer, default=0)
    load1: Mapped[float] = mapped_column(Float, default=0.0)
    disk_percent: Mapped[float] = mapped_column(Float, default=0.0)
    net_sent_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_recv_rate: Mapped[float] = mapped_column(Float, default=0.0)
    tcp_connections: Mapped[int] = mapped_column(Integer, default=0)
    net_errin_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_errout_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_dropin_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_dropout_rate: Mapped[float] = mapped_column(Float, default=0.0)
    tcp_retrans_rate: Mapped[float] = mapped_column(Float, default=0.0)
