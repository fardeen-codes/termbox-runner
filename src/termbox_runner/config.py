"""Configuration settings for termbox-runner."""

from functools import lru_cache
from typing import Optional, List, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_prefix="TERMBOX_",
        env_file=".env",
        extra="ignore",
    )

    # Application settings
    app_name: str = "termbox-runner"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    default_log_level: str = 'INFO'
    max_log_buffer_bytes: int = 10 * 1024 * 1024  # 10MB output cap
    host: str = "0.0.0.0"
    port: int = 8000

    # Persistence
    db_path: str = "termbox_runner.db"
    db_busy_timeout_ms: int = 5000

    # Docker defaults & resource limits
    default_docker_image: str = "python:3.12-slim"
    container_hostname: str = "sandbox"
    extra_docker_args: List[str] = Field(default_factory=list)
    default_dns_servers: List[str] = Field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])
    default_timeout_seconds: float = 30.0
    max_timeout_seconds: float = 300.0

    default_mem_limit: str = "512m"
    max_mem_limit: str = "2g"

    default_cpu_quota: float = 1.0  # Equivalent to 1.0 core
    max_cpu_quota: float = 4.0

    default_pids_limit: int = 128
    max_pids_limit: int = 1024

    default_network_mode: str = "none"
    allow_network_override: bool = True

    docker_base_url: Optional[str] = None
    execution_mode: str = "docker"  # "docker" or "mock"
    workspace_root: str = "/tmp/termbox_workspaces"
    tmpfs_size_mb: int = 64
    stop_grace_period_seconds: int = 2
    webhook_timeout_seconds: float = 5.0
    webhook_max_retries: int = 3
    workspace_retention_minutes: int = 60
    max_request_body_size_bytes: int = 10 * 1024 * 1024
    allowed_cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    enable_prometheus_metrics: bool = True
    default_swappiness: int = 0
    default_cpuset_cpus: Optional[str] = None
    container_shm_size: str = '64m'
    max_concurrent_runs: int = 16
    enable_audit_logging: bool = True
    def sanitized_dict(self) -> Dict[str, Any]:
        """Export sanitized settings dictionary omitting sensitive paths/tokens."""
        data = self.model_dump()
        data.pop("docker_base_url", None)
        return data



@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
