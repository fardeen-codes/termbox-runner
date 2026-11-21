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
