"""Tests for webhook notification dispatcher."""

import pytest
from termbox_runner.models import FailureMode, RunManifest, RunStatus, TaskSubmission
from termbox_runner.webhooks import dispatch_webhook


@pytest.mark.asyncio
async def test_dispatch_webhook_graceful_on_failure():
    task = TaskSubmission(main_cmd="echo hello", webhook_url="http://127.0.0.1:59999/nonexistent")
    manifest = RunManifest(task=task, status=RunStatus.COMPLETED, failure_mode=FailureMode.PASSED)
    # Gracefully catches connection refused / timeout and returns False without raising
    success = await dispatch_webhook(task.webhook_url, manifest, timeout=0.5)
    assert success is False
