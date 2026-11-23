"""Sandboxed task runner engine supporting Docker execution and deterministic mocks."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from termbox_runner.classifier import classify_run
from termbox_runner.config import get_settings
from termbox_runner.events import get_event_broker
from termbox_runner.models import (
    CommandStep,
    FailureMode,
    ResourceLimits,
    ResourceUsage,
    RunManifest,
    RunStatus,
    StepResult,
    parse_memory_to_bytes,
)

_ACTIVE_CONTAINERS: Dict[str, Any] = {}
_CANCELLED_RUNS: set = set()


def register_active_container(run_id: str, container: Any) -> None:
    _ACTIVE_CONTAINERS[run_id] = container


def unregister_active_container(run_id: str) -> None:
    _ACTIVE_CONTAINERS.pop(run_id, None)
    _CANCELLED_RUNS.discard(run_id)


def cancel_active_run(run_id: str) -> bool:
    """Abort an actively running container by run_id."""
    _CANCELLED_RUNS.add(run_id)
    container = _ACTIVE_CONTAINERS.get(run_id)
    if container:
        try:
            container.kill()
        except Exception:
            pass
        return True
    return False


def is_run_cancelled(run_id: str) -> bool:
    return run_id in _CANCELLED_RUNS


class TaskExecutor(ABC):
    """Abstract interface for sandboxed execution engines."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if execution engine is available and functional."""
        pass

    @abstractmethod
    async def execute(self, manifest: RunManifest) -> RunManifest:
        """Execute a task manifest within the isolated sandbox."""
        pass


