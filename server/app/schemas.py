"""Pydantic 请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


class MetricIn(BaseModel):
    """客户端上报的数据结构。"""

    agent_id: str = Field(..., max_length=128)
    hostname: str = Field(..., max_length=255)
    os: str = ""
    kernel: str = ""
    arch: str = ""

    cpu_count: int = 0
    cpu_percent: float = 0.0
    mem_total: int = 0
    mem_used: int = 0
    mem_percent: float = 0.0
    process_count: int = 0
    load1: float = 0.0
    uptime_seconds: int = 0


class AgentOut(BaseModel):
    agent_id: str
    hostname: str
    os: str
    kernel: str
    arch: str
    cpu_count: int
    mem_total: int
    cpu_percent: float
    mem_percent: float
    mem_used: int
    process_count: int
    load1: float
    uptime_seconds: int
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

    class Config:
        from_attributes = True
