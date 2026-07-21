"""指标采集。

使用 psutil 采集 CPU / 内存 / 进程数 / 负载 / 磁盘 / 网络IO / TCP连接 / Top进程 等指标。

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

import psutil

# 指向宿主机 /proc（若已只读挂载），实现最小权限下的宿主机采集
_host_proc = os.getenv("HOST_PROC")
if _host_proc and os.path.isdir(_host_proc):
    psutil.PROCFS_PATH = _host_proc

# 磁盘统计路径（默认容器自身根分区；可指向只读挂载的宿主机路径）
_disk_path = os.getenv("DISK_PATH") or ("C:\\" if os.name == "nt" else "/")

# Top 进程数量
_top_n = int(os.getenv("TOP_N", "5"))

# 用于计算网络 IO 速率的上一次采样：(时间戳, 累计发送, 累计接收)
_prev_net: tuple[float, int, int] | None = None


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


def _net_rate() -> tuple[float, float, int, int]:
    """返回 (发送速率B/s, 接收速率B/s, 累计发送B, 累计接收B)。"""
    global _prev_net
    try:
        io = psutil.net_io_counters()
    except Exception:  # noqa: BLE001
        return 0.0, 0.0, 0, 0
    now = time.monotonic()
    sent_rate = recv_rate = 0.0
    if _prev_net is not None:
        prev_t, prev_s, prev_r = _prev_net
        elapsed = now - prev_t
        if elapsed > 0:
            sent_rate = max(0.0, (io.bytes_sent - prev_s) / elapsed)
            recv_rate = max(0.0, (io.bytes_recv - prev_r) / elapsed)
    _prev_net = (now, io.bytes_sent, io.bytes_recv)
    return round(sent_rate, 1), round(recv_rate, 1), io.bytes_sent, io.bytes_recv


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
    net_sent_rate, net_recv_rate, net_bytes_sent, net_bytes_recv = _net_rate()
    tcp_connections, tcp_established = _tcp()

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
        # 网络 IO
        "net_sent_rate": net_sent_rate,
        "net_recv_rate": net_recv_rate,
        "net_bytes_sent": net_bytes_sent,
        "net_bytes_recv": net_bytes_recv,
        # TCP 连接
        "tcp_connections": tcp_connections,
        "tcp_established": tcp_established,
        # Top 进程
        "top_processes": _top_processes(_top_n),
    }


def prime() -> None:
    """预热 cpu_percent 与网络速率基线（首次调用返回 0，需先建立基线）。"""
    psutil.cpu_percent(interval=None)
    _net_rate()
