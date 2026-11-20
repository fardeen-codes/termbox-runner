"""Domain schemas and models for termbox-runner."""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class FailureMode(str, Enum):
    """Deterministic failure modes for task runs."""

    PASSED = "PASSED"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    TIMEOUT = "TIMEOUT"
    OOM_KILLED = "OOM_KILLED"
    SETUP_ERROR = "SETUP_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"


class RunStatus(str, Enum):
    """Execution lifecycle status."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CommandStep(str, Enum):
    """Phases of execution inside the sandbox."""

    SETUP = "SETUP"
    MAIN = "MAIN"
    VERIFIER = "VERIFIER"


def parse_memory_to_bytes(mem_str: str) -> int:
    """Parse string representation of memory (e.g., '512m', '1g', '256k') to bytes."""
    mem_str = mem_str.strip().lower()
    match = re.match(r"^(\d+)([kmg]?b?)?$", mem_str)
    if not match:
        raise ValueError(f"Invalid memory format: {mem_str}. Expected e.g. 512m, 1g, 64k")

    value, unit = match.groups()
    num = int(value)
    if not unit or unit == "b":
        return num
    elif unit.startswith("k"):
        return num * 1024
    elif unit.startswith("m"):
        return num * 1024 * 1024
    elif unit.startswith("g"):
        return num * 1024 * 1024 * 1024
    return num


class SecurityOptions(BaseModel):
    """Hardened sandboxing security and privilege isolation options."""

    read_only_rootfs: bool = Field(default=False, description="Mount root filesystem as read-only")
    drop_capabilities: List[str] = Field(
        default_factory=lambda: ["ALL"],
        description="Linux capabilities to drop (e.g. ['ALL', 'NET_RAW', 'SYS_ADMIN'])",
    )
    add_capabilities: List[str] = Field(
        default_factory=list,
        description="Explicit Linux capabilities to retain (e.g. ['CHOWN'])",
    )
    no_new_privileges: bool = Field(default=True, description="Disallow acquiring additional privileges")
    seccomp_profile: Optional[str] = Field(default=None, description="Custom seccomp profile JSON string or path")


class ResourceLimits(BaseModel):
    """Resource constraints imposed on container execution."""

    mem_limit: str = Field(default="512m", description="Container memory limit, e.g. 256m, 1g")
    cpu_quota: float = Field(default=1.0, ge=0.1, le=16.0, description="CPU allocation quota in cores")
    pids_limit: int = Field(default=128, ge=16, le=4096, description="Max concurrent process count")
    network_mode: str = Field(default="none", description="Container network mode ('none', 'bridge', etc.)")
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=600.0, description="Hard wall-clock timeout in seconds")
    security: SecurityOptions = Field(default_factory=SecurityOptions, description="Security sandbox controls")

    @field_validator("mem_limit")
    @classmethod
    def validate_mem_limit(cls, v: str) -> str:
        try:
            bytes_val = parse_memory_to_bytes(v)
            if bytes_val < 16 * 1024 * 1024:
                raise ValueError("mem_limit must be at least 16m")
        except Exception as e:
            raise ValueError(f"Invalid mem_limit: {e}")
        return v


class ResourceUsage(BaseModel):
    """Resource consumption metrics captured during execution."""

    cpu_percent: float = Field(default=0.0, description="Estimated CPU core utilization percentage")
    memory_peak_bytes: int = Field(default=0, description="Peak memory consumption in bytes")
    io_read_bytes: int = Field(default=0, description="Disk/volume bytes read")
    io_write_bytes: int = Field(default=0, description="Disk/volume bytes written")


class StepResult(BaseModel):
    """Execution telemetry captured for an individual step."""

    step: CommandStep
    command: str
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    oom_killed: bool = False
    timed_out: bool = False
    resource_usage: Optional[ResourceUsage] = None


class TaskSubmission(BaseModel):
    """User submission requesting sandboxed task execution."""

    task_id: Optional[str] = Field(default=None, description="Client-provided task or benchmark identifier")
    image: Optional[str] = Field(default=None, description="Base Docker image; defaults to system configured image")
    setup_cmd: Optional[str] = Field(default=None, description="Initial command executed during container preparation")
    main_cmd: str = Field(..., description="Main task or agent command to execute")
    verifier_cmd: Optional[str] = Field(default=None, description="Automated test/evaluator command (e.g. pytest)")
    files: Dict[str, str] = Field(default_factory=dict, description="Files to inject into the workspace path -> content")
    extract_artifacts: List[str] = Field(
        default_factory=list,
        description="Glob patterns or relative paths to extract after execution (e.g. ['out/*', 'test-results.xml'])",
    )
    environment: Dict[str, str] = Field(default_factory=dict, description="Custom environment variables")
    tags: List[str] = Field(default_factory=list, description="Categorization tags, e.g. ['smoke', 'eval', 'pr-123']")
    limits: ResourceLimits = Field(default_factory=ResourceLimits, description="Resource bounds for the run")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary task metadata or tags")


class RunManifest(BaseModel):
    """Complete manifest and execution trace for a single run."""

    run_id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    parent_run_id: Optional[str] = Field(default=None, description="Lineage pointer if spawned via replay")
    task: TaskSubmission
    status: RunStatus = Field(default=RunStatus.QUEUED)
    failure_mode: Optional[FailureMode] = None
    failure_reason: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    steps: List[StepResult] = Field(default_factory=list)
    combined_stdout: str = ""
    combined_stderr: str = ""
    container_id: Optional[str] = None
    replay_count: int = 0
    peak_memory_bytes: int = 0
    average_cpu_percent: float = 0.0
    artifacts: Dict[str, str] = Field(default_factory=dict, description="Artifact relative path -> file content")


class ReplayRequest(BaseModel):
    """Parameters allowing overrides when replaying a previous run."""

    override_limits: Optional[ResourceLimits] = None
    override_image: Optional[str] = None
    override_environment: Optional[Dict[str, str]] = None
    override_main_cmd: Optional[str] = None
    override_verifier_cmd: Optional[str] = None


class RunSummary(BaseModel):
    """Lightweight summary record for run listings."""

    run_id: str
    parent_run_id: Optional[str] = None
    task_id: Optional[str] = None
    status: RunStatus
    failure_mode: Optional[FailureMode] = None
    exit_code: Optional[int] = None
    duration_ms: float = 0.0
    created_at: datetime
    finished_at: Optional[datetime] = None
    image: str
    main_cmd: str
    replay_count: int = 0
    tags: List[str] = Field(default_factory=list)


class RunListResponse(BaseModel):
    """Paginated or filtered list of run summaries."""

    total: int
    runs: List[RunSummary]


class BenchmarkTemplate(BaseModel):
    """Pre-configured benchmark or evaluation template."""

    id: str
    name: str
    category: str
    description: str
    task: TaskSubmission


class HealthResponse(BaseModel):
    """System health and operational status."""

    status: str = "ok"
    version: str = "0.1.0"
    docker_available: bool = False
    active_runs: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
