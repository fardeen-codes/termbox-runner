# REST API Reference

Full HTTP endpoint specifications for Termbox Runner.

- `POST /runs`: Submit a new task execution.
- `GET /runs`: List execution manifests.
- `GET /runs/{run_id}`: Retrieve manifest and telemetry.
- `POST /runs/{run_id}/replay`: Replay execution with lineage tracking.
- `GET /metrics`: Prometheus metrics scraper endpoint.
