"""Configuration settings for termbox-runner."""

from functools import lru_cache
from typing import Optional
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

    # Docker defaults & resource limits
    default_docker_image: str = "python:3.12-slim"
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


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
