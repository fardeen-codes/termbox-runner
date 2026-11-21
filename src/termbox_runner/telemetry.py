"""System resource telemetry, performance profiling, and metric calculation helpers."""

import os
from typing import Tuple


def get_system_load_average() -> Tuple[float, float, float]:
    """Return 1-minute, 5-minute, and 15-minute system load averages."""
    try:
        return os.getloadavg()
    except (AttributeError, OSError):
        return (0.0, 0.0, 0.0)

def calculate_memory_percent(peak_bytes: int, limit_bytes: int) -> float:
    """Calculate percentage of allocated memory limit consumed."""
    if limit_bytes <= 0:
        return 0.0
    return round((peak_bytes / limit_bytes) * 100.0, 2)

def estimate_disk_throughput(io_bytes: int, duration_ms: float) -> float:
    """Estimate IO throughput in megabytes per second (MB/s)."""
    if duration_ms <= 0:
        return 0.0
    duration_s = duration_ms / 1000.0
    return round((io_bytes / (1024 * 1024)) / duration_s, 2)
