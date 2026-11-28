
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

## [0.5.0] - 2026-11-25
### Added
- Extended runtime diagnostics for Ruby, PHP fatal errors, Rust panic backtraces, and Go deadlocks.
- Benchmark templates for Ruby RSpec, Go CPU profiling, and Rust Cargo clippy.
- Bazel test.xml and CTRF standard test report format exporters.
- Daily run aggregation statistics and `/stats/daily` endpoint.
- CI/CD agent evaluation harness integration guide.

## [0.6.0] - 2026-11-26
### Added
- Strict network seccomp profiles and container PID/IPC namespace isolation flags.
- Extended error diagnostics for Haskell, OCaml, Zig, and AddressSanitizer (ASan).
- Functional & systems language benchmark templates (Haskell Cabal, OCaml Dune, Zig test).
- Allure 2.x test report exporter and memory page faults telemetry metrics.
- AddressSanitizer debugging guide in docs.

## [0.7.0] - 2026-11-27
### Added
- Cgroups v2 controllers (memory.high, cpu.weight, io.weight) and tier presets (LOW, STANDARD, HIGH, EVAL).
- Multi-language error classification for Perl, R, Julia, Scala, Kotlin, Swift, Dart, Lua, Elixir, and Clojure.
- Web framework & security benchmark presets (Express, NestJS, Actix-web, CORS, JWT, Alembic, Prisma).
- Enterprise CI/CD exporters for CircleCI, Azure DevOps, Bitbucket Pipelines, and SVG Status Badges.
- SQLite exit codes distribution, average duration analytics, and WAL checkpoint endpoints.

## [0.8.0] - 2026-11-27
### Added
- Extended container configuration: custom DNS servers, DNS search domains, extra /etc/hosts entries.
- Runtime classifiers for Erlang, Common Lisp, F#, Groovy, Ada, D, Nim, Crystal, V, Valgrind, and Fortran.
- Evaluation benchmark presets for Common Lisp, Rebar3, Spock, GNAT, Dub, Nimble, OpenAPI, Terraform, and Ansible.
- TAP 14 output generator and HMAC-SHA256 webhook signatures.
- Memory page reclamation and network bandwidth telemetry metrics.

## [0.9.0] - 2026-11-27
### Added
- Advanced OOM killer score adjustment (`oom_score_adj`) and CPU shares weighting.
- Runtime diagnostics for Racket, Scheme, FreePascal, COBOL, GAS Assembler, LLVM crashes, and Strace errors.
- Data science & OLAP benchmark templates: DuckDB, Polars, PyArrow, Fastparquet, Wasmtime.
- Standard deviation and Median Absolute Deviation (MAD) duration analytics.
- Jenkins JUnit and Travis CI folding log export integrations.

## [1.0.0] - 2026-11-27
### Added
- Production-grade multi-tenant container isolation and cgroups v2 resource quotas.
- Extensive language diagnostics covering 20+ programming languages and fatal signals.
- 50+ benchmark templates for web, systems, database, AI/ML, and security evaluation.
- Enterprise CI/CD reporting formats (GitHub Summary, GitLab, CircleCI, Azure DevOps, Allure, TAP 14, Jenkins).
- Distributed telemetry, SLA latency percentiles, and SQLite high-performance WAL optimizations.

## [1.1.0] - 2026-11-28
### Added
- Extended language templates for Zig, Deno, Bun, and OCaml.
- Slack Block Kit and Discord Webhook alert exporters.
- Telemetry TPS, latency jitter, and EMA trackers.
- Ulimits parsing and security hardening validators.
