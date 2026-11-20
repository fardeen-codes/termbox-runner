"""FastAPI application exposing sandboxed task runner endpoints and UI."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse

from termbox_runner.config import get_settings
from termbox_runner.models import (
    BenchmarkTemplate,
    FailureMode,
    HealthResponse,
    ReplayRequest,
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
    limit: int = Query(default=50, ge=1, le=200, description="Max runs to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    storage: RunStorage = Depends(get_storage_dependency),
):
    """List executions with optional filtering by status or failure mode."""
    summaries, total = await storage.list_runs(
        status=status,
        failure_mode=failure_mode,
        parent_run_id=parent_run_id,
        limit=limit,
        offset=offset,
    )
    return RunListResponse(total=total, runs=summaries)


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
