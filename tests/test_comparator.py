"""Tests for run comparator and differential engine."""

import pytest
from httpx import AsyncClient
from termbox_runner.comparator import compare_runs
from termbox_runner.models import FailureMode, RunManifest, RunStatus, TaskSubmission


def test_compare_runs_unit():
    task_a = TaskSubmission(main_cmd="echo 'version 1'")
    run_a = RunManifest(
        task=task_a,
        status=RunStatus.FAILED,
        failure_mode=FailureMode.RUNTIME_ERROR,
        exit_code=1,
        duration_ms=100.0,
        combined_stdout="version 1\n",
        peak_memory_bytes=1000,
    )

    task_b = TaskSubmission(main_cmd="echo 'version 2'")
    run_b = RunManifest(
        task=task_b,
        status=RunStatus.COMPLETED,
        failure_mode=FailureMode.PASSED,
        exit_code=0,
        duration_ms=150.0,
        combined_stdout="version 2\n",
        peak_memory_bytes=2000,
    )

    diff = compare_runs(run_a, run_b)
    assert diff.status_changed is True
    assert diff.exit_code_diff == (1, 0)
    assert diff.duration_diff_ms == 50.0
    assert diff.peak_memory_diff_bytes == 1000
    assert "version 1" in diff.stdout_unified_diff
    assert "version 2" in diff.stdout_unified_diff


@pytest.mark.asyncio
async def test_compare_runs_api(async_client: AsyncClient):
    r1 = await async_client.post("/runs", json={"main_cmd": "echo A"})
    r2 = await async_client.post("/runs", json={"main_cmd": "echo B"})
    id1 = r1.json()["run_id"]
    id2 = r2.json()["run_id"]

    res = await async_client.get(f"/runs/{id1}/diff/{id2}")
    assert res.status_code == 200
    diff_data = res.json()
    assert diff_data["run_a_id"] == id1
    assert diff_data["run_b_id"] == id2
    assert "command_diff" in diff_data


def test_comparator_utilities():
    from termbox_runner.comparator import (
        calculate_duration_delta_percent,
        generate_stdout_diff,
        detect_exit_code_change,
        compute_memory_delta,
        format_diff_line,
    )

    assert calculate_duration_delta_percent(100.0, 150.0) == 50.0
    assert detect_exit_code_change(0, 1) is True
    assert detect_exit_code_change(0, 0) is False

    assert compute_memory_delta(1024, 2048) == 1024

    diff = generate_stdout_diff("hello\n", "world\n")
    assert "-hello" in diff
    assert "+world" in diff

    assert format_diff_line("+added").startswith("[ADD]")
    assert format_diff_line("-deleted").startswith("[DEL]")
