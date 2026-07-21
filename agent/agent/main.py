"""客户端主循环：通过 WebSocket 周期性采集并上报指标，支持断线自动重连。"""

import asyncio
import json
import logging
import signal

import websockets
from websockets.exceptions import ConnectionClosed

from .collector import collect, prime
from .config import AgentConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("mon-agent")


def build_payload(cfg: AgentConfig) -> dict:
    data = collect()
    data["agent_id"] = cfg.agent_id
    data["hostname"] = cfg.hostname
    return data


async def _report_loop(cfg: AgentConfig, stop: asyncio.Event) -> None:
    """维护一条 WebSocket 连接并持续上报，断线后由外层重连。"""
    async with websockets.connect(
        cfg.server_url, ping_interval=20, ping_timeout=20, open_timeout=10
    ) as ws:
        log.info("已连接管理端，开始上报")
        while not stop.is_set():
            payload = build_payload(cfg)
            await ws.send(json.dumps(payload))
            try:
                ack = await asyncio.wait_for(ws.recv(), timeout=cfg.interval)
                status = json.loads(ack).get("status", "?")
            except asyncio.TimeoutError:
                status = "no-ack"
            log.info(
                "已上报 cpu=%.1f%% mem=%.1f%% proc=%d [%s]",
                payload["cpu_percent"],
                payload["mem_percent"],
                payload["process_count"],
                status,
            )
            try:
                await asyncio.wait_for(stop.wait(), timeout=cfg.interval)
            except asyncio.TimeoutError:
                pass


async def _main() -> None:
    cfg = AgentConfig.from_env()
    log.info("启动 mon-agent | agent_id=%s hostname=%s", cfg.agent_id, cfg.hostname)
    log.info("上报目标=%s 间隔=%ss", cfg.server_url, cfg.interval)

    prime()
    await asyncio.sleep(1)  # 让 cpu_percent 建立基线

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows 下部分信号不支持
            signal.signal(sig, lambda *_: stop.set())

    backoff = 1
    while not stop.is_set():
        try:
            await _report_loop(cfg, stop)
        except (OSError, ConnectionClosed, asyncio.TimeoutError) as e:
            log.warning("连接中断：%s，%ss 后重连", e, backoff)
            try:
                await asyncio.wait_for(stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 30)  # 指数退避，最长 30s
        except Exception as e:  # noqa: BLE001
            log.error("未预期异常：%s，%ss 后重连", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        else:
            backoff = 1

    log.info("mon-agent 已停止")


def run() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
