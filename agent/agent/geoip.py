"""外网 IP 与所属国家查询（带缓存）。

- 仅通过一次**出站 HTTP 请求**查询公网出口 IP 及国家，属于只读观测，
  不需要任何提权/特权容器。
- 使用标准库 urllib，避免引入额外依赖。
- 结果在进程内缓存，默认每 30 分钟刷新一次（公网 IP 很少变动），
  查询失败时静默降级为上一次结果（或空值），不影响其他指标上报。

可通过环境变量调整：
- GEOIP_ENDPOINT：查询接口（需返回 query/countryCode/country 字段）
- GEOIP_TTL：缓存有效期（秒）
- GEOIP_DISABLE=1：完全关闭外网 IP 查询
"""

import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("mon-agent.geoip")

_DISABLED = os.getenv("GEOIP_DISABLE", "").lower() in ("1", "true", "yes")
_TTL = float(os.getenv("GEOIP_TTL", "1800"))
_ENDPOINT = os.getenv(
    "GEOIP_ENDPOINT",
    "http://ip-api.com/json/?fields=status,message,query,countryCode,country",
)

_cache: dict = {"public_ip": "", "country_code": "", "country": ""}
_fetched_at: float = 0.0


def _fetch() -> dict:
    req = urllib.request.Request(_ENDPOINT, headers={"User-Agent": "mon-agent"})
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 - 固定可信端点
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("status") == "fail":
        raise RuntimeError(data.get("message", "geoip lookup failed"))
    return {
        "public_ip": data.get("query") or "",
        "country_code": (data.get("countryCode") or "").upper(),
        "country": data.get("country") or "",
    }


def refresh(force: bool = False) -> dict:
    """刷新缓存并返回。带 TTL 节流；失败时保留旧值。阻塞调用，建议放入线程池执行。"""
    global _cache, _fetched_at
    if _DISABLED:
        return _cache
    now = time.monotonic()
    if not force and _cache["public_ip"] and (now - _fetched_at) < _TTL:
        return _cache
    try:
        _cache = _fetch()
        _fetched_at = now
        log.info(
            "外网IP=%s 国家=%s(%s)",
            _cache["public_ip"],
            _cache["country"],
            _cache["country_code"],
        )
    except Exception as e:  # noqa: BLE001 - 网络异常时降级，不影响其他指标
        log.warning("获取外网IP失败：%s", e)
    return _cache


def current() -> dict:
    """返回当前缓存（非阻塞）。"""
    return dict(_cache)
