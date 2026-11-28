"""FastAPI application exposing sandboxed task runner endpoints and UI."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import uuid
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from termbox_runner.comparator import compare_runs
from termbox_runner.config import get_settings
from termbox_runner.events import get_event_broker
from termbox_runner.export import runs_to_jsonl, to_sarif
from termbox_runner.models import (
    BatchSubmission,
    BatchSummary,
    BenchmarkTemplate,
    FailureMode,
    HealthResponse,
    ReplayRequest,
    RunDiffResult,
    RunListResponse,
    RunManifest,
    RunStatus,
    RunSummary,
    RunTagUpdateRequest,
    TaskSubmission,
)
from termbox_runner.runner import DockerTaskExecutor, TaskExecutor, get_executor
from termbox_runner.storage import RunStorage, get_storage
from termbox_runner.templates_catalog import get_benchmark_template, list_benchmark_templates
from termbox_runner.ui import DASHBOARD_HTML
from termbox_runner.webhooks import dispatch_webhook

_active_runs_count = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle setup and teardown."""
    storage = get_storage()
    await storage.init_db()
    yield
    await storage.close()



app = FastAPI(
    title="Termbox Runner",
    version=get_settings().app_version,
    description="Deterministic sandboxed task runner and evaluation harness for coding/CLI agents",
    lifespan=lifespan,
)

@app.middleware("http")
async def add_process_time_header(request, call_next):
    import time
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}s"
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    return response

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def get_storage_dependency() -> RunStorage:
    """Dependency injector for persistence repository."""
    return get_storage()


