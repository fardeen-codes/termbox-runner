"""Tests for execution resource usage telemetry."""

import pytest
from termbox_runner.models import RunManifest, TaskSubmission
from termbox_runner.runner import MockTaskExecutor


@pytest.mark.asyncio
async def test_resource_usage_telemetry():
    executor = MockTaskExecutor()
    task = TaskSubmission(main_cmd="python -c 'print(1)'")
    manifest = RunManifest(task=task)
    result = await executor.execute(manifest)

    assert result.peak_memory_bytes > 0
    assert result.average_cpu_percent > 0.0
    assert len(result.steps) == 1
    assert result.steps[0].resource_usage is not None
    assert result.steps[0].resource_usage.memory_peak_bytes > 0


def test_telemetry_helpers():
    from termbox_runner.telemetry import (
        calculate_memory_percent,
        estimate_disk_throughput,
        format_bytes,
        format_percent,
        get_system_load_average,
    )

    assert calculate_memory_percent(256 * 1024 * 1024, 512 * 1024 * 1024) == 50.0
    assert calculate_memory_percent(10, 0) == 0.0

    tp = estimate_disk_throughput(10 * 1024 * 1024, 1000.0)
    assert tp == 10.0

    assert format_bytes(500) == "500 B"
    assert "KB" in format_bytes(2048)
    assert "MB" in format_bytes(10 * 1024 * 1024)

    assert format_percent(42.56) == "42.6%"

    load = get_system_load_average()
    assert len(load) == 3

def test_telemetry_part1_utilities():
    from termbox_runner.telemetry import (
        generate_traceparent,
        parse_traceparent,
        inject_trace_context_env,
        record_rss_metric,
        record_disk_io_metric,
        record_network_drop_metric,
        calculate_percentile_buckets,
        format_prometheus_histogram_buckets,
        format_audit_log_entry,
        generate_correlation_id,
        mask_sensitive_env_vars,
    )
    tp = generate_traceparent()
    parsed = parse_traceparent(tp)
    assert "trace_id" in parsed
    assert "TRACEPARENT" in inject_trace_context_env(tp)
    assert record_rss_metric("r1", 1024)["value"] == 1024
    assert record_disk_io_metric("r1", 50, 100)["write_bytes"] == 100
    assert record_network_drop_metric("r1", 3)["drops"] == 3
    buckets = calculate_percentile_buckets([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    assert buckets["p50"] >= 50
    lines = format_prometheus_histogram_buckets("test_hist", {0.1: 5, 0.5: 10})
    assert len(lines) == 2
    audit = format_audit_log_entry("login", "admin", "runner", "SUCCESS")
    assert "admin" in audit
    assert generate_correlation_id().startswith("corr_")
    masked = mask_sensitive_env_vars({"API_KEY": "secret123", "PORT": "8000"})
    assert masked["API_KEY"] == "********"
    assert masked["PORT"] == "8000"
