
## [0.2.0] - Extensibility & Observability Milestone

### Added
- System telemetry and host load average recording.
- Real-time run differential analysis and unified diff generation.
- Chat webhook notifications for Slack and Discord.
- SonarQube XML and TAP v13 test export formatters.
- Enhanced CLI commands: `stats`, `top`, `prune`, `logs`, `diff`, `search`.
- Configurable tmpfs mounts and Linux capabilities dropping.

# Changelog

## [0.1.0] - Production Release

### Added
- Sandboxed Docker task runner with memory, CPU, PID, and network isolation.
- Deterministic failure mode classifier for OOM, timeouts, assertions, and runtime errors.
- Persistent SQLite storage with full replay lineage trees.
- Interactive dark-mode dashboard with benchmark presets and real-time inspector.
- Multi-language benchmark templates catalog.
- CLI interface (`termbox`) with health, list, inspect, run, and replay commands.
- Export formats: SARIF v2.1.0, JUnit XML, CSV, and Markdown.
