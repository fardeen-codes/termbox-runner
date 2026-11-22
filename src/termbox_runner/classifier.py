"""Deterministic failure-mode classification for sandboxed executions."""

from typing import List, Optional, Tuple
from termbox_runner.models import CommandStep, FailureMode, StepResult


def extract_diagnostic_summary(output: str, max_lines: int = 4) -> str:
    """Extract a concise diagnostic summary from output logs."""
    if not output:
        return ""
    lines = [line.strip() for line in output.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    # Return last few non-empty lines which typically contain the root error or assertion
    summary = " | ".join(lines[-max_lines:])
    if len(summary) > 240:
        summary = summary[:237] + "..."
    return summary


def classify_run(
    steps: List[StepResult],
    container_oom: bool = False,
    run_timed_out: bool = False,
    timeout_seconds: Optional[float] = None,
) -> Tuple[FailureMode, str]:
    """Deterministically classify the outcome of a sandboxed execution.

    Classification precedence (highest to lowest):
    1. TIMEOUT: Wall-clock timeout exceeded or step timeout detected (exit code 124 or timed_out flag).
    2. OOM_KILLED: Container OOM signal, oom_killed flag, or exit code 137 (SIGKILL) under memory pressure.
    3. SETUP_ERROR: Setup command failed with non-zero exit code.
    4. ASSERTION_FAILED: Verifier command failed (e.g. pytest assertion failure) or explicit assertion failure.
    5. RUNTIME_ERROR: Main command failed with non-zero exit code.
    6. PASSED: All executed steps completed with exit code 0.
    """
    # 1. TIMEOUT Check
    if run_timed_out:
        t_msg = f" after {timeout_seconds}s" if timeout_seconds else ""
        return FailureMode.TIMEOUT, f"Execution exceeded hard wall-clock timeout{t_msg}."

    for step in steps:
        if step.timed_out or step.exit_code == 124:
            return (
                FailureMode.TIMEOUT,
                f"Step '{step.step.value}' timed out during execution.",
            )

    # 2. OOM_KILLED Check
    if container_oom:
        return FailureMode.OOM_KILLED, "Container was terminated by Docker Out-Of-Memory (OOM) killer."

    for step in steps:
        if step.exit_code == 139:
            return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Segmentation Fault (SIGSEGV, exit code 139)."
        if step.exit_code == 132:
            return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Illegal Instruction (SIGILL, exit code 132)."
        if step.exit_code == 135:
            return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Bus Error (SIGBUS, exit code 135)."
        if step.exit_code == 136:
            return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Floating Point Exception (SIGFPE, exit code 136)."
        if step.exit_code == 126:
            mode = FailureMode.SETUP_ERROR if step.step == CommandStep.SETUP else FailureMode.RUNTIME_ERROR
            return mode, f"Step '{step.step.value}' permission denied or command not executable (exit code 126)."
        if step.exit_code == 127:
            mode = FailureMode.SETUP_ERROR if step.step == CommandStep.SETUP else FailureMode.RUNTIME_ERROR
            return mode, f"Step '{step.step.value}' command not found or binary missing (exit code 127)."

    for step in steps:
        if step.oom_killed:
            return (
                FailureMode.OOM_KILLED,
                f"Step '{step.step.value}' terminated due to out-of-memory (OOM) condition.",
            )
        # Check for Python recursion limit
        if "recursionerror: maximum recursion depth exceeded" in (step.stderr + " " + step.stdout).lower():
            return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' exceeded maximum recursion depth (RecursionError)."

        # Check for missing Python module
        if "modulenotfounderror: no module named" in (step.stderr + " " + step.stdout).lower():
            diag = extract_diagnostic_summary(step.stderr or step.stdout)
            mode = FailureMode.SETUP_ERROR if step.step == CommandStep.SETUP else FailureMode.RUNTIME_ERROR
            return mode, f"Step '{step.step.value}' missing dependency: {diag}"

        # Check for division by zero
        if "zerodivisionerror: division by zero" in (step.stderr + " " + step.stdout).lower():
            return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with ZeroDivisionError: division by zero."

        # Exit code 137 = 128 + 9 (SIGKILL), often OOM when not explicitly timed out
        if step.exit_code == 137:
            combined = (step.stderr + " " + step.stdout).lower()
            if "killed" in combined or "out of memory" in combined or "oom" in combined or not step.timed_out:
                return (
                    FailureMode.OOM_KILLED,
                    f"Step '{step.step.value}' received SIGKILL (exit code 137), likely OOM killed.",
                )

    # Find step results by type
    step_map = {step.step: step for step in steps}

    # 3. SETUP_ERROR Check
    setup_step = step_map.get(CommandStep.SETUP)
    if setup_step and setup_step.exit_code not in (0, None):
        err = extract_diagnostic_summary(setup_step.stderr or setup_step.stdout)
        reason = f"Setup command failed with exit code {setup_step.exit_code}."
        if err:
            reason += f" Details: {err}"
        return FailureMode.SETUP_ERROR, reason

    # 4. ASSERTION_FAILED Check
    # Priority: Verifier step failure represents test / assertion failure
    verifier_step = step_map.get(CommandStep.VERIFIER)
    if verifier_step and verifier_step.exit_code not in (0, None):
        diag = extract_diagnostic_summary(verifier_step.stdout or verifier_step.stderr)
        reason = f"Verifier assertion/evaluation failed with exit code {verifier_step.exit_code}."
        if diag:
            reason += f" Details: {diag}"
        return FailureMode.ASSERTION_FAILED, reason

    # 5. RUNTIME_ERROR Check
    main_step = step_map.get(CommandStep.MAIN)
    if main_step and main_step.exit_code not in (0, None):
        output = main_step.stderr or main_step.stdout
        # If no separate verifier was provided and main step failed with AssertionError or pytest failure
        lower_out = output.lower()
        if (
            not verifier_step
            and ("assertionerror" in lower_out or "assert " in lower_out or "failed (" in lower_out or "pytest" in main_step.command.lower())
        ):
            diag = extract_diagnostic_summary(output)
            reason = f"Task assertion failed in main command with exit code {main_step.exit_code}."
            if diag:
                reason += f" Details: {diag}"
            return FailureMode.ASSERTION_FAILED, reason

        diag = extract_diagnostic_summary(output)
        reason = f"Main command terminated with runtime error (exit code {main_step.exit_code})."
        if diag:
            reason += f" Details: {diag}"
        return FailureMode.RUNTIME_ERROR, reason

    # If any other step had non-zero exit code
    for step in steps:
        if step.exit_code not in (0, None):
            diag = extract_diagnostic_summary(step.stderr or step.stdout)
            return (
                FailureMode.RUNTIME_ERROR,
                f"Step '{step.step.value}' failed with exit code {step.exit_code}. Details: {diag}",
            )

    # 6. PASSED
    return FailureMode.PASSED, "All sandbox commands completed successfully."


def describe_signal(exit_code: int) -> Optional[str]:
    """Return the human-readable POSIX signal name for exit codes > 128."""
    if exit_code <= 128:
        return None
    sig = exit_code - 128
    signals = {
        1: "SIGHUP", 2: "SIGINT", 3: "SIGQUIT", 4: "SIGILL", 6: "SIGABRT",
        8: "SIGFPE", 9: "SIGKILL", 11: "SIGSEGV", 13: "SIGPIPE", 14: "SIGALRM", 15: "SIGTERM"
    }
    return signals.get(sig, f"SIG#{sig}")
