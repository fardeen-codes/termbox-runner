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
