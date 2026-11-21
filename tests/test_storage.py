"""Unit tests for SQLite persistent storage layer and replay lineage."""

import pytest
from termbox_runner.models import (
    CommandStep,
    FailureMode,
    RunManifest,
    RunStatus,
    StepResult,
    TaskSubmission,
)
from termbox_runner.storage import RunStorage


@pytest.mark.asyncio
async def test_save_and_get_run(test_storage: RunStorage):
    task = TaskSubmission(
        main_cmd="python main.py",
        files={"main.py": "print('hello')"},
    )
    manifest = RunManifest(
        task=task,
        status=RunStatus.COMPLETED,
        failure_mode=FailureMode.PASSED,
        exit_code=0,
        duration_ms=45.2,
        combined_stdout="hello\n",
    )
    manifest.steps.append(
        StepResult(step=CommandStep.MAIN, command="python main.py", exit_code=0, stdout="hello\n")
    )

    await test_storage.save_run(manifest)

    fetched = await test_storage.get_run(manifest.run_id)
    assert fetched is not None
    assert fetched.run_id == manifest.run_id
    assert fetched.task.main_cmd == "python main.py"
    assert fetched.status == RunStatus.COMPLETED
    assert fetched.failure_mode == FailureMode.PASSED
    assert fetched.exit_code == 0
    assert fetched.combined_stdout == "hello\n"
    assert len(fetched.steps) == 1
    assert fetched.steps[0].command == "python main.py"


@pytest.mark.asyncio
async def test_get_nonexistent_run(test_storage: RunStorage):
    fetched = await test_storage.get_run("run_does_not_exist")
    assert fetched is None


@pytest.mark.asyncio
async def test_list_runs_filtering(test_storage: RunStorage):
    for i in range(5):
        mode = FailureMode.PASSED if i % 2 == 0 else FailureMode.OOM_KILLED
        status = RunStatus.COMPLETED if i % 2 == 0 else RunStatus.FAILED
        m = RunManifest(
            task=TaskSubmission(main_cmd=f"cmd_{i}"),
            status=status,
            failure_mode=mode,
        )
        await test_storage.save_run(m)

    all_runs, total = await test_storage.list_runs()
    assert total == 5
    assert len(all_runs) == 5

    passed_runs, passed_total = await test_storage.list_runs(failure_mode=FailureMode.PASSED)
    assert passed_total == 3
    assert len(passed_runs) == 3

    oom_runs, oom_total = await test_storage.list_runs(failure_mode=FailureMode.OOM_KILLED)
    assert oom_total == 2
    assert len(oom_runs) == 2


@pytest.mark.asyncio
async def test_replay_lineage_tracking(test_storage: RunStorage):
    # Gen 1 (Root)
    root = RunManifest(
        task=TaskSubmission(main_cmd="eval_v1"),
        status=RunStatus.FAILED,
        failure_mode=FailureMode.TIMEOUT,
    )
    await test_storage.save_run(root)

    # Gen 2 (Replay of Root)
    gen2 = RunManifest(
        parent_run_id=root.run_id,
        task=TaskSubmission(main_cmd="eval_v2"),
        status=RunStatus.FAILED,
        failure_mode=FailureMode.ASSERTION_FAILED,
    )
    await test_storage.save_run(gen2)
    await test_storage.increment_replay_count(root.run_id)

    # Gen 3 (Replay of Gen 2)
    gen3 = RunManifest(
        parent_run_id=gen2.run_id,
        task=TaskSubmission(main_cmd="eval_v3"),
        status=RunStatus.COMPLETED,
        failure_mode=FailureMode.PASSED,
    )
    await test_storage.save_run(gen3)
    await test_storage.increment_replay_count(gen2.run_id)

    # Trace lineage from Gen 3
    lineage = await test_storage.get_replay_lineage(gen3.run_id)
    assert len(lineage) == 3
    assert lineage[0].run_id == root.run_id
    assert lineage[1].run_id == gen2.run_id
    assert lineage[2].run_id == gen3.run_id

    # Trace lineage from Root
    lineage_from_root = await test_storage.get_replay_lineage(root.run_id)
    assert len(lineage_from_root) == 3

    # Check root replay count
    updated_root = await test_storage.get_run(root.run_id)
    assert updated_root is not None
    assert updated_root.replay_count == 1


@pytest.mark.asyncio
async def test_storage_additional_queries(tmp_path):
    storage = RunStorage(str(tmp_path / "test_queries.db"))
    await storage.init_db()

    task = TaskSubmission(main_cmd="echo hello", tags=["unit", "test"])
    manifest = RunManifest(task=task, exit_code=0, duration_ms=120.0)
    await storage.save_run(manifest)

    status_counts = await storage.count_runs_by_status()
    assert manifest.status.value in status_counts

    total_time = await storage.get_total_execution_time_ms()
    assert total_time >= 120.0

    updated = await storage.update_tags(manifest.run_id, ["prod", "v2"])
    assert updated is True

    await storage.vacuum()
    deleted = await storage.delete_run(manifest.run_id)
    assert deleted is True

    await storage.close()
