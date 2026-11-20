"""Tests for artifact extraction and artifact API endpoints."""

import pytest
from httpx import AsyncClient
from termbox_runner.models import RunManifest, TaskSubmission
from termbox_runner.runner import MockTaskExecutor


@pytest.mark.asyncio
async def test_artifact_extraction_in_runner():
    executor = MockTaskExecutor()
    task = TaskSubmission(
        main_cmd="python -c \"with open('result.txt', 'w') as f: f.write('artifact_content')\"",
        extract_artifacts=["result.txt"],
    )
    manifest = RunManifest(task=task)
    result = await executor.execute(manifest)

    assert "result.txt" in result.artifacts
    assert result.artifacts["result.txt"] == "artifact_content"


@pytest.mark.asyncio
async def test_artifact_api_endpoints(async_client: AsyncClient):
    task_payload = {
        "main_cmd": "python -c \"with open('summary.json', 'w') as f: f.write('{\\\"score\\\": 98}')\"",
        "extract_artifacts": ["*.json"],
    }
    create_res = await async_client.post("/runs", json=task_payload)
    assert create_res.status_code == 201
    run_id = create_res.json()["run_id"]

    # List artifacts
    list_res = await async_client.get(f"/runs/{run_id}/artifacts")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["count"] >= 1
    assert any(a["path"] == "summary.json" for a in data["artifacts"])

    # Download artifact
    file_res = await async_client.get(f"/runs/{run_id}/artifacts/summary.json")
    assert file_res.status_code == 200
    assert '{"score": 98}' in file_res.text

    # 404 for missing artifact
    missing_res = await async_client.get(f"/runs/{run_id}/artifacts/does_not_exist.txt")
    assert missing_res.status_code == 404
