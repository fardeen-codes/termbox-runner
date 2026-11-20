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
