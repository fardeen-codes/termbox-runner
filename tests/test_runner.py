"""Unit and integration tests for task execution engines."""

import pytest
from termbox_runner.models import (
    CommandStep,
    FailureMode,
    ResourceLimits,
    RunManifest,
    RunStatus,
    TaskSubmission,
)
from termbox_runner.runner import DockerTaskExecutor, MockTaskExecutor, get_executor


@pytest.mark.asyncio
async def test_mock_executor_clean_pass():
    executor = MockTaskExecutor()
    task = TaskSubmission(
        main_cmd="python -c 'print(40 + 2)'",
        files={"solution.py": "# mock file"},
    )
    manifest = RunManifest(task=task)
    result = await executor.execute(manifest)

    assert result.status == RunStatus.COMPLETED
    assert result.failure_mode == FailureMode.PASSED
    assert result.exit_code == 0
    assert "42" in result.combined_stdout
    assert len(result.steps) == 1
    assert result.steps[0].step == CommandStep.MAIN


@pytest.mark.asyncio
async def test_mock_executor_oom():
    executor = MockTaskExecutor()
    task = TaskSubmission(
        main_cmd="python -c 'alloc'",
        metadata={"mock_behavior": "oom"},
    )
    manifest = RunManifest(task=task)
    result = await executor.execute(manifest)

    assert result.status == RunStatus.FAILED
    assert result.failure_mode == FailureMode.OOM_KILLED
    assert result.exit_code == 137
    assert result.steps[0].oom_killed is True


@pytest.mark.asyncio
async def test_mock_executor_timeout():
    executor = MockTaskExecutor()
    task = TaskSubmission(
        main_cmd="sleep 100",
        metadata={"mock_behavior": "timeout"},
        limits=ResourceLimits(timeout_seconds=2),
    )
    manifest = RunManifest(task=task)
    result = await executor.execute(manifest)

    assert result.status == RunStatus.FAILED
    assert result.failure_mode == FailureMode.TIMEOUT
    assert result.exit_code == 124
    assert result.steps[0].timed_out is True


@pytest.mark.asyncio
async def test_mock_executor_assertion_failure():
    executor = MockTaskExecutor()
    task = TaskSubmission(
        main_cmd="python agent.py",
        verifier_cmd="pytest tests/",
        metadata={"mock_behavior": "assertion_failed"},
    )
    manifest = RunManifest(task=task)
    result = await executor.execute(manifest)

    assert result.status == RunStatus.FAILED
    assert result.failure_mode == FailureMode.ASSERTION_FAILED
    assert result.exit_code == 1
    assert "AssertionError" in result.failure_reason or "FAILED" in result.combined_stdout


@pytest.mark.asyncio
async def test_mock_executor_setup_error():
    executor = MockTaskExecutor()
    task = TaskSubmission(
        setup_cmd="pip install bad-pkg-fail",
        main_cmd="python agent.py",
        metadata={"mock_behavior": "setup_error"},
    )
    manifest = RunManifest(task=task)
    result = await executor.execute(manifest)

    assert result.status == RunStatus.FAILED
    assert result.failure_mode == FailureMode.SETUP_ERROR
    assert result.steps[0].step == CommandStep.SETUP
    # Main should not have executed if setup failed
    assert len(result.steps) == 1


@pytest.mark.asyncio
async def test_docker_executor_pass_integration():
    docker_exec = DockerTaskExecutor()
    if not docker_exec.is_available():
        pytest.skip("Docker daemon not available for integration test")

    task = TaskSubmission(
        image="python:3.12-slim",
        main_cmd="python -c 'import json; print(json.dumps({\"status\": \"ok\", \"val\": 99}))'",
        files={"config.json": '{"app": "termbox"}'},
    )
    manifest = RunManifest(task=task)
    result = await docker_exec.execute(manifest)

    assert result.status == RunStatus.COMPLETED
    assert result.failure_mode == FailureMode.PASSED
    assert result.exit_code == 0
    assert '"status": "ok"' in result.combined_stdout
    assert result.container_id is not None


@pytest.mark.asyncio
async def test_docker_executor_timeout_enforcement():
    docker_exec = DockerTaskExecutor()
    if not docker_exec.is_available():
        pytest.skip("Docker daemon not available for integration test")

    task = TaskSubmission(
        image="python:3.12-slim",
        main_cmd="sleep 10",
        limits=ResourceLimits(timeout_seconds=1.5),
    )
    manifest = RunManifest(task=task)
    result = await docker_exec.execute(manifest)

    assert result.status == RunStatus.FAILED
    assert result.failure_mode == FailureMode.TIMEOUT
    assert result.steps[0].timed_out is True
    assert result.exit_code == 124


@pytest.mark.asyncio
async def test_docker_executor_oom_enforcement():
    docker_exec = DockerTaskExecutor()
    if not docker_exec.is_available():
        pytest.skip("Docker daemon not available for integration test")

    # Limit to 32MB and allocate 120MB
    task = TaskSubmission(
        image="python:3.12-slim",
        main_cmd="python -c 'b = bytearray(120 * 1024 * 1024)'",
        limits=ResourceLimits(mem_limit="32m", timeout_seconds=10),
    )
    manifest = RunManifest(task=task)
    result = await docker_exec.execute(manifest)

    assert result.status == RunStatus.FAILED
    assert result.failure_mode == FailureMode.OOM_KILLED
    assert result.exit_code == 137


def test_runner_utilities():
    from termbox_runner.runner import sanitize_environment_variables, get_sandbox_hostname, estimate_mock_memory_usage
    
    env = {"API_KEY": "secret123", "SAFE_VAR": "hello"}
    sanitized = sanitize_environment_variables(env)
    assert sanitized["API_KEY"] == "***MASKED***"
    assert sanitized["SAFE_VAR"] == "hello"

    assert get_sandbox_hostname() == "sandbox"


def test_runner_sandboxing_helpers():
    from termbox_runner.runner import (
        build_tmpfs_config,
        get_container_dns_servers,
        build_security_opt,
        calculate_swap_limit,
        calculate_cgroup_cpu_quota,
        parse_inspect_oom_killed,
    )

    tmpfs = build_tmpfs_config(32)
    assert "/tmp" in tmpfs
    assert "size=32m" in tmpfs["/tmp"]

    assert get_container_dns_servers("none") == []

    sec = build_security_opt(True)
    assert "no-new-privileges:true" in sec

    assert calculate_swap_limit(1024) == 1024

    period, quota = calculate_cgroup_cpu_quota(1.5, 100000)
    assert period == 100000
    assert quota == 150000

    assert parse_inspect_oom_killed({"State": {"OOMKilled": True}}) is True
    assert parse_inspect_oom_killed({}) is False


def test_runner_advanced_kwargs_helpers():
    from termbox_runner.runner import (
        is_valid_network_mode,
        enforce_pids_limit_bounds,
        truncate_output_if_needed,
        safe_parse_memory_bytes,
        build_standard_container_kwargs,
    )

    assert is_valid_network_mode("none") is True
    assert is_valid_network_mode("invalid_mode") is False

    assert enforce_pids_limit_bounds(5) == 16
    assert enforce_pids_limit_bounds(100) == 100

    truncated = truncate_output_if_needed("abcdefghij", 5)
    assert "[TRUNCATED]" in truncated

    assert safe_parse_memory_bytes("256m") == 256 * 1024 * 1024
    assert safe_parse_memory_bytes("invalid_format", 123) == 123

    kwargs = build_standard_container_kwargs("python:3.12-slim", "echo 1")
    assert kwargs["image"] == "python:3.12-slim"
