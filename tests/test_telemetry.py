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

def test_telemetry_batch1_helpers():
    from termbox_runner.telemetry import (
        format_prometheus_cpu_seconds,
        format_prometheus_memory_bytes,
        generate_w3c_baggage_header,
        parse_w3c_baggage_header,
        record_lifecycle_timing,
        assign_latency_bucket,
        build_run_audit_event,
        record_memory_swap_metric,
        record_process_count_metric,
    )
    cpu_lines = format_prometheus_cpu_seconds("r1", 0.12, 0.05)
    assert len(cpu_lines) == 2
    mem_line = format_prometheus_memory_bytes("r1", 1048576)
    assert "1048576" in mem_line
    baggage = generate_w3c_baggage_header({"user": "alice", "env": "prod"})
    parsed = parse_w3c_baggage_header(baggage)
    assert parsed["user"] == "alice"
    assert parsed["env"] == "prod"
    timing = record_lifecycle_timing("r1", 10.0, 50.0, 20.0)
    assert timing["total_ms"] == 80.0
    assert assign_latency_bucket(45.0) == 50.0
    audit = build_run_audit_event("r1", "STARTED", {"image": "python"})
    assert audit["run_id"] == "r1"
    assert record_memory_swap_metric("r1", 0)["swap_bytes"] == 0
    assert record_process_count_metric("r1", 4)["pids"] == 4
