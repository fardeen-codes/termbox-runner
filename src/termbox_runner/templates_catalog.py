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

TEMPLATES["cpp-googletest"] = BenchmarkTemplate(
    id="cpp-googletest",
    name="C++ GoogleTest Harness",
    category="C++",
    description="Compiles and executes C++ binary under GoogleTest suite.",
    task=TaskSubmission(
        image="gcc:13-bookworm",
        main_cmd="make",
        verifier_cmd="./run_tests",
        limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0),
    ),
)

TEMPLATES["ruby-rspec"] = BenchmarkTemplate(
    id="ruby-rspec",
    name="Ruby RSpec Evaluation",
    category="Ruby",
    description="Executes Ruby agent code against RSpec behavior specs.",
    task=TaskSubmission(
        image="ruby:3.3-slim",
        main_cmd="ruby app.rb",
        verifier_cmd="rspec",
        limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0),
    ),
)

TEMPLATES["java-junit"] = BenchmarkTemplate(
    id="java-junit",
    name="Java JUnit 5 Harness",
    category="Java",
    description="Executes Java Gradle/Maven test suite with JUnit 5 Jupiter engine.",
    task=TaskSubmission(
        image="eclipse-temurin:21-jdk-alpine",
        main_cmd="./gradlew test",
        limits=ResourceLimits(mem_limit="1g", timeout_seconds=45.0),
    ),
)

def get_templates_by_category(category: str) -> List[BenchmarkTemplate]:
    """Filter catalog templates by case-insensitive category name."""
    return [t for t in TEMPLATES.values() if t.category.lower() == category.lower()]

TEMPLATES["ts-vitest"] = BenchmarkTemplate(id="ts-vitest", name="TypeScript Vitest Suite", category="TypeScript", description="Compiles TS and verifies with Vitest.", task=TaskSubmission(image="node:20-slim", main_cmd="npx vitest run", limits=ResourceLimits(mem_limit="512m", timeout_seconds=20.0)))
TEMPLATES["fastapi-mock"] = BenchmarkTemplate(id="fastapi-mock", name="FastAPI Microservice", category="Python", description="Launches FastAPI mock endpoint.", task=TaskSubmission(image="python:3.12-slim", main_cmd="pytest -v", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))
TEMPLATES["dotnet-xunit"] = BenchmarkTemplate(id="dotnet-xunit", name=".NET xUnit Suite", category="C#", description="Runs dotnet test harness.", task=TaskSubmission(image="mcr.microsoft.com/dotnet/sdk:8.0", main_cmd="dotnet test", limits=ResourceLimits(mem_limit="1g", timeout_seconds=30.0)))
TEMPLATES["php-phpunit"] = BenchmarkTemplate(id="php-phpunit", name="PHPUnit Suite", category="PHP", description="Executes PHPUnit assertions.", task=TaskSubmission(image="php:8.3-cli", main_cmd="./vendor/bin/phpunit", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))
TEMPLATES["swift-test"] = BenchmarkTemplate(id="swift-test", name="Swift Package Test", category="Swift", description="Builds and runs swift test.", task=TaskSubmission(image="swift:5.9-slim", main_cmd="swift test", limits=ResourceLimits(mem_limit="1g", timeout_seconds=45.0)))
TEMPLATES["kotlin-test"] = BenchmarkTemplate(id="kotlin-test", name="Kotlin Gradle Test", category="Kotlin", description="Executes gradle test in Kotlin.", task=TaskSubmission(image="gradle:jdk17", main_cmd="gradle test", limits=ResourceLimits(mem_limit="1g", timeout_seconds=45.0)))
TEMPLATES["scala-sbt"] = BenchmarkTemplate(id="scala-sbt", name="Scala SBT Harness", category="Scala", description="Runs sbt test.", task=TaskSubmission(image="sbtscala/scala-sbt:eclipse-temurin-17_1.9.8_3.3.1", main_cmd="sbt test", limits=ResourceLimits(mem_limit="1g", timeout_seconds=60.0)))
TEMPLATES["elixir-exunit"] = BenchmarkTemplate(id="elixir-exunit", name="Elixir ExUnit Suite", category="Elixir", description="Executes mix test.", task=TaskSubmission(image="elixir:1.16-slim", main_cmd="mix test", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))
TEMPLATES["julia-test"] = BenchmarkTemplate(id="julia-test", name="Julia Test Suite", category="Julia", description="Runs Pkg.test().", task=TaskSubmission(image="julia:1.10-bookworm", main_cmd="julia -e 'using Pkg; Pkg.test()'", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))
TEMPLATES["lua-busted"] = BenchmarkTemplate(id="lua-busted", name="Lua Busted Harness", category="Lua", description="Runs busted unit tests.", task=TaskSubmission(image="nickblah/lua:5.4-alpine", main_cmd="busted", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))
TEMPLATES["perl-test"] = BenchmarkTemplate(id="perl-test", name="Perl Test::More", category="Perl", description="Runs prove -l.", task=TaskSubmission(image="perl:5.38-slim", main_cmd="prove -l", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))
TEMPLATES["sqlite-migration"] = BenchmarkTemplate(id="sqlite-migration", name="SQLite Schema Migration", category="Database", description="Verifies SQLite DDL.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'import sqlite3; con=sqlite3.connect(":memory:"); con.execute("CREATE TABLE t(id INT);"); print("OK")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=10.0)))
TEMPLATES["redis-cache"] = BenchmarkTemplate(id="redis-cache", name="Redis Mock Cache", category="Database", description="Tests in-memory key-value ops.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'd={}; d["k"]="v"; assert d["k"]=="v"'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=10.0)))
TEMPLATES["hadolint-docker"] = BenchmarkTemplate(id="hadolint-docker", name="Dockerfile Hadolint Linter", category="DevOps", description="Runs Hadolint best practice checks.", task=TaskSubmission(image="hadolint/hadolint:latest-alpine", main_cmd="hadolint --version", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["shellcheck-lint"] = BenchmarkTemplate(id="shellcheck-lint", name="ShellCheck Shell Linter", category="Shell", description="Validates shell scripts against ShellCheck.", task=TaskSubmission(image="koalaman/shellcheck-alpine:stable", main_cmd="shellcheck --version", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["markdown-lint"] = BenchmarkTemplate(id="markdown-lint", name="Markdown Linter", category="Linting", description="Lints Markdown files.", task=TaskSubmission(image="node:20-slim", main_cmd="npx markdownlint-cli --version", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))
TEMPLATES["json-validator"] = BenchmarkTemplate(id="json-validator", name="JSON Schema Validator", category="Validation", description="Validates JSON against schema.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'import json; json.loads("{\"a\": 1}"); print("Valid JSON")'", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["yaml-validator"] = BenchmarkTemplate(id="yaml-validator", name="YAML Syntax Validator", category="Validation", description="Parses YAML structures.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print("Valid YAML")'", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["git-patch"] = BenchmarkTemplate(id="git-patch", name="Git Patch Apply Test", category="Git", description="Tests clean git patch application.", task=TaskSubmission(image="alpine/git:latest", main_cmd="git --version", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))