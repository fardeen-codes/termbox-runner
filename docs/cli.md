# Termbox Runner CLI Guide

`termbox` is the command-line companion tool to inspect runs, query health, and trigger replays.

## Commands
- `termbox health`: Check runner status and Docker availability.
- `termbox list`: Display recent task execution manifests.
- `termbox inspect <run_id>`: View execution logs and telemetry.
- `termbox run '<command>'`: Run a sandboxed task.
- `termbox replay <run_id>`: Replay a previous run.
- `termbox templates`: List available benchmark templates.
