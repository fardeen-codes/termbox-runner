# 📦 Termbox Runner

> **Deterministic Sandboxed Task Runner & Evaluation Harness for Coding/CLI Agents and Automated Verifiers.**

`termbox-runner` is an isolated, reproducible execution engine built for benchmark evaluation, AI coding agent assessment, and test harness execution. It enforces hard wall-clock timeouts, CPU quotas, memory caps, PID bounds, and strict network isolation (`network_mode="none"`) inside ephemeral Docker sandboxes—with guaranteed cleanup and replay lineage tracking.

---

## 🏛️ Architecture & Execution Model

```
 ┌─────────────────────────────────────────────────────────────┐
 │                     Client / Agent                          │
 └──────────────┬──────────────────────────────▲───────────────┘
                │ HTTP POST /runs              │ RunManifest
                ▼                              │
 ┌─────────────────────────────────────────────────────────────┐
 │             FastAPI Application Layer (api.py)              │
 │   - Synchronous / Async execution options                   │
 │   - Replay lineage resolution (/runs/{id}/replay, /lineage) │
 │   - Dark-mode engineering inspection UI (/ui)               │
 └──────────────┬──────────────────────────────▲───────────────┘
                │ TaskSubmission               │ Manifest
                ▼                              │
 ┌─────────────────────────────────────────────────────────────┐
 │            Execution Sandbox Engine (runner.py)             │
 │                                                             │
 │   1. Temp Workspace Preparation (files injection)           │
 │   2. Docker Container Creation (cgroups & namespaces)       │
 │      - mem_limit + memswap_limit (Strict OOM enforcement)   │
 │      - nano_cpus / cpu_quota                                │
 │      - pids_limit (fork bomb mitigation)                    │
 │      - network_mode="none" (strict airgap)                  │
 │   3. Sequential Phase Execution (/workspace):               │
 │      ┌───────────┐    ┌───────────┐    ┌──────────────┐     │
 │      │ SETUP_CMD │ ─► │ MAIN_CMD  │ ─► │ VERIFIER_CMD │     │
 │      └───────────┘    └───────────┘    └──────────────┘     │
 │   4. Hard Wall-Clock Budget & Timeout Timer                 │
 │   5. Guaranteed Cleanup (try/finally stop + rm -f)          │
 └──────────────┬──────────────────────────────▲───────────────┘
                │ Raw telemetry & step results │
                ▼                              │
 ┌─────────────────────────────────────────────────────────────┐
 │       Deterministic Classification Engine (classifier.py)   │
 │                                                             │
 │   Priority:                                                 │
 │   1. TIMEOUT          (Wall-clock exceeded / exit 124)      │
 │   2. OOM_KILLED       (Docker OOM flag / SIGKILL 137)       │
 │   3. SETUP_ERROR      (Non-zero setup exit code)            │
 │   4. ASSERTION_FAILED (Verifier failure / pytest assert)    │
 │   5. RUNTIME_ERROR    (Main command non-zero crash)         │
 │   6. PASSED           (All phases exit 0)                   │
 └──────────────┬──────────────────────────────────────────────┘
                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │              Persistent Storage (storage.py)                │
 │   SQLite (aiosqlite) with recursive lineage queries         │
 └─────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

- **Strict Sandbox Constraints**: Configure exact memory (`mem_limit`, e.g., `256m`, `1g`), CPU quota (`nano_cpus`), process limits (`pids_limit`), and network policies (`network_mode="none"`).
- **Hard Timeout Enforcement**: Guaranteed termination on wall-clock expiration, terminating lingering subprocesses and cleaning up containers immediately.
- **Deterministic Failure Classifier**: Eliminates ambiguous test outcomes by categorizing executions into `PASSED`, `ASSERTION_FAILED`, `TIMEOUT`, `OOM_KILLED`, `SETUP_ERROR`, or `RUNTIME_ERROR`.
- **Replay Lineage**: Trace the full evolutionary history of runs (`parent_run_id`), re-executing previous tasks with modified limits or patches while preserving ancestry.
- **Graceful Fallback & Offline Testing**: Includes `MockTaskExecutor` so unit tests and CI pipelines can simulate execution outcomes deterministically even without an active Docker daemon.
- **Dark-Mode Engineering Dashboard**: Built-in visual UI served at `/` and `/ui` to submit runs, inspect logs, run presets, trigger replays, and view live step metrics.

---

## 🚀 Quickstart

### Prerequisites

- Python 3.11+
- Docker Engine (optional if using mock mode)
- `uv` (recommended) or `pip`

### 1. Installation

```bash
git clone https://github.com/fardeen-codes/termbox-runner.git
cd termbox-runner

# Using uv
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Run the Server

```bash
uvicorn termbox_runner.api:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser to:
- **UI Dashboard**: [http://localhost:8000/ui](http://localhost:8000/ui)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🐳 Docker & Docker Compose Setup

Run the entire runner inside Docker with persistence and host Docker daemon access:

```bash
docker compose up -d --build
```

The container mounts `/var/run/docker.sock` to orchestrate sibling task containers directly on the host engine.

---

## 🧪 Testing

Run the full pytest suite covering models, failure classification, replay lineage, sandbox execution, and API routes:

```bash
pytest -v
```

---

## 📡 API Reference & Example `curl` Commands

### 1. System Health Check

```bash
curl -s http://localhost:8000/health | jq .
```
```json
{
  "status": "ok",
  "version": "0.1.0",
  "docker_available": true,
  "active_runs": 0,
  "timestamp": "2026-11-19T17:00:00Z"
}
```

### 2. Clean Pass Execution

Execute a task with injected files that completes successfully:

```bash
curl -s -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "image": "python:3.12-slim",
    "main_cmd": "python -c \"import math; print(\x27Result:\x27, math.factorial(5))\"",
    "limits": {
      "timeout_seconds": 15,
      "mem_limit": "256m"
    }
  }' | jq '{run_id, status, failure_mode, exit_code, duration_ms, stdout: .combined_stdout}'
