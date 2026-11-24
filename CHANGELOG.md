
## [0.3.0] - Enterprise Sandboxing & Multi-Language Milestone

### Added
- 20+ Multi-language benchmark presets (TypeScript, C#, Kotlin, Elixir, Scala, Swift, Rego OPA).
- CLI companion utilities: timeline, metrics, integrity, percentiles, export formatters.
- Interactive Gantt timeline visualization and theme customization.
- Strict container security options: tmpfs mounts, zero-swap limits, seccomp profiles.


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

## [0.4.0] - 2026-11-24
### Added
- AppArmor and Seccomp security profiles with read-only rootfs validation.
- SWE-bench and security benchmark templates (Django, Flask, SQLi, ReDoS).
- OpenTelemetry span schemas and W3C traceparent context injection.
- Multi-format CI test reporters: GitHub Step Summary, GitLab JUnit, SARIF v2.1.0, Cobertura, LCOV.
- SQLite query optimization pragmas, log compression, and schema migrations.
