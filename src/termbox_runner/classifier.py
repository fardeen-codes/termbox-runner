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
    if "nomethoderror" in lowered:
        return FailureMode.RUNTIME_ERROR, "Ruby NoMethodError encountered."
    if "nameerror" in lowered:
        return FailureMode.RUNTIME_ERROR, "Ruby NameError uninitialized constant."
    if "loaderror" in lowered:
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

def detect_go_deadlock(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Detect Go fatal runtime deadlock where all goroutines are asleep."""
    if "fatal error: all goroutines are asleep - deadlock!" in combined_output.lower():
        return FailureMode.RUNTIME_ERROR, "Go concurrency deadlock (all goroutines asleep)."
    return None

def detect_haskell_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Detect Haskell GHC type or syntax errors."""
    lowered = combined_output.lower()
    if "couldn't match expected type" in lowered:
        return FailureMode.RUNTIME_ERROR, "Haskell type mismatch error."
    if "parse error on input" in lowered:
        return FailureMode.RUNTIME_ERROR, "Haskell syntax parse error."
    return None

def detect_ocaml_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Detect OCaml fatal runtime exceptions."""
    lowered = combined_output.lower()
    if "fatal error: exception" in lowered:
        return FailureMode.RUNTIME_ERROR, "OCaml unhandled fatal exception."
    if "syntax error" in lowered and "ocaml" in lowered:
        return FailureMode.RUNTIME_ERROR, "OCaml syntax error."
    return None

def detect_zig_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Detect Zig panic or compiler error."""
    lowered = combined_output.lower()
    if "panic: reached unreachable code" in lowered or "thread panicked" in lowered and "zig" in lowered:
        return FailureMode.RUNTIME_ERROR, "Zig unreachable code reached panic."
    if "error: expected type" in lowered and ".zig:" in lowered:
        return FailureMode.RUNTIME_ERROR, "Zig type mismatch compile error."
    return None

def detect_asan_violation(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Detect LLVM AddressSanitizer (ASan) memory safety violations."""
    lowered = combined_output.lower()
    if "addresssanitizer: heap-buffer-overflow" in lowered:
        return FailureMode.RUNTIME_ERROR, "AddressSanitizer: heap-buffer-overflow detected."
    if "addresssanitizer: use-after-free" in lowered:
        return FailureMode.RUNTIME_ERROR, "AddressSanitizer: use-after-free detected."
    if "leakspan: detected memory leaks" in lowered or "detected memory leaks" in lowered:
        return FailureMode.RUNTIME_ERROR, "AddressSanitizer: memory leak detected."
    return None

def detect_perl_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Perl runtime die or compilation errors."""
    lowered = combined_output.lower()
    if "syntax error at " in lowered and ".pl line" in lowered:
        return FailureMode.RUNTIME_ERROR, "Perl syntax error encountered."
    if "can't locate " in lowered and ".pm in @inc" in lowered:
        return FailureMode.SETUP_ERROR, "Perl missing module dependency."
    if "died at " in lowered:
        return FailureMode.RUNTIME_ERROR, "Perl fatal die exception."
    return None

def detect_r_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract R runtime errors such as subscript out of bounds or stop()."""
    lowered = combined_output.lower()
    if "error: subscript out of bounds" in lowered:
        return FailureMode.RUNTIME_ERROR, "R subscript out of bounds error."
    if "error in " in lowered and "could not find function" in lowered:
        return FailureMode.RUNTIME_ERROR, "R undefined function error."
    return None

def detect_julia_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Julia BoundsError, MethodError, or UndefVarError."""
    lowered = combined_output.lower()
    if "boundserror: attempt to access" in lowered:
        return FailureMode.RUNTIME_ERROR, "Julia BoundsError encountered."
    if "methoderror: no method matching" in lowered:
        return FailureMode.RUNTIME_ERROR, "Julia MethodError encountered."
    if "undefvarerror:" in lowered:
        return FailureMode.RUNTIME_ERROR, "Julia UndefVarError encountered."
    return None

def detect_scala_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Scala pattern matching errors."""
    lowered = combined_output.lower()
    if "scala.matcherror" in lowered:
        return FailureMode.RUNTIME_ERROR, "Scala MatchError pattern mismatch."
    if "java.lang.classcastexception" in lowered:
        return FailureMode.RUNTIME_ERROR, "Scala/JVM ClassCastException."
    return None

def detect_kotlin_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Kotlin specific runtime exceptions."""
    lowered = combined_output.lower()
    if "kotlinnullpointerexception" in lowered:
        return FailureMode.RUNTIME_ERROR, "KotlinNullPointerException encountered."
    if "uninitializedpropertyaccessexception" in lowered:
        return FailureMode.RUNTIME_ERROR, "Kotlin UninitializedPropertyAccessException."
    return None

def detect_swift_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Swift runtime fatalErrors."""
    lowered = combined_output.lower()
    if "fatal error: index out of range" in lowered:
        return FailureMode.RUNTIME_ERROR, "Swift fatal error: index out of range."
    if "fatal error: unexpectedly found nil" in lowered:
        return FailureMode.RUNTIME_ERROR, "Swift unwrapping optional nil value."
    return None

def detect_dart_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Dart runtime exceptions."""
    lowered = combined_output.lower()
    if "nosuchmethoderror:" in lowered:
        return FailureMode.RUNTIME_ERROR, "Dart NoSuchMethodError."
    if "rangeerror (index):" in lowered:
        return FailureMode.RUNTIME_ERROR, "Dart RangeError index out of range."
    return None

def detect_lua_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Lua table nil index runtime error."""
    lowered = combined_output.lower()
    if "attempt to index a nil value" in lowered:
        return FailureMode.RUNTIME_ERROR, "Lua attempt to index nil value."
    if "attempt to call a nil value" in lowered:
        return FailureMode.RUNTIME_ERROR, "Lua attempt to call nil value."
    return None

def detect_elixir_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Elixir function clause and match errors."""
    lowered = combined_output.lower()
    if "functionclauseerror" in lowered:
        return FailureMode.RUNTIME_ERROR, "Elixir FunctionClauseError no matching clause."
    if "matcherror" in lowered and "no match of right hand side" in lowered:
        return FailureMode.RUNTIME_ERROR, "Elixir MatchError pattern mismatch."
    return None

def detect_clojure_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Clojure argument count mismatch error."""
    lowered = combined_output.lower()
    if "clojure.lang.arityexception: wrong number of args" in lowered:
        return FailureMode.RUNTIME_ERROR, "Clojure ArityException wrong number of arguments."
    return None

def is_sigxcpu_signal(exit_code: Optional[int]) -> bool:
    """Check if exit code corresponds to SIGXCPU (128 + 24 = 152)."""
    return exit_code in (152, 24)

def is_sigxfsz_signal(exit_code: Optional[int]) -> bool:
    """Check if exit code corresponds to SIGXFSZ (128 + 25 = 153)."""
    return exit_code in (153, 25)

def is_sigsys_signal(exit_code: Optional[int]) -> bool:
    """Check if exit code corresponds to SIGSYS (128 + 31 = 159)."""
    return exit_code in (159, 31)

def detect_erlang_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Erlang crash reports and server terminations."""
    lowered = combined_output.lower()
    if "** generic server " in lowered and " terminating" in lowered:
        return FailureMode.RUNTIME_ERROR, "Erlang gen_server crash termination."
    if "** reason for termination ==" in lowered:
        return FailureMode.RUNTIME_ERROR, "Erlang process crash termination."
    return None

def detect_lisp_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Common Lisp runtime conditions."""
    lowered = combined_output.lower()
    if "the variable " in lowered and " is unbound" in lowered:
        return FailureMode.RUNTIME_ERROR, "Common Lisp UNBOUND-VARIABLE condition."
    if "undefined-function" in lowered:
        return FailureMode.RUNTIME_ERROR, "Common Lisp UNDEFINED-FUNCTION condition."
    return None

def detect_fsharp_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract F# match failure exceptions."""
    lowered = combined_output.lower()
    if "matchfailureexception" in lowered:
        return FailureMode.RUNTIME_ERROR, "F# MatchFailureException."
    if "system.invalidoperationexception" in lowered:
        return FailureMode.RUNTIME_ERROR, "F# System.InvalidOperationException."
    return None

def detect_groovy_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Groovy missing method runtime errors."""
    lowered = combined_output.lower()
    if "groovy.lang.missingmethodexception" in lowered:
        return FailureMode.RUNTIME_ERROR, "Groovy MissingMethodException."
    if "groovy.lang.missingpropertyexception" in lowered:
        return FailureMode.RUNTIME_ERROR, "Groovy MissingPropertyException."
    return None

def detect_ada_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Ada GNAT runtime exceptions."""
    lowered = combined_output.lower()
    if "raised constraint_error" in lowered:
        return FailureMode.RUNTIME_ERROR, "Ada CONSTRAINT_ERROR out of range."
    if "raised program_error" in lowered:
        return FailureMode.RUNTIME_ERROR, "Ada PROGRAM_ERROR exception."
    return None

def detect_d_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract D runtime exceptions."""
    lowered = combined_output.lower()
    if "core.exception.rangeerror" in lowered:
        return FailureMode.RUNTIME_ERROR, "D core.exception.RangeError."
    if "core.exception.asserterror" in lowered:
        return FailureMode.ASSERTION_FAILED, "D core.exception.AssertError."
    return None

def detect_nim_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Nim defects and runtime errors."""
    lowered = combined_output.lower()
    if "indexdefect: index out of bounds" in lowered:
        return FailureMode.RUNTIME_ERROR, "Nim IndexDefect out of bounds."
    if "nilaccessdefect" in lowered:
        return FailureMode.RUNTIME_ERROR, "Nim NilAccessDefect."
    return None

def detect_crystal_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Crystal runtime exceptions."""
    lowered = combined_output.lower()
    if "indexoutofboundserror" in lowered:
        return FailureMode.RUNTIME_ERROR, "Crystal IndexOutOfBoundsError."
    return None

def detect_v_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract V language panic output."""
    lowered = combined_output.lower()
    if "v panic:" in lowered:
        return FailureMode.RUNTIME_ERROR, "V language runtime panic."
    return None

def detect_valgrind_violation(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Valgrind Memcheck memory access violations."""
    lowered = combined_output.lower()
    if "invalid read of size" in lowered or "invalid write of size" in lowered:
        return FailureMode.RUNTIME_ERROR, "Valgrind Memcheck invalid memory read/write."
    if "definitely lost in loss record" in lowered:
        return FailureMode.RUNTIME_ERROR, "Valgrind definitely lost memory leak."
    return None

def detect_fortran_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Fortran runtime IO and subscript errors."""
    lowered = combined_output.lower()
    if "fortran runtime error: end of file" in lowered:
        return FailureMode.RUNTIME_ERROR, "Fortran EOF runtime error."
    if "fortran runtime error: index" in lowered and "out of bounds" in lowered:
        return FailureMode.RUNTIME_ERROR, "Fortran array index out of bounds."
    return None

def is_sigtrap_signal(exit_code: Optional[int]) -> bool:
    """Check if exit code corresponds to SIGTRAP (128 + 5 = 133)."""
    return exit_code in (133, 5)

def is_sigabrt_signal(exit_code: Optional[int]) -> bool:
    """Check if exit code corresponds to SIGABRT (128 + 6 = 134)."""
    return exit_code in (134, 6)

def detect_racket_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Racket contract and type violations."""
    lowered = combined_output.lower()
    if "contract violation" in lowered and "expected:" in lowered:
        return FailureMode.RUNTIME_ERROR, "Racket contract violation."
    if "hash-ref: no value found for key" in lowered:
        return FailureMode.RUNTIME_ERROR, "Racket hash-ref key not found."
    return None

def detect_guile_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract Guile Scheme runtime argument errors."""
    lowered = combined_output.lower()
    if "wrong type argument in position" in lowered:
        return FailureMode.RUNTIME_ERROR, "Guile Scheme wrong type argument."
    if "unbound variable:" in lowered:
        return FailureMode.RUNTIME_ERROR, "Guile Scheme unbound variable."
    return None

def detect_pascal_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract FreePascal runtime errors (201 range check, 216 general protection)."""
    lowered = combined_output.lower()
    if "runtime error 201 at" in lowered or "range check error" in lowered:
        return FailureMode.RUNTIME_ERROR, "FreePascal Range check error (Error 201)."
    if "runtime error 216 at" in lowered:
        return FailureMode.RUNTIME_ERROR, "FreePascal Access violation (Error 216)."
    return None

def detect_cobol_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract GnuCOBOL runtime subscript errors."""
    lowered = combined_output.lower()
    if "subscript out of range" in lowered:
        return FailureMode.RUNTIME_ERROR, "COBOL subscript out of range."
    return None

def detect_gas_assembler_error(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract GNU Assembler syntax and operand errors."""
    lowered = combined_output.lower()
    if "assembler messages:" in lowered and "error:" in lowered:
        return FailureMode.RUNTIME_ERROR, "GNU Assembler compilation error."
    return None

def detect_llvm_crash(combined_output: str) -> Optional[Tuple[FailureMode, str]]:
    """Extract LLVM internal fatal compiler errors."""
    lowered = combined_output.lower()
    if "llvm error:" in lowered or "please submit a full bug report" in lowered:
        return FailureMode.RUNTIME_ERROR, "LLVM internal compiler fatal error."
    return None

def has_gdb_stacktrace(combined_output: str) -> bool:
    """Check if output contains GDB stacktrace frames (#0, #1)."""
    return "#0 " in combined_output and ("in main" in combined_output or "0x" in combined_output)

def detect_strace_permission_denied(combined_output: str) -> bool:
    """Check if strace log recorded EPERM or EACCES error."""
    return "= -1 eperm" in combined_output.lower() or "= -1 eacces" in combined_output.lower()

def has_jvm_thread_dump(combined_output: str) -> bool:
    """Check if output contains JVM thread dump dump."""
    return "prio=" in combined_output and "tid=" in combined_output and "nid=" in combined_output

def has_python_warning(combined_output: str) -> bool:
    """Check if output contains standard Python warnings."""
    lowered = combined_output.lower()
    return "deprecationwarning:" in lowered or "userwarning:" in lowered

def extract_typescript_error_code(output: str) -> Optional[str]:
    """Extract TS error codes (e.g. TS2304, TS2322)."""
    import re
    match = re.search(r'error (TS[0-9]+):', output)
    return match.group(1) if match else None

def extract_csharp_error_code(output: str) -> Optional[str]:
    """Extract C# Roslyn error codes (e.g. CS0103, CS0246)."""
    import re
    match = re.search(r'error (CS[0-9]+):', output)
    return match.group(1) if match else None

def detect_javac_cannot_find_symbol(output: str) -> bool:
    """Check if javac reported cannot find symbol error."""
    return "cannot find symbol" in output.lower() and "symbol:" in output.lower()

def detect_rust_use_of_moved_value(output: str) -> bool:
    """Check if rustc reported borrow of moved value (E0382)."""
    return "error[e0382]: use of moved value" in output.lower()

def detect_rust_mutable_borrow_error(output: str) -> bool:
    """Check if rustc reported cannot borrow as mutable (E0502)."""
    return "error[e0502]: cannot borrow" in output.lower()

def detect_go_type_mismatch(output: str) -> bool:
    """Check if go build reported cannot use type error."""
    return "cannot use " in output.lower() and " as type " in output.lower()

def detect_clang_header_not_found(output: str) -> bool:
    """Check if clang reported missing include file."""
    return "fatal error:" in output.lower() and "file not found" in output.lower()
