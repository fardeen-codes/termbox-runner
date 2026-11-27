"""Unit tests for deterministic failure-mode classification."""

from termbox_runner.classifier import classify_run, extract_diagnostic_summary
from termbox_runner.models import CommandStep, FailureMode, StepResult


def test_classify_passed():
    steps = [
        StepResult(step=CommandStep.SETUP, command="pip install pytest", exit_code=0),
        StepResult(step=CommandStep.MAIN, command="python solution.py", exit_code=0, stdout="Success"),
        StepResult(step=CommandStep.VERIFIER, command="pytest", exit_code=0, stdout="1 passed"),
    ]
    mode, reason = classify_run(steps)
    assert mode == FailureMode.PASSED
    assert "completed successfully" in reason.lower()


def test_classify_timeout_wall_clock():
    steps = [
        StepResult(step=CommandStep.MAIN, command="sleep 100", exit_code=None),
    ]
    mode, reason = classify_run(steps, run_timed_out=True, timeout_seconds=30.0)
    assert mode == FailureMode.TIMEOUT
    assert "timeout after 30.0s" in reason.lower() or "timeout" in reason.lower()


def test_classify_timeout_step():
    steps = [
        StepResult(step=CommandStep.MAIN, command="sleep 100", exit_code=124, timed_out=True),
    ]
    mode, reason = classify_run(steps)
    assert mode == FailureMode.TIMEOUT
    assert "timed out" in reason.lower()


def test_classify_oom_container_flag():
    steps = [
        StepResult(step=CommandStep.MAIN, command="alloc_mem", exit_code=137),
    ]
    mode, reason = classify_run(steps, container_oom=True)
    assert mode == FailureMode.OOM_KILLED
    assert "out-of-memory" in reason.lower() or "oom" in reason.lower()


def test_classify_oom_step_flag():
    steps = [
        StepResult(step=CommandStep.MAIN, command="alloc_mem", exit_code=137, oom_killed=True),
    ]
    mode, reason = classify_run(steps)
    assert mode == FailureMode.OOM_KILLED


def test_classify_oom_exit_code_137():
    steps = [
        StepResult(step=CommandStep.MAIN, command="python -c mem", exit_code=137, stderr="Killed"),
    ]
    mode, reason = classify_run(steps)
    assert mode == FailureMode.OOM_KILLED


def test_classify_setup_error():
    steps = [
        StepResult(
            step=CommandStep.SETUP,
            command="apt-get install nonexistent",
            exit_code=100,
            stderr="E: Unable to locate package nonexistent",
        ),
    ]
    mode, reason = classify_run(steps)
    assert mode == FailureMode.SETUP_ERROR
    assert "exit code 100" in reason
    assert "nonexistent" in reason


def test_classify_assertion_failed_verifier():
    steps = [
        StepResult(step=CommandStep.MAIN, command="python agent.py", exit_code=0),
        StepResult(
            step=CommandStep.VERIFIER,
            command="pytest",
            exit_code=1,
            stdout="FAILED test_solution.py::test_eval - AssertionError: expected 42",
        ),
    ]
    mode, reason = classify_run(steps)
    assert mode == FailureMode.ASSERTION_FAILED
    assert "AssertionError" in reason or "failed with exit code 1" in reason


def test_classify_assertion_failed_main_without_verifier():
    steps = [
        StepResult(
            step=CommandStep.MAIN,
            command="python -m unittest",
            exit_code=1,
            stdout="FAIL: test_run\nAssertionError: False is not true",
        ),
    ]
    mode, reason = classify_run(steps)
    assert mode == FailureMode.ASSERTION_FAILED


def test_classify_runtime_error():
    steps = [
        StepResult(
            step=CommandStep.MAIN,
            command="python -c '1/0'",
            exit_code=1,
            stderr="ZeroDivisionError: division by zero",
        ),
    ]
    mode, reason = classify_run(steps)
    assert mode == FailureMode.RUNTIME_ERROR
    assert "ZeroDivisionError" in reason


def test_extract_diagnostic_summary():
    traceback_log = """
Traceback (most recent call last):
  File "main.py", line 12, in <module>
    calculate_score()
  File "main.py", line 8, in calculate_score
    raise ValueError("Score calculation exploded")
ValueError: Score calculation exploded
"""
    summary = extract_diagnostic_summary(traceback_log, max_lines=2)
    assert "ValueError: Score calculation exploded" in summary


