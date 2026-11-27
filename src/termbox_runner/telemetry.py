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

def record_disk_io_metric(run_id: str, read_bytes: int, write_bytes: int) -> dict:
    """Construct disk I/O telemetry datapoint."""
    return {"metric": "container_disk_io_bytes", "run_id": run_id, "read_bytes": read_bytes, "write_bytes": write_bytes}

def record_network_drop_metric(run_id: str, drops: int) -> dict:
    """Construct dropped packets telemetry datapoint."""
    return {"metric": "container_network_drops_total", "run_id": run_id, "drops": drops}

def calculate_percentile_buckets(durations: list[float]) -> dict[str, float]:
    """Compute p25, p50, p75, p90, p95, p99 percentile distribution."""
    if not durations:
        return {"p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
    s = sorted(durations)
    n = len(s)
    def pct(p): return s[min(int(n * p), n - 1)]
    return {"p25": pct(0.25), "p50": pct(0.50), "p75": pct(0.75), "p90": pct(0.90), "p95": pct(0.95), "p99": pct(0.99)}

def format_prometheus_histogram_buckets(metric_name: str, buckets: dict[float, int]) -> list[str]:
    """Format histogram buckets into standard Prometheus exposition format."""
    lines = []
    for le, count in sorted(buckets.items()):
        lines.append(f'{metric_name}_bucket{{le="{le}"}} {count}')
    return lines

def format_audit_log_entry(action: str, actor: str, target: str, status: str) -> str:
    """Format audit event into single-line JSON log."""
    import json
    from datetime import datetime, timezone
    return json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor": actor,
        "target": target,
        "status": status
    })

def generate_correlation_id() -> str:
    """Generate correlation ID for request tracing."""
    import uuid
    return f"corr_{uuid.uuid4().hex[:12]}"

def mask_sensitive_env_vars(env: dict[str, str], secret_keys: list[str] = None) -> dict[str, str]:
    """Mask passwords, tokens, and secrets in environment dictionary."""
    secrets = {"token", "key", "secret", "password", "auth", "credential"}
    if secret_keys:
        secrets.update(k.lower() for k in secret_keys)
    masked = {}
    for k, v in env.items():
        if any(s in k.lower() for s in secrets):
            masked[k] = "********"
        else:
            masked[k] = v
    return masked

def record_page_faults_metric(run_id: str, major_faults: int, minor_faults: int) -> dict:
    """Construct memory page faults telemetry datapoint."""
    return {
        "metric": "container_page_faults_total",
        "run_id": run_id,
        "major_faults": major_faults,
        "minor_faults": minor_faults
    }

def format_prometheus_cpu_seconds(run_id: str, user_sec: float, sys_sec: float) -> list[str]:
    """Format user and system CPU seconds in Prometheus gauge format."""
    return [
        f'termbox_container_cpu_user_seconds_total{{run_id="{run_id}"}} {user_sec:.4f}',
        f'termbox_container_cpu_system_seconds_total{{run_id="{run_id}"}} {sys_sec:.4f}'
    ]

def format_prometheus_memory_bytes(run_id: str, peak_bytes: int) -> str:
    """Format peak container memory usage in Prometheus gauge format."""
    return f'termbox_container_memory_peak_bytes{{run_id="{run_id}"}} {peak_bytes}'

def generate_w3c_baggage_header(items: dict[str, str]) -> str:
    """Generate W3C baggage header from key-value pairs."""
    return ", ".join(f"{k}={v}" for k, v in sorted(items.items()))

def parse_w3c_baggage_header(header: str) -> dict[str, str]:
    """Parse W3C baggage header into key-value dictionary."""
    res = {}
    for part in header.split(","):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            res[k] = v
    return res
