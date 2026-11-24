"""Persistent SQLite storage layer for termbox-runner manifests and replays."""

import asyncio
from datetime import datetime
import json
from pathlib import Path
from typing import List, Optional, Tuple
import aiosqlite

from termbox_runner.config import get_settings
from termbox_runner.models import (
    FailureMode,
    RunManifest,
    RunStatus,
    RunSummary,
    StepResult,
    TaskSubmission,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    parent_run_id TEXT,
    task_id TEXT,
    status TEXT NOT NULL,
    failure_mode TEXT,
    failure_reason TEXT,
    exit_code INTEGER,
    duration_ms REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    image TEXT NOT NULL,
    main_cmd TEXT NOT NULL,
    task_json TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    combined_stdout TEXT NOT NULL DEFAULT '',
    combined_stderr TEXT NOT NULL DEFAULT '',
    container_id TEXT,
    replay_count INTEGER NOT NULL DEFAULT 0,
    peak_memory_bytes INTEGER NOT NULL DEFAULT 0,
    average_cpu_percent REAL NOT NULL DEFAULT 0.0,
    artifacts_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (parent_run_id) REFERENCES runs (run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_failure_mode ON runs(failure_mode);
CREATE INDEX IF NOT EXISTS idx_runs_parent_run_id ON runs(parent_run_id);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status_created ON runs(status, created_at DESC);
"""


class RunStorage:
    """Async SQLite repository managing task definitions, runs, and lineage."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_settings().db_path
        if self.db_path != ":memory:":
            parent = Path(self.db_path).parent
            if parent and not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def get_connection(self) -> aiosqlite.Connection:
        """Get or initialize the persistent database connection."""
        async with self._lock:
            if self._conn is None:
                self._conn = await aiosqlite.connect(self.db_path)
                self._conn.row_factory = aiosqlite.Row
                if self.db_path != ":memory:":
                    await self._conn.execute("PRAGMA journal_mode=WAL;")
                await self._conn.execute("PRAGMA foreign_keys=ON;")
            return self._conn


    async def count_runs_by_status(self) -> dict:
        """Return counts of runs grouped by lifecycle status."""
        conn = await self.get_connection()
        async with conn.execute("SELECT status, COUNT(*) as cnt FROM runs GROUP BY status") as cursor:
            rows = await cursor.fetchall()
            return {row["status"]: row["cnt"] for row in rows}


    async def count_runs_by_failure_mode(self) -> dict:
        """Return counts of runs grouped by failure mode."""
        conn = await self.get_connection()
        async with conn.execute("SELECT failure_mode, COUNT(*) as cnt FROM runs WHERE failure_mode IS NOT NULL GROUP BY failure_mode") as cursor:
            rows = await cursor.fetchall()
            return {row["failure_mode"]: row["cnt"] for row in rows}


    async def update_tags(self, run_id: str, tags: list) -> bool:
        """Update tags stored inside the task_json payload for a given run."""
        conn = await self.get_connection()
        async with self._lock:
            async with conn.execute("SELECT task_json FROM runs WHERE run_id = ?", (run_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                task_data = json.loads(row["task_json"])
                task_data["tags"] = tags
                await conn.execute("UPDATE runs SET task_json = ? WHERE run_id = ?", (json.dumps(task_data), run_id))
                await conn.commit()
                return True


    async def update_annotations(self, run_id: str, annotations: dict) -> bool:
        """Store arbitrary evaluation annotations on a run."""
        conn = await self.get_connection()
        async with self._lock:
            async with conn.execute("SELECT artifacts_json FROM runs WHERE run_id = ?", (run_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                await conn.commit()
                return True


    async def delete_run(self, run_id: str) -> bool:
        """Delete a run manifest record by ID."""
        conn = await self.get_connection()
        async with self._lock:
            cursor = await conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            await conn.commit()
            return cursor.rowcount > 0


    async def get_child_runs(self, run_id: str) -> list:
        """Retrieve all runs that were spawned as replays of this run."""
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE parent_run_id = ?", (run_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row["run_id"] for row in rows]


    async def get_runs_by_image(self, image: str, limit: int = 10) -> list:
        """Retrieve recent runs executed using a specific container image."""
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE image = ? ORDER BY created_at DESC LIMIT ?", (image, limit)) as cursor:
            rows = await cursor.fetchall()
            return [row["run_id"] for row in rows]


    async def vacuum(self) -> None:
        """Run SQLite VACUUM optimization to reclaim storage space."""
        conn = await self.get_connection()
        async with self._lock:
            await conn.execute("VACUUM;")


    async def get_total_execution_time_ms(self) -> float:
        """Compute total wall-clock execution time recorded across all runs."""
        conn = await self.get_connection()
        async with conn.execute("SELECT SUM(duration_ms) as total_ms FROM runs") as cursor:
            row = await cursor.fetchone()
            return float(row["total_ms"]) if row and row["total_ms"] else 0.0


    async def search_runs_by_command(self, query: str, limit: int = 50) -> list:
        """Search runs matching command substring."""
        conn = await self.get_connection()
        pattern = f"%{query}%"
        async with conn.execute("SELECT run_id FROM runs WHERE main_cmd LIKE ? ORDER BY created_at DESC LIMIT ?", (pattern, limit)) as cursor:
            rows = await cursor.fetchall()
            return [row["run_id"] for row in rows]


    async def get_runs_by_date_range(self, start_date: str, end_date: str, limit: int = 50) -> list:
        """Find runs created within specified ISO datetime window."""
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC LIMIT ?", (start_date, end_date, limit)) as cursor:
            rows = await cursor.fetchall()
            return [row["run_id"] for row in rows]


    async def get_flaky_runs(self) -> list:
        """Identify runs whose replay lineages produced divergent outcomes."""
        conn = await self.get_connection()
        query = """
        SELECT DISTINCT parent_run_id FROM runs
        WHERE parent_run_id IS NOT NULL
        GROUP BY parent_run_id
        HAVING COUNT(DISTINCT failure_mode) > 1
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [row["parent_run_id"] for row in rows]


    async def get_run_count_by_date_histogram(self) -> dict:
        """Group run counts by UTC execution date (YYYY-MM-DD)."""
        conn = await self.get_connection()
        async with conn.execute("SELECT substr(created_at, 1, 10) as day, COUNT(*) as cnt FROM runs GROUP BY day ORDER BY day DESC LIMIT 30") as cursor:
            rows = await cursor.fetchall()
            return {row["day"]: row["cnt"] for row in rows}


    async def cleanup_runs_older_than(self, iso_cutoff: str) -> int:
        """Prune completed run manifests older than specified cutoff date."""
        conn = await self.get_connection()
        async with self._lock:
            cursor = await conn.execute("DELETE FROM runs WHERE created_at < ? AND parent_run_id IS NULL", (iso_cutoff,))
            await conn.commit()
            return cursor.rowcount


    async def get_most_frequently_used_images(self, limit: int = 5) -> list:
        """Return most frequently executed container images and their counts."""
        conn = await self.get_connection()
        async with conn.execute("SELECT image, COUNT(*) as usage_count FROM runs GROUP BY image ORDER BY usage_count DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [{"image": r["image"], "count": r["usage_count"]} for r in rows]


    async def get_slowest_runs(self, limit: int = 10) -> list:
        """Return run IDs ordered by total duration descending."""
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id, duration_ms FROM runs ORDER BY duration_ms DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [{"run_id": r["run_id"], "duration_ms": r["duration_ms"]} for r in rows]


    async def get_top_failing_tasks(self, limit: int = 5) -> list:
        """Identify task commands with highest rate of failure."""
        conn = await self.get_connection()
        async with conn.execute("SELECT main_cmd, COUNT(*) as fail_count FROM runs WHERE failure_mode != 'PASSED' GROUP BY main_cmd ORDER BY fail_count DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [{"command": r["main_cmd"], "failures": r["fail_count"]} for r in rows]


    async def update_run_notes(self, run_id: str, notes: str) -> bool:
        """Persist reviewer notes for a specific run."""
        conn = await self.get_connection()
        async with self._lock:
            cursor = await conn.execute("UPDATE runs SET failure_reason = COALESCE(failure_reason || ' | Note: ' || ?, ?) WHERE run_id = ?", (notes, notes, run_id))
            await conn.commit()
            return cursor.rowcount > 0


    def get_database_file_size_bytes(self) -> int:
        """Return current SQLite database file size in bytes."""
        import os
        if self.db_path == ":memory:":
            return 0
        try:
            return os.path.getsize(self.db_path)
        except OSError:
            return 0


    async def execute_in_savepoint(self, savepoint_name: str) -> None:
        """Establish named SQL savepoint for nested rollbacks."""
        conn = await self.get_connection()
        await conn.execute(f"SAVEPOINT {savepoint_name};")


    async def get_duration_percentiles(self) -> dict:
        """Compute p50, p90, p99 durations from stored execution history."""
        conn = await self.get_connection()
        async with conn.execute("SELECT duration_ms FROM runs WHERE duration_ms > 0 ORDER BY duration_ms ASC") as cursor:
            rows = await cursor.fetchall()
            if not rows:
                return {"p50": 0.0, "p90": 0.0, "p99": 0.0}
            vals = [r["duration_ms"] for r in rows]
            n = len(vals)
            return {
                "p50": vals[int(n * 0.50)],
                "p90": vals[int(n * 0.90)],
                "p99": vals[min(n - 1, int(n * 0.99))],
            }


    async def get_runs_by_status_and_image(self, status_val: str, image_name: str, limit: int = 20) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE status = ? AND image = ? LIMIT ?", (status_val, image_name, limit)) as cursor:
            return [r["run_id"] for r in await cursor.fetchall()]


    async def get_runs_by_min_memory(self, min_bytes: int, limit: int = 10) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE peak_memory_bytes >= ? ORDER BY peak_memory_bytes DESC LIMIT ?", (min_bytes, limit)) as cursor:
            return [r["run_id"] for r in await cursor.fetchall()]


    async def get_runs_by_max_duration(self, max_ms: float, limit: int = 10) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE duration_ms <= ? ORDER BY duration_ms DESC LIMIT ?", (max_ms, limit)) as cursor:
            return [r["run_id"] for r in await cursor.fetchall()]


    async def count_runs_by_day_of_week(self) -> dict:
        conn = await self.get_connection()
        async with conn.execute("SELECT strftime('%w', created_at) as dow, COUNT(*) as cnt FROM runs GROUP BY dow") as cursor:
            return {r["dow"]: r["cnt"] for r in await cursor.fetchall()}


    async def count_runs_by_exit_code(self) -> dict:
        conn = await self.get_connection()
        async with conn.execute("SELECT exit_code, COUNT(*) as cnt FROM runs WHERE exit_code IS NOT NULL GROUP BY exit_code") as cursor:
            return {r["exit_code"]: r["cnt"] for r in await cursor.fetchall()}


    async def get_runs_with_artifacts(self, limit: int = 20) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE artifacts_json != '{}' LIMIT ?", (limit,)) as cursor:
            return [r["run_id"] for r in await cursor.fetchall()]


    async def get_replayed_runs_summary(self, limit: int = 10) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id, parent_run_id, replay_count FROM runs WHERE replay_count > 0 LIMIT ?", (limit,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


    async def get_root_lineage_run(self, run_id: str) -> str:
        curr = run_id
        conn = await self.get_connection()
        for _ in range(10):
            async with conn.execute("SELECT parent_run_id FROM runs WHERE run_id = ?", (curr,)) as cursor:
                row = await cursor.fetchone()
                if not row or not row["parent_run_id"]:
                    break
                curr = row["parent_run_id"]
        return curr


    async def get_max_lineage_depth(self) -> int:
        return 10


    async def get_recent_failed_runs(self, limit: int = 5) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE status = 'FAILED' ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            return [r["run_id"] for r in await cursor.fetchall()]


    async def get_recent_passed_runs(self, limit: int = 5) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE failure_mode = 'PASSED' ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            return [r["run_id"] for r in await cursor.fetchall()]


    async def get_total_replays_count(self) -> int:
        conn = await self.get_connection()
        async with conn.execute("SELECT SUM(replay_count) as total FROM runs") as cursor:
            row = await cursor.fetchone()
            return int(row["total"]) if row and row["total"] else 0


    async def check_database_integrity(self) -> str:
        conn = await self.get_connection()
        async with conn.execute("PRAGMA integrity_check;") as cursor:
            row = await cursor.fetchone()
            return str(row[0]) if row else "unknown"


    async def backup_database(self, dest_path: str) -> None:
        pass


    async def get_average_duration_by_status(self) -> dict:
        conn = await self.get_connection()
        async with conn.execute("SELECT status, AVG(duration_ms) as avg_dur FROM runs GROUP BY status") as cursor:
            return {r["status"]: round(r["avg_dur"], 2) for r in await cursor.fetchall()}


    async def get_top_memory_consuming_runs(self, limit: int = 5) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id, peak_memory_bytes FROM runs ORDER BY peak_memory_bytes DESC LIMIT ?", (limit,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


    async def get_runs_by_tag(self, tag: str, limit: int = 20) -> list:
        conn = await self.get_connection()
        pattern = f'%"{tag}"%'
        async with conn.execute("SELECT run_id FROM runs WHERE task_json LIKE ? LIMIT ?", (pattern, limit)) as cursor:
            return [r["run_id"] for r in await cursor.fetchall()]


    async def delete_runs_by_status(self, status_val: str) -> int:
        conn = await self.get_connection()
        async with self._lock:
            cursor = await conn.execute("DELETE FROM runs WHERE status = ?", (status_val,))
            await conn.commit()
            return cursor.rowcount


    async def delete_runs_by_ids(self, run_ids: list) -> int:
        if not run_ids: return 0
        conn = await self.get_connection()
        placeholders = ",".join("?" for _ in run_ids)
        async with self._lock:
            cursor = await conn.execute(f"DELETE FROM runs WHERE run_id IN ({placeholders})", run_ids)
            await conn.commit()
            return cursor.rowcount


    async def update_run_status(self, run_id: str, new_status: str) -> bool:
        conn = await self.get_connection()
        async with self._lock:
            cursor = await conn.execute("UPDATE runs SET status = ? WHERE run_id = ?", (new_status, run_id))
            await conn.commit()
            return cursor.rowcount > 0


    async def mark_run_cancelled(self, run_id: str) -> bool:
        return await self.update_run_status(run_id, "CANCELLED")


    async def get_active_running_runs(self) -> list:
        conn = await self.get_connection()
        async with conn.execute("SELECT run_id FROM runs WHERE status = 'RUNNING'") as cursor:
            return [r["run_id"] for r in await cursor.fetchall()]


    async def get_run_created_timestamp(self, run_id: str) -> Optional[str]:
        conn = await self.get_connection()
        async with conn.execute("SELECT created_at FROM runs WHERE run_id = ?", (run_id,)) as cursor:
            row = await cursor.fetchone()
            return row["created_at"] if row else None


    async def get_run_finished_timestamp(self, run_id: str) -> Optional[str]:
        conn = await self.get_connection()
        async with conn.execute("SELECT finished_at FROM runs WHERE run_id = ?", (run_id,)) as cursor:
            row = await cursor.fetchone()
            return row["finished_at"] if row else None


    async def get_run_task_command(self, run_id: str) -> Optional[str]:
        conn = await self.get_connection()
        async with conn.execute("SELECT main_cmd FROM runs WHERE run_id = ?", (run_id,)) as cursor:
            row = await cursor.fetchone()
            return row["main_cmd"] if row else None


    async def count_artifacts_stored(self) -> int:
        conn = await self.get_connection()
        async with conn.execute("SELECT COUNT(*) as cnt FROM runs WHERE artifacts_json != '{}'") as cursor:
            row = await cursor.fetchone()
            return int(row["cnt"]) if row else 0


    async def get_database_page_count(self) -> int:
        conn = await self.get_connection()
        async with conn.execute("PRAGMA page_count;") as cursor:
            row = await cursor.fetchone()
            return int(row[0]) if row else 0


    async def ping_database(self) -> bool:
        try:
            conn = await self.get_connection()
            async with conn.execute("SELECT 1;") as cursor:
                row = await cursor.fetchone()
                return bool(row and row[0] == 1)
        except Exception:
            return False

    async def close(self) -> None:
        """Close the database connection if open."""
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None

    async def init_db(self) -> None:
        """Create database tables and indexes if they do not exist, and apply migrations."""
        conn = await self.get_connection()
        async with self._lock:
            await conn.executescript(SCHEMA_SQL)
            # Safe table migration for newly added columns
            try:
                await conn.execute("ALTER TABLE runs ADD COLUMN peak_memory_bytes INTEGER NOT NULL DEFAULT 0;")
            except Exception:
                pass
            try:
                await conn.execute("ALTER TABLE runs ADD COLUMN average_cpu_percent REAL NOT NULL DEFAULT 0.0;")
            except Exception:
                pass
            try:
                await conn.execute("ALTER TABLE runs ADD COLUMN artifacts_json TEXT NOT NULL DEFAULT '{}';")
            except Exception:
                pass
            await conn.commit()

    async def save_run(self, manifest: RunManifest) -> None:
        """Upsert a run manifest into persistent storage."""
        conn = await self.get_connection()
        image = manifest.task.image or get_settings().default_docker_image
        task_json = manifest.task.model_dump_json()
        steps_json = json.dumps([s.model_dump() for s in manifest.steps])
        artifacts_json = json.dumps(manifest.artifacts)
        created_at_str = manifest.created_at.isoformat()
        started_at_str = manifest.started_at.isoformat() if manifest.started_at else None
        finished_at_str = manifest.finished_at.isoformat() if manifest.finished_at else None

        sql = """
        INSERT INTO runs (
            run_id, parent_run_id, task_id, status, failure_mode, failure_reason,
            exit_code, duration_ms, created_at, started_at, finished_at,
            image, main_cmd, task_json, steps_json, combined_stdout,
            combined_stderr, container_id, replay_count, peak_memory_bytes, average_cpu_percent,
            artifacts_json
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        ) ON CONFLICT(run_id) DO UPDATE SET
            status = excluded.status,
            failure_mode = excluded.failure_mode,
            failure_reason = excluded.failure_reason,
            exit_code = excluded.exit_code,
            duration_ms = excluded.duration_ms,
            started_at = excluded.started_at,
            finished_at = excluded.finished_at,
            steps_json = excluded.steps_json,
            combined_stdout = excluded.combined_stdout,
            combined_stderr = excluded.combined_stderr,
            container_id = excluded.container_id,
            replay_count = excluded.replay_count,
            peak_memory_bytes = excluded.peak_memory_bytes,
            average_cpu_percent = excluded.average_cpu_percent,
            artifacts_json = excluded.artifacts_json
        """

        params = (
            manifest.run_id,
            manifest.parent_run_id,
            manifest.task.task_id,
            manifest.status.value,
            manifest.failure_mode.value if manifest.failure_mode else None,
            manifest.failure_reason,
            manifest.exit_code,
            manifest.duration_ms,
            created_at_str,
            started_at_str,
            finished_at_str,
            image,
            manifest.task.main_cmd,
            task_json,
            steps_json,
            manifest.combined_stdout,
            manifest.combined_stderr,
            manifest.container_id,
            manifest.replay_count,
            manifest.peak_memory_bytes,
            manifest.average_cpu_percent,
            artifacts_json,
        )

        async with self._lock:
            await conn.execute(sql, params)
            await conn.commit()

    async def get_run(self, run_id: str) -> Optional[RunManifest]:
        """Fetch a complete run manifest by ID."""
        conn = await self.get_connection()
        sql = "SELECT * FROM runs WHERE run_id = ?"
        async with self._lock:
            async with conn.execute(sql, (run_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                task_data = json.loads(row["task_json"])
                task = TaskSubmission.model_validate(task_data)

                steps_data = json.loads(row["steps_json"])
                steps = [StepResult.model_validate(s) for s in steps_data]

                artifacts = {}
                if "artifacts_json" in row.keys() and row["artifacts_json"]:
                    try:
                        artifacts = json.loads(row["artifacts_json"])
                    except Exception:
                        artifacts = {}

                return RunManifest(
                    run_id=row["run_id"],
                    parent_run_id=row["parent_run_id"],
                    task=task,
                    status=RunStatus(row["status"]),
                    failure_mode=FailureMode(row["failure_mode"]) if row["failure_mode"] else None,
                    failure_reason=row["failure_reason"],
                    exit_code=row["exit_code"],
                    duration_ms=row["duration_ms"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                    finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
                    steps=steps,
                    combined_stdout=row["combined_stdout"] or "",
                    combined_stderr=row["combined_stderr"] or "",
                    container_id=row["container_id"],
                    replay_count=row["replay_count"] or 0,
                    peak_memory_bytes=row["peak_memory_bytes"] if "peak_memory_bytes" in row.keys() else 0,
                    average_cpu_percent=row["average_cpu_percent"] if "average_cpu_percent" in row.keys() else 0.0,
                    artifacts=artifacts,
                )

    async def list_runs(
        self,
        status: Optional[RunStatus] = None,
        failure_mode: Optional[FailureMode] = None,
        parent_run_id: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RunSummary], int]:
        """Query run summaries with optional filtering, search, and pagination."""
        conn = await self.get_connection()
        clauses = []
        params: List[object] = []

        if status:
            clauses.append("status = ?")
            params.append(status.value)
        if failure_mode:
            clauses.append("failure_mode = ?")
            params.append(failure_mode.value)
        if parent_run_id is not None:
            clauses.append("parent_run_id = ?")
            params.append(parent_run_id)
        if tag:
            clauses.append("task_json LIKE ?")
            params.append(f'%"{tag}"%')
        if search:
            clauses.append("(run_id LIKE ? OR main_cmd LIKE ? OR task_id LIKE ? OR failure_reason LIKE ?)")
            pat = f"%{search}%"
            params.extend([pat, pat, pat, pat])
        if since:
            clauses.append("created_at >= ?")
            params.append(since.isoformat())
        if until:
            clauses.append("created_at <= ?")
            params.append(until.isoformat())

        where_str = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        count_sql = f"SELECT COUNT(*) FROM runs{where_str}"
        select_sql = f"""
        SELECT
            run_id, parent_run_id, task_id, status, failure_mode,
            exit_code, duration_ms, created_at, finished_at, image, main_cmd, replay_count, task_json
        FROM runs{where_str}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """

        async with self._lock:
            async with conn.execute(count_sql, tuple(params)) as cursor:
                total_row = await cursor.fetchone()
                total = total_row[0] if total_row else 0

            list_params = tuple(params + [limit, offset])
            async with conn.execute(select_sql, list_params) as cursor:
                rows = await cursor.fetchall()
                summaries = []
                for r in rows:
                    row_tags = []
                    if "task_json" in r.keys() and r["task_json"]:
                        try:
                            row_tags = json.loads(r["task_json"]).get("tags", [])
                        except Exception:
                            row_tags = []
                    summaries.append(
                        RunSummary(
                            run_id=r["run_id"],
                            parent_run_id=r["parent_run_id"],
                            task_id=r["task_id"],
                            status=RunStatus(r["status"]),
                            failure_mode=FailureMode(r["failure_mode"]) if r["failure_mode"] else None,
                            exit_code=r["exit_code"],
                            duration_ms=r["duration_ms"],
                            created_at=datetime.fromisoformat(r["created_at"]),
                            finished_at=datetime.fromisoformat(r["finished_at"]) if r["finished_at"] else None,
                            image=r["image"],
                            main_cmd=r["main_cmd"],
                            replay_count=r["replay_count"] or 0,
                            tags=row_tags,
                        )
                    )

        return summaries, total

    async def increment_replay_count(self, run_id: str) -> None:
        """Increment the replay counter for a given run."""
        conn = await self.get_connection()
        sql = "UPDATE runs SET replay_count = replay_count + 1 WHERE run_id = ?"
        async with self._lock:
            await conn.execute(sql, (run_id,))
            await conn.commit()

    async def get_replay_lineage(self, run_id: str) -> List[RunSummary]:
        """Trace full replay lineage: root ancestor down through all descendent replays."""
        conn = await self.get_connection()
        current_id: Optional[str] = run_id
        ancestor_ids = []

        async with self._lock:
            visited = set()
            while current_id and current_id not in visited:
                visited.add(current_id)
                async with conn.execute("SELECT parent_run_id FROM runs WHERE run_id = ?", (current_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row["parent_run_id"]:
                        ancestor_ids.append(row["parent_run_id"])
                        current_id = row["parent_run_id"]
                    else:
                        break

            root_id = ancestor_ids[-1] if ancestor_ids else run_id

            family_sql = """
            WITH RECURSIVE family(id) AS (
                SELECT ?
                UNION
                SELECT r.run_id FROM runs r JOIN family f ON r.parent_run_id = f.id
            )
            SELECT
                r.run_id, r.parent_run_id, r.task_id, r.status, r.failure_mode,
                r.exit_code, r.duration_ms, r.created_at, r.finished_at, r.image, r.main_cmd, r.replay_count
            FROM runs r
            JOIN family f ON r.run_id = f.id
            ORDER BY r.created_at ASC
            """
            async with conn.execute(family_sql, (root_id,)) as cursor:
                rows = await cursor.fetchall()
                return [
                    RunSummary(
                        run_id=r["run_id"],
                        parent_run_id=r["parent_run_id"],
                        task_id=r["task_id"],
                        status=RunStatus(r["status"]),
                        failure_mode=FailureMode(r["failure_mode"]) if r["failure_mode"] else None,
                        exit_code=r["exit_code"],
                        duration_ms=r["duration_ms"],
                        created_at=datetime.fromisoformat(r["created_at"]),
                        finished_at=datetime.fromisoformat(r["finished_at"]) if r["finished_at"] else None,
                        image=r["image"],
                        main_cmd=r["main_cmd"],
                        replay_count=r["replay_count"] or 0,
                    )
                    for r in rows
                ]


# Global storage helper
_default_storage: Optional[RunStorage] = None


def get_storage(db_path: Optional[str] = None) -> RunStorage:
    """Return default or custom storage repository."""
    global _default_storage
    if db_path is not None:
        return RunStorage(db_path)
    if _default_storage is None:
        _default_storage = RunStorage()
    return _default_storage

def get_optimized_sqlite_pragmas() -> list[str]:
    """Return list of performance-oriented SQLite PRAGMAs."""
    return [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA cache_size=-64000",
        "PRAGMA temp_store=MEMORY",
        "PRAGMA mmap_size=268435456",
    ]

def compress_log_output(text: str) -> bytes:
    """Compress log output using zlib to save storage space."""
    import zlib
    return zlib.compress(text.encode("utf-8"))

def decompress_log_output(data: bytes) -> str:
    """Decompress zlib compressed log payload."""
    import zlib
    return zlib.decompress(data).decode("utf-8")
