"""指标采集。

使用 psutil 采集 CPU / 内存 / 进程数 / 负载 / 磁盘 / 网络IO与质量 / TCP连接 / Top进程 等指标。

安全与最小权限原则：
- 本采集器只做**只读**观测，不需要任何提权、特权容器或 host PID 命名空间。
- 容器化部署时，若希望采集宿主机（而非容器）的数据，可将宿主机的 `/proc`
  以**只读**方式挂载进容器，并通过环境变量 `HOST_PROC=/host/proc` 指定路径；
  psutil 会据此读取宿主机的 CPU/内存/进程/网络/TCP 信息。这属于只读观测，
  不构成容器逃逸。
- 磁盘使用率默认统计容器自身可见的文件系统；如需统计宿主机磁盘，可将宿主机
  目录**只读**挂载进容器（如 `-v /:/host/root:ro`），并设置 `DISK_PATH=/host/root`。
"""

import os
import platform
import time
from pathlib import Path

import psutil

from . import geoip

# 指向宿主机 /proc（若已只读挂载），实现最小权限下的宿主机采集
_host_proc = os.getenv("HOST_PROC")
if _host_proc and os.path.isdir(_host_proc):
    psutil.PROCFS_PATH = _host_proc

# 磁盘统计路径（默认容器自身根分区；可指向只读挂载的宿主机路径）
_disk_path = os.getenv("DISK_PATH") or ("C:\\" if os.name == "nt" else "/")

# Top 进程数量
_top_n = int(os.getenv("TOP_N", "5"))

# 网络采样基线：(时间戳, bytes_sent, bytes_recv, errin, errout, dropin, dropout, tcp_retrans)
_prev_net: tuple[float, int, int, int, int, int, int, int] | None = None


def _kernel() -> str:
    uname = platform.uname()
    # 容器与宿主共享内核，release 即宿主内核版本
    return f"{uname.system} {uname.release}"


def _disk() -> tuple[int, int, float]:
    try:
        du = psutil.disk_usage(_disk_path)
        return du.total, du.used, du.percent
    except Exception:  # noqa: BLE001
        return 0, 0, 0.0


def _tcp_retrans_total() -> int:
    """读取 TCP 累计重传段数（Linux: /proc/net/snmp 的 RetransSegs）。只读，无需提权。"""
    proc = getattr(psutil, "PROCFS_PATH", "/proc")
    path = os.path.join(proc, "net", "snmp")
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return 0
    header: list[str] | None = None
    for line in lines:
        if not line.startswith("Tcp:"):
            continue
        parts = line.split()[1:]
        if header is None:
            header = parts
            continue
        if header and "RetransSegs" in header:
            idx = header.index("RetransSegs")
            if idx < len(parts):
                try:
                    return int(parts[idx])
                except ValueError:
                    return 0
    return 0


def _net_quality() -> dict:
    """采集网络吞吐与质量指标（只读 net_io_counters + /proc/net/snmp）。

    返回速率（/s）与累计计数：
    - 吞吐：net_sent_rate / net_recv_rate / net_bytes_*
    - 错误：net_errin / net_errout 及对应速率
    - 丢包：net_dropin / net_dropout 及对应速率
    - TCP 重传：tcp_retrans / tcp_retrans_rate（非 Linux 时为 0）
    """
    global _prev_net
    empty = {
        "net_sent_rate": 0.0,
        "net_recv_rate": 0.0,
        "net_bytes_sent": 0,
        "net_bytes_recv": 0,
        "net_errin": 0,
        "net_errout": 0,
        "net_dropin": 0,
        "net_dropout": 0,
        "net_errin_rate": 0.0,
        "net_errout_rate": 0.0,
        "net_dropin_rate": 0.0,
        "net_dropout_rate": 0.0,
        "tcp_retrans": 0,
        "tcp_retrans_rate": 0.0,
    }
    try:
        io = psutil.net_io_counters()
    except Exception:  # noqa: BLE001
        return empty

    errin = int(getattr(io, "errin", 0) or 0)
    errout = int(getattr(io, "errout", 0) or 0)
    dropin = int(getattr(io, "dropin", 0) or 0)
    dropout = int(getattr(io, "dropout", 0) or 0)
    retrans = _tcp_retrans_total()
    now = time.monotonic()

    sent_rate = recv_rate = 0.0
    errin_rate = errout_rate = dropin_rate = dropout_rate = retrans_rate = 0.0
    if _prev_net is not None:
        prev_t, prev_s, prev_r, prev_ei, prev_eo, prev_di, prev_do, prev_rt = _prev_net
        elapsed = now - prev_t
        if elapsed > 0:

            def _rate(cur: int, prev: int) -> float:
                return max(0.0, (cur - prev) / elapsed)

            sent_rate = _rate(io.bytes_sent, prev_s)
            recv_rate = _rate(io.bytes_recv, prev_r)
            errin_rate = _rate(errin, prev_ei)
            errout_rate = _rate(errout, prev_eo)
            dropin_rate = _rate(dropin, prev_di)
            dropout_rate = _rate(dropout, prev_do)
            retrans_rate = _rate(retrans, prev_rt)

    _prev_net = (
        now,
        io.bytes_sent,
        io.bytes_recv,
        errin,
        errout,
        dropin,
        dropout,
        retrans,
    )
    return {
        "net_sent_rate": round(sent_rate, 1),
        "net_recv_rate": round(recv_rate, 1),
        "net_bytes_sent": io.bytes_sent,
        "net_bytes_recv": io.bytes_recv,
        "net_errin": errin,
        "net_errout": errout,
        "net_dropin": dropin,
        "net_dropout": dropout,
        "net_errin_rate": round(errin_rate, 2),
        "net_errout_rate": round(errout_rate, 2),
        "net_dropin_rate": round(dropin_rate, 2),
        "net_dropout_rate": round(dropout_rate, 2),
        "tcp_retrans": retrans,
        "tcp_retrans_rate": round(retrans_rate, 2),
    }


