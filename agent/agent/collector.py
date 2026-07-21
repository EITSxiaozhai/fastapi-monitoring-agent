"""指标采集。

使用 psutil 采集 CPU / 内存 / 进程数 / 负载等指标。

容器化部署时，若希望采集宿主机（而非容器）的数据，可将宿主机的
`/proc` 以只读方式挂载进容器，并通过环境变量 `HOST_PROC=/host/proc`
指定路径。psutil 会据此读取宿主机信息，同时容器本身仍保持最小权限。
"""

import os
import platform
import time

import psutil

# 指向宿主机 /proc（若已只读挂载），实现最小权限下的宿主机采集
_host_proc = os.getenv("HOST_PROC")
if _host_proc and os.path.isdir(_host_proc):
    psutil.PROCFS_PATH = _host_proc


def _kernel() -> str:
    uname = platform.uname()
    # 容器与宿主共享内核，release 即宿主内核版本
    return f"{uname.system} {uname.release}"


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
    }


def prime() -> None:
    """预热 cpu_percent（首次调用返回 0，需先建立基线）。"""
    psutil.cpu_percent(interval=None)
