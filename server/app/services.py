"""共享业务逻辑：在线判定、快照构建。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Agent
from .schemas import AgentOut


def is_online(last_seen: datetime) -> bool:
    threshold = get_settings().offline_threshold_seconds
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last_seen) <= timedelta(seconds=threshold)


def to_agent_out(agent: Agent) -> AgentOut:
    data = {**agent.__dict__, "online": is_online(agent.last_seen)}
    if data.get("top_processes") is None:
        data["top_processes"] = []
    return AgentOut(**data)


async def build_snapshot(session: AsyncSession) -> dict:
    """构建供前端展示的完整快照：汇总统计 + 机器列表。"""
    result = await session.execute(select(Agent).order_by(Agent.hostname))
    agents = result.scalars().all()
    outs = [to_agent_out(a) for a in agents]
    online = sum(1 for a in outs if a.online)
    summary = {
        "total": len(outs),
        "online": online,
        "offline": len(outs) - online,
        "avg_cpu": round(sum(a.cpu_percent for a in outs if a.online) / online, 1)
        if online
        else 0.0,
        "avg_mem": round(sum(a.mem_percent for a in outs if a.online) / online, 1)
        if online
        else 0.0,
    }
    return {
        "type": "snapshot",
        "summary": summary,
        "agents": [a.model_dump(mode="json") for a in outs],
    }
