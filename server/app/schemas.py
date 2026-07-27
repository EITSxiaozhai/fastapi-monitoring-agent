"""Pydantic 请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


class ProcessInfo(BaseModel):
    pid: int = 0
    name: str = ""
    cpu_percent: float = 0.0
    mem_percent: float = 0.0


class MetricIn(BaseModel):
    """客户端上报的数据结构。"""

    agent_id: str = Field(..., max_length=128)
    hostname: str = Field(..., max_length=255)
    os: str = ""
    kernel: str = ""
    arch: str = ""

    # 外网 IP 与所属国家
    public_ip: str = Field("", max_length=64)
    country_code: str = Field("", max_length=8)
    country: str = Field("", max_length=64)

    cpu_count: int = 0
    cpu_percent: float = 0.0
    mem_total: int = 0
    mem_used: int = 0
    mem_percent: float = 0.0
    process_count: int = 0
    load1: float = 0.0
    uptime_seconds: int = 0

    # 磁盘
    disk_total: int = 0
    disk_used: int = 0
    disk_percent: float = 0.0

    # 网络 IO
    net_sent_rate: float = 0.0
    net_recv_rate: float = 0.0
    net_bytes_sent: int = 0
    net_bytes_recv: int = 0
    # 网络质量（错误 / 丢包 / TCP 重传）
    net_errin: int = 0
    net_errout: int = 0
    net_dropin: int = 0
    net_dropout: int = 0
    net_errin_rate: float = 0.0
    net_errout_rate: float = 0.0
    net_dropin_rate: float = 0.0
    net_dropout_rate: float = 0.0
    tcp_retrans: int = 0
    tcp_retrans_rate: float = 0.0

    # TCP 连接
    tcp_connections: int = 0
    tcp_established: int = 0

    # Top 进程
    top_processes: list[ProcessInfo] = Field(default_factory=list)


class AgentOut(BaseModel):
    agent_id: str
    hostname: str
    os: str
    kernel: str
    arch: str
    public_ip: str = ""
    country_code: str = ""
    country: str = ""
    cpu_count: int
    mem_total: int
    cpu_percent: float
    mem_percent: float
    mem_used: int
    process_count: int
    load1: float
    uptime_seconds: int

    disk_total: int = 0
    disk_used: int = 0
    disk_percent: float = 0.0
    net_sent_rate: float = 0.0
    net_recv_rate: float = 0.0
    net_bytes_sent: int = 0
    net_bytes_recv: int = 0
    net_errin: int = 0
    net_errout: int = 0
    net_dropin: int = 0
    net_dropout: int = 0
    net_errin_rate: float = 0.0
    net_errout_rate: float = 0.0
    net_dropin_rate: float = 0.0
    net_dropout_rate: float = 0.0
    tcp_retrans: int = 0
    tcp_retrans_rate: float = 0.0
    tcp_connections: int = 0
    tcp_established: int = 0
    top_processes: list[ProcessInfo] = Field(default_factory=list)

    first_seen: datetime
    last_seen: datetime
    online: bool

    class Config:
        from_attributes = True


class MetricPoint(BaseModel):
    time: datetime
    cpu_percent: float
    mem_percent: float
    mem_used: int
    process_count: int
    load1: float
    disk_percent: float = 0.0
    net_sent_rate: float = 0.0
    net_recv_rate: float = 0.0
    tcp_connections: int = 0
    net_errin_rate: float = 0.0
    net_errout_rate: float = 0.0
    net_dropin_rate: float = 0.0
    net_dropout_rate: float = 0.0
    tcp_retrans_rate: float = 0.0

    class Config:
        from_attributes = True


class MachinesDisplayPrefs(BaseModel):
    show_stat_cards: bool = True
    show_machine_cards: bool = True

    class Config:
        from_attributes = True


class MachinesDisplayPrefsIn(BaseModel):
    show_stat_cards: bool = True
    show_machine_cards: bool = True
