# OpenTelemetry & Observability Guide

## Distributed Tracing
Every task execution receives a standard W3C `traceparent` header injected into the sandbox environment:
- `TRACEPARENT=00-{trace_id}-{span_id}-01`
- `OTEL_TRACE_ID={trace_id}`

## Exporting Spans
Query active and completed trace spans via:
```bash
curl -s http://localhost:8000/telemetry/spans
```
