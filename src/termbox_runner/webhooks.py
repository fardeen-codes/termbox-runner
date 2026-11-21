"""Asynchronous webhook notification dispatcher for run completion events."""

import asyncio
import logging
from typing import Optional
import httpx
from termbox_runner.models import RunManifest

logger = logging.getLogger(__name__)


async def dispatch_webhook(webhook_url: str, manifest: RunManifest, timeout: float = 5.0) -> bool:
    """Send asynchronous HTTP POST callback notification to client webhook URL."""
    payload = {
        "event": "run.completed",
        "run_id": manifest.run_id,
        "parent_run_id": manifest.parent_run_id,
        "task_id": manifest.task.task_id,
        "status": manifest.status.value,
        "failure_mode": manifest.failure_mode.value if manifest.failure_mode else None,
        "exit_code": manifest.exit_code,
        "duration_ms": manifest.duration_ms,
        "finished_at": manifest.finished_at.isoformat() if manifest.finished_at else None,
    }
    headers = {
        "User-Agent": "Termbox-Runner-Webhook/0.1.0",
        "Content-Type": "application/json",
        "X-Termbox-Event": "run.completed",
        "X-Termbox-Run-Id": manifest.run_id,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(webhook_url, json=payload, headers=headers)
            return res.is_success
    except Exception as exc:
        logger.warning(f"Failed to dispatch webhook to {webhook_url}: {exc}")
        return False

def generate_hmac_signature(payload: bytes, secret: str) -> str:
    """Compute SHA-256 HMAC digest for webhook request verification."""
    import hmac, hashlib
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

def compute_retry_delay(attempt: int, base: float = 1.0, max_delay: float = 30.0) -> float:
    """Calculate exponential backoff delay for retry attempts."""
    delay = base * (2 ** max(0, attempt - 1))
    return min(delay, max_delay)

def determine_event_type(manifest: RunManifest) -> str:
    """Return granular event string based on execution failure mode."""
    if manifest.failure_mode:
        return f"run.{manifest.failure_mode.value.lower()}"
    return "run.completed"

def log_dispatch_result(webhook_url: str, run_id: str, success: bool, duration_ms: float) -> None:
    """Log webhook outcome and network latency."""
    status_str = "SUCCESS" if success else "FAILED"
    logger.info(f"Webhook dispatch [{status_str}] for run={run_id} to {webhook_url} ({duration_ms:.1f}ms)")