def test_classify_signals_and_exit_codes():
    from termbox_runner.classifier import describe_signal

    step_segv = StepResult(step=CommandStep.MAIN, command="c_app", exit_code=139)
    mode, reason = classify_run([step_segv])
    assert mode == FailureMode.RUNTIME_ERROR
    assert "Segmentation Fault" in reason

    step_ill = StepResult(step=CommandStep.MAIN, command="bad_ins", exit_code=132)
    mode, reason = classify_run([step_ill])
    assert mode == FailureMode.RUNTIME_ERROR
    assert "Illegal Instruction" in reason

    step_127 = StepResult(step=CommandStep.MAIN, command="nonexistent", exit_code=127)
    mode, reason = classify_run([step_127])
    assert mode == FailureMode.RUNTIME_ERROR
    assert "not found" in reason

    assert describe_signal(137) == "SIGKILL"
    assert describe_signal(139) == "SIGSEGV"
    assert describe_signal(0) is None


def test_classifier_python_exceptions():
    from termbox_runner.classifier import get_failure_severity, extract_stacktrace_snippet

    step_div = StepResult(step=CommandStep.MAIN, command="calc.py", exit_code=1, stderr="ZeroDivisionError: division by zero")
    mode, reason = classify_run([step_div])
    assert mode == FailureMode.RUNTIME_ERROR
    assert "ZeroDivisionError" in reason

    assert get_failure_severity(FailureMode.OOM_KILLED) == "CRITICAL"
    assert get_failure_severity(FailureMode.PASSED) == "INFO"

    trace = 'File "test.py", line 12, in <module>\nZeroDivisionError'
    snippet = extract_stacktrace_snippet(trace)
    assert 'line 12' in snippet


def test_classifier_multilang_detections():
    from termbox_runner.classifier import get_diagnostic_action_hint, get_failure_mode_doc_url

    step_rust = StepResult(step=CommandStep.MAIN, command="cargo build", exit_code=1, stderr="error[E0425]: cannot find value in this scope")
    mode, reason = classify_run([step_rust])
    assert mode == FailureMode.RUNTIME_ERROR
    assert "E0425" in reason

    assert "mem_limit" in get_diagnostic_action_hint(FailureMode.OOM_KILLED)
    assert "failures#" in get_failure_mode_doc_url(FailureMode.TIMEOUT)


def test_classifier_jvm_and_fatal_signals():
    from termbox_runner.classifier import (
        detect_jvm_exception,
        format_fatal_signal_summary,
    )

    # JVM OOM detection
    diag = detect_jvm_exception("Exception in thread \"main\" java.lang.OutOfMemoryError: Java heap space")
    assert diag is not None
    assert diag[0] == FailureMode.OOM_KILLED
    assert "heap exhausted" in diag[1]

    # JVM NPE detection
    step_npe = StepResult(step=CommandStep.MAIN, command="mvn test", exit_code=1, stderr="java.lang.NullPointerException at com.example.App.main")
    mode, reason = classify_run([step_npe])
    assert mode == FailureMode.RUNTIME_ERROR
    assert "NullPointerException" in reason

    # Fatal signal formatting
    assert "SIGSEGV" in format_fatal_signal_summary(139)
    assert "SIGABRT" in format_fatal_signal_summary(134)
    assert format_fatal_signal_summary(0) is None


def test_multilang_diagnostics_extended():
    from termbox_runner.classifier import (
        detect_ruby_exception,
        detect_php_fatal_error,
        extract_rust_panic_message,
        detect_go_deadlock,
    )
    from termbox_runner.models import FailureMode

    ruby_res = detect_ruby_exception("undefined method 'foo' for nil:NilClass (NoMethodError)")
    assert ruby_res is not None
    assert ruby_res[0] == FailureMode.RUNTIME_ERROR

    php_res = detect_php_fatal_error("Fatal error: Uncaught Error: Call to undefined function")
    assert php_res is not None

    rust_msg = extract_rust_panic_message("thread 'main' panicked at src/main.rs:10:5:\nexplicit panic")
    assert rust_msg is not None
    assert "panicked at" in rust_msg

    go_res = detect_go_deadlock("fatal error: all goroutines are asleep - deadlock!")
    assert go_res is not None
    assert "deadlock" in go_res[1]

