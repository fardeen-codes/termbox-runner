# Termbox Runner Troubleshooting Guide

## Common Issues & Diagnoses

### 1. Docker Daemon Not Reachable (`docker_available: false`)
- Verify Docker is running: `sudo systemctl status docker`
- Ensure current user is in `docker` group: `sudo usermod -aG docker $USER`
- Check mock mode fallback: configured via `TERMBOX_EXECUTION_MODE=mock`.

### 2. Timeouts (`TIMEOUT`)
- Increase timeout limit in task submission: `limits.timeout_seconds: 60.0`.
- Verify CPU contention on host.

### 3. Out of Memory (`OOM_KILLED` / Exit 137)
- Default container limit is `512m`. Increase via `limits.mem_limit: "1g"`.
