"""管理端查询接口：机器列表、单机历史指标、汇总统计（需登录）。"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_dependency
from ..models import Agent, Metric
from ..schemas import AgentOut, MetricPoint
from ..security import get_current_user
from ..services import build_snapshot, to_agent_out

router = APIRouter(prefix="/api/v1", tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/agents", response_model=list[AgentOut])
async def list_agents(session: AsyncSession = Depends(session_dependency)) -> list[AgentOut]:
    result = await session.execute(select(Agent).order_by(Agent.hostname))
    return [to_agent_out(a) for a in result.scalars().all()]


@router.get("/agents/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: str, session: AsyncSession = Depends(session_dependency)
) -> AgentOut:
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="机器不存在")
    return to_agent_out(agent)


@router.get("/agents/{agent_id}/metrics", response_model=list[MetricPoint])
async def get_metrics(
    agent_id: str,
    minutes: int = Query(default=60, ge=1, le=10080),
    session: AsyncSession = Depends(session_dependency),
) -> list[MetricPoint]:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    result = await session.execute(
        select(Metric)
        .where(Metric.agent_id == agent_id, Metric.time >= since)
        .order_by(Metric.time)
    )
    return list(result.scalars().all())


@router.get("/summary")
async def summary(session: AsyncSession = Depends(session_dependency)) -> dict:
    snapshot = await build_snapshot(session)
    return snapshot["summary"]