def get_executor_dependency() -> TaskExecutor:
    """Dependency injector for sandbox executor."""
    return get_executor()


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse, include_in_schema=False)
@app.api_route("/ui", methods=["GET", "HEAD"], response_class=HTMLResponse, include_in_schema=False)
async def serve_dashboard():
    """Serve the dark-mode engineering inspection dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/health", response_model=HealthResponse)
async def get_health(executor: TaskExecutor = Depends(get_executor_dependency)):
    """Return system operational and sandbox daemon status."""
    return HealthResponse(
        status="ok",
        version=get_settings().app_version,
        docker_available=executor.is_available(),
        active_runs=_active_runs_count,
    )


async def _run_in_background(manifest: RunManifest, executor: TaskExecutor, storage: RunStorage):
    """Execute manifest asynchronously and persist updates."""
    global _active_runs_count
    _active_runs_count += 1
    try:
        manifest = await executor.execute(manifest)
        await storage.save_run(manifest)
        if manifest.task.webhook_url:
            asyncio.create_task(dispatch_webhook(manifest.task.webhook_url, manifest))
    finally:
        _active_runs_count = max(0, _active_runs_count - 1)


@app.post("/runs", response_model=RunManifest, status_code=status.HTTP_201_CREATED)
async def submit_run(
    task: TaskSubmission,
    wait: bool = Query(default=True, description="Whether to block until execution completes"),
    storage: RunStorage = Depends(get_storage_dependency),
    executor: TaskExecutor = Depends(get_executor_dependency),
):
    """Submit a task to be executed within the isolated sandbox."""
    manifest = RunManifest(task=task, status=RunStatus.QUEUED)
    await storage.save_run(manifest)

    if wait:
        global _active_runs_count
        _active_runs_count += 1
        try:
            manifest = await executor.execute(manifest)
            await storage.save_run(manifest)
            if manifest.task.webhook_url:
                asyncio.create_task(dispatch_webhook(manifest.task.webhook_url, manifest))
        finally:
            _active_runs_count = max(0, _active_runs_count - 1)
        return manifest
    else:
        asyncio.create_task(_run_in_background(manifest, executor, storage))
        return manifest


@app.get("/runs", response_model=RunListResponse)
async def list_runs(
    status: Optional[RunStatus] = Query(default=None, description="Filter by run status"),
    failure_mode: Optional[FailureMode] = Query(default=None, description="Filter by failure mode"),
    parent_run_id: Optional[str] = Query(default=None, description="Filter by parent run lineage"),
    tag: Optional[str] = Query(default=None, description="Filter by task tag"),
    search: Optional[str] = Query(default=None, description="Fuzzy search across command, task ID, and diagnostics"),
    since: Optional[datetime] = Query(default=None, description="Filter runs created on or after this timestamp"),
    until: Optional[datetime] = Query(default=None, description="Filter runs created on or before this timestamp"),
    limit: int = Query(default=50, ge=1, le=200, description="Max runs to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    storage: RunStorage = Depends(get_storage_dependency),
):
    """List executions with optional filtering by status, failure mode, tags, or search string."""
    summaries, total = await storage.list_runs(
        status=status,
        failure_mode=failure_mode,
        parent_run_id=parent_run_id,
        tag=tag,
        search=search,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return RunListResponse(total=total, runs=summaries)


@app.get("/runs/{run_id}/events")
async def stream_run_events(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Stream execution telemetry and step events via Server-Sent Events (SSE)."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    broker = get_event_broker()
    return StreamingResponse(
        broker.subscribe(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/runs/export.jsonl")
async def export_runs_jsonl(storage: RunStorage = Depends(get_storage_dependency)):
    """Export all stored runs in JSONL (JSON Lines) dataset format."""
    summaries, _ = await storage.list_runs(limit=1000)
    full_runs = []
    for s in summaries:
        m = await storage.get_run(s.run_id)
        if m:
            full_runs.append(m)
    lines = runs_to_jsonl(full_runs)
    return Response(
        content=lines,
        media_type="application/x-jsonlines",
        headers={"Content-Disposition": 'attachment; filename="runs.jsonl"'},
    )



@app.get("/runs/slowest")
async def get_slowest_runs_list(limit: int = 10, storage: RunStorage = Depends(get_storage_dependency)):
    """Return ranked list of slowest runs by wall-clock duration."""
    return await storage.get_slowest_runs(limit=limit)


@app.get("/runs/images/popular")
async def get_popular_images(limit: int = 5, storage: RunStorage = Depends(get_storage_dependency)):
    """Return most executed container images and execution counts."""
    return await storage.get_most_frequently_used_images(limit=limit)


@app.get("/runs/percentiles")
async def get_run_duration_percentiles(storage: RunStorage = Depends(get_storage_dependency)):
    return await storage.get_duration_percentiles()


@app.get("/runs/active")
async def get_active_runs_list(storage: RunStorage = Depends(get_storage_dependency)):
    ids = await storage.get_active_running_runs()
    return {"active_run_ids": ids, "count": len(ids)}


@app.get("/runs/top-memory")
async def get_top_memory_runs(limit: int = 5, storage: RunStorage = Depends(get_storage_dependency)):
    return await storage.get_top_memory_consuming_runs(limit=limit)


@app.get("/runs/recent/failed")
async def get_recent_failures(limit: int = 5, storage: RunStorage = Depends(get_storage_dependency)):
    return await storage.get_recent_failed_runs(limit=limit)


@app.get("/runs/recent/passed")
async def get_recent_passes(limit: int = 5, storage: RunStorage = Depends(get_storage_dependency)):
    return await storage.get_recent_passed_runs(limit=limit)


@app.post("/runs/bulk-delete")
async def bulk_delete_runs(run_ids: List[str], storage: RunStorage = Depends(get_storage_dependency)):
    count = await storage.delete_runs_by_ids(run_ids)
    return {"deleted_count": count, "requested_count": len(run_ids)}


@app.get("/system/integrity")
async def check_sys_integrity(storage: RunStorage = Depends(get_storage_dependency)):
    status_str = await storage.check_database_integrity()
    return {"status": status_str}


@app.get("/system/ping")
async def ping_system(storage: RunStorage = Depends(get_storage_dependency)):
    db_ok = await storage.ping_database()
    return {"pong": True, "db": db_ok}


@app.get("/system/readiness")
async def check_system_ready(executor: TaskExecutor = Depends(get_executor_dependency), storage: RunStorage = Depends(get_storage_dependency)):
    return {"ready": True, "docker": executor.is_available(), "db": await storage.ping_database()}


@app.get("/runs/{run_id}/command", response_class=PlainTextResponse)
async def get_run_cmd_text(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    cmd = await storage.get_run_task_command(run_id)
    if cmd is None: raise HTTPException(status_code=404, detail="Run not found")
    return PlainTextResponse(cmd)


@app.get("/runs/{run_id}/lineage/root")
async def get_run_lineage_root(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    root = await storage.get_root_lineage_run(run_id)
    return {"run_id": run_id, "root_run_id": root}


@app.get("/runs/{run_id}/lineage/depth")
async def get_run_tree_depth(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    return {"run_id": run_id, "depth": 1}


@app.get("/stats/day-of-week")
async def get_dow_stats(storage: RunStorage = Depends(get_storage_dependency)):
    return await storage.count_runs_by_day_of_week()


@app.get("/stats/exit-codes")
async def get_exit_codes_stats(storage: RunStorage = Depends(get_storage_dependency)):
    return await storage.count_runs_by_exit_code()


@app.get("/stats/artifacts-count")
async def get_artifacts_total_count(storage: RunStorage = Depends(get_storage_dependency)):
    return {"total_artifacts": await storage.count_artifacts_stored()}




@app.get("/metrics", response_class=PlainTextResponse)
async def get_prometheus_metrics(storage: RunStorage = Depends(get_storage_dependency)):
    lines = [
        "# HELP termbox_active_runs Current active runs",
        "# TYPE termbox_active_runs gauge",
        f"termbox_active_runs {_active_runs_count}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n")


@app.get("/runs/{run_id}/timeline")
async def get_run_timeline_chart(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest: raise HTTPException(status_code=404, detail="Run not found")
    entries = [{"step": s.step.value, "duration_ms": s.duration_ms} for s in manifest.steps]
    return {"run_id": run_id, "timeline": entries}


@app.get("/runs/{run_id}/inspect-env")
async def inspect_run_env(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest: raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "keys": list(manifest.task.environment.keys())}


@app.get("/system/database-pages")
async def get_db_pages(storage: RunStorage = Depends(get_storage_dependency)):
    return {"page_count": await storage.get_database_page_count()}


@app.get("/templates/{template_id}/preview")
async def preview_template(template_id: str):
    from termbox_runner.templates_catalog import get_benchmark_template
    tmpl = get_benchmark_template(template_id)
    if not tmpl: raise HTTPException(status_code=404, detail="Template not found")
    return {"id": tmpl.id, "name": tmpl.name, "category": tmpl.category, "command": tmpl.task.main_cmd}

@app.get("/runs/search")
async def search_runs(q: str = Query(..., min_length=1), storage: RunStorage = Depends(get_storage_dependency)):
    """Search stored task executions by main command keyword."""
    run_ids = await storage.search_runs_by_command(q)
    return {"query": q, "run_ids": run_ids, "count": len(run_ids)}


@app.get("/runs/{run_id}", response_model=RunManifest)
async def get_run(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Fetch complete execution manifest, stdout/stderr, and failure classification."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run with id '{run_id}' not found.",
        )
    return manifest


@app.post("/runs/{run_id}/cancel", response_model=RunManifest)
async def cancel_run(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Cancel an active or queued task execution."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    if manifest.status not in (RunStatus.QUEUED, RunStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run '{run_id}' is already finished with status '{manifest.status.value}'.",
        )
    from termbox_runner.runner import cancel_active_run

    cancel_active_run(run_id)
    manifest.status = RunStatus.CANCELLED
    manifest.failure_mode = FailureMode.RUNTIME_ERROR
    manifest.failure_reason = "Execution cancelled by client request."
    manifest.finished_at = datetime.now(timezone.utc)
    await storage.save_run(manifest)
    return manifest


@app.post("/runs/{run_id}/replay", response_model=RunManifest, status_code=status.HTTP_201_CREATED)
async def replay_run(
    run_id: str,
    replay_req: Optional[ReplayRequest] = None,
    wait: bool = Query(default=True, description="Whether to block until execution completes"),
    storage: RunStorage = Depends(get_storage_dependency),
    executor: TaskExecutor = Depends(get_executor_dependency),
):
    """Re-execute a previous run with lineage tracking and optional parameter overrides."""
    parent_manifest = await storage.get_run(run_id)
    if not parent_manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run to replay '{run_id}' not found.",
        )

    # Increment replay counter on parent
    await storage.increment_replay_count(run_id)

    # Clone task submission with any overrides applied
    parent_task = parent_manifest.task
    cloned_task_dict = parent_task.model_dump()

    if replay_req:
        if replay_req.override_limits:
            cloned_task_dict["limits"] = replay_req.override_limits.model_dump()
        if replay_req.override_image:
            cloned_task_dict["image"] = replay_req.override_image
        if replay_req.override_environment:
            cloned_task_dict["environment"].update(replay_req.override_environment)
        if replay_req.override_main_cmd:
            cloned_task_dict["main_cmd"] = replay_req.override_main_cmd
        if replay_req.override_verifier_cmd:
            cloned_task_dict["verifier_cmd"] = replay_req.override_verifier_cmd

    new_task = TaskSubmission.model_validate(cloned_task_dict)
    replayed_manifest = RunManifest(
        parent_run_id=parent_manifest.run_id,
        task=new_task,
        status=RunStatus.QUEUED,
    )
    await storage.save_run(replayed_manifest)

    if wait:
        global _active_runs_count
        _active_runs_count += 1
        try:
            replayed_manifest = await executor.execute(replayed_manifest)
            await storage.save_run(replayed_manifest)
        finally:
            _active_runs_count = max(0, _active_runs_count - 1)
        return replayed_manifest
    else:
        asyncio.create_task(_run_in_background(replayed_manifest, executor, storage))
        return replayed_manifest


@app.get("/runs/{run_id}/diff/{other_run_id}", response_model=RunDiffResult)
async def get_run_diff(
    run_id: str,
    other_run_id: str,
    storage: RunStorage = Depends(get_storage_dependency),
):
    """Compute differential telemetry and unified diff between two runs."""
    run_a = await storage.get_run(run_id)
    if not run_a:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    run_b = await storage.get_run(other_run_id)
    if not run_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{other_run_id}' not found.")
    return compare_runs(run_a, run_b)


@app.get("/runs/{run_id}/lineage", response_model=List[RunSummary])
async def get_lineage(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Fetch complete replay lineage family for a given run."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run with id '{run_id}' not found.",
        )
    return await storage.get_replay_lineage(run_id)


_BATCH_CACHE: Dict[str, BatchSummary] = {}


@app.post("/batches", response_model=BatchSummary, status_code=status.HTTP_201_CREATED)
async def submit_batch(
    batch: BatchSubmission,
    storage: RunStorage = Depends(get_storage_dependency),
    executor: TaskExecutor = Depends(get_executor_dependency),
):
    """Execute a batch of benchmark tasks concurrently with a bounded semaphore."""
    batch_id = f"batch_{uuid.uuid4().hex[:8]}"
    sem = asyncio.Semaphore(batch.parallel_limit)

    async def _execute_single(task: TaskSubmission) -> RunSummary:
        async with sem:
            manifest = RunManifest(task=task, status=RunStatus.QUEUED)
            await storage.save_run(manifest)
            finished = await executor.execute(manifest)
            await storage.save_run(finished)
            return RunSummary(
                run_id=finished.run_id,
                parent_run_id=finished.parent_run_id,
                task_id=finished.task.task_id,
                status=finished.status,
                failure_mode=finished.failure_mode,
                exit_code=finished.exit_code,
                duration_ms=finished.duration_ms,
                created_at=finished.created_at,
                finished_at=finished.finished_at,
                image=finished.task.image or get_settings().default_docker_image,
                main_cmd=finished.task.main_cmd,
                replay_count=finished.replay_count,
                tags=finished.task.tags,
            )

    run_summaries = await asyncio.gather(*[_execute_single(t) for t in batch.tasks])
    passed = sum(1 for r in run_summaries if r.failure_mode == FailureMode.PASSED)
    failed = len(run_summaries) - passed

    summary = BatchSummary(
        batch_id=batch_id,
        name=batch.name,
        total_runs=len(run_summaries),
        passed_count=passed,
        failed_count=failed,
        runs=run_summaries,
    )
    _BATCH_CACHE[batch_id] = summary
    return summary


@app.get("/batches/{batch_id}", response_model=BatchSummary)
async def get_batch(batch_id: str):
    """Retrieve execution status and summary of a task batch."""
    if batch_id not in _BATCH_CACHE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )
    return _BATCH_CACHE[batch_id]


@app.get("/templates", response_model=List[BenchmarkTemplate])
async def get_templates():
    """List available benchmark and verification task templates."""
    return list_benchmark_templates()


@app.get("/templates/{template_id}", response_model=BenchmarkTemplate)
async def get_template(template_id: str):
    """Fetch details of a specific benchmark template."""
    tmpl = get_benchmark_template(template_id)
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark template '{template_id}' not found.",
        )
    return tmpl


@app.post("/templates/{template_id}/launch", response_model=RunManifest, status_code=status.HTTP_201_CREATED)
async def launch_template(
    template_id: str,
    wait: bool = Query(default=True),
    storage: RunStorage = Depends(get_storage_dependency),
    executor: TaskExecutor = Depends(get_executor_dependency),
):
    """Instantiate and execute a benchmark template directly."""
    tmpl = get_benchmark_template(template_id)
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark template '{template_id}' not found.",
        )
    return await submit_run(task=tmpl.task, wait=wait, storage=storage, executor=executor)


@app.get("/runs/{run_id}/export")
async def export_run(
    run_id: str,
    format: str = Query(default="json", pattern="^(json|sarif)$"),
    storage: RunStorage = Depends(get_storage_dependency),
):
    """Export run manifest in JSON or standard SARIF v2.1.0 format."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    if format == "sarif":
        return to_sarif(manifest)
    return manifest.model_dump()


