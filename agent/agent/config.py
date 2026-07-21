"""客户端配置，全部来自环境变量。"""

import os
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path


def _resolve_agent_id() -> str:
    """稳定的唯一机器标识。

    优先级：显式环境变量 > /etc/machine-id > 主机名派生的 UUID。
    """
    explicit = os.getenv("AGENT_ID")
    if explicit:
        return explicit

    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            mid = Path(path).read_text().strip()
            if mid:
                return mid
        except OSError:
            continue

    hostname = socket.gethostname()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname))


@dataclass(frozen=True)
class AgentConfig:
    server_url: str
    api_key: str
    agent_id: str
    hostname: str
    interval: float

    @classmethod
    def from_env(cls) -> "AgentConfig":
        # SERVER_URL 支持 http(s):// 或 ws(s)://，统一转换为 WebSocket 上报地址
        server = os.getenv("SERVER_URL", "ws://localhost:8000").rstrip("/")
        if server.startswith("http://"):
            server = "ws://" + server[len("http://") :]
        elif server.startswith("https://"):
            server = "wss://" + server[len("https://") :]
        api_key = os.getenv("API_KEY", "changeme-dev-key")
        return cls(
            server_url=f"{server}/ws/ingest?api_key={api_key}",
            api_key=api_key,
            agent_id=_resolve_agent_id(),
            hostname=os.getenv("AGENT_HOSTNAME", socket.gethostname()),
            interval=float(os.getenv("INTERVAL", "2")),
        )