def test_classifier_functional_and_asan_diagnostics():
    from termbox_runner.classifier import (
        detect_haskell_error,
        detect_ocaml_error,
        detect_zig_error,
        detect_asan_violation,
    )
    from termbox_runner.models import FailureMode

    hask = detect_haskell_error("Couldn't match expected type 'Int' with actual type 'Bool'")
    assert hask is not None and hask[0] == FailureMode.RUNTIME_ERROR

    ocaml = detect_ocaml_error('Fatal error: exception Failure("empty list")')
    assert ocaml is not None and ocaml[0] == FailureMode.RUNTIME_ERROR

    zig = detect_zig_error("main.zig:12:5: error: expected type 'u32', found 'bool'")
    assert zig is not None and zig[0] == FailureMode.RUNTIME_ERROR

    asan = detect_asan_violation("==1234==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x00")
    assert asan is not None and "heap-buffer-overflow" in asan[1]

def test_multilang_batch1_diagnostics():
    from termbox_runner.classifier import (
        detect_perl_error,
        detect_r_error,
        detect_julia_error,
        detect_scala_error,
        detect_kotlin_error,
        detect_swift_error,
        detect_dart_error,
        detect_lua_error,
        detect_elixir_error,
        detect_clojure_error,
        is_sigxcpu_signal,
        is_sigxfsz_signal,
        is_sigsys_signal,
    )
    assert detect_perl_error("syntax error at test.pl line 5") is not None
    assert detect_r_error("Error: subscript out of bounds") is not None
    assert detect_julia_error("BoundsError: attempt to access 3-element") is not None
    assert detect_scala_error("scala.MatchError: 42") is not None
    assert detect_kotlin_error("KotlinNullPointerException") is not None
    assert detect_swift_error("Fatal error: Index out of range") is not None
    assert detect_dart_error("NoSuchMethodError: method not found") is not None
    assert detect_lua_error("attempt to index a nil value") is not None
    assert detect_elixir_error("FunctionClauseError") is not None
    assert detect_clojure_error("clojure.lang.ArityException: Wrong number of args") is not None
    assert is_sigxcpu_signal(152) is True
    assert is_sigxfsz_signal(153) is True
    assert is_sigsys_signal(159) is True

def test_multilang_batch2_diagnostics():
    from termbox_runner.classifier import (
        detect_erlang_error,
        detect_lisp_error,
        detect_fsharp_error,
        detect_groovy_error,
        detect_ada_error,
        detect_d_error,
        detect_nim_error,
        detect_crystal_error,
        detect_v_error,
        detect_valgrind_violation,
        detect_fortran_error,
        is_sigtrap_signal,
        is_sigabrt_signal,
    )
    assert detect_erlang_error("** Generic server foo terminating") is not None
    assert detect_lisp_error("The variable x is unbound") is not None
    assert detect_fsharp_error("MatchFailureException") is not None
    assert detect_groovy_error("groovy.lang.MissingMethodException") is not None
    assert detect_ada_error("raised CONSTRAINT_ERROR : index out of range") is not None
    assert detect_d_error("core.exception.RangeError") is not None
    assert detect_nim_error("IndexDefect: index out of bounds") is not None
    assert detect_crystal_error("IndexOutOfBoundsError") is not None
    assert detect_v_error("V panic: array index out of range") is not None
    assert detect_valgrind_violation("Invalid read of size 4") is not None
    assert detect_fortran_error("Fortran runtime error: End of file") is not None
    assert is_sigtrap_signal(133) is True
    assert is_sigabrt_signal(134) is True

def test_multilang_batch3_diagnostics():
    from termbox_runner.classifier import (
        detect_racket_error,
        detect_guile_error,
        detect_pascal_error,
        detect_cobol_error,
        detect_gas_assembler_error,
        detect_llvm_crash,
        has_gdb_stacktrace,
        detect_strace_permission_denied,
        has_jvm_thread_dump,
        has_python_warning,
    )
    assert detect_racket_error("contract violation expected: number?") is not None
    assert detect_guile_error("Wrong type argument in position 1") is not None
    assert detect_pascal_error("Runtime error 201 at $00000000") is not None
    assert detect_cobol_error("Subscript out of range") is not None
    assert detect_gas_assembler_error("Assembler messages: Error: junk at end of line") is not None
    assert detect_llvm_crash("LLVM ERROR: out of memory") is not None
    assert has_gdb_stacktrace("#0 0x00000001 in main ()") is True
    assert detect_strace_permission_denied("openat(AT_FDCWD, \"/root\", O_RDONLY) = -1 EPERM (Operation not permitted)") is True
    assert has_jvm_thread_dump('"main" prio=5 tid=0x01 nid=0x02') is True
    assert has_python_warning("UserWarning: experimental feature") is True
