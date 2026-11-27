"""Domain schemas and models for termbox-runner."""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple
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

    @property
    def is_infrastructure_failure(self) -> bool:
        """Return True if failure was due to infra constraints rather than code logic."""
        return self in (FailureMode.OOM_KILLED, FailureMode.TIMEOUT, FailureMode.SETUP_ERROR)


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
    seccomp_profile_path: Optional[str] = None
    apparmor_profile: Optional[str] = None
    cap_add: List[str] = Field(default_factory=list)
    no_new_privs: bool = True
    seccomp_profile: Optional[str] = Field(default=None, description="Custom seccomp profile JSON string or path")


class ResourceLimits(BaseModel):
    """Resource constraints imposed on container execution."""

    mem_limit: str = Field(default="512m", description="Container memory limit, e.g. 256m, 1g")
    cpu_quota: float = Field(default=1.0, ge=0.1, le=16.0, description="CPU allocation quota in cores")
    pids_limit: int = Field(default=128, ge=16, le=4096, description="Max concurrent process count")
    network_mode: str = Field(default="none", description="Container network mode ('none', 'bridge', etc.)")
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=600.0, description="Hard wall-clock timeout in seconds")
    max_open_files: int = Field(default=1024, ge=64, le=65536, description="Max open file descriptors (ulimit nofile)")
    shm_size: Optional[str] = Field(default='64m', description='Size of /dev/shm')
    cpuset_cpus: Optional[str] = Field(default=None, description='CPUs in which to allow execution (e.g. 0-3)')
    swappiness: Optional[int] = Field(default=0, ge=0, le=100, description='Memory swappiness')
    sysctls: Dict[str, str] = Field(default_factory=dict, description='Container sysctls')
    security: SecurityOptions = Field(default_factory=SecurityOptions, description="Security sandbox controls")
    ulimit_nofile: Optional[int] = Field(default=1024, description="Max open file descriptors")
    ulimit_nproc: Optional[int] = Field(default=512, description="Max child processes")
    stop_signal: str = Field(default="SIGKILL", description="Signal to stop container")
    pid_mode: Optional[str] = Field(default=None, description="PID namespace mode")
    ipc_mode: Optional[str] = Field(default=None, description="IPC namespace mode")
    memory_high: Optional[str] = Field(default=None, description="Cgroups v2 memory.high throttle threshold")

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
    load_average: Optional[float] = Field(default=None, description="System 1-min load average at execution time")
    peak_cpu_cores: float = 0.0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    disk_read_iops: int = 0
    disk_write_iops: int = 0


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

    @property
    def is_success(self) -> bool:
        """Return True if step finished cleanly with exit code 0."""
        return self.exit_code == 0


class TaskSubmission(BaseModel):
    """User submission requesting sandboxed task execution."""

    task_id: Optional[str] = Field(default=None, description="Client-provided task or benchmark identifier")
    priority: int = Field(default=0, ge=-10, le=10, description="Task execution priority ranking")
    git_commit: Optional[str] = Field(default=None, description="Source commit SHA")
    git_branch: Optional[str] = Field(default=None, description="Source branch name")
    workdir: Optional[str] = Field(default="/workspace", description="Working directory inside the container")
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
    webhook_url: Optional[str] = Field(default=None, description="HTTP callback URL to invoke upon run completion")
    webhook_secret: Optional[str] = Field(default=None, description="Shared secret for HMAC-SHA256 callback signing")
    container_labels: Dict[str, str] = Field(default_factory=dict, description='Custom container labels')
    client_ip: Optional[str] = None
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
    runner_node_id: str = 'node-default'
    scheduling_delay_ms: float = 0.0
    container_exit_signal: Optional[str] = None
    replay_count: int = 0
    annotations: Dict[str, str] = Field(default_factory=dict, description="User notes or review annotations")

    @property
    def exit_signal(self) -> Optional[int]:
        """Return the POSIX exit signal number if process exited via a signal (>128)."""
        if self.exit_code is not None and self.exit_code > 128:
            return self.exit_code - 128
        return None
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
    annotations: Dict[str, str] = Field(default_factory=dict, description="User notes or review annotations")

    @property
    def exit_signal(self) -> Optional[int]:
        """Return the POSIX exit signal number if process exited via a signal (>128)."""
        if self.exit_code is not None and self.exit_code > 128:
            return self.exit_code - 128
        return None
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


