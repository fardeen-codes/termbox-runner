# Production Deployment Checklist

## Environment & Infrastructure
- [ ] Mount `/var/run/docker.sock` with minimal privileges or use Docker-in-Docker (DinD).
- [ ] Set `TERMBOX_DB_PATH` on persistent SSD volume.
- [ ] Configure `TERMBOX_MAX_LOG_BUFFER_BYTES` to cap runaway agent log output.
- [ ] Enable WAL mode on SQLite (default enabled).
- [ ] Expose metrics via Prometheus or `/stats/summary`.
