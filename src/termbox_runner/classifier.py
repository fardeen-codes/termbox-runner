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


def detect_jvm_exception(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Detect Java / JVM fatal errors such as OutOfMemoryError or NullPointerException."""
    lowered = combined_output.lower()
    if "java.lang.outofmemoryerror" in lowered:
        return FailureMode.OOM_KILLED, "JVM heap exhausted (java.lang.OutOfMemoryError)."
    if "java.lang.stackoverflowerror" in lowered:
        return FailureMode.RUNTIME_ERROR, "JVM stack overflow (java.lang.StackOverflowError)."
    if "java.lang.nullpointerexception" in lowered:
        return FailureMode.RUNTIME_ERROR, "Java NullPointerException encountered."
    return None


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

        # Check for index or key lookup error
        if "indexerror: list index out of range" in (step.stderr + " " + step.stdout).lower() or "keyerror:" in (step.stderr + " " + step.stdout).lower():
            return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Index or Key lookup failure."

        # Check for syntax error in Python code
        if "syntaxerror: invalid syntax" in (step.stderr + " " + step.stdout).lower():
            mode = FailureMode.SETUP_ERROR if step.step == CommandStep.SETUP else FailureMode.RUNTIME_ERROR
            return mode, f"Step '{step.step.value}' failed with Python SyntaxError."

        # Check for indentation error
        if "indentationerror:" in (step.stderr + " " + step.stdout).lower():
            mode = FailureMode.SETUP_ERROR if step.step == CommandStep.SETUP else FailureMode.RUNTIME_ERROR
            return mode, f"Step '{step.step.value}' failed with IndentationError."

        # Check for type error
        if "typeerror:" in (step.stderr + " " + step.stdout).lower():
            return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' failed with TypeError."

        # Check for subprocess timeout
        if "timeoutexpired:" in (step.stderr + " " + step.stdout).lower():
            return FailureMode.TIMEOUT, f"Step '{step.step.value}' subprocess timed out (TimeoutExpired)."

        # Check for git merge conflict markers
        if "conflict (content): merge conflict in" in (step.stderr + " " + step.stdout).lower():
            return FailureMode.SETUP_ERROR, "Git merge conflict encountered while preparing patch."

        if 'cannot borrow' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' failed with Rust borrow checker error."
        if 'error[e0425]' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' failed with Rust unresolved name error (E0425)."
        if 'error[e0308]' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' failed with Rust mismatched types error (E0308)."
        if 'panic: runtime error: invalid memory address or nil pointer' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Go nil pointer dereference panic."
        if 'fatal error: concurrent map read and map write' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Go concurrent map access panic."
        if 'panic: runtime error: index out of range' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Go slice index out of range panic."
        if 'unhandledpromiserejection' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Node.js UnhandledPromiseRejection."
        if 'cannot find module' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.SETUP_ERROR if step.step == CommandStep.SETUP else FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' failed with Node.js module resolution failure."
        if 'rangeerror: maximum call stack size exceeded' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' crashed with Node.js call stack overflow."
        if 'std::bad_alloc' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.OOM_KILLED, f"Step '{step.step.value}' threw C++ std::bad_alloc exception."
        if 'std::out_of_range' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' threw C++ std::out_of_range exception."
        if 'assertion failed:' in (step.stderr + ' ' + step.stdout).lower() or 'assert(' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.ASSERTION_FAILED, f"Step '{step.step.value}' failed C/C++ assertion."
        if step.exit_code == 130: return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' terminated by user interrupt (SIGINT, exit 130)."
        if step.exit_code == 141: return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' broken pipe (SIGPIPE, exit 141)."
        if step.exit_code == 143: return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' received graceful termination (SIGTERM, exit 143)."
        if 'errors during collection' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.SETUP_ERROR, f"Step '{step.step.value}' failed during Pytest test collection."
        if 'fixture' in (step.stderr + ' ' + step.stdout).lower() and 'not found' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.SETUP_ERROR, f"Step '{step.step.value}' failed resolving Pytest test fixture."
        if 'unrecognized arguments:' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.SETUP_ERROR, f"Step '{step.step.value}' failed with CLI argument parsing error."
        if 'no space left on device' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' failed with disk quota exceeded (ENOSPC)."
        if 'cannot allocate memory' in (step.stderr + ' ' + step.stdout).lower() or 'resource temporarily unavailable' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' failed with process/fork resource limit (EAGAIN)."
        if 'connection refused' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' network connection refused (ECONNREFUSED)."
        if 'network is unreachable' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' network unreachable (ENETUNREACH)."
        if 'exec format error' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.SETUP_ERROR, f"Step '{step.step.value}' binary architecture incompatible (Exec format error)."
        if 'error while loading shared libraries:' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.SETUP_ERROR, f"Step '{step.step.value}' missing dynamically linked library (.so)."
        if 'core dumped' in (step.stderr + ' ' + step.stdout).lower(): return FailureMode.RUNTIME_ERROR, f"Step '{step.step.value}' process dumped core."
        if 'killed' in (step.stderr + ' ' + step.stdout).lower() and step.exit_code == 137: return FailureMode.OOM_KILLED, f"Step '{step.step.value}' was killed by host kernel (SIGKILL 137)."
        jvm_diag = detect_jvm_exception(step.stderr + " " + step.stdout)
        if jvm_diag:
            mode, msg = jvm_diag
            return mode, f"Step '{step.step.value}' {msg}"
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

def get_failure_severity(failure_mode: Optional[FailureMode]) -> str:
    """Assign alert severity (CRITICAL, HIGH, MEDIUM, LOW, INFO) to failure mode."""
    if not failure_mode or failure_mode == FailureMode.PASSED:
        return "INFO"
    severities = {
        FailureMode.OOM_KILLED: "CRITICAL",
        FailureMode.TIMEOUT: "HIGH",
        FailureMode.SETUP_ERROR: "MEDIUM",
        FailureMode.ASSERTION_FAILED: "LOW",
        FailureMode.RUNTIME_ERROR: "LOW",
    }
    return severities.get(failure_mode, "MEDIUM")

def extract_stacktrace_snippet(stderr_text: str, max_lines: int = 6) -> str:
    """Extract innermost Python stacktrace frames from stderr."""
    lines = stderr_text.splitlines()
    frames = [line for line in lines if "File \"" in line or "line " in line]
    return "\n".join(frames[-max_lines:]) if frames else ""

def get_diagnostic_action_hint(mode: FailureMode) -> str:
    hints = {FailureMode.OOM_KILLED: 'Increase container mem_limit in limits', FailureMode.TIMEOUT: 'Increase timeout_seconds in limits', FailureMode.SETUP_ERROR: 'Check dependency installation in setup_cmd'}
    return hints.get(mode, 'Inspect command execution logs')
def get_failure_mode_doc_url(mode: FailureMode) -> str:
    return f'https://github.com/fardeen-codes/termbox-runner/docs/failures#{mode.value.lower()}'
def clean_error_prefix(text: str) -> str:
    return text.lstrip(' \t\n')


def format_fatal_signal_summary(exit_code: Optional[int]) -> Optional[str]:
    """Return a descriptive explanation of standard Linux fatal signals."""
    if not exit_code or exit_code <= 128:
        return None
    sig = exit_code - 128
    descriptions = {
        6: "Aborted (SIGABRT): Process called abort() or assertion failed.",
        8: "Floating Point Exception (SIGFPE): Arithmetic overflow or divide by zero.",
        9: "Killed (SIGKILL): Hard termination by OS kernel (often OOM killer).",
        11: "Segmentation Fault (SIGSEGV): Invalid memory reference or memory corruption.",
        13: "Broken Pipe (SIGPIPE): Write to pipe with no readers.",
        14: "Alarm Clock (SIGALRM): Timed out waiting for timer signal.",
        15: "Terminated (SIGTERM): Graceful termination request received.",
    }
    return descriptions.get(sig, f"Signal {sig} terminated process.")

def detect_ruby_exception(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Ruby runtime exceptions such as NameError, NoMethodError, or LoadError."""
    lowered = combined_output.lower()
    if "nomethoderror: undefined method" in lowered:
        return FailureMode.RUNTIME_ERROR, "Ruby NoMethodError encountered."
    if "nameerror: uninitialized constant" in lowered:
        return FailureMode.RUNTIME_ERROR, "Ruby NameError uninitialized constant."
    if "loaderror: cannot load such file" in lowered:
        return FailureMode.SETUP_ERROR, "Ruby LoadError missing gem or dependency."
    return None

def detect_php_fatal_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract PHP fatal runtime errors and parse errors."""
    lowered = combined_output.lower()
    if "fatal error: uncaught error:" in lowered or "fatal error: uncaught exception" in lowered:
        return FailureMode.RUNTIME_ERROR, "PHP uncaught fatal exception."
    if "parse error: syntax error" in lowered:
        return FailureMode.RUNTIME_ERROR, "PHP parse syntax error."
    return None

def extract_rust_panic_message(stderr_text: str) -> Optional[str]:
    """Extract panic location and message from Rust backtrace output."""
    for line in stderr_text.splitlines():
        if "panicked at " in line:
            return line.strip()
    return None
