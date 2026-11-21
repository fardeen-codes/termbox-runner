"""Tests for SARIF and JSONL export generators."""

import pytest
from httpx import AsyncClient
from termbox_runner.export import runs_to_jsonl, to_sarif
from termbox_runner.models import FailureMode, RunManifest, RunStatus, TaskSubmission


def test_to_sarif_unit():
    task = TaskSubmission(main_cmd="python broken.py")
    manifest = RunManifest(
        task=task,
        status=RunStatus.FAILED,
        failure_mode=FailureMode.ASSERTION_FAILED,
        failure_reason="AssertionError: values differ",
        exit_code=1,
    )
    sarif = to_sarif(manifest)
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "ASSERTION_FAILED"


@pytest.mark.asyncio
async def test_export_api_endpoints(async_client: AsyncClient):
    # Create run
    res = await async_client.post("/runs", json={"main_cmd": "echo test_export"})
    run_id = res.json()["run_id"]

    # Export SARIF
    sarif_res = await async_client.get(f"/runs/{run_id}/export?format=sarif")
    assert sarif_res.status_code == 200
    assert sarif_res.json()["version"] == "2.1.0"

    # Export JSON
    json_res = await async_client.get(f"/runs/{run_id}/export?format=json")
    assert json_res.status_code == 200
    assert json_res.json()["run_id"] == run_id

    # Export JSONL
    jsonl_res = await async_client.get("/runs/export.jsonl")
    assert jsonl_res.status_code == 200
    assert "test_export" in jsonl_res.text


def test_junit_and_csv_exports():
    from termbox_runner.export import build_junit_xml, export_run_to_markdown, export_github_step_summary
    from termbox_runner.models import TaskSubmission, RunManifest, FailureMode
    
    task = TaskSubmission(main_cmd="pytest")
    manifest = RunManifest(task=task, exit_code=0, failure_mode=FailureMode.PASSED, duration_ms=450.0)
    
    xml = build_junit_xml(manifest)
    assert 'failures="0"' in xml
    assert 'name="termbox"' in xml

    md = export_run_to_markdown(manifest)
    assert "# Run Execution Report" in md

    gh = export_github_step_summary(manifest)
    assert "✅" in gh
