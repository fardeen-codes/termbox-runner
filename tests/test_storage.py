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


@pytest.mark.asyncio
async def test_storage_histograms_and_cleanup(tmp_path):
    storage = RunStorage(str(tmp_path / "hist.db"))
    await storage.init_db()

    task = TaskSubmission(main_cmd="echo hist")
    manifest = RunManifest(task=task, duration_ms=250.0)
    await storage.save_run(manifest)

    hist = await storage.get_run_count_by_date_histogram()
    assert len(hist) >= 1

    slowest = await storage.get_slowest_runs(limit=1)
    assert len(slowest) == 1
    assert slowest[0]["duration_ms"] >= 250.0

    size = storage.get_database_file_size_bytes()
    assert size > 0

    await storage.update_run_notes(manifest.run_id, "Verified clean run")
    pruned = await storage.cleanup_runs_older_than("2099-01-01")
    assert pruned >= 1

    await storage.close()


@pytest.mark.asyncio
async def test_storage_additional_queries_part2(tmp_path):
    storage = RunStorage(str(tmp_path / "part2.db"))
    await storage.init_db()

    assert await storage.ping_database() is True
    assert await storage.check_database_integrity() == "ok"

    task = TaskSubmission(main_cmd="echo part2", tags=["batch"])
    manifest = RunManifest(task=task, duration_ms=150.0)
    await storage.save_run(manifest)

    p = await storage.get_duration_percentiles()
    assert "p50" in p

    assert await storage.get_root_lineage_run(manifest.run_id) == manifest.run_id
    assert await storage.get_run_task_command(manifest.run_id) == "echo part2"

    deleted = await storage.delete_runs_by_ids([manifest.run_id])
    assert deleted == 1

    await storage.close()

def test_storage_part2_features():
    from termbox_runner.storage import (
        get_optimized_sqlite_pragmas,
        compress_log_output,
        decompress_log_output,
    )
    pragmas = get_optimized_sqlite_pragmas()
    assert any("WAL" in p for p in pragmas)
    raw = "Test execution log output for storage compression check."
    comp = compress_log_output(raw)
    assert len(comp) > 0
    assert decompress_log_output(comp) == raw

async def test_storage_batch1_queries():
    from termbox_runner.storage import count_table_rows
    # synchronous check of table names
    assert await count_table_rows(None, "invalid_table") == 0

def test_storage_batch2_helpers():
    from termbox_runner.export import sign_webhook_payload, sanitize_cdata_text
    sig = sign_webhook_payload(b"hello", "secret")
    assert len(sig) == 64
    assert "]]]]><![CDATA[>" in sanitize_cdata_text("test]]>text")


async def test_storage_range_and_bucket_queries(tmp_path):
    from termbox_runner.storage import (
        RunStorage,
        query_runs_by_duration_range,
        query_runs_by_exit_code_range,
        query_runs_in_time_window,
        count_runs_by_date_bucket,
        calculate_average_duration_by_image,
    )
    db_file = str(tmp_path / "range_test.db")
    storage = RunStorage(db_file)
    await storage.init_db()
    res1 = await query_runs_by_duration_range(storage, 0.0, 5000.0)
    assert isinstance(res1, list)
    res2 = await query_runs_by_exit_code_range(storage, 0, 1)
    assert isinstance(res2, list)
    res3 = await query_runs_in_time_window(storage, "2020-01-01", "2030-01-01")
    assert isinstance(res3, list)
    buckets = await count_runs_by_date_bucket(storage)
    assert isinstance(buckets, dict)
    avg_img = await calculate_average_duration_by_image(storage)
    assert isinstance(avg_img, dict)
    await storage.close()