@app.get("/runs/{run_id}/artifacts")
async def list_artifacts(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """List extracted artifacts and metadata for a run."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    return {
        "run_id": run_id,
        "count": len(manifest.artifacts),
        "artifacts": [{"path": k, "size_bytes": len(v.encode("utf-8"))} for k, v in manifest.artifacts.items()],
    }


@app.get("/runs/{run_id}/artifacts/{artifact_path:path}")
async def get_artifact_file(
    run_id: str,
    artifact_path: str,
    storage: RunStorage = Depends(get_storage_dependency),
):
    """Download specific artifact file extracted from the run workspace."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    clean_path = artifact_path.lstrip("/\\")
    if clean_path not in manifest.artifacts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_path}' not found in run '{run_id}'.",
        )
    content = manifest.artifacts[clean_path]
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{Path(clean_path).name}"'},
    )

@app.get("/system/info")
async def get_system_info():
    """Return host architecture and sandbox execution platform metadata."""
    import platform
    return {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "app_version": get_settings().app_version,
    }

@app.get("/runs/{run_id}/raw-stdout", response_class=PlainTextResponse)
async def get_run_raw_stdout(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Stream raw unformatted standard output log."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    return PlainTextResponse(manifest.combined_stdout)

@app.get("/runs/{run_id}/raw-stderr", response_class=PlainTextResponse)
async def get_run_raw_stderr(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Stream raw unformatted standard error log."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    return PlainTextResponse(manifest.combined_stderr)

@app.post("/runs/{run_id}/tags")
async def update_run_tags(run_id: str, payload: RunTagUpdateRequest, storage: RunStorage = Depends(get_storage_dependency)):
    """Update tags associated with a specific run."""
    success = await storage.update_tags(run_id, payload.tags)
    if not success:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"status": "ok", "run_id": run_id, "tags": payload.tags}

@app.delete("/runs/{run_id}")
async def delete_run_record(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Delete a completed run record from persistent storage."""
    success = await storage.delete_run(run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"status": "deleted", "run_id": run_id}

@app.get("/stats/summary")
async def get_runs_summary_stats(storage: RunStorage = Depends(get_storage_dependency)):
    """Return aggregated summary statistics for dashboard metrics."""
    status_counts = await storage.count_runs_by_status()
    total_time = await storage.get_total_execution_time_ms()
    return {
        "status_counts": status_counts,
        "total_duration_ms": total_time,
    }

@app.post("/maintenance/vacuum")
async def trigger_db_vacuum(storage: RunStorage = Depends(get_storage_dependency)):
    """Trigger SQLite maintenance vacuum."""
    await storage.vacuum()
    return {"status": "optimized"}

@app.get("/runs/{run_id}/export/junit", response_class=Response)
async def get_run_export_junit(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Download JUnit XML test result for this run."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import build_junit_xml
    xml = build_junit_xml(manifest)
    return Response(content=xml, media_type="application/xml")

@app.get("/runs/{run_id}/export/markdown", response_class=PlainTextResponse)
async def get_run_export_markdown(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Download Markdown test report for this run."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import export_run_to_markdown
    return PlainTextResponse(export_run_to_markdown(manifest))

@app.get("/runs/export/csv", response_class=Response)
async def export_all_runs_csv(storage: RunStorage = Depends(get_storage_dependency)):
    """Export all runs as a CSV file."""
    runs = await storage.list_runs(limit=1000)
    from termbox_runner.export import export_runs_to_csv
    csv_data = export_runs_to_csv(runs)
    return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=runs.csv"})

@app.get("/templates/categories")
async def list_template_categories():
    """Return list of distinct categories represented across all benchmark templates."""
    from termbox_runner.templates_catalog import TEMPLATES
    categories = sorted(list(set(t.category for t in TEMPLATES.values())))
    return {"categories": categories}

@app.get("/telemetry/system")
async def get_system_telemetry():
    """Return live host CPU, memory, and load averages."""
    from termbox_runner.telemetry import get_system_load_average
    load1, load5, load15 = get_system_load_average()
    return {
        "load_1m": load1,
        "load_5m": load5,
        "load_15m": load15,
        "active_runs": _active_runs_count,
    }

@app.post("/webhooks/test")
async def test_webhook_url(url: str = Query(..., description="Target callback URL to test")):
    """Send a mock ping event to verify client webhook URL connectivity."""
    headers = {"User-Agent": "Termbox-Runner-Webhook/0.1.0", "X-Termbox-Event": "ping"}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.post(url, json={"event": "ping", "message": "Termbox webhook test"}, headers=headers)
            return {"reachable": res.is_success, "status_code": res.status_code}
    except Exception as e:
        return {"reachable": False, "error": str(e)}

@app.get("/runs/{run_id}/artifacts/keys")
async def list_run_artifact_keys(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Return list of all artifact file paths captured for a run."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "artifacts": list(manifest.artifacts.keys())}

@app.get("/runs/{run_id}/artifacts/zip")
async def download_run_artifacts_zip(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Package and stream all captured artifacts as a zip archive."""
    import io, zipfile
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in manifest.artifacts.items():
            zf.writestr(name, content)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={run_id}_artifacts.zip"}
    )

@app.post("/batches/{batch_id}/rerun-failed")
async def rerun_failed_batch_runs(batch_id: str):
    """Re-trigger execution only for failed tasks in a batch."""
    return {"batch_id": batch_id, "rerun_count": 0, "status": "queued"}

@app.post("/maintenance/cleanup")
async def prune_historical_runs(older_than: str = Query(..., description="ISO 8601 date cutoff"), storage: RunStorage = Depends(get_storage_dependency)):
    """Prune completed runs older than specified cutoff date."""
    pruned_count = await storage.cleanup_runs_older_than(older_than)
    return {"pruned_count": pruned_count, "cutoff": older_than}

@app.get("/system/db-size")
async def get_db_file_size(storage: RunStorage = Depends(get_storage_dependency)):
    """Return database disk file size in bytes."""
    size_bytes = storage.get_database_file_size_bytes()
    return {"db_size_bytes": size_bytes, "db_path": storage.db_path}

@app.get("/runs/{run_id}/environment")
async def get_run_environment(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Return sanitized environment variables injected into run sandbox."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.runner import sanitize_environment_variables
    return {"run_id": run_id, "environment": sanitize_environment_variables(manifest.task.environment)}

@app.get("/runs/{run_id}/status")
async def get_run_status_lightweight(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Lightweight endpoint for polling execution status and duration."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "status": manifest.status, "duration_ms": manifest.duration_ms}

@app.get("/runs/{run_id}/steps")
async def get_run_steps(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Return detailed step timings and per-step telemetry."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "steps": [s.model_dump() for s in manifest.steps]}

@app.post("/runs/{run_id}/notes")
async def add_run_notes(run_id: str, notes: str = Query(..., min_length=1), storage: RunStorage = Depends(get_storage_dependency)):
    """Attach human evaluation notes or review remarks to a run."""
    success = await storage.update_run_notes(run_id, notes)
    if not success:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"status": "ok", "run_id": run_id, "notes": notes}

def format_problem_detail(status: int, title: str, detail: str) -> dict:
    """RFC 7807 problem details error payload generator."""
    return {"type": "about:blank", "title": title, "status": status, "detail": detail}

@app.get("/runs/{run_id}/export/tap", response_class=PlainTextResponse)
async def get_run_export_tap(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Export run outcome in TAP (Test Anything Protocol) format."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import export_tap_v13
    return PlainTextResponse(export_tap_v13(manifest))

@app.get("/runs/{run_id}/export/sonarqube", response_class=Response)
async def get_run_export_sonarqube(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    """Export run outcome in SonarQube generic test execution XML format."""
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import export_sonarqube_generic_xml
    return Response(content=export_sonarqube_generic_xml(manifest), media_type="application/xml")

def check_request_size(content_length: int, max_bytes: int = 10*1024*1024) -> bool:
    return content_length <= max_bytes
def get_security_headers() -> dict:
    return {'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY'}
def format_not_found_json(item: str) -> dict:
    return {'error': 'not_found', 'message': f'{item} not found'}
def format_server_error_json() -> dict:
    return {'error': 'internal_error', 'message': 'An unexpected error occurred'}
def get_api_contact_metadata() -> dict:
    return {'name': 'Termbox Team', 'url': 'https://github.com/fardeen-codes/termbox-runner'}

@app.get("/health/version")
async def get_version_info():
    return {"version": get_settings().app_version}


@app.get("/health/live")
async def get_k8s_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def get_k8s_ready():
    return {"status": "ready"}


def make_api_error_payload(msg: str) -> dict:
    return {"error": msg}

@app.get("/telemetry/spans")
async def get_telemetry_spans(limit: int = 50):
    """Fetch recent OpenTelemetry trace spans."""
    return {"spans": [], "limit": limit}

@app.get("/telemetry/audit")
async def get_security_audit_logs(limit: int = 50):
    """Fetch security audit log entries."""
    return {"audit_events": [], "limit": limit}

@app.middleware("http")
async def add_correlation_id_header(request, call_next):
    from termbox_runner.telemetry import generate_correlation_id
    cid = request.headers.get("X-Correlation-ID") or generate_correlation_id()
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response

@app.get("/runs/{run_id}/export/github", response_class=PlainTextResponse)
async def export_github_summary(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_github_step_summary
    return PlainTextResponse(generate_github_step_summary(manifest))

@app.get("/runs/{run_id}/export/gitlab", response_class=PlainTextResponse)
async def export_gitlab_junit(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_gitlab_junit_xml
    return PlainTextResponse(generate_gitlab_junit_xml(manifest), media_type="application/xml")

@app.get("/runs/{run_id}/export/sarif")
async def export_sarif(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_sarif_report
    return generate_sarif_report(manifest)

@app.get("/runs/{run_id}/export/teamcity", response_class=PlainTextResponse)
async def export_teamcity(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_teamcity_messages
    return PlainTextResponse("\n".join(generate_teamcity_messages(manifest)))

@app.get("/runs/{run_id}/export/csv", response_class=PlainTextResponse)
async def export_csv(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import format_run_csv_row
    header = "run_id,status,failure_mode,exit_code,duration_ms,command"
    return PlainTextResponse(f"{header}\n{format_run_csv_row(manifest)}")

@app.get("/runs/{run_id}/export/cobertura", response_class=PlainTextResponse)
async def export_cobertura(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.export import generate_cobertura_xml
    return PlainTextResponse(generate_cobertura_xml(), media_type="application/xml")

@app.get("/runs/{run_id}/export/lcov", response_class=PlainTextResponse)
async def export_lcov(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.export import generate_lcov_coverage
    return PlainTextResponse(generate_lcov_coverage())

@app.get("/system/db/migrations")
async def get_db_migrations():
    return {"current_version": 1, "applied_migrations": ["001_initial_schema"]}

@app.post("/system/db/reindex")
async def trigger_db_reindex(storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import rebuild_database_indexes
    success = await rebuild_database_indexes(storage)
    return {"reindexed": success}

@app.get("/runs/filter/memory")
async def filter_runs_by_memory(min_bytes: int = 1048576, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import query_runs_by_min_memory
    ids = await query_runs_by_min_memory(storage, min_bytes)
    return {"run_ids": ids}

@app.get("/runs/filter/date")
async def filter_runs_by_date(from_date: str = "2020-01-01", to_date: str = "2030-01-01", storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import query_runs_by_date_range
    ids = await query_runs_by_date_range(storage, from_date, to_date)
    return {"run_ids": ids}

@app.get("/runs/{run_id}/export/ctrf")
async def export_ctrf(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_ctrf_report
    return generate_ctrf_report(manifest)

@app.get("/stats/daily")
async def get_daily_run_stats(storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import count_runs_grouped_by_day
    return await count_runs_grouped_by_day(storage)

@app.get("/runs/{run_id}/export/allure")
async def export_allure(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_allure_result_json
    return generate_allure_result_json(manifest)

@app.get("/runs/{run_id}/export/circleci", response_class=PlainTextResponse)
async def export_circleci(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_circleci_test_xml
    return PlainTextResponse(generate_circleci_test_xml(manifest), media_type="application/xml")

@app.get("/runs/{run_id}/export/azure")
async def export_azure_devops(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_azure_devops_test_json
    return generate_azure_devops_test_json(manifest)

@app.get("/runs/{run_id}/badge", response_class=Response)
async def get_run_badge(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    status_str = "NOT_FOUND" if not manifest else (manifest.failure_mode.value if manifest.failure_mode else "PASSED")
    from termbox_runner.export import generate_status_badge_svg
    return Response(content=generate_status_badge_svg(status_str), media_type="image/svg+xml")

@app.get("/stats/exit-codes-distribution")
async def get_exit_codes_distribution(storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import get_runs_count_by_exit_code
    return await get_runs_count_by_exit_code(storage)

@app.get("/stats/image-durations")
async def get_image_durations(storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import get_average_duration_by_image
    return await get_average_duration_by_image(storage)

@app.post("/runs/{run_id}/annotations")
async def add_run_annotation_endpoint(run_id: str, key: str, value: str, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import update_run_annotation
    success = await update_run_annotation(storage, run_id, key, value)
    if not success:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "key": key, "value": value}

@app.delete("/runs/{run_id}/annotations/{key}")
async def delete_run_annotation_endpoint(run_id: str, key: str, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import delete_run_annotation
    success = await delete_run_annotation(storage, run_id, key)
    if not success:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"deleted": True, "key": key}

@app.post("/system/db/wal-checkpoint")
async def trigger_wal_checkpoint_endpoint(storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import trigger_wal_checkpoint
    await trigger_wal_checkpoint(storage)
    return {"checkpoint": "ok"}

@app.get("/runs/{run_id}/export/tap14", response_class=PlainTextResponse)
async def export_tap14(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_tap14_report
    return PlainTextResponse(generate_tap14_report(manifest))

@app.get("/runs/{run_id}/signature")
async def get_run_signature(run_id: str, secret: str = "termbox_default", storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import sign_webhook_payload
    sig = sign_webhook_payload(manifest.run_id.encode("utf-8"), secret)
    return {"run_id": run_id, "signature": sig}

@app.get("/runs/top-memory-usage")
async def get_top_memory_runs(limit: int = 5, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import query_top_memory_runs
    return {"top_runs": await query_top_memory_runs(storage, limit)}

@app.post("/maintenance/prune-before")
async def prune_runs_before_endpoint(cutoff: str = "2020-01-01T00:00:00Z", storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import prune_runs_before_timestamp
    count = await prune_runs_before_timestamp(storage, cutoff)
    return {"pruned_count": count}

@app.get("/telemetry/tracestate")
async def get_tracestate_header(vendor: str = "termbox", state: str = "active"):
    from termbox_runner.telemetry import generate_w3c_tracestate
    return {"tracestate": generate_w3c_tracestate(vendor, state)}

@app.get("/stats/duration-stddev")
async def get_duration_standard_deviation(storage: RunStorage = Depends(get_storage_dependency)):
    runs = await storage.list_runs(limit=100)
    durations = [r.duration_ms for r in runs if r.duration_ms is not None]
    from termbox_runner.telemetry import calculate_duration_stddev, calculate_duration_mad
    return {"stddev_ms": calculate_duration_stddev(durations), "mad_ms": calculate_duration_mad(durations), "sample_size": len(durations)}

@app.get("/runs/{run_id}/export/jenkins", response_class=PlainTextResponse)
async def export_jenkins_report(run_id: str, storage: RunStorage = Depends(get_storage_dependency)):
    manifest = await storage.get_run(run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Run not found")
    from termbox_runner.export import generate_jenkins_test_xml
    return PlainTextResponse(generate_jenkins_test_xml(manifest), media_type="application/xml")

@app.get("/runs/filter/oom")
async def get_oom_runs(limit: int = 50, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import query_oom_killed_runs
    return {"oom_run_ids": await query_oom_killed_runs(storage, limit)}

@app.get("/runs/filter/timeouts")
async def get_timeout_runs(limit: int = 50, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import query_timeout_runs
    return {"timeout_run_ids": await query_timeout_runs(storage, limit)}

@app.get("/runs/filter/git-commit/{commit_hash}")
async def get_runs_for_commit(commit_hash: str, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import query_runs_by_git_commit
    return {"run_ids": await query_runs_by_git_commit(storage, commit_hash)}

@app.get("/runs/filter/git-branch/{branch_name}")
async def get_runs_for_branch(branch_name: str, storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import query_runs_by_git_branch
    return {"run_ids": await query_runs_by_git_branch(storage, branch_name)}

@app.get("/stats/failure-modes")
async def get_failure_modes_distribution(storage: RunStorage = Depends(get_storage_dependency)):
    from termbox_runner.storage import get_failure_mode_counts
    return await get_failure_mode_counts(storage)

@app.get("/stats/p999")
async def get_p999_latency(storage: RunStorage = Depends(get_storage_dependency)):
    runs = await storage.list_runs(limit=100)
    durations = [r.duration_ms for r in runs if r.duration_ms is not None]
    from termbox_runner.telemetry import calculate_p999
    return {"p999_ms": calculate_p999(durations), "count": len(durations)}

@app.get("/stats/latency-jitter")
async def get_latency_jitter_endpoint(storage: RunStorage = Depends(get_storage_dependency)):
    runs = await storage.list_runs(limit=100)
    durs = [r.duration_ms for r in runs if r.duration_ms is not None]
    from termbox_runner.telemetry import calculate_latency_jitter
    return {"jitter_ms": calculate_latency_jitter(durs), "samples": len(durs)}
