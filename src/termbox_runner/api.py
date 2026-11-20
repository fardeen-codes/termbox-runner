"""FastAPI application exposing sandboxed task runner endpoints and UI."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import uuid
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
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