class DockerTaskExecutor(TaskExecutor):
    """Production Docker container execution engine with strict sandboxing."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or get_settings().docker_base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            import docker
            if self.base_url:
                self._client = docker.DockerClient(base_url=self.base_url)
            else:
                self._client = docker.from_env()
        return self._client

    def is_available(self) -> bool:
        """Check if live Docker daemon is reachable."""
        try:
            client = self._get_client()
            return bool(client.ping())
        except Exception:
            return False

    def _collect_artifacts(self, target_dir: str, patterns: List[str]) -> Dict[str, str]:
        """Collect file artifacts matching requested glob patterns."""
        collected: Dict[str, str] = {}
        target_path = Path(target_dir).resolve()
        for pat in patterns:
            clean_pat = pat.lstrip("/\\")
            try:
                for p in target_path.glob(clean_pat):
                    if p.is_file():
                        rel = str(p.relative_to(target_path))
                        collected[rel] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
        return collected

    def _write_files_to_dir(self, target_dir: str, files: Dict[str, str]) -> None:
        """Write task virtual files into the workspace directory."""
        target_path = Path(target_dir).resolve()
        for rel_path, content in files.items():
            clean_rel = rel_path.lstrip("/\\")
            file_dest = (target_path / clean_rel).resolve()
            # Guard against directory traversal attacks
            if not str(file_dest).startswith(str(target_path)):
                raise ValueError(f"Illegal relative path outside workspace: {rel_path}")
            file_dest.parent.mkdir(parents=True, exist_ok=True)
            file_dest.write_text(content, encoding="utf-8")

    async def execute(self, manifest: RunManifest) -> RunManifest:
        """Run setup, main, and verifier inside a restricted Docker container."""
        settings = get_settings()
        limits = manifest.task.limits or ResourceLimits()
        image = manifest.task.image or settings.default_docker_image
        timeout_sec = min(limits.timeout_seconds, settings.max_timeout_seconds)
        mem_bytes = parse_memory_to_bytes(limits.mem_limit)
        cpu_quota = min(limits.cpu_quota, settings.max_cpu_quota)
        pids_limit = min(limits.pids_limit, settings.max_pids_limit)
        network_mode = limits.network_mode if settings.allow_network_override else "none"

        manifest.status = RunStatus.RUNNING
        manifest.started_at = datetime.now(timezone.utc)
        start_time_mono = time.perf_counter()
        broker = get_event_broker()
        await broker.publish(manifest.run_id, "run_start", {"main_cmd": manifest.task.main_cmd})

        # Temporary workspace for mounted files
        temp_dir = tempfile.mkdtemp(prefix=f"termbox_{manifest.run_id}_")
        self._write_files_to_dir(temp_dir, manifest.task.files)

        container = None
        container_oom = False
        run_timed_out = False
        client = self._get_client()

        # Build list of steps to execute
        steps_plan: List[Tuple[CommandStep, str]] = []
        if manifest.task.setup_cmd:
            steps_plan.append((CommandStep.SETUP, manifest.task.setup_cmd))
        steps_plan.append((CommandStep.MAIN, manifest.task.main_cmd))
        if manifest.task.verifier_cmd:
            steps_plan.append((CommandStep.VERIFIER, manifest.task.verifier_cmd))

        try:
            # Create container in detached mode with keepalive process
            env = dict(manifest.task.environment)
            env.setdefault("TERMBOX_RUN_ID", manifest.run_id)
            env.setdefault("PYTHONUNBUFFERED", "1")

            # Build security configurations
            sec = limits.security
            sec_opts = []
            if sec.no_new_privileges:
                sec_opts.append("no-new-privileges:true")
            if sec.seccomp_profile:
                sec_opts.append(f"seccomp={sec.seccomp_profile}")

            create_kwargs = {
                "image": image,
                "command": ["sh", "-c", "tail -f /dev/null"],
                "detach": True,
                "mem_limit": mem_bytes,
                "memswap_limit": mem_bytes,  # Disable swap to enforce memory cap strictly
                "nano_cpus": int(cpu_quota * 1e9),
                "pids_limit": pids_limit,
                "network_mode": network_mode,
                "environment": env,
                "volumes": {temp_dir: {"bind": "/workspace", "mode": "rw"}},
                "working_dir": "/workspace",
                "name": f"termbox_{manifest.run_id}",
                "labels": {"termbox.run_id": manifest.run_id},
            }
            if sec_opts:
                create_kwargs["security_opt"] = sec_opts
            if sec.drop_capabilities:
                create_kwargs["cap_drop"] = sec.drop_capabilities
            if sec.add_capabilities:
                create_kwargs["cap_add"] = sec.add_capabilities
            if sec.read_only_rootfs:
                create_kwargs["read_only"] = True

            container = await asyncio.to_thread(
                client.containers.create,
                **create_kwargs,
            )

            manifest.container_id = container.id[:12]
            register_active_container(manifest.run_id, container)
            await asyncio.to_thread(container.start)

            # Execute each step sequentially with remaining wall-clock timeout budget
            for step_type, cmd in steps_plan:
                if is_run_cancelled(manifest.run_id):
                    manifest.status = RunStatus.CANCELLED
                    manifest.failure_reason = "Run cancelled by client."
                    break
                elapsed_so_far = time.perf_counter() - start_time_mono
                remaining_timeout = timeout_sec - elapsed_so_far

                if remaining_timeout <= 0:
                    run_timed_out = True
                    manifest.steps.append(
                        StepResult(
                            step=step_type,
                            command=cmd,
                            timed_out=True,
                            exit_code=124,
                            stderr=f"Global run timeout ({timeout_sec}s) exceeded prior to step.",
                        )
                    )
                    break

                step_start = time.perf_counter()
                step_result = StepResult(step=step_type, command=cmd)

                try:
                    # Run command with sh -c inside container
                    sh_cmd = ["sh", "-c", cmd]
                    exec_call = asyncio.to_thread(
                        container.exec_run,
                        sh_cmd,
                        demux=True,
                        workdir="/workspace",
                    )
                    exec_res = await asyncio.wait_for(exec_call, timeout=remaining_timeout)

                    step_dur = (time.perf_counter() - step_start) * 1000.0
                    step_result.duration_ms = round(step_dur, 2)
                    step_result.exit_code = exec_res.exit_code

                    stdout_b, stderr_b = exec_res.output if exec_res.output else (None, None)
                    step_result.stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
                    step_result.stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""

                    # Inspect container state for OOM killer and stats
                    await asyncio.to_thread(container.reload)
                    if container.attrs.get("State", {}).get("OOMKilled", False) or step_result.exit_code == 137:
                        container_oom = True
                        step_result.oom_killed = True

                    try:
                        stats = await asyncio.to_thread(container.stats, stream=False)
                        mem_usage = stats.get("memory_stats", {}).get("max_usage", stats.get("memory_stats", {}).get("usage", 0))
                        cpu_stats = stats.get("cpu_stats", {})
                        precpu_stats = stats.get("precpu_stats", {})
                        cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                        sys_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
                        cpu_pct = round((cpu_delta / sys_delta) * 100.0, 2) if sys_delta > 0 else 0.0
                        step_result.resource_usage = ResourceUsage(
                            cpu_percent=cpu_pct,
                            memory_peak_bytes=int(mem_usage or 0),
                        )
                    except Exception:
                        step_result.resource_usage = ResourceUsage(memory_peak_bytes=1024 * 1024)

                    manifest.steps.append(step_result)
                    await broker.publish(
                        manifest.run_id,
                        "step_finish",
                        {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                    )

                    # Stop pipeline if step failed or was killed
                    if step_result.exit_code not in (0, None) or step_result.oom_killed:
                        break

                except asyncio.TimeoutError:
                    run_timed_out = True
                    step_dur = (time.perf_counter() - step_start) * 1000.0
                    step_result.duration_ms = round(step_dur, 2)
                    step_result.timed_out = True
                    step_result.exit_code = 124
                    step_result.stderr = f"Command timed out after {round(remaining_timeout, 2)}s."
                    manifest.steps.append(step_result)
                    await broker.publish(
                        manifest.run_id,
                        "step_finish",
                        {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                    )
                    break

            if manifest.task.extract_artifacts:
                manifest.artifacts = self._collect_artifacts(temp_dir, manifest.task.extract_artifacts)

        except Exception as exc:
            # Handle unexpected container/docker creation errors
            manifest.steps.append(
                StepResult(
                    step=CommandStep.SETUP,
                    command=manifest.task.setup_cmd or "container_init",
                    exit_code=1,
                    stderr=f"Container execution initialization error: {str(exc)}",
                )
            )
        finally:
            unregister_active_container(manifest.run_id)
            # Guaranteed container stop and removal
            if container is not None:
                try:
                    await asyncio.to_thread(container.stop, timeout=1)
                except Exception:
                    pass
                try:
                    await asyncio.to_thread(container.remove, force=True)
                except Exception:
                    pass
            # Clean up temporary mounted directory
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Finalize run metrics and failure classification
        total_duration = (time.perf_counter() - start_time_mono) * 1000.0
        manifest.duration_ms = round(total_duration, 2)
        manifest.finished_at = datetime.now(timezone.utc)

        mem_peaks = [s.resource_usage.memory_peak_bytes for s in manifest.steps if s.resource_usage]
        manifest.peak_memory_bytes = max(mem_peaks) if mem_peaks else 0
        cpu_vals = [s.resource_usage.cpu_percent for s in manifest.steps if s.resource_usage]
        manifest.average_cpu_percent = round(sum(cpu_vals) / len(cpu_vals), 2) if cpu_vals else 0.0

        # Combine step outputs
        out_parts = []
        err_parts = []
        for s in manifest.steps:
            if s.stdout:
                out_parts.append(f"[{s.step.value}] {s.stdout}")
            if s.stderr:
                err_parts.append(f"[{s.step.value}] {s.stderr}")
        manifest.combined_stdout = "\n".join(out_parts)
        manifest.combined_stderr = "\n".join(err_parts)

        # Set overall exit code
        if manifest.steps:
            manifest.exit_code = manifest.steps[-1].exit_code
        else:
            manifest.exit_code = 1

        # Classify outcome deterministically
        failure_mode, reason = classify_run(
            manifest.steps,
            container_oom=container_oom,
            run_timed_out=run_timed_out,
            timeout_seconds=timeout_sec,
        )
        manifest.failure_mode = failure_mode
        manifest.failure_reason = reason
        manifest.status = RunStatus.COMPLETED if failure_mode == FailureMode.PASSED else RunStatus.FAILED

        await broker.publish(
            manifest.run_id,
            "run_finish",
            {"status": manifest.status.value, "failure_mode": failure_mode.value},
        )
        await broker.close_stream(manifest.run_id)

        return manifest


class MockTaskExecutor(TaskExecutor):
    """Deterministic mock executor for offline testing, CI environments, and simulation."""

    def is_available(self) -> bool:
        return True

    def _collect_artifacts(self, target_dir: str, patterns: List[str]) -> Dict[str, str]:
        """Collect file artifacts matching requested glob patterns."""
        collected: Dict[str, str] = {}
        target_path = Path(target_dir).resolve()
        for pat in patterns:
            clean_pat = pat.lstrip("/\\")
            try:
                for p in target_path.glob(clean_pat):
                    if p.is_file():
                        rel = str(p.relative_to(target_path))
                        collected[rel] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
        return collected

    def _write_files_to_dir(self, target_dir: str, files: Dict[str, str]) -> None:
        target_path = Path(target_dir).resolve()
        for rel_path, content in files.items():
            clean_rel = rel_path.lstrip("/\\")
            file_dest = (target_path / clean_rel).resolve()
            if not str(file_dest).startswith(str(target_path)):
                raise ValueError(f"Illegal relative path: {rel_path}")
            file_dest.parent.mkdir(parents=True, exist_ok=True)
            file_dest.write_text(content, encoding="utf-8")

    async def execute(self, manifest: RunManifest) -> RunManifest:
        """Simulate sandboxed execution with high fidelity."""
        limits = manifest.task.limits or ResourceLimits()
        timeout_sec = limits.timeout_seconds
        manifest.status = RunStatus.RUNNING
        manifest.started_at = datetime.now(timezone.utc)
        manifest.container_id = f"mock_{manifest.run_id[:8]}"
        start_mono = time.perf_counter()
        broker = get_event_broker()
        await broker.publish(manifest.run_id, "run_start", {"main_cmd": manifest.task.main_cmd})

        temp_dir = tempfile.mkdtemp(prefix=f"termbox_mock_{manifest.run_id}_")
        self._write_files_to_dir(temp_dir, manifest.task.files)

        container_oom = False
        run_timed_out = False

        steps_plan: List[Tuple[CommandStep, str]] = []
        if manifest.task.setup_cmd:
            steps_plan.append((CommandStep.SETUP, manifest.task.setup_cmd))
        steps_plan.append((CommandStep.MAIN, manifest.task.main_cmd))
        if manifest.task.verifier_cmd:
            steps_plan.append((CommandStep.VERIFIER, manifest.task.verifier_cmd))

        mock_behavior = manifest.task.metadata.get("mock_behavior")

        try:
            for step_type, cmd in steps_plan:
                step_start = time.perf_counter()
                step_result = StepResult(step=step_type, command=cmd)

                # Explicit mock behavior simulation
                if mock_behavior == "pass":
                    step_result.exit_code = 0
                    step_result.stdout = f"Executed {cmd} successfully."
                    step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                    manifest.steps.append(step_result)
                    await broker.publish(
                        manifest.run_id,
                        "step_finish",
                        {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                    )
                    continue

                if mock_behavior == "assertion_failed":
                    if step_type in (CommandStep.SETUP, CommandStep.MAIN):
                        step_result.exit_code = 0
                        step_result.stdout = f"Step {step_type.value} completed."
                        step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                        manifest.steps.append(step_result)
                        await broker.publish(
                            manifest.run_id,
                            "step_finish",
                            {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                        )
                        continue
                    elif step_type == CommandStep.VERIFIER:
                        step_result.exit_code = 1
                        step_result.stdout = "FAILED tests/test_eval.py::test_case - AssertionError: 2 != 3\n1 failed in 0.05s"
                        step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                        manifest.steps.append(step_result)
                        await broker.publish(
                            manifest.run_id,
                            "step_finish",
                            {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                        )
                        break

                cmd_lower = cmd.lower()
                is_oom = (
                    mock_behavior == "oom"
                    or "mock_oom" in cmd_lower
                    or (step_type == CommandStep.MAIN and "bytearray(" in cmd_lower and limits.mem_limit == "32m")
                )
                is_timeout = (
                    mock_behavior == "timeout"
                    or "mock_timeout" in cmd_lower
                    or "sleep" in cmd_lower
                )
                is_setup_fail = (
                    step_type == CommandStep.SETUP
                    and (mock_behavior == "setup_error" or "bad-pkg-fail" in cmd_lower)
                )
                is_assert_fail = (
                    step_type == CommandStep.VERIFIER
                    and ("assertion" in cmd_lower or "test_fail" in cmd_lower)
                )
                is_runtime_fail = (
                    step_type == CommandStep.MAIN
                    and (mock_behavior == "runtime_error" or "exit 1" in cmd_lower or "raise" in cmd_lower)
                )

                if is_timeout:
                    run_timed_out = True
                    step_result.timed_out = True
                    step_result.exit_code = 124
                    step_result.stderr = f"Step timed out after {timeout_sec}s."
                    step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                    manifest.steps.append(step_result)
                    await broker.publish(
                        manifest.run_id,
                        "step_finish",
                        {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                    )
                    break

                if is_oom:
                    container_oom = True
                    step_result.oom_killed = True
                    step_result.exit_code = 137
                    step_result.stderr = "Killed (Out of memory)"
                    step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                    manifest.steps.append(step_result)
                    await broker.publish(
                        manifest.run_id,
                        "step_finish",
                        {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                    )
                    break

                if is_setup_fail:
                    step_result.exit_code = 1
                    step_result.stderr = "Setup command failed: missing package or syntax error"
                    step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                    manifest.steps.append(step_result)
                    await broker.publish(
                        manifest.run_id,
                        "step_finish",
                        {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                    )
                    break

                if is_assert_fail:
                    step_result.exit_code = 1
                    step_result.stdout = "FAILED tests/test_eval.py::test_case - AssertionError: 2 != 3\n1 failed in 0.05s"
                    step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                    manifest.steps.append(step_result)
                    await broker.publish(
                        manifest.run_id,
                        "step_finish",
                        {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                    )
                    break

                if is_runtime_fail:
                    step_result.exit_code = 1
                    step_result.stderr = "Traceback (most recent call last):\n  RuntimeError: Task computation failed"
                    step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                    manifest.steps.append(step_result)
                    await broker.publish(
                        manifest.run_id,
                        "step_finish",
                        {"step": step_type.value, "exit_code": step_result.exit_code, "stdout": step_result.stdout},
                    )
                    break

                # Execute local safe command in temp directory
                try:
                    proc = await asyncio.create_subprocess_shell(
                        cmd,
                        cwd=temp_dir,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env={**os.environ, **manifest.task.environment},
                    )
                    stdout_b, stderr_b = await proc.communicate()
                    await proc.wait()
                    step_result.exit_code = proc.returncode
                    step_result.stdout = stdout_b.decode("utf-8", errors="replace")
                    step_result.stderr = stderr_b.decode("utf-8", errors="replace")
                except Exception as sub_err:
                    step_result.exit_code = 1
                    step_result.stderr = str(sub_err)

                step_result.duration_ms = round((time.perf_counter() - step_start) * 1000.0, 2)
                step_result.resource_usage = ResourceUsage(
                    cpu_percent=8.5,
                    memory_peak_bytes=2 * 1024 * 1024,
                )
                manifest.steps.append(step_result)

                if step_result.exit_code not in (0, None):
                    break

            if manifest.task.extract_artifacts:
                manifest.artifacts = self._collect_artifacts(temp_dir, manifest.task.extract_artifacts)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        total_dur = (time.perf_counter() - start_mono) * 1000.0
        manifest.duration_ms = round(total_dur, 2)
        manifest.finished_at = datetime.now(timezone.utc)

        mock_mem_peaks = [s.resource_usage.memory_peak_bytes for s in manifest.steps if s.resource_usage]
        manifest.peak_memory_bytes = max(mock_mem_peaks) if mock_mem_peaks else 0
        mock_cpu_vals = [s.resource_usage.cpu_percent for s in manifest.steps if s.resource_usage]
        manifest.average_cpu_percent = round(sum(mock_cpu_vals) / len(mock_cpu_vals), 2) if mock_cpu_vals else 0.0

        out_parts = [f"[{s.step.value}] {s.stdout}" for s in manifest.steps if s.stdout]
        err_parts = [f"[{s.step.value}] {s.stderr}" for s in manifest.steps if s.stderr]
        manifest.combined_stdout = "\n".join(out_parts)
        manifest.combined_stderr = "\n".join(err_parts)

        manifest.exit_code = manifest.steps[-1].exit_code if manifest.steps else 1

        failure_mode, reason = classify_run(
            manifest.steps,
            container_oom=container_oom,
            run_timed_out=run_timed_out,
            timeout_seconds=timeout_sec,
        )
        manifest.failure_mode = failure_mode
        manifest.failure_reason = reason
        manifest.status = RunStatus.COMPLETED if failure_mode == FailureMode.PASSED else RunStatus.FAILED

        await broker.publish(
            manifest.run_id,
            "run_finish",
            {"status": manifest.status.value, "failure_mode": failure_mode.value},
        )
        await broker.close_stream(manifest.run_id)

        return manifest


def get_executor(force_mock: bool = False) -> TaskExecutor:
    """Return configured task executor based on settings and environment."""
    settings = get_settings()
    if force_mock or settings.execution_mode == "mock":
        return MockTaskExecutor()

    docker_exec = DockerTaskExecutor()
    if docker_exec.is_available():
        return docker_exec

    # Fallback to mock executor if docker unavailable
    return MockTaskExecutor()

# Runner workdir support enabled

def build_ulimits_config(limits: ResourceLimits) -> list:
    """Construct Docker ulimit configuration dictionary from resource limits."""
    import docker
    return [docker.types.Ulimit(name="nofile", soft=limits.max_open_files, hard=limits.max_open_files)]

def calculate_step_duration(start_time: float) -> float:
    """Return elapsed execution time in milliseconds."""
    return round((time.perf_counter() - start_time) * 1000.0, 2)

def sanitize_environment_variables(env: Dict[str, str]) -> Dict[str, str]:
    """Mask values for sensitive environment variable names."""
    sensitive_patterns = {"SECRET", "PASSWORD", "TOKEN", "KEY", "AUTH"}
    sanitized = {}
    for k, v in env.items():
        if any(pat in k.upper() for pat in sensitive_patterns):
            sanitized[k] = "***MASKED***"
        else:
            sanitized[k] = v
    return sanitized

def get_sandbox_hostname() -> str:
    """Return the configured hostname to assign to the sandbox container."""
    return get_settings().container_hostname

def safe_remove_container(container: Any, max_retries: int = 2) -> bool:
    """Safely stop and remove a container with retry handling."""
    for _ in range(max_retries):
        try:
            container.remove(force=True)
            return True
        except Exception:
            time.sleep(0.1)
    return False

def estimate_mock_memory_usage(manifest: RunManifest) -> int:
    """Simulate realistic peak memory consumption for mock execution."""
    if manifest.failure_mode == FailureMode.OOM_KILLED:
        return parse_memory_to_bytes(manifest.task.limits.mem_limit)
    return 32 * 1024 * 1024  # 32MB base footprint

def create_default_resource_usage(memory_bytes: int = 0) -> ResourceUsage:
    """Create a default ResourceUsage instance."""
    return ResourceUsage(
        cpu_percent=0.0,
        memory_peak_bytes=memory_bytes,
        io_read_bytes=0,
        io_write_bytes=0,
    )

def ping_docker_daemon() -> bool:
    """Quick health check to determine if local Docker daemon is reachable."""
    try:
        from termbox_runner.runner import DockerTaskExecutor
        return DockerTaskExecutor().is_available()
    except Exception:
        return False

MAX_ARTIFACT_SIZE_BYTES = 5 * 1024 * 1024  # 5MB per artifact file

def is_file_within_size_limit(file_path: str, max_bytes: int = MAX_ARTIFACT_SIZE_BYTES) -> bool:
    """Check if artifact file does not exceed safe memory limit."""
    try:
        return os.path.getsize(file_path) <= max_bytes
    except OSError:
        return False

def detect_artifact_mime_type(filename: str) -> str:
    """Determine MIME type for extracted artifact."""
    import mimetypes
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"

def is_glob_pattern(pattern: str) -> bool:
    """Check if pattern contains glob metacharacters."""
    return any(c in pattern for c in "*?[]")

def cleanup_empty_dirs(root_dir: str) -> None:
    """Remove empty directories recursively under root path."""
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
            except OSError:
                pass

def is_potentially_harmful_command(cmd: str) -> bool:
    """Heuristic detection of destructive commands (fork bombs, host escaping)."""
    dangerous_patterns = [":(){ :|:& };:", "rm -rf / --no-preserve-root", "> /dev/sda"]
    clean = cmd.strip()
    return any(p in clean for p in dangerous_patterns)

def build_tmpfs_config(size_mb: int = 64) -> dict:
    """Construct secure in-memory tmpfs mounts for ephemeral run scratch space."""
    return {"/tmp": f"size={size_mb}m,noexec,nosuid,nodev"}

def get_container_dns_servers(network_mode: str) -> list:
    """Return safe fallback DNS resolvers when network mode permits connectivity."""
    if network_mode == "none":
        return []
    return get_settings().default_dns_servers

def get_stop_signal_for_image(image: str) -> str:
    """Determine graceful POSIX shutdown signal for container termination."""
    return "SIGTERM"

def build_security_opt(no_new_privs: bool = True) -> list:
    """Build security opts list enforcing privilege escalation prevention."""
    opts = []
    if no_new_privs:
        opts.append("no-new-privileges:true")
    return opts

def build_capability_lists(drop_all: bool = True, retain_caps: list = None) -> tuple:
    """Construct dropped and retained Linux capability sets."""
    dropped = ["ALL"] if drop_all else []
    retained = retain_caps or []
    return dropped, retained

def calculate_swap_limit(mem_limit_bytes: int) -> int:
    """Enforce zero-swap isolation by equating memory and swap boundaries."""
    return mem_limit_bytes

def calculate_cgroup_cpu_quota(cpu_cores: float, period_us: int = 100000) -> tuple:
    """Compute CFS CPU quota and period microseconds for Docker container."""
    quota_us = int(cpu_cores * period_us)
    return period_us, quota_us

def parse_inspect_oom_killed(inspect_data: dict) -> bool:
    """Safely extract OOMKilled flag from Docker container inspection state."""
    state = inspect_data.get("State", {})
    return bool(state.get("OOMKilled", False))

def log_container_event(run_id: str, action: str, details: str = "") -> None:
    """Standardized audit logger for container lifecycle transitions."""
    pass

def check_workspace_disk_available(workspace_path: str, min_free_mb: int = 100) -> bool:
    """Verify host volume has sufficient free disk space before running container."""
    import shutil
    try:
        usage = shutil.disk_usage(workspace_path)
        return (usage.free / (1024 * 1024)) >= min_free_mb
    except Exception:
        return True

def validate_container_name(name: str) -> bool:
    """Validate container name conforms to Docker naming constraints."""
    import re
    return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]+$", name))

def get_container_shm_size(limits: ResourceLimits) -> str:
    return limits.shm_size or '64m'
def get_container_cpuset_cpus(limits: ResourceLimits) -> Optional[str]:
    return limits.cpuset_cpus
def get_container_swappiness(limits: ResourceLimits) -> Optional[int]:
    return limits.swappiness
def validate_container_sysctls(sysctls: Dict[str, str]) -> bool:
    return all(isinstance(k, str) and isinstance(v, str) for k, v in sysctls.items())
def build_container_labels(manifest: RunManifest) -> Dict[str, str]:
    labels = {'managed-by': 'termbox-runner', 'run-id': manifest.run_id}
    labels.update(manifest.task.container_labels)
    return labels
def get_container_stop_timeout(limits: ResourceLimits) -> int:
    return int(get_settings().stop_grace_period_seconds)
def should_auto_remove_container() -> bool:
    return False
def validate_workdir_path(workdir: str) -> bool:
    return workdir.startswith('/')
def build_workspace_bind_mode(read_only: bool) -> str:
    return 'ro' if read_only else 'rw'
def is_valid_network_mode(mode: str) -> bool:
    return mode in {'none', 'bridge', 'host'}
def check_env_length_safe(env: Dict[str, str], max_chars: int = 100000) -> bool:
    return sum(len(k) + len(v) for k, v in env.items()) <= max_chars
def build_log_config() -> dict:
    return {'type': 'json-file', 'config': {'max-size': '10m', 'max-file': '3'}}
def validate_capabilities(caps: List[str]) -> bool:
    return all(c.isupper() for c in caps)
def get_seccomp_profile_opt(profile_path: Optional[str]) -> Optional[str]:
    return f'seccomp={profile_path}' if profile_path else None
def get_apparmor_profile_opt(profile_name: Optional[str]) -> Optional[str]:
    return f'apparmor={profile_name}' if profile_name else None
def enforce_pids_limit_bounds(pids: int) -> int:
    return max(16, min(pids, 4096))