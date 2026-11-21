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


def test_webhook_hmac_and_backoff():
    from termbox_runner.webhooks import generate_hmac_signature, compute_retry_delay, determine_event_type
    from termbox_runner.models import RunManifest, TaskSubmission, FailureMode

    sig = generate_hmac_signature(b'{"test":1}', "secret123")
    assert sig.startswith("sha256=")

    assert compute_retry_delay(1, base=1.0) == 1.0
    assert compute_retry_delay(2, base=1.0) == 2.0
    assert compute_retry_delay(3, base=1.0) == 4.0

    task = TaskSubmission(main_cmd="echo 1")
    manifest = RunManifest(task=task, failure_mode=FailureMode.TIMEOUT)
    assert determine_event_type(manifest) == "run.timeout"
