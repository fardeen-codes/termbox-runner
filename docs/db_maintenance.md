# SQLite Database Maintenance & WAL Management

## Automatic Checkpoints
Trigger manual checkpoint via REST API:
```bash
curl -X POST http://localhost:8000/system/db/wal-checkpoint
```

## Reindexing
```bash
curl -X POST http://localhost:8000/system/db/reindex
```
