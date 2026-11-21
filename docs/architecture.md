# Architecture & Security Boundary

```
[Client / Agent] -> [FastAPI REST / CLI] -> [Task Executor (Docker / Mock)] -> [Isolated Cgroup Container]
                                     |
                             [SQLite Storage] (Replay Lineage, Artifacts, Telemetry)
```

## Security Hardening
- Network isolation by default (`network_mode="none"`).
- Read-only root filesystem option.
- Linux capabilities dropped (`drop_capabilities=["ALL"]`).
- Resource boundaries: memory caps, CPU quotas, process caps.
