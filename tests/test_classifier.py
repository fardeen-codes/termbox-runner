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
