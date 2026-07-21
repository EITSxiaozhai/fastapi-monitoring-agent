"""WebSocket 端点：客户端上报(/ws/ingest) 与前端实时订阅(/ws/dashboard)。"""

import logging
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Agent, Metric
from ..realtime import broadcaster
from ..schemas import MetricIn
from ..security import decode_token, verify_api_key
from ..services import to_agent_out

log = logging.getLogger("mon-server.ws")

router = APIRouter(tags=["websocket"])


async def _persist(session: AsyncSession, payload: MetricIn) -> Agent:
    now = datetime.now(timezone.utc)
    agent = await session.get(Agent, payload.agent_id)
    if agent is None:
        agent = Agent(agent_id=payload.agent_id, first_seen=now)
        session.add(agent)

    agent.hostname = payload.hostname
    agent.os = payload.os
    agent.kernel = payload.kernel
    agent.arch = payload.arch
    agent.cpu_count = payload.cpu_count
    agent.mem_total = payload.mem_total
    agent.cpu_percent = payload.cpu_percent
    agent.mem_percent = payload.mem_percent
    agent.mem_used = payload.mem_used
    agent.process_count = payload.process_count
    agent.load1 = payload.load1
    agent.uptime_seconds = payload.uptime_seconds
    agent.disk_total = payload.disk_total
    agent.disk_used = payload.disk_used
    agent.disk_percent = payload.disk_percent
    agent.net_sent_rate = payload.net_sent_rate
    agent.net_recv_rate = payload.net_recv_rate
    agent.net_bytes_sent = payload.net_bytes_sent
    agent.net_bytes_recv = payload.net_bytes_recv
    agent.tcp_connections = payload.tcp_connections
    agent.tcp_established = payload.tcp_established
    agent.top_processes = [p.model_dump() for p in payload.top_processes]
    agent.last_seen = now

    session.add(
        Metric(
            time=now,
            agent_id=payload.agent_id,
            cpu_percent=payload.cpu_percent,
            mem_percent=payload.mem_percent,
            mem_used=payload.mem_used,
            process_count=payload.process_count,
            load1=payload.load1,
            disk_percent=payload.disk_percent,
            net_sent_rate=payload.net_sent_rate,
            net_recv_rate=payload.net_recv_rate,
            tcp_connections=payload.tcp_connections,
        )
    )
    await session.commit()
    await session.refresh(agent)
    return agent


@router.websocket("/ws/ingest")
async def ws_ingest(websocket: WebSocket, api_key: str | None = None) -> None:
    """客户端通过该端点持续上报指标。鉴权使用查询参数 ?api_key=。"""
    if not verify_api_key(api_key):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    peer = websocket.client.host if websocket.client else "?"
    log.info("客户端已连接上报通道：%s", peer)

    try:
        async with get_session() as session:
            while True:
                raw = await websocket.receive_json()
                try:
                    payload = MetricIn.model_validate(raw)
                except ValidationError as exc:
                    await websocket.send_json({"status": "error", "detail": exc.errors()})
                    continue

                agent = await _persist(session, payload)
                await websocket.send_json(
                    {"status": "accepted", "agent_id": payload.agent_id}
                )
                # 实时推送单机更新给所有前端订阅者
                await broadcaster.broadcast(
                    {"type": "agent", "data": to_agent_out(agent).model_dump(mode="json")}
                )
    except WebSocketDisconnect:
        log.info("客户端断开上报通道：%s", peer)
    except Exception as exc:  # noqa: BLE001
        log.warning("上报通道异常(%s)：%s", peer, exc)


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket, token: str | None = None) -> None:
    """前端订阅实时数据。鉴权使用查询参数 ?token=<JWT>。"""
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        decode_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await broadcaster.connect(websocket)
    try:
        await broadcaster.send_snapshot(websocket)
        # 保持连接：读取（并忽略）客户端消息，用于检测断开
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        log.debug("订阅连接关闭：%s", exc)
    finally:
        await broadcaster.disconnect(websocket)
