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

def calculate_start_jitter(created_at, started_at) -> float:
    """Calculate scheduling delay in milliseconds between submission and start."""
    if not created_at or not started_at:
        return 0.0
    delta = (started_at - created_at).total_seconds()
    return max(0.0, round(delta * 1000.0, 2))

def format_bytes(num_bytes: int) -> str:
    """Format byte count into human-readable string (KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"

def format_percent(val: float) -> str:
    """Format floating percentage with standard unit."""
    return f"{val:.1f}%"

def generate_traceparent(trace_id: str = None, span_id: str = None) -> str:
    """Generate W3C traceparent header string (version-trace_id-parent_id-flags)."""
    import uuid
    tid = trace_id or uuid.uuid4().hex
    sid = span_id or uuid.uuid4().hex[:16]
    return f"00-{tid}-{sid}-01"

def parse_traceparent(header: str) -> dict:
    """Parse W3C traceparent header into component parts."""
    parts = header.strip().split("-")
    if len(parts) != 4:
        return {}
    return {"version": parts[0], "trace_id": parts[1], "parent_id": parts[2], "flags": parts[3]}

def inject_trace_context_env(traceparent: str) -> dict[str, str]:
    """Inject W3C traceparent into subprocess environment dictionary."""
    return {"TRACEPARENT": traceparent, "OTEL_TRACE_ID": traceparent.split("-")[1]}

def record_rss_metric(run_id: str, rss_bytes: int) -> dict:
    """Construct RSS memory telemetry datapoint."""
    return {"metric": "container_memory_rss_bytes", "run_id": run_id, "value": rss_bytes, "unit": "bytes"}
