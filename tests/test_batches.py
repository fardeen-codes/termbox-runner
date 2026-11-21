"""Tests for batch task execution and aggregation endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_batch_execution(async_client: AsyncClient):
    batch_payload = {
        "name": "matrix_test",
        "parallel_limit": 2,
        "tasks": [
            {"main_cmd": "python -c 'print(10)'"},
            {"main_cmd": "python -c 'print(20)'"},
            {"main_cmd": "python -c 'import sys; sys.exit(1)'", "metadata": {"mock_behavior": "runtime_error"}},
        ],
    }

    res = await async_client.post("/batches", json=batch_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "matrix_test"
    assert data["total_runs"] == 3
    assert data["passed_count"] == 2
    assert data["failed_count"] == 1
    assert len(data["runs"]) == 3

    batch_id = data["batch_id"]
    get_res = await async_client.get(f"/batches/{batch_id}")
    assert get_res.status_code == 200
    assert get_res.json()["batch_id"] == batch_id


@pytest.mark.asyncio
async def test_batch_rerun_failed(async_client):
    res = await async_client.post("/batches/b123/rerun-failed")
    assert res.status_code == 200
    assert res.json()["batch_id"] == "b123"
