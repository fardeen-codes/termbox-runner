# Termbox Runner Operational Runbook & Troubleshooting

## Overview
This runbook provides actionable procedures for diagnosing, triaging, and resolving common infrastructure, sandboxing, and classification issues in Termbox Runner.

---

## 1. Quick Diagnostics with CLI

Run the built-in diagnostic doctor:
```bash
termbox doctor
```

Verify server health and active task workers:
```bash
termbox health
curl -s http://localhost:8000/health | jq .
```

---

## 2. Docker Daemon & Socket Permissions

### Symptoms:
- `docker_available` reports `false` in `GET /health`.
- Runner automatically falls back to deterministic mock execution mode.

### Triage:
1. Ensure Docker system service is running:
   ```bash
   sudo systemctl status docker
   ```
2. Verify access permissions on the UNIX domain socket `/var/run/docker.sock`:
   ```bash
   ls -la /var/run/docker.sock
   ```
3. Add the application execution user to the `docker` system group:
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```

---

## 3. Sandboxed Failure Modes & Mitigation

### Out-of-Memory (`OOM_KILLED` / Exit 137)
- **Container OOM:** The container memory usage breached `limits.mem_limit` (default: `512m`). The Linux OOM killer terminated the root PID with SIGKILL.
  - *Fix:* Increase `mem_limit` in the task request (e.g., `"1g"` or `"2g"`).
- **JVM Heap Exhaustion:** `java.lang.OutOfMemoryError: Java heap space`.
  - *Fix:* Add `-Xmx` parameter to task command or scale container RAM limit.

### Fatal Signals (SIGSEGV / Exit 139)
- **Segmentation Fault:** Native code attempted to access unauthorized memory addresses or suffered a stack overflow.
  - *Fix:* Inspect core dump, check shared library linkage (`ldd`), or increase stack size via `ulimit -s`.

### Network Isolation Errors
- By default, `network_mode="none"` prevents sandboxed containers from reaching external networks.
- If dependencies must be installed at runtime, pre-install them into custom Docker base images rather than enabling network access in untrusted evaluation runs.

---

## 4. SQLite Database Maintenance

If the SQLite database experiences contention or large footprints:
```bash
# Check database integrity
termbox integrity

# View disk footprint
termbox db-size
```
