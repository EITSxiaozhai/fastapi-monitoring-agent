"""实时广播管理器。

维护所有已订阅的前端 Dashboard WebSocket 连接，将机器状态变更实时推送出去。
同时提供一个后台循环，周期性广播全量快照，以便及时反映机器的离线状态。
"""

import asyncio
import contextlib
import json
import logging

from fastapi import WebSocket

from .config import get_settings
from .database import get_session
from .services import build_snapshot

log = logging.getLogger("mon-server.realtime")


class Broadcaster:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        data = json.dumps(message, default=str)
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001 - 连接已断开
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    async def send_snapshot(self, ws: WebSocket) -> None:
        async with get_session() as session:
            snapshot = await build_snapshot(session)
        await ws.send_text(json.dumps(snapshot, default=str))

    async def _loop(self) -> None:
        interval = get_settings().broadcast_interval_seconds
        while True:
            try:
                await asyncio.sleep(interval)
                async with self._lock:
                    has_clients = bool(self._clients)
                if not has_clients:
                    continue
                async with get_session() as session:
                    snapshot = await build_snapshot(session)
                await self.broadcast(snapshot)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                log.warning("广播循环异常：%s", exc)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None


broadcaster = Broadcaster()
