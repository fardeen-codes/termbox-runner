"""Run comparison and differential telemetry analysis."""

import difflib
from termbox_runner.models import RunDiffResult, RunManifest


def compare_runs(run_a: RunManifest, run_b: RunManifest) -> RunDiffResult:
    """Compute unified diffs and delta telemetry between two executions."""
    # Stdout diff
    a_lines = run_a.combined_stdout.splitlines(keepends=True)
    b_lines = run_b.combined_stdout.splitlines(keepends=True)
    stdout_diff = "".join(
        difflib.unified_diff(a_lines, b_lines, fromfile=f"{run_a.run_id}.stdout", tofile=f"{run_b.run_id}.stdout")
    )

    # Stderr diff
    a_err = run_a.combined_stderr.splitlines(keepends=True)
    b_err = run_b.combined_stderr.splitlines(keepends=True)
    stderr_diff = "".join(
        difflib.unified_diff(a_err, b_err, fromfile=f"{run_a.run_id}.stderr", tofile=f"{run_b.run_id}.stderr")
    )

    return RunDiffResult(
        run_a_id=run_a.run_id,
        run_b_id=run_b.run_id,
        status_changed=(run_a.status != run_b.status or run_a.failure_mode != run_b.failure_mode),
        failure_mode_a=run_a.failure_mode,
        failure_mode_b=run_b.failure_mode,
        exit_code_diff=(run_a.exit_code, run_b.exit_code),
        duration_diff_ms=round(run_b.duration_ms - run_a.duration_ms, 2),
        peak_memory_diff_bytes=run_b.peak_memory_bytes - run_a.peak_memory_bytes,
        stdout_unified_diff=stdout_diff,
        stderr_unified_diff=stderr_diff,
        command_diff=(run_a.task.main_cmd, run_b.task.main_cmd),
    )
