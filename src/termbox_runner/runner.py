"""Sandboxed task runner engine supporting Docker execution and deterministic mocks."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Dict, List, Optional, Tuple

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
            await asyncio.to_thread(container.start)

            # Execute each step sequentially with remaining wall-clock timeout budget
            for step_type, cmd in steps_plan:
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
