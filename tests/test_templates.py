"""Tests for benchmark template catalog and template launcher endpoints."""

import pytest
from httpx import AsyncClient
from termbox_runner.templates_catalog import get_benchmark_template, list_benchmark_templates


def test_template_catalog_definitions():
    templates = list_benchmark_templates()
    assert len(templates) >= 5
    ids = [t.id for t in templates]
    assert "humaneval-py" in ids
    assert "swe-mini" in ids
    assert "memory-stress" in ids
    assert "wallclock-timeout" in ids

    tmpl = get_benchmark_template("humaneval-py")
    assert tmpl is not None
    assert "solution.py" in tmpl.task.files


@pytest.mark.asyncio
async def test_template_api_endpoints(async_client: AsyncClient):
    # List templates
    res = await async_client.get("/templates")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 5

    # Get specific template
    res_one = await async_client.get("/templates/humaneval-py")
    assert res_one.status_code == 200
    assert res_one.json()["id"] == "humaneval-py"

    # Launch template
    res_launch = await async_client.post("/templates/humaneval-py/launch")
    assert res_launch.status_code == 201
    run = res_launch.json()
    assert run["run_id"].startswith("run_")

    # 404 for invalid template
    res_404 = await async_client.get("/templates/nonexistent_template")
    assert res_404.status_code == 404