```

### 3. Automated Verifier Assertion Failure

Execute an agent task followed by a verifier test suite (`pytest`) that catches an assertion error:

```bash
curl -s -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "image": "python:3.12-slim",
    "main_cmd": "python -c \"print(\x27Agent finished work\x27)\"",
    "verifier_cmd": "python -c \"assert 1 + 1 == 3, \x27Arithmetic assertion failed\x27\"",
    "limits": {
      "timeout_seconds": 15
    }
  }' | jq '{run_id, failure_mode, failure_reason, exit_code}'
```
Output:
```json
{
  "run_id": "run_a1b2c3d4e5f6",
  "failure_mode": "ASSERTION_FAILED",
  "failure_reason": "Verifier assertion/evaluation failed with exit code 1. Details: AssertionError: Arithmetic assertion failed",
  "exit_code": 1
}
```

### 4. Wall-Clock Timeout Enforcement

Submit a hanging process with a strict 2-second timeout:

```bash
curl -s -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "image": "python:3.12-slim",
    "main_cmd": "sleep 30",
    "limits": {
      "timeout_seconds": 2
    }
  }' | jq '{run_id, failure_mode, failure_reason, duration_ms}'
```
Output:
```json
{
  "run_id": "run_9876543210ab",
  "failure_mode": "TIMEOUT",
  "failure_reason": "Step \x27MAIN\x27 timed out during execution.",
  "duration_ms": 2010.5
}
```

### 5. Memory Limit & OOM Killer (Exit Code 137)

Submit a memory-hungry task restricted by a 32MB container memory cap:

```bash
curl -s -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "image": "python:3.12-slim",
    "main_cmd": "python -c \"b = bytearray(120 * 1024 * 1024)\"",
    "limits": {
      "mem_limit": "32m",
      "timeout_seconds": 15
    }
  }' | jq '{run_id, failure_mode, failure_reason, exit_code}'
```
Output:
```json
{
  "run_id": "run_oom123456789",
  "failure_mode": "OOM_KILLED",
  "failure_reason": "Container was terminated by Docker Out-Of-Memory (OOM) killer.",
  "exit_code": 137
}
```

### 6. Replaying a Previous Run with Lineage

Trigger a replay of an existing run ID, optionally overriding commands or limits:

```bash
# Replay run_oom123456789 with higher memory limit
curl -s -X POST http://localhost:8000/runs/run_oom123456789/replay \
  -H "Content-Type: application/json" \
  -d '{
    "override_limits": {
      "mem_limit": "256m",
      "timeout_seconds": 20
    }
  }' | jq '{run_id, parent_run_id, failure_mode, exit_code}'
```

### 7. Inspecting Lineage Family Tree

Fetch all ancestral generations and child replays:

```bash
curl -s http://localhost:8000/runs/run_oom123456789/lineage | jq .
```

### 8. Listing Runs with Filters

```bash
# Filter only OOM killed executions
curl -s "http://localhost:8000/runs?failure_mode=OOM_KILLED&limit=10" | jq .
```

---

## ⚙️ Configuration Reference

All settings can be configured via environment variables prefixed with `TERMBOX_`:

| Variable | Default | Description |
|---|---|---|
| `TERMBOX_HOST` | `0.0.0.0` | Bind IP host |
| `TERMBOX_PORT` | `8000` | Bind port |
| `TERMBOX_DB_PATH` | `termbox_runner.db` | SQLite database file location |
| `TERMBOX_DEFAULT_DOCKER_IMAGE` | `python:3.12-slim` | Default image if not specified in task |
| `TERMBOX_DEFAULT_TIMEOUT_SECONDS` | `30.0` | Default execution timeout in seconds |
| `TERMBOX_MAX_TIMEOUT_SECONDS` | `300.0` | Upper bound for requested timeouts |
| `TERMBOX_DEFAULT_MEM_LIMIT` | `512m` | Default container memory constraint |
| `TERMBOX_MAX_MEM_LIMIT` | `2g` | Maximum allowed memory limit |
| `TERMBOX_DEFAULT_CPU_QUOTA` | `1.0` | Default CPU allocation in cores |
| `TERMBOX_DEFAULT_PIDS_LIMIT` | `128` | Maximum concurrent process count |
| `TERMBOX_DEFAULT_NETWORK_MODE` | `none` | Network sandboxing policy (`none` recommended) |
| `TERMBOX_ALLOW_NETWORK_OVERRIDE` | `true` | Whether clients may request network access |
| `TERMBOX_EXECUTION_MODE` | `docker` | Engine mode: `docker` or `mock` |

---

## ⚠️ Known Limitations & Operational Considerations

1. **Host Docker Socket Access**:
   When running `termbox-runner` inside a container via `docker-compose`, sibling containers share the host's volume filesystem. File injection mounts default to `/tmp/termbox_workspaces`.
2. **Cgroups v2 Requirement**:
   Strict memory limit enforcement without swap requires host support for cgroups v2 (`/sys/fs/cgroup`). If swap is enabled on older kernels, processes might swap rather than immediately receiving SIGKILL unless swap limit is set equal to memory limit (which termbox-runner configures by default).
3. **Privileged Escalation**:
   User commands run inside root or default container users. For multi-tenant hostile code execution, rootless Docker or user namespaces (`userns-remap`) and gVisor (`runsc`) runtime flags are recommended in hardened production clusters.

---

## 📄 License

MIT License. Designed and maintained for production AI benchmark evaluation and agent sandboxing.
