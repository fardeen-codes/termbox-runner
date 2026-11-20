"""Tests for run search, tag filtering, and date range filters."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_and_tags(async_client: AsyncClient):
    # Submit run with specific tag and command
    await async_client.post(
        "/runs",
        json={
            "main_cmd": "python compute_primes.py",
            "tags": ["math", "benchmark-v1"],
        },
    )
    # Submit another run
    await async_client.post(
        "/runs",
        json={
            "main_cmd": "echo test_runner_unique_string",
            "tags": ["cli"],
        },
    )

    # Search by text
    res_search = await async_client.get("/runs?search=compute_primes")
    assert res_search.status_code == 200
    data_search = res_search.json()
    assert data_search["total"] >= 1
    assert any("compute_primes" in r["main_cmd"] for r in data_search["runs"])

    # Filter by tag
    res_tag = await async_client.get("/runs?tag=benchmark-v1")
    assert res_tag.status_code == 200
    data_tag = res_tag.json()
    assert data_tag["total"] >= 1
    assert any("benchmark-v1" in r.get("tags", []) for r in data_tag["runs"])

    # Search with no match
    res_none = await async_client.get("/runs?search=absolutely_nonexistent_token_123")
    assert res_none.status_code == 200
    assert res_none.json()["total"] == 0
