"""Built-in benchmark template catalog for coding agents and test harnesses."""

from typing import Dict, List, Optional
from termbox_runner.models import BenchmarkTemplate, ResourceLimits, TaskSubmission

TEMPLATES: Dict[str, BenchmarkTemplate] = {
    "humaneval-py": BenchmarkTemplate(
        id="humaneval-py",
        name="HumanEval Function Synthesis",
        category="Coding Benchmark",
        description="Evaluates agent on algorithmic function completion against rigorous unit tests.",
        task=TaskSubmission(
            image="python:3.12-slim",
            main_cmd="python solution.py",
            verifier_cmd="pytest -v test_eval.py",
            files={
                "solution.py": "def has_close_elements(numbers, threshold):\n    for idx, elem in enumerate(numbers):\n        for idx2, elem2 in enumerate(numbers):\n            if idx != idx2 and abs(elem - elem2) < threshold:\n                return True\n    return False\n",
                "test_eval.py": "from solution import has_close_elements\n\ndef test_has_close_elements():\n    assert has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) is True\n    assert has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) is False\n    assert has_close_elements([1.0, 2.0, 5.9, 4.0, 5.0], 0.95) is True\n",
            },
            limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0),
        ),
    ),
    "swe-mini": BenchmarkTemplate(
        id="swe-mini",
        name="SWE-bench Bug Repair",
        category="Software Engineering",
        description="Applies simulated agent git diff/patch and runs regression test suite.",
        task=TaskSubmission(
            image="python:3.12-slim",
            main_cmd="python -c \"with open('src/calc.py', 'w') as f: f.write('def divide(a, b): return a / b if b != 0 else None\\n')\"",
            verifier_cmd="python -c \"from src.calc import divide; assert divide(10, 2) == 5; assert divide(5, 0) is None; print('Regression tests passed!')\"",
            files={
                "src/calc.py": "def divide(a, b): return a / b\n",
            },
            limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0),
        ),
    ),
    "cli-compliance": BenchmarkTemplate(
        id="cli-compliance",
        name="POSIX CLI Flags & Help Compliance",
        category="System / CLI",
        description="Verifies that CLI agent scripts support standard flags (--help, --version, non-zero exits).",
        task=TaskSubmission(
            image="python:3.12-slim",
            main_cmd="python cli.py --version",
            verifier_cmd="python cli.py --help && python cli.py --invalid-flag 2>&1 | grep -q 'unrecognized'",
            files={
                "cli.py": "import sys, argparse\nparser = argparse.ArgumentParser(prog='tool')\nparser.add_argument('--version', action='version', version='1.0.0')\nparser.parse_args()\n",
            },
            limits=ResourceLimits(mem_limit="128m", timeout_seconds=10.0),
        ),
    ),
    "memory-stress": BenchmarkTemplate(
        id="memory-stress",
        name="Strict OOM Limit Boundary Verification",
        category="Harness Robustness",
        description="Tests sandbox containment by attempting to allocate memory beyond cgroup limit.",
        task=TaskSubmission(
            image="python:3.12-slim",
            main_cmd="python -c \"bytearray(128 * 1024 * 1024)\"",
            limits=ResourceLimits(mem_limit="32m", timeout_seconds=10.0),
        ),
    ),
    "wallclock-timeout": BenchmarkTemplate(
        id="wallclock-timeout",
        name="Hard Wall-Clock Budget Enforcement",
        category="Harness Robustness",
        description="Tests hard timeout enforcement on infinite loop / hanging command.",
        task=TaskSubmission(
            image="python:3.12-slim",
            main_cmd="python -c \"import time; time.sleep(100)\"",
            limits=ResourceLimits(timeout_seconds=2.0),
        ),
    ),
}


def list_benchmark_templates() -> List[BenchmarkTemplate]:
    """Return all available benchmark templates."""
    return list(TEMPLATES.values())


def get_benchmark_template(template_id: str) -> Optional[BenchmarkTemplate]:
    """Get a template by ID or None."""
    return TEMPLATES.get(template_id)

TEMPLATES["nodejs-jest"] = BenchmarkTemplate(
    id="nodejs-jest",
    name="Node.js Jest Test Suite",
    category="JavaScript",
    description="Evaluates Node.js functions against Jest unit assertions.",
    task=TaskSubmission(
        image="node:20-slim",
        main_cmd="node index.js",
        verifier_cmd="npm test",
        files={"index.js": "module.exports = (a, b) => a + b;\n"},
        limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0),
    ),
)

TEMPLATES["rust-cargo"] = BenchmarkTemplate(
    id="rust-cargo",
    name="Rust Cargo Test Suite",
    category="Rust",
    description="Compiles and tests Rust modules with memory safety guarantees.",
    task=TaskSubmission(
        image="rust:1.76-slim",
        main_cmd="cargo check",
        verifier_cmd="cargo test",
        limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0),
    ),
)

TEMPLATES["golang-test"] = BenchmarkTemplate(
    id="golang-test",
    name="Go Standard Test Harness",
    category="Golang",
    description="Executes Go package unit tests with coverage reporting.",
    task=TaskSubmission(
        image="golang:1.22-alpine",
        main_cmd="go build ./...",
        verifier_cmd="go test -v ./...",
        limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0),
    ),
)

TEMPLATES["bash-script"] = BenchmarkTemplate(
    id="bash-script",
    name="POSIX Shell Script Compliance",
    category="Shell",
    description="Validates bash script execution under strict unofficial bash strict mode.",
    task=TaskSubmission(
        image="bash:5.2-alpine",
        main_cmd="bash -euo pipefail script.sh",
        files={"script.sh": "echo 'Strict mode OK'\n"},
        limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0),
    ),
)