class BatchSubmission(BaseModel):
    """Matrix or batch collection of tasks for concurrent execution."""

    name: str = Field(default="batch_evaluation", description="Batch campaign name")
    tasks: List[TaskSubmission] = Field(default_factory=list, description="List of tasks to evaluate")
    parallel_limit: int = Field(default=4, ge=1, le=16, description="Concurrency limit")


class BatchSummary(BaseModel):
    """Aggregated outcome of a batch evaluation run."""

    batch_id: str
    name: str
    total_runs: int
    passed_count: int
    failed_count: int
    runs: List[RunSummary]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunDiffResult(BaseModel):
    """Comparative differential between two sandbox runs."""

    run_a_id: str
    run_b_id: str
    status_changed: bool
    failure_mode_a: Optional[FailureMode] = None
    failure_mode_b: Optional[FailureMode] = None
    exit_code_diff: Tuple[Optional[int], Optional[int]]
    duration_diff_ms: float
    peak_memory_diff_bytes: int
    stdout_unified_diff: str
    stderr_unified_diff: str
    command_diff: Tuple[str, str]


class HealthResponse(BaseModel):
    """System health and operational status."""

    status: str = "ok"
    version: str = "0.1.0"
    docker_available: bool = False
    active_runs: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunTagUpdateRequest(BaseModel):
    """Payload for updating tags on an existing run."""
    tags: List[str] = Field(..., description="Replacement list of tags")


class WebhookEvent(BaseModel):
    """Typed payload sent to client webhook receiver endpoints."""
    event: str
    run_id: str
    status: str
    failure_mode: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: float = 0.0


class ArtifactMetadata(BaseModel):
    """Metadata descriptor for an extracted sandbox artifact."""
    path: str
    size_bytes: int = 0
    mime_type: str = "application/octet-stream"


class RunComparisonSummary(BaseModel):
    """Compact summary of differential analysis between two runs."""
    run_a_id: str
    run_b_id: str
    duration_delta_ms: float = 0.0
    exit_codes: Tuple[Optional[int], Optional[int]]
    status_changed: bool = False


class BatchFilterParams(BaseModel):
    """Query parameters for filtering runs in a batch."""
    status: Optional[RunStatus] = None
    failure_mode: Optional[FailureMode] = None
    min_duration_ms: Optional[float] = None


class NotificationPayload(BaseModel):
    """Generic notification envelope for chat and alerting channels."""
    channel: str = "slack"
    title: str
    body: str
    severity: str = "INFO"


class RunAuditEntry(BaseModel):
    """Audit record capturing security state at task inception."""
    run_id: str
    image: str
    network_mode: str
    no_new_privileges: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelemetrySpan(BaseModel):
    span_id: str
    trace_id: str
    name: str
    duration_ms: float
    attributes: dict = Field(default_factory=dict)

class CpuUsageBreakdown(BaseModel):
    user_cpu_us: int = 0
    system_cpu_us: int = 0
    total_cpu_us: int = 0

class StepTimelineEntry(BaseModel):
    """Timeline slice representation for step Gantt execution."""
    step_name: str
    start_offset_ms: float
    duration_ms: float
    exit_code: Optional[int]


class ExecutionTimeline(BaseModel):
    """Full execution timeline traces for task analysis."""
    run_id: str
    total_duration_ms: float
    entries: List[StepTimelineEntry] = Field(default_factory=list)


class RunMetricPoint(BaseModel):
    """Timeseries metric point for monitoring."""
    timestamp: datetime
    metric_name: str
    value: float


class BulkRunDeleteRequest(BaseModel):
    """Bulk deletion parameters."""
    run_ids: List[str]


class BulkRunDeleteResponse(BaseModel):
    """Bulk deletion summary output."""
    deleted_count: int
    requested_count: int


class RunFilterOptions(BaseModel):
    """Advanced filtering options for run querying."""
    status: Optional[RunStatus] = None
    failure_mode: Optional[FailureMode] = None
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    image: Optional[str] = None


class SystemDiskStats(BaseModel):
    """Storage volume statistics."""
    total_bytes: int
    used_bytes: int
    free_bytes: int


class DockerDaemonInfo(BaseModel):
    """Host Docker engine operational details."""
    server_version: str = "unknown"
    containers_running: int = 0
    driver: str = "overlay2"


class RunPercentileStats(BaseModel):
    """Latency percentiles across recorded runs."""
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p99_ms: float = 0.0


class RunVerificationResult(BaseModel):
    """Harness verification assertion record."""
    verifier_name: str
    passed: bool
    details: str = ""


class TaskFingerprint(BaseModel):
    """SHA-256 fingerprint for deduplicating identical task definitions."""
    hash_value: str
    image: str
    command: str
