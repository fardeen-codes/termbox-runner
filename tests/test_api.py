"""API integration tests for termbox-runner HTTP endpoints."""

import pytest
from httpx import AsyncClient
from termbox_runner.models import FailureMode, RunStatus


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    res = await async_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "docker_available" in data


@pytest.mark.asyncio
async def test_ui_endpoint(async_client: AsyncClient):
    res = await async_client.get("/ui")
    assert res.status_code == 200
    assert "Termbox Runner" in res.text
    assert "<!DOCTYPE html>" in res.text

    # Also root endpoint
    res_root = await async_client.get("/")
    assert res_root.status_code == 200
    assert "Termbox Runner" in res_root.text


@pytest.mark.asyncio
async def test_submit_run_sync(async_client: AsyncClient):
    payload = {
        "main_cmd": "python -c 'print(100 + 23)'",
        "limits": {"timeout_seconds": 15, "mem_limit": "256m"},
    }
    res = await async_client.post("/runs", json=payload)
    assert res.status_code == 201
    run = res.json()

    assert run["run_id"].startswith("run_")
    assert run["status"] == RunStatus.COMPLETED.value
    assert run["failure_mode"] == FailureMode.PASSED.value
    assert run["exit_code"] == 0
    assert "123" in run["combined_stdout"]


@pytest.mark.asyncio
async def test_submit_run_async(async_client: AsyncClient):
    import asyncio
    payload = {
        "main_cmd": "python -c 'print(999)'",
        "metadata": {"mock_behavior": "pass"},
    }
    res = await async_client.post("/runs?wait=false", json=payload)
    assert res.status_code == 201
    run = res.json()
    assert run["run_id"].startswith("run_")
    assert run["status"] == RunStatus.QUEUED.value
    # Let background task complete cleanly
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_list_runs_and_filters(async_client: AsyncClient):
    # Submit passing run
    await async_client.post(
        "/runs",
        json={"main_cmd": "echo pass_1", "metadata": {"mock_behavior": "pass"}},
    )
    # Submit failing run
    await async_client.post(
        "/runs",
        json={"main_cmd": "echo oom_1", "metadata": {"mock_behavior": "oom"}},
    )

    res_all = await async_client.get("/runs")
    assert res_all.status_code == 200
    all_runs = res_all.json()
    assert all_runs["total"] >= 2

    # Filter by failure_mode PASSED
    res_passed = await async_client.get("/runs?failure_mode=PASSED")
    assert res_passed.status_code == 200
    passed_runs = res_passed.json()
    assert passed_runs["total"] >= 1
    assert all(r["failure_mode"] == "PASSED" for r in passed_runs["runs"])

    # Filter by failure_mode OOM_KILLED
    res_oom = await async_client.get("/runs?failure_mode=OOM_KILLED")
    assert res_oom.status_code == 200
    oom_runs = res_oom.json()
    assert oom_runs["total"] >= 1
    assert all(r["failure_mode"] == "OOM_KILLED" for r in oom_runs["runs"])


@pytest.mark.asyncio
async def test_get_run_by_id(async_client: AsyncClient):
    # Create run
    create_res = await async_client.post(
        "/runs",
        json={"main_cmd": "echo test_get", "files": {"hello.py": "print('hello')"}},
    )
    created = create_res.json()
    run_id = created["run_id"]

    # Fetch
    get_res = await async_client.get(f"/runs/{run_id}")
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert fetched["run_id"] == run_id
    assert fetched["task"]["main_cmd"] == "echo test_get"
    assert fetched["task"]["files"]["hello.py"] == "print('hello')"


@pytest.mark.asyncio
async def test_get_run_not_found(async_client: AsyncClient):
    res = await async_client.get("/runs/nonexistent_run_999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_replay_flow_and_lineage(async_client: AsyncClient):
    # Step 1: create root run that failed with assertion error
    root_res = await async_client.post(
        "/runs",
        json={
            "main_cmd": "python agent.py",
            "verifier_cmd": "pytest",
            "metadata": {"mock_behavior": "assertion_failed"},
        },
    )
    root = root_res.json()
    root_id = root["run_id"]
    assert root["failure_mode"] == FailureMode.ASSERTION_FAILED.value

    # Step 2: replay with override main_cmd that passes
    replay_payload = {
        "override_main_cmd": "python fixed_agent.py",
        "override_limits": {"timeout_seconds": 45, "mem_limit": "512m"},
    }
    replay_res = await async_client.post(f"/runs/{root_id}/replay", json=replay_payload)
    assert replay_res.status_code == 201
    replayed = replay_res.json()
    replayed_id = replayed["run_id"]

    assert replayed_id != root_id
    assert replayed["parent_run_id"] == root_id
    assert replayed["task"]["main_cmd"] == "python fixed_agent.py"
    assert replayed["task"]["limits"]["timeout_seconds"] == 45

    # Step 3: verify lineage
    lineage_res = await async_client.get(f"/runs/{replayed_id}/lineage")
    assert lineage_res.status_code == 200
    lineage = lineage_res.json()
    assert len(lineage) == 2
    assert lineage[0]["run_id"] == root_id
    assert lineage[1]["run_id"] == replayed_id

    # Step 4: verify replay count on root
    root_fetched = await async_client.get(f"/runs/{root_id}")
    assert root_fetched.json()["replay_count"] == 1


@pytest.mark.asyncio
async def test_replay_not_found(async_client: AsyncClient):
    res = await async_client.post("/runs/nonexistent_run/replay", json={})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_lineage_not_found(async_client: AsyncClient):
    res = await async_client.get("/runs/nonexistent_run/lineage")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_system_info_and_headers(async_client):
    res = await async_client.get("/system/info")
    assert res.status_code == 200
    assert "os" in res.json()
    assert "X-Process-Time" in res.headers
    assert "X-Request-ID" in res.headers


@pytest.mark.asyncio
async def test_stats_summary_endpoint(async_client):
    res = await async_client.get("/stats/summary")
    assert res.status_code == 200
    assert "status_counts" in res.json()


@pytest.mark.asyncio
async def test_system_telemetry_endpoint(async_client):
    res = await async_client.get("/telemetry/system")
    assert res.status_code == 200
    data = res.json()
    assert "load_1m" in data
    assert "active_runs" in data


@pytest.mark.asyncio
async def test_webhook_test_endpoint_unreachable(async_client):
    res = await async_client.post("/webhooks/test?url=http://127.0.0.1:19999/nonexistent")
    assert res.status_code == 200
    assert res.json()["reachable"] is False


@pytest.mark.asyncio
async def test_artifact_keys_and_zip_endpoints(async_client):
    res = await async_client.get("/runs/nonexistent_run/artifacts/keys")
    assert res.status_code == 404

    zip_res = await async_client.get("/runs/nonexistent_run/artifacts/zip")
    assert zip_res.status_code == 404
