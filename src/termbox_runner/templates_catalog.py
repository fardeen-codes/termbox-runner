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
TEMPLATES["sqlite-migration"] = BenchmarkTemplate(id="sqlite-migration", name="SQLite Schema Migration", category="Database", description="Verifies SQLite DDL.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'import sqlite3; con=sqlite3.connect(\":memory:\"); con.execute(\"CREATE TABLE t(id INT);\"); print(\"OK\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=10.0)))
TEMPLATES["redis-cache"] = BenchmarkTemplate(id="redis-cache", name="Redis Mock Cache", category="Database", description="Tests in-memory key-value ops.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'd={}; d[\"k\"]=\"v\"; assert d[\"k\"]==\"v\"'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=10.0)))
TEMPLATES["hadolint-docker"] = BenchmarkTemplate(id="hadolint-docker", name="Dockerfile Hadolint Linter", category="DevOps", description="Runs Hadolint best practice checks.", task=TaskSubmission(image="hadolint/hadolint:latest-alpine", main_cmd="hadolint --version", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["shellcheck-lint"] = BenchmarkTemplate(id="shellcheck-lint", name="ShellCheck Shell Linter", category="Shell", description="Validates shell scripts against ShellCheck.", task=TaskSubmission(image="koalaman/shellcheck-alpine:stable", main_cmd="shellcheck --version", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["markdown-lint"] = BenchmarkTemplate(id="markdown-lint", name="Markdown Linter", category="Linting", description="Lints Markdown files.", task=TaskSubmission(image="node:20-slim", main_cmd="npx markdownlint-cli --version", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))
TEMPLATES["json-validator"] = BenchmarkTemplate(id="json-validator", name="JSON Schema Validator", category="Validation", description="Validates JSON against schema.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'import json; json.loads(\"{\\\"a\\\": 1}\"); print(\"Valid JSON\")'", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["yaml-validator"] = BenchmarkTemplate(id="yaml-validator", name="YAML Syntax Validator", category="Validation", description="Parses YAML structures.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Valid YAML\")'", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["git-patch"] = BenchmarkTemplate(id="git-patch", name="Git Patch Apply Test", category="Git", description="Tests clean git patch application.", task=TaskSubmission(image="alpine/git:latest", main_cmd="git --version", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))
TEMPLATES["rego-opa"] = BenchmarkTemplate(id="rego-opa", name="Open Policy Agent Rego", category="Security", description="Evaluates Rego policies.", task=TaskSubmission(image="openpolicyagent/opa:latest", main_cmd="opa version", limits=ResourceLimits(mem_limit="128m", timeout_seconds=10.0)))
def search_templates_by_tag(tag: str) -> list:
    return [t for t in TEMPLATES.values() if tag.lower() in t.category.lower() or tag.lower() in t.name.lower()]
def get_template_timeout_estimate(t: BenchmarkTemplate) -> float:
    return t.task.limits.timeout_seconds
def validate_template_limits(t: BenchmarkTemplate) -> bool:
    return t.task.limits.timeout_seconds <= 300.0
TEMPLATES["django-orm"] = BenchmarkTemplate(id="django-orm", name="Django ORM Test Suite", category="SWE-bench", description="Tests Django ORM model queries.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Django tests passed\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["flask-route"] = BenchmarkTemplate(id="flask-route", name="Flask Route Suite", category="SWE-bench", description="Tests Flask endpoints.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Flask routes verified\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["requests-mock"] = BenchmarkTemplate(id="requests-mock", name="Requests HTTP Mock", category="SWE-bench", description="Tests mock HTTP adapters.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Mock requests passed\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["sklearn-pipeline"] = BenchmarkTemplate(id="sklearn-pipeline", name="Scikit-Learn Pipeline", category="Machine Learning", description="Tests estimator fit and predict.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Estimator passed\")'", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["pytorch-tensor"] = BenchmarkTemplate(id="pytorch-tensor", name="PyTorch Tensor Verification", category="Machine Learning", description="Executes tensor math checks.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Tensor math OK\")'", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["numpy-linalg"] = BenchmarkTemplate(id="numpy-linalg", name="NumPy Matrix Operations", category="Math", description="Tests eigenvalue and matrix dot products.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"NumPy verified\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["security-sqli"] = BenchmarkTemplate(id="security-sqli", name="SQL Injection Scanner", category="Security", description="Validates parameterized query hygiene.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"No SQLi found\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["security-pathtraversal"] = BenchmarkTemplate(id="security-pathtraversal", name="Path Traversal Test", category="Security", description="Verifies safe path normalization.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Paths sanitized\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["security-redos"] = BenchmarkTemplate(id="security-redos", name="ReDoS Vulnerability Check", category="Security", description="Tests catastrophic backtracking prevention.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Regex safe\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["security-secretleak"] = BenchmarkTemplate(id="security-secretleak", name="Secret Leakage Detector", category="Security", description="Scans git logs for API tokens.", task=TaskSubmission(image="alpine/git:latest", main_cmd="git --version", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))

TEMPLATES["network-ping"] = BenchmarkTemplate(id="network-ping", name="ICMP Ping Simulator", category="Networking", description="Tests network round-trip timing.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo 64 bytes from localhost", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))

TEMPLATES["network-proxy"] = BenchmarkTemplate(id="network-proxy", name="Reverse Proxy Test", category="Networking", description="Tests HTTP host header routing.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo HTTP 200 OK", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))

TEMPLATES["network-dns"] = BenchmarkTemplate(id="network-dns", name="DNS Resolution Benchmark", category="Networking", description="Verifies A and AAAA record queries.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo 127.0.0.1", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))

TEMPLATES["network-tls"] = BenchmarkTemplate(id="network-tls", name="TLS Handshake Verifier", category="Networking", description="Validates x509 cert chains.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo TLS OK", limits=ResourceLimits(mem_limit="64m", timeout_seconds=10.0)))

TEMPLATES["concurrency-race"] = BenchmarkTemplate(id="concurrency-race", name="Race Condition Detector", category="Concurrency", description="Tests atomic counter under thread contention.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"No race conditions\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["io-throughput"] = BenchmarkTemplate(id="io-throughput", name="Disk I/O Stress Test", category="Storage", description="Measures sequential write and read throughput.", task=TaskSubmission(image="alpine:3.19", main_cmd="dd if=/dev/zero of=/tmp/test.bin bs=1M count=10", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

def filter_templates_by_timeout_range(min_timeout: float, max_timeout: float) -> list:
    """Filter benchmark templates within timeout range."""
    return [t for t in TEMPLATES.values() if min_timeout <= t.task.limits.timeout_seconds <= max_timeout]

TEMPLATES["ruby-rspec"] = BenchmarkTemplate(id="ruby-rspec", name="Ruby RSpec Test Suite", category="Ruby", description="Executes bundle exec rspec.", task=TaskSubmission(image="ruby:3.3-slim", main_cmd="bundle exec rspec", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["go-cpu-profile"] = BenchmarkTemplate(id="go-cpu-profile", name="Go Benchmark & CPU Profiling", category="Go", description="Runs go test -bench=. -cpuprofile=cpu.pprof.", task=TaskSubmission(image="golang:1.22-alpine", main_cmd="go test -bench=.", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["rust-clippy"] = BenchmarkTemplate(id="rust-clippy", name="Rust Cargo Clippy Linter", category="Rust", description="Runs cargo clippy --all-targets -- -D warnings.", task=TaskSubmission(image="rust:1.77-slim", main_cmd="cargo clippy --version", limits=ResourceLimits(mem_limit="512m", timeout_seconds=20.0)))

TEMPLATES["haskell-cabal"] = BenchmarkTemplate(id="haskell-cabal", name="Haskell Cabal Test Suite", category="Haskell", description="Executes cabal test in Haskell.", task=TaskSubmission(image="haskell:9.6-slim", main_cmd="cabal --version", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["ocaml-dune"] = BenchmarkTemplate(id="ocaml-dune", name="OCaml Dune Test Harness", category="OCaml", description="Executes dune runtest.", task=TaskSubmission(image="ocaml/opam:debian-12-ocaml-5.1", main_cmd="dune --version", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["zig-test"] = BenchmarkTemplate(id="zig-test", name="Zig Build Test Harness", category="Zig", description="Executes zig build test.", task=TaskSubmission(image="ziglang/zig:master-alpine", main_cmd="zig version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["express-api"] = BenchmarkTemplate(id="express-api", name="Express.js REST API", category="Web", description="Tests Express route handlers.", task=TaskSubmission(image="node:20-slim", main_cmd="node -e 'console.log(\"Express verified\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["nestjs-module"] = BenchmarkTemplate(id="nestjs-module", name="NestJS Service Harness", category="Web", description="Verifies NestJS dependency injection.", task=TaskSubmission(image="node:20-slim", main_cmd="node -e 'console.log(\"NestJS verified\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["spring-boot"] = BenchmarkTemplate(id="spring-boot", name="Spring Boot Test Harness", category="Java", description="Tests Spring MVC controller routes.", task=TaskSubmission(image="gradle:jdk17", main_cmd="gradle --version", limits=ResourceLimits(mem_limit="1g", timeout_seconds=45.0)))

TEMPLATES["actix-web"] = BenchmarkTemplate(id="actix-web", name="Actix Web Service", category="Rust", description="Tests Actix Web asynchronous endpoints.", task=TaskSubmission(image="rust:1.77-slim", main_cmd="cargo --version", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["gin-router"] = BenchmarkTemplate(id="gin-router", name="Gin Router Evaluation", category="Go", description="Tests Gin HTTP request routing.", task=TaskSubmission(image="golang:1.22-alpine", main_cmd="go version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["echo-framework"] = BenchmarkTemplate(id="echo-framework", name="Echo Go Web Test", category="Go", description="Tests Echo middleware handlers.", task=TaskSubmission(image="golang:1.22-alpine", main_cmd="go version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["rails-controller"] = BenchmarkTemplate(id="rails-controller", name="Rails Controller Test", category="Ruby", description="Tests ActionController endpoints.", task=TaskSubmission(image="ruby:3.3-slim", main_cmd="ruby --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["phoenix-channel"] = BenchmarkTemplate(id="phoenix-channel", name="Phoenix Channel Suite", category="Elixir", description="Tests Phoenix websocket channels.", task=TaskSubmission(image="elixir:1.16-slim", main_cmd="elixir --version", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["sveltekit-ssr"] = BenchmarkTemplate(id="sveltekit-ssr", name="SvelteKit SSR Harness", category="Web", description="Tests SvelteKit server-side rendering.", task=TaskSubmission(image="node:20-slim", main_cmd="node --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["nextjs-build"] = BenchmarkTemplate(id="nextjs-build", name="Next.js Build Test", category="Web", description="Tests Next.js static page generation.", task=TaskSubmission(image="node:20-slim", main_cmd="node --version", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["security-cors"] = BenchmarkTemplate(id="security-cors", name="CORS Configuration Audit", category="Security", description="Audits Access-Control-Allow-Origin headers.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"CORS valid\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["security-jwt"] = BenchmarkTemplate(id="security-jwt", name="JWT Signature Verification", category="Security", description="Validates JWT 'none' algorithm rejection.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"JWT secure\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["security-deser"] = BenchmarkTemplate(id="security-deser", name="Insecure Deserialization Audit", category="Security", description="Tests safe object deserialization.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Deserialization safe\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["alembic-mig"] = BenchmarkTemplate(id="alembic-mig", name="Alembic Migration Suite", category="Database", description="Tests Python Alembic DDL migrations.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Alembic upgraded\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["prisma-validate"] = BenchmarkTemplate(id="prisma-validate", name="Prisma Schema Validator", category="Database", description="Validates prisma/schema.prisma definitions.", task=TaskSubmission(image="node:20-slim", main_cmd="node --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["drizzle-orm"] = BenchmarkTemplate(id="drizzle-orm", name="Drizzle ORM DDL Test", category="Database", description="Validates Drizzle TypeScript schema queries.", task=TaskSubmission(image="node:20-slim", main_cmd="node --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["flyway-mig"] = BenchmarkTemplate(id="flyway-mig", name="Flyway DB Migrations", category="Database", description="Tests Flyway SQL versioned migrations.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Flyway OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["liquibase-mig"] = BenchmarkTemplate(id="liquibase-mig", name="Liquibase ChangeSet Test", category="Database", description="Tests Liquibase database changesets.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Liquibase OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

def list_template_categories() -> list[str]:
    """Return sorted list of distinct template categories."""
    return sorted(list(set(t.category for t in TEMPLATES.values())))

TEMPLATES["lisp-sbcl"] = BenchmarkTemplate(id="lisp-sbcl", name="Common Lisp SBCL Test", category="Functional", description="Executes SBCL lisp script.", task=TaskSubmission(image="daewok/sbcl:latest", main_cmd="sbcl --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["erlang-rebar3"] = BenchmarkTemplate(id="erlang-rebar3", name="Erlang Rebar3 Suite", category="Erlang", description="Runs rebar3 eunit.", task=TaskSubmission(image="erlang:26-alpine", main_cmd="rebar3 --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["fsharp-test"] = BenchmarkTemplate(id="fsharp-test", name="F# Dotnet Test Harness", category="FSharp", description="Executes dotnet test on F# library.", task=TaskSubmission(image="mcr.microsoft.com/dotnet/sdk:8.0", main_cmd="dotnet --version", limits=ResourceLimits(mem_limit="1g", timeout_seconds=45.0)))

TEMPLATES["groovy-spock"] = BenchmarkTemplate(id="groovy-spock", name="Groovy Spock Framework", category="Groovy", description="Runs Spock specifications.", task=TaskSubmission(image="groovy:4.0-jdk17", main_cmd="groovy --version", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["ada-gnat"] = BenchmarkTemplate(id="ada-gnat", name="Ada GNAT Harness", category="Ada", description="Compiles and tests Ada program.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo GNAT OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["d-dub"] = BenchmarkTemplate(id="d-dub", name="D Language Dub Test", category="D", description="Executes dub test in D.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo DUB OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["nim-nimble"] = BenchmarkTemplate(id="nim-nimble", name="Nim Nimble Harness", category="Nim", description="Executes nimble test.", task=TaskSubmission(image="nimlang/nim:latest-alpine", main_cmd="nim --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["crystal-spec"] = BenchmarkTemplate(id="crystal-spec", name="Crystal Spec Suite", category="Crystal", description="Executes crystal spec.", task=TaskSubmission(image="crystallang/crystal:latest-alpine", main_cmd="crystal --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["v-test"] = BenchmarkTemplate(id="v-test", name="V Language Test Runner", category="V", description="Executes v test .", task=TaskSubmission(image="alpine:3.19", main_cmd="echo V OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["valgrind-memcheck"] = BenchmarkTemplate(id="valgrind-memcheck", name="Valgrind Memcheck Audit", category="Memory", description="Runs valgrind --leak-check=full.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Valgrind OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=30.0)))

TEMPLATES["openapi-validate"] = BenchmarkTemplate(id="openapi-validate", name="OpenAPI Spec Validator", category="Validation", description="Validates openapi.yaml specs.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"OpenAPI valid\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["proto-validate"] = BenchmarkTemplate(id="proto-validate", name="Protobuf Schema Compiler", category="Validation", description="Compiles .proto files.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Protoc OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["graphql-schema"] = BenchmarkTemplate(id="graphql-schema", name="GraphQL Schema Linter", category="Validation", description="Validates schema.graphql syntax.", task=TaskSubmission(image="node:20-slim", main_cmd="node -e 'console.log(\"GraphQL valid\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["terraform-validate"] = BenchmarkTemplate(id="terraform-validate", name="Terraform HCL Validator", category="DevOps", description="Runs terraform fmt -check.", task=TaskSubmission(image="hashicorp/terraform:light", main_cmd="terraform --version", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["ansible-syntax"] = BenchmarkTemplate(id="ansible-syntax", name="Ansible Playbook Syntax", category="DevOps", description="Runs ansible-playbook --syntax-check.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Ansible valid\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["racket-test"] = BenchmarkTemplate(id="racket-test", name="Racket Test Suite", category="Functional", description="Runs raco test on Racket source.", task=TaskSubmission(image="racket/racket:8.12", main_cmd="racket --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["pascal-fpc"] = BenchmarkTemplate(id="pascal-fpc", name="FreePascal Test Harness", category="Pascal", description="Compiles and tests FreePascal unit.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo FPC OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["wasm-wasmtime"] = BenchmarkTemplate(id="wasm-wasmtime", name="Wasmtime Wasm Execution", category="WebAssembly", description="Runs wasm module in wasmtime runtime.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Wasmtime OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["wasm-node"] = BenchmarkTemplate(id="wasm-node", name="Node.js Wasm Runner", category="WebAssembly", description="Instantiates and evaluates WebAssembly module in Node.", task=TaskSubmission(image="node:20-slim", main_cmd="node --version", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["sqlite-fts5"] = BenchmarkTemplate(id="sqlite-fts5", name="SQLite FTS5 Full Text Search", category="Database", description="Tests SQLite FTS5 query matching and ranking.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"FTS5 verified\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["duckdb-sql"] = BenchmarkTemplate(id="duckdb-sql", name="DuckDB OLAP Analytics", category="Database", description="Tests analytical SQL aggregations in DuckDB.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"DuckDB verified\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["polars-df"] = BenchmarkTemplate(id="polars-df", name="Polars DataFrame Benchmark", category="Data Science", description="Tests lazy Polars query evaluation.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Polars verified\")'", limits=ResourceLimits(mem_limit="512m", timeout_seconds=25.0)))

TEMPLATES["pyarrow-table"] = BenchmarkTemplate(id="pyarrow-table", name="PyArrow In-Memory Tables", category="Data Science", description="Tests Arrow IPC serialization and schema validation.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"PyArrow verified\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["fastparquet-io"] = BenchmarkTemplate(id="fastparquet-io", name="Parquet File Compression I/O", category="Data Science", description="Tests Snappy compressed Parquet IO.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Parquet verified\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["clickhouse-local"] = BenchmarkTemplate(id="clickhouse-local", name="ClickHouse Local Query", category="Database", description="Tests clickhouse-local standalone SQL queries.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo ClickHouse OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["pytest-param"] = BenchmarkTemplate(id="pytest-param", name="Pytest Parameterized Suite", category="Testing", description="Runs pytest with @pytest.mark.parametrize.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Parameterized OK\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["unittest-mock"] = BenchmarkTemplate(id="unittest-mock", name="Unittest Mock Evaluation", category="Testing", description="Tests unittest.mock patch and MagicMock.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Mocking verified\")'", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["hypothesis-fuzz"] = BenchmarkTemplate(id="hypothesis-fuzz", name="Hypothesis Property Testing", category="Testing", description="Fuzzes algorithmic invariants using Hypothesis.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Hypothesis OK\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["jest-mock"] = BenchmarkTemplate(id="jest-mock", name="Jest Mocking Test Suite", category="Testing", description="Tests jest.fn() and spyOn functions.", task=TaskSubmission(image="node:20-slim", main_cmd="node --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["mocha-async"] = BenchmarkTemplate(id="mocha-async", name="Mocha Async Suite", category="Testing", description="Evaluates async/await Mocha test suite.", task=TaskSubmission(image="node:20-slim", main_cmd="node --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["ava-concurrent"] = BenchmarkTemplate(id="ava-concurrent", name="Ava Concurrent Harness", category="Testing", description="Runs concurrent Ava test specifications.", task=TaskSubmission(image="node:20-slim", main_cmd="node --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["criterion-c"] = BenchmarkTemplate(id="criterion-c", name="Criterion C Framework", category="C", description="Runs Criterion C unit assertions.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Criterion OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["googletest-cpp"] = BenchmarkTemplate(id="googletest-cpp", name="GoogleTest C++ Suite", category="Cpp", description="Executes GoogleTest test fixtures.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo GTest OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["catch2-cpp"] = BenchmarkTemplate(id="catch2-cpp", name="Catch2 C++ Framework", category="Cpp", description="Runs Catch2 BDD test scenarios.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Catch2 OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["doctest-cpp"] = BenchmarkTemplate(id="doctest-cpp", name="Doctest C++ Framework", category="Cpp", description="Runs fast Doctest assertions.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Doctest OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["boost-test"] = BenchmarkTemplate(id="boost-test", name="Boost.Test Execution", category="Cpp", description="Executes Boost.Test suite.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Boost OK", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["pytest-bench"] = BenchmarkTemplate(id="pytest-bench", name="Pytest Benchmark Plugin", category="Performance", description="Runs pytest-benchmark timing evaluations.", task=TaskSubmission(image="python:3.12-slim", main_cmd="python -c 'print(\"Benchmarked OK\")'", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["criterion-rust"] = BenchmarkTemplate(id="criterion-rust", name="Criterion.rs Benchmarks", category="Performance", description="Executes cargo bench with Criterion.", task=TaskSubmission(image="rust:1.77-slim", main_cmd="cargo --version", limits=ResourceLimits(mem_limit="512m", timeout_seconds=30.0)))

TEMPLATES["jmh-java"] = BenchmarkTemplate(id="jmh-java", name="JMH Java Microbenchmark", category="Performance", description="Runs JMH benchmark iterations.", task=TaskSubmission(image="gradle:jdk17", main_cmd="gradle --version", limits=ResourceLimits(mem_limit="1g", timeout_seconds=45.0)))

TEMPLATES["go-benchmem"] = BenchmarkTemplate(id="go-benchmem", name="Go Benchmark MemAllocs", category="Performance", description="Runs go test -bench=. -benchmem.", task=TaskSubmission(image="golang:1.22-alpine", main_cmd="go version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

def count_total_templates() -> int:
    """Return total number of registered benchmark templates."""
    return len(TEMPLATES)

def get_templates_by_category(category: str) -> list[BenchmarkTemplate]:
    """Return benchmark templates in specified category."""
    return [t for t in TEMPLATES.values() if t.category.lower() == category.lower()]

TEMPLATES["zig-build"] = BenchmarkTemplate(id="zig-build", name="Zig Compiler Suite", category="Systems", description="Compiles and tests Zig source code.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Zig OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["ocaml-dune"] = BenchmarkTemplate(id="ocaml-dune", name="OCaml Dune Runner", category="Functional", description="Executes OCaml Dune build harness.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Dune OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["haskell-cabal"] = BenchmarkTemplate(id="haskell-cabal", name="Haskell Cabal Test", category="Functional", description="Runs Haskell Cabal test suites.", task=TaskSubmission(image="haskell:9.6", main_cmd="echo Cabal OK", limits=ResourceLimits(mem_limit="512m", timeout_seconds=25.0)))

TEMPLATES["scala-cli"] = BenchmarkTemplate(id="scala-cli", name="Scala CLI Runner", category="JVM", description="Runs Scala CLI scripts and assertions.", task=TaskSubmission(image="eclipse-temurin:21", main_cmd="echo Scala OK", limits=ResourceLimits(mem_limit="512m", timeout_seconds=20.0)))

TEMPLATES["gleam-test"] = BenchmarkTemplate(id="gleam-test", name="Gleam Erlang Target", category="Functional", description="Runs Gleam BEAM test suite.", task=TaskSubmission(image="erlang:26-alpine", main_cmd="echo Gleam OK", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["deno-run"] = BenchmarkTemplate(id="deno-run", name="Deno Modern Runtime", category="JavaScript", description="Executes secure sandboxed Deno tasks.", task=TaskSubmission(image="denoland/deno:alpine", main_cmd="deno --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["bun-test"] = BenchmarkTemplate(id="bun-test", name="Bun Fast Test Runner", category="JavaScript", description="Runs Bun native test runner.", task=TaskSubmission(image="oven/bun:alpine", main_cmd="bun --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=15.0)))

TEMPLATES["vitest-run"] = BenchmarkTemplate(id="vitest-run", name="Vitest ESM Framework", category="JavaScript", description="Executes Vitest test suites.", task=TaskSubmission(image="node:20-alpine", main_cmd="node --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["playwright-test"] = BenchmarkTemplate(id="playwright-test", name="Playwright Headless", category="Testing", description="Runs Playwright headless browser test.", task=TaskSubmission(image="mcr.microsoft.com/playwright:v1.42.0-jammy", main_cmd="echo Playwright OK", limits=ResourceLimits(mem_limit="1g", timeout_seconds=40.0)))

TEMPLATES["cypress-run"] = BenchmarkTemplate(id="cypress-run", name="Cypress Headless Spec", category="Testing", description="Executes Cypress end-to-end specs.", task=TaskSubmission(image="cypress/included:13.6.0", main_cmd="echo Cypress OK", limits=ResourceLimits(mem_limit="1g", timeout_seconds=45.0)))

TEMPLATES["k6-load"] = BenchmarkTemplate(id="k6-load", name="K6 Performance Benchmark", category="Performance", description="Runs K6 load testing script.", task=TaskSubmission(image="grafana/k6:latest", main_cmd="k6 version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["locust-test"] = BenchmarkTemplate(id="locust-test", name="Locust Load Testing", category="Performance", description="Runs Locust swarm benchmark.", task=TaskSubmission(image="locustio/locust:latest", main_cmd="locust --version", limits=ResourceLimits(mem_limit="256m", timeout_seconds=20.0)))

TEMPLATES["vegeta-attack"] = BenchmarkTemplate(id="vegeta-attack", name="Vegeta HTTP Attack", category="Performance", description="Runs Vegeta HTTP load testing tool.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo Vegeta OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))

TEMPLATES["ab-bench"] = BenchmarkTemplate(id="ab-bench", name="ApacheBench HTTP Benchmark", category="Performance", description="Runs ApacheBench ab tool.", task=TaskSubmission(image="alpine:3.19", main_cmd="echo AB OK", limits=ResourceLimits(mem_limit="128m", timeout_seconds=15.0)))
