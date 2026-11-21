"""Unit tests for models and schemas."""

import pytest
from pydantic import ValidationError
from termbox_runner.models import (
    CommandStep,
    FailureMode,
    ResourceLimits,
    RunManifest,
    RunStatus,
    StepResult,
    TaskSubmission,
    parse_memory_to_bytes,
)


def test_parse_memory_to_bytes_valid():
    assert parse_memory_to_bytes("512m") == 512 * 1024 * 1024
    assert parse_memory_to_bytes("1g") == 1024 * 1024 * 1024
    assert parse_memory_to_bytes("64k") == 64 * 1024
    assert parse_memory_to_bytes("1048576b") == 1048576
    assert parse_memory_to_bytes("1024") == 1024


def test_parse_memory_to_bytes_invalid():
    with pytest.raises(ValueError):
        parse_memory_to_bytes("invalid_mem")
    with pytest.raises(ValueError):
        parse_memory_to_bytes("-10m")


def test_resource_limits_validation():
    limits = ResourceLimits(mem_limit="256m", timeout_seconds=60, cpu_quota=2.0)
    assert limits.mem_limit == "256m"
    assert limits.timeout_seconds == 60
    assert limits.cpu_quota == 2.0

    # Test mem_limit too low (<16m)
    with pytest.raises(ValidationError):
        ResourceLimits(mem_limit="8m")

    # Test invalid timeout (<1.0)
    with pytest.raises(ValidationError):
        ResourceLimits(timeout_seconds=0.5)

    # Test invalid cpu_quota (<0.1)
    with pytest.raises(ValidationError):
        ResourceLimits(cpu_quota=0.05)


def test_task_submission_defaults():
    sub = TaskSubmission(main_cmd="echo hello")
    assert sub.main_cmd == "echo hello"
    assert sub.setup_cmd is None
    assert sub.verifier_cmd is None
    assert sub.files == {}
    assert sub.environment == {}
    assert sub.limits.mem_limit == "512m"


def test_run_manifest_serialization():
    task = TaskSubmission(
        main_cmd="python main.py",
        files={"main.py": "print('hello')"},
    )
    manifest = RunManifest(task=task)
    assert manifest.run_id.startswith("run_")
    assert manifest.status == RunStatus.QUEUED
    assert manifest.parent_run_id is None

    # Step result addition
    manifest.steps.append(
        StepResult(
            step=CommandStep.MAIN,
            command="python main.py",
            exit_code=0,
            stdout="hello\n",
            duration_ms=12.5,
        )
    )

    # JSON round trip
    json_data = manifest.model_dump_json()
    reconstituted = RunManifest.model_validate_json(json_data)
    assert reconstituted.run_id == manifest.run_id
    assert len(reconstituted.steps) == 1
    assert reconstituted.steps[0].stdout == "hello\n"


def test_task_submission_new_fields():
    sub = TaskSubmission(main_cmd="echo 1", priority=3, git_commit="c0ffee", git_branch="main", workdir="/app")
    assert sub.priority == 3
    assert sub.git_commit == "c0ffee"
    assert sub.git_branch == "main"
    assert sub.workdir == "/app"


def test_manifest_exit_signal_and_step_success():
    task = TaskSubmission(main_cmd="echo 1")
    manifest = RunManifest(task=task, exit_code=137)
    assert manifest.exit_signal == 9
    
    clean = RunManifest(task=task, exit_code=0)
    assert clean.exit_signal is None

    step = StepResult(step=CommandStep.MAIN, command="test", exit_code=0)
    assert step.is_success is True
    step_fail = StepResult(step=CommandStep.MAIN, command="test", exit_code=1)
    assert step_fail.is_success is False
