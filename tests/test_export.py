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


def test_tap_and_sonarqube_exports():
    from termbox_runner.export import export_tap_v13, export_sonarqube_generic_xml, format_github_action_annotation
    from termbox_runner.models import TaskSubmission, RunManifest, FailureMode

    task = TaskSubmission(main_cmd="test.sh")
    manifest = RunManifest(task=task, exit_code=0, failure_mode=FailureMode.PASSED, duration_ms=100.0)

    tap = export_tap_v13(manifest)
    assert "TAP version 13" in tap
    assert "ok 1" in tap

    sq = export_sonarqube_generic_xml(manifest)
    assert "<testExecutions" in sq

    gh = format_github_action_annotation(manifest)
    assert "::notice" in gh

def test_export_additional_ci_formats():
    from termbox_runner.models import RunManifest, TaskSubmission, RunStatus, FailureMode
    from termbox_runner.export import (
        generate_github_step_summary,
        generate_gitlab_junit_xml,
        generate_teamcity_messages,
        generate_cobertura_xml,
        generate_sarif_report,
        generate_lcov_coverage,
        format_run_csv_row,
        serialize_jsonl_events,
    )
    manifest = RunManifest(task=TaskSubmission(main_cmd="echo 1"), status=RunStatus.COMPLETED, failure_mode=FailureMode.PASSED, duration_ms=12.5)
    gh = generate_github_step_summary(manifest)
    assert "Termbox Execution Summary" in gh
    assert "echo 1" in gh
    gitlab = generate_gitlab_junit_xml(manifest)
    assert "<testsuite" in gitlab
    tc = generate_teamcity_messages(manifest)
    assert len(tc) >= 2
    cob = generate_cobertura_xml(85.0)
    assert 'line-rate="0.85"' in cob
    sarif = generate_sarif_report(manifest)
    assert sarif["version"] == "2.1.0"
    lcov = generate_lcov_coverage()
    assert "end_of_record" in lcov
    csv_row = format_run_csv_row(manifest)
    assert "echo 1" in csv_row
    jsonl = serialize_jsonl_events([{"a": 1}, {"b": 2}])
    assert "\n" in jsonl

def test_export_bazel_and_ctrf():
    from termbox_runner.models import RunManifest, TaskSubmission, RunStatus, FailureMode
    from termbox_runner.export import generate_bazel_test_xml, generate_ctrf_report

    m = RunManifest(task=TaskSubmission(main_cmd="echo ok"), status=RunStatus.COMPLETED, failure_mode=FailureMode.PASSED, duration_ms=25.0)
    bazel_xml = generate_bazel_test_xml(m)
    assert '<testsuite name="bazel.test"' in bazel_xml

    ctrf = generate_ctrf_report(m)
    assert ctrf["reportFormat"] == "CTRF"
    assert ctrf["results"]["summary"]["passed"] == 1

def test_export_allure_and_page_faults():
    from termbox_runner.models import RunManifest, TaskSubmission, RunStatus, FailureMode
    from termbox_runner.export import generate_allure_result_json
    from termbox_runner.telemetry import record_page_faults_metric

    m = RunManifest(task=TaskSubmission(main_cmd="echo test"), status=RunStatus.COMPLETED, failure_mode=FailureMode.PASSED, duration_ms=10.0)
    allure = generate_allure_result_json(m)
    assert allure["status"] == "passed"
    assert allure["labels"][0]["name"] == "suite"

    pf = record_page_faults_metric("r1", 0, 150)
    assert pf["minor_faults"] == 150

def test_export_batch1_ci_formats():
    from termbox_runner.models import RunManifest, TaskSubmission, RunStatus, FailureMode
    from termbox_runner.export import (
        generate_circleci_test_xml,
        generate_azure_devops_test_json,
        generate_bitbucket_report_xml,
        generate_sonarqube_generic_xml,
        generate_testrail_result_json,
        generate_status_badge_svg,
        format_multi_run_markdown_matrix,
        encode_ndjson_event,
    )
    m = RunManifest(task=TaskSubmission(main_cmd="echo test"), status=RunStatus.COMPLETED, failure_mode=FailureMode.PASSED, duration_ms=15.0)
    assert '<testsuite name="circleci.task"' in generate_circleci_test_xml(m)
    assert generate_azure_devops_test_json(m)["outcome"] == "Passed"
    assert "SUCCESS" in generate_bitbucket_report_xml(m)
    assert "<testExecutions" in generate_sonarqube_generic_xml(m)
    assert generate_testrail_result_json(m)["status_id"] == 1
    assert "<svg" in generate_status_badge_svg("PASSED")
    assert "echo test" in format_multi_run_markdown_matrix([m])
    assert "data" in encode_ndjson_event("STARTED", {"id": 1})

def test_export_batch3_ci_annotations():
    from termbox_runner.models import RunManifest, TaskSubmission, RunStatus, FailureMode
    from termbox_runner.export import (
        generate_jenkins_test_xml,
        format_travis_log_section,
        format_github_action_error,
        format_github_action_warning,
    )
    m = RunManifest(task=TaskSubmission(main_cmd="echo test"), status=RunStatus.COMPLETED, failure_mode=FailureMode.PASSED, duration_ms=20.0)
    assert "<testsuite name="jenkins.runner"" in generate_jenkins_test_xml(m)
    assert "travis_fold:start:build" in format_travis_log_section("build", "Compiling...")
    assert "::error" in format_github_action_error("OOM", "Memory limit exceeded")
    assert "::warning" in format_github_action_warning("Slow", "Execution took > 10s")
