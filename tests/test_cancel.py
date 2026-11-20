"""Tests for task cancellation and abortion endpoints."""

import pytest
from httpx import AsyncClient
from termbox_runner.models import RunStatus


@pytest.mark.asyncio
async def test_cancel_active_run(async_client: AsyncClient, test_storage):
    from termbox_runner.models import RunManifest, TaskSubmission

    # Insert a run currently marked RUNNING
    active_manifest = RunManifest(
        task=TaskSubmission(main_cmd="python -c 'import time; time.sleep(10)'"),
        status=RunStatus.RUNNING,
    )
    await test_storage.save_run(active_manifest)

    # Cancel it
    res_cancel = await async_client.post(f"/runs/{active_manifest.run_id}/cancel")
    assert res_cancel.status_code == 200
    cancelled_run = res_cancel.json()
    assert cancelled_run["status"] == RunStatus.CANCELLED.value
    assert "cancelled" in cancelled_run["failure_reason"].lower()

    # Cancel already finished run returns 400
    res_cancel_again = await async_client.post(f"/runs/{active_manifest.run_id}/cancel")
    assert res_cancel_again.status_code == 400