def _tcp() -> tuple[int, int]:
    """返回 (TCP 连接总数, ESTABLISHED 连接数)。只读 /proc/net/tcp，无需提权。"""
    try:
        conns = psutil.net_connections(kind="tcp")
        total = len(conns)
        established = sum(1 for c in conns if c.status == "ESTABLISHED")
        return total, established
    except Exception:  # noqa: BLE001 - 权限不足时降级为 0，不影响其他指标
        return 0, 0


def _top_processes(n: int) -> list[dict]:
    """按 CPU 使用率返回前 n 个进程。只读进程表，无需提权。"""
    procs = list(psutil.process_iter(["pid", "name", "memory_percent"]))
    # cpu_percent 首次调用建立基线，短暂采样后再读取
    for p in procs:
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.1)
    ncpu = psutil.cpu_count() or 1
    # Windows 的 System Idle Process(pid 0) 表示空闲 CPU，会误报为最高占用，过滤掉
    _skip = {"System Idle Process"}
    result: list[dict] = []
    for p in procs:
        try:
            info = p.info
            if info["pid"] == 0 or (info.get("name") or "") in _skip:
                continue
            cpu = p.cpu_percent(None) / ncpu
            result.append(
                {
                    "pid": info["pid"],
                    "name": (info.get("name") or "?")[:64],
                    "cpu_percent": round(cpu, 1),
                    "mem_percent": round(info.get("memory_percent") or 0.0, 1),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    result.sort(key=lambda x: x["cpu_percent"], reverse=True)
    return result[:n]


def collect() -> dict:
    """采集一次快照。返回可直接上报的字典。"""
    vm = psutil.virtual_memory()

    try:
        load1 = os.getloadavg()[0]
    except (OSError, AttributeError):
        # Windows 无 loadavg，退化为 CPU 使用率的近似
        load1 = psutil.cpu_percent(interval=None) / 100.0 * psutil.cpu_count()

    try:
        boot = psutil.boot_time()
        uptime = int(time.time() - boot)
    except Exception:  # noqa: BLE001
        uptime = 0

    disk_total, disk_used, disk_percent = _disk()
    net = _net_quality()
    tcp_connections, tcp_established = _tcp()
    geo = geoip.current()

    return {
        "os": platform.system(),
        "kernel": _kernel(),
        "arch": platform.machine(),
        "cpu_count": psutil.cpu_count() or 0,
        "cpu_percent": psutil.cpu_percent(interval=None),
        "mem_total": vm.total,
        "mem_used": vm.total - vm.available,
        "mem_percent": vm.percent,
        "process_count": len(psutil.pids()),
        "load1": round(load1, 2),
        "uptime_seconds": uptime,
        # 磁盘
        "disk_total": disk_total,
        "disk_used": disk_used,
        "disk_percent": disk_percent,
        # 网络 IO + 质量（错误/丢包/TCP重传）
        **net,
        # TCP 连接
        "tcp_connections": tcp_connections,
        "tcp_established": tcp_established,
        # Top 进程
        "top_processes": _top_processes(_top_n),
        # 外网 IP 与所属国家
        "public_ip": geo["public_ip"],
        "country_code": geo["country_code"],
        "country": geo["country"],
    }


def prime() -> None:
    """预热 cpu_percent 与网络质量基线（首次调用返回 0，需先建立基线）。"""
    psutil.cpu_percent(interval=None)
    _net_quality()
