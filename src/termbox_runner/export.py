"""Export formats for run manifests including SARIF v2.1.0 and JSONL."""

import json
from typing import Any, Dict, List
from termbox_runner.models import FailureMode, RunManifest, RunStatus


def to_sarif(manifest: RunManifest) -> Dict[str, Any]:
    """Convert a RunManifest into standard SARIF v2.1.0 report format."""
    results = []

    if manifest.failure_mode and manifest.failure_mode != FailureMode.PASSED:
        level = "error" if manifest.failure_mode in (FailureMode.ASSERTION_FAILED, FailureMode.OOM_KILLED) else "warning"
        results.append(
            {
                "ruleId": manifest.failure_mode.value,
                "level": level,
                "message": {
                    "text": manifest.failure_reason or f"Execution failed with mode {manifest.failure_mode.value}"
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": manifest.task.main_cmd},
                            "region": {"startLine": 1},
                        }
                    }
                ],
            }
        )

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Termbox-Runner",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/fardeen-codes/termbox-runner",
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": manifest.failure_mode == FailureMode.PASSED,
                        "exitCode": manifest.exit_code or 0,
                    }
                ],
                "results": results,
            }
        ],
    }


def runs_to_jsonl(runs: List[RunManifest]) -> str:
    """Serialize a list of RunManifest instances into newline-delimited JSON (JSONL)."""
    return "\n".join(r.model_dump_json() for r in runs)

def build_junit_xml(manifest: RunManifest) -> str:
    """Format run execution result as standard JUnit XML report."""
    time_s = manifest.duration_ms / 1000.0
    failures = 1 if manifest.failure_mode and manifest.failure_mode != FailureMode.PASSED else 0
    failure_tag = ""
    if failures:
        msg = manifest.failure_reason or manifest.failure_mode.value
        failure_tag = f'<failure message="{msg}" type="{manifest.failure_mode.value}"/>'
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="termbox" tests="1" failures="{failures}" errors="0" time="{time_s:.3f}">
  <testcase classname="termbox.runner" name="{manifest.run_id}" time="{time_s:.3f}">
    {failure_tag}
  </testcase>
</testsuite>'''

def export_runs_to_csv(runs: list) -> str:
    """Export list of run summaries into CSV format."""
    import csv, io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["run_id", "status", "failure_mode", "exit_code", "duration_ms", "image", "main_cmd"])
    for r in runs:
        writer.writerow([r.run_id, r.status.value, r.failure_mode.value if r.failure_mode else "", r.exit_code, r.duration_ms, r.image, r.main_cmd])
    return out.getvalue()

def export_run_to_markdown(manifest: RunManifest) -> str:
    """Format run execution manifest as GitHub-flavored Markdown."""
    mode = manifest.failure_mode.value if manifest.failure_mode else manifest.status.value
    lines = [
        f"# Run Execution Report: `{manifest.run_id}`",
        f"- **Status**: {manifest.status.value}",
        f"- **Failure Mode**: {mode}",
        f"- **Exit Code**: {manifest.exit_code}",
        f"- **Duration**: {manifest.duration_ms:.2f}ms",
        f"- **Command**: `{manifest.task.main_cmd}`",
        "",
        "## Standard Output",
        "```",
        manifest.combined_stdout or "(empty)",
        "```",
    ]
    return "\n".join(lines)

def export_github_step_summary(manifest: RunManifest) -> str:
    """Generate concise summary suitable for $GITHUB_STEP_SUMMARY."""
    status_icon = "✅" if manifest.failure_mode == FailureMode.PASSED else "❌"
    return f"### {status_icon} Termbox Run: `{manifest.run_id}` ({manifest.duration_ms / 1000:.2f}s)"

def export_runs_to_ndjson(runs: list) -> str:
    """Serialize list of runs as newline-delimited JSON."""
    return "\n".join(r.model_dump_json() for r in runs)

def xml_escape(text: str) -> str:
    """Escape string for safe inclusion in XML attributes and elements."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def export_sonarqube_generic_xml(manifest: RunManifest) -> str:
    """Export test results in SonarQube generic test execution XML format."""
    dur_ms = int(manifest.duration_ms)
    status_tag = "" if manifest.failure_mode == FailureMode.PASSED else f'<skipped message="{manifest.failure_mode.value}"/>'
    return f'''<testExecutions version="1">
  <file path="{manifest.task.main_cmd}">
    <testCase name="{manifest.run_id}" duration="{dur_ms}">
      {status_tag}
    </testCase>
  </file>
</testExecutions>'''

def export_tap_v13(manifest: RunManifest) -> str:
    """Export results conforming to Test Anything Protocol v13."""
    ok_str = "ok" if manifest.failure_mode == FailureMode.PASSED else "not ok"
    return f'''TAP version 13
1..1
{ok_str} 1 - {manifest.run_id} ({manifest.duration_ms:.1f}ms)
'''

def format_github_action_annotation(manifest: RunManifest) -> str:
    """Produce GitHub Actions ::error or ::notice command string."""
    level = "notice" if manifest.failure_mode == FailureMode.PASSED else "error"
    msg = manifest.failure_reason or (manifest.failure_mode.value if manifest.failure_mode else "Passed")
    return f"::{level} title=Termbox Run {manifest.run_id}::{msg}"

def format_slack_blocks_payload(manifest: RunManifest) -> dict:
    """Build rich Slack Block Kit notification message."""
    icon = ":white_check_mark:" if manifest.failure_mode == FailureMode.PASSED else ":x:"
    return {
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{icon} *Termbox Run {manifest.run_id}* finished with *{manifest.status.value}* ({manifest.duration_ms:.1f}ms)"}
            }
        ]
    }

def format_discord_embed(manifest: RunManifest) -> dict:
    """Build Discord webhook embed notification payload."""
    color = 0x10B981 if manifest.failure_mode == FailureMode.PASSED else 0xEF4444
    return {
        "embeds": [
            {
                "title": f"Run {manifest.run_id}",
                "description": f"Status: {manifest.status.value} | Mode: {manifest.failure_mode.value if manifest.failure_mode else 'PASSED'}",
                "color": color
            }
        ]
    }

def sanitize_slack_mrkdwn(text: str) -> str:
    """Sanitize text to prevent Slack markdown injection."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def generate_github_step_summary(manifest: RunManifest) -> str:
    """Generate GitHub Actions $GITHUB_STEP_SUMMARY Markdown format."""
    status_icon = "✅" if manifest.status == RunStatus.COMPLETED and manifest.failure_mode == FailureMode.PASSED else "❌"
    lines = [
        f"### {status_icon} Termbox Execution Summary ({manifest.run_id})",
        "",
        "| Attribute | Value |",
        "| :--- | :--- |",
        f"| **Status** | `{manifest.status.value}` |",
        f"| **Failure Mode** | `{manifest.failure_mode.value if manifest.failure_mode else 'PASSED'}` |",
        f"| **Exit Code** | `{manifest.exit_code if manifest.exit_code is not None else '-'}` |",
        f"| **Duration** | `{manifest.duration_ms:.1f}ms` |",
        "",
        "#### Command",
        f"```bash\n{manifest.task.main_cmd}\n```",
    ]
    return "\n".join(lines)

def generate_gitlab_junit_xml(manifest: RunManifest) -> str:
    """Generate GitLab CI compliant JUnit XML format."""
    return f'<?xml version="1.0" encoding="UTF-8"?><testsuites><testsuite name="termbox" tests="1" failures="{1 if manifest.failure_mode and manifest.failure_mode != FailureMode.PASSED else 0}"><testcase name="{manifest.run_id}" classname="termbox.runner" time="{manifest.duration_ms / 1000.0:.3f}"/></testsuite></testsuites>'

def generate_teamcity_messages(manifest: RunManifest) -> list[str]:
    """Format execution events as TeamCity service messages."""
    name = f"TermboxTask_{manifest.run_id}"
    messages = [f"##teamcity[testStarted name='{name}']"]
    if manifest.failure_mode and manifest.failure_mode != FailureMode.PASSED:
        messages.append(f"##teamcity[testFailed name='{name}' message='{manifest.failure_mode.value}']")
    messages.append(f"##teamcity[testFinished name='{name}' duration='{int(manifest.duration_ms)}']")
    return messages

def generate_cobertura_xml(coverage_pct: float = 100.0, packages: list = None) -> str:
    """Generate Cobertura code coverage XML report."""
    line_rate = coverage_pct / 100.0
    return f'<?xml version="1.0"?><coverage line-rate="{line_rate:.2f}" branch-rate="{line_rate:.2f}" version="2.0.3"><packages/></coverage>'

def generate_sarif_report(manifest: RunManifest) -> dict:
    """Construct OASIS SARIF v2.1.0 diagnostic output structure."""
    results = []
    if manifest.failure_mode and manifest.failure_mode != FailureMode.PASSED:
        results.append({
            "ruleId": manifest.failure_mode.value,
            "level": "error",
            "message": {"text": manifest.failure_reason or f"Execution failed with {manifest.failure_mode.value}"},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": "sandbox://task"}}}]
        })
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Termbox Runner", "version": "0.1.0"}}, "results": results}]
    }

def generate_lcov_coverage(source_file: str = "main.py", hit_lines: list = None) -> str:
    """Generate standard LCOV tracefile output."""
    hits = hit_lines or [1, 2, 3]
    lines = [f"TN:", f"SF:{source_file}"]
    for l in hits:
        lines.append(f"DA:{l},1")
    lines.append(f"LH:{len(hits)}")
    lines.append(f"LF:{len(hits)}")
    lines.append("end_of_record")
    return "\n".join(lines)

def format_run_csv_row(manifest: RunManifest) -> str:
    """Format run manifest into CSV record line."""
    mode = manifest.failure_mode.value if manifest.failure_mode else "PASSED"
    exit_c = manifest.exit_code if manifest.exit_code is not None else ""
    cmd_clean = manifest.task.main_cmd.replace('"', '""')
    return f'"{manifest.run_id}","{manifest.status.value}","{mode}","{exit_c}","{manifest.duration_ms:.1f}","{cmd_clean}"'

def serialize_jsonl_events(events: list) -> str:
    """Serialize list of telemetry or execution events into JSONL string."""
    import json
    return "\n".join(json.dumps(ev) for ev in events)

def generate_bazel_test_xml(manifest: RunManifest) -> str:
    """Format task execution results in Bazel test.xml convention."""
    status = "failed" if manifest.failure_mode and manifest.failure_mode != FailureMode.PASSED else "passed"
    return f'<?xml version="1.0" encoding="UTF-8"?><testsuites><testsuite name="bazel.test" tests="1" errors="0" failures="{1 if status == "failed" else 0}"><testcase name="{manifest.run_id}" status="{status}" time="{manifest.duration_ms / 1000.0:.3f}"/></testsuite></testsuites>'

def generate_ctrf_report(manifest: RunManifest) -> dict:
    """Generate CTRF standard JSON report for modern CI/CD dashboards."""
    passed = manifest.status == RunStatus.COMPLETED and (not manifest.failure_mode or manifest.failure_mode == FailureMode.PASSED)
    return {
        "reportFormat": "CTRF",
        "specVersion": "0.0.1",
        "results": {
            "tool": {"name": "termbox-runner"},
            "summary": {"tests": 1, "passed": 1 if passed else 0, "failed": 0 if passed else 1, "start": 0, "stop": int(manifest.duration_ms)},
            "tests": [{"name": manifest.run_id, "status": "passed" if passed else "failed", "duration": int(manifest.duration_ms)}]
        }
    }

def generate_allure_result_json(manifest: RunManifest) -> dict:
    """Generate standard Allure 2.x JSON test result structure."""
    status = "passed" if not manifest.failure_mode or manifest.failure_mode == FailureMode.PASSED else "failed"
    return {
        "name": f"TaskExecution_{manifest.run_id}",
        "status": status,
        "statusDetails": {"message": manifest.failure_reason or "Completed clean"},
        "stage": "finished",
        "start": int(manifest.duration_ms),
        "stop": int(manifest.duration_ms),
        "parameters": [{"name": "command", "value": manifest.task.main_cmd}],
        "labels": [{"name": "suite", "value": "termbox-runner"}, {"name": "framework", "value": "termbox"}]
    }

def generate_circleci_test_xml(manifest: RunManifest) -> str:
    """Format task execution results in CircleCI test results XML convention."""
    failures = 1 if manifest.failure_mode and manifest.failure_mode != FailureMode.PASSED else 0
    return f'<?xml version="1.0" encoding="UTF-8"?><testsuite name="circleci.task" tests="1" failures="{failures}" time="{manifest.duration_ms / 1000.0:.3f}"><testcase name="{manifest.run_id}" classname="termbox.runner"/></testsuite>'

def generate_azure_devops_test_json(manifest: RunManifest) -> dict:
    """Format task execution results in Azure DevOps Test Runs JSON schema."""
    outcome = "Passed" if not manifest.failure_mode or manifest.failure_mode == FailureMode.PASSED else "Failed"
    return {
        "title": f"Termbox Task {manifest.run_id}",
        "outcome": outcome,
        "durationInMs": int(manifest.duration_ms),
        "errorMessage": manifest.failure_reason if outcome == "Failed" else None,
        "runId": manifest.run_id
    }

def generate_bitbucket_report_xml(manifest: RunManifest) -> str:
    """Format results for Bitbucket Pipelines Test Reports."""
    passed = not manifest.failure_mode or manifest.failure_mode == FailureMode.PASSED
    return f'<?xml version="1.0" encoding="UTF-8"?><testcase name="{manifest.run_id}" status="{"SUCCESS" if passed else "FAILED"}" duration="{int(manifest.duration_ms)}"/>'

def generate_sonarqube_generic_xml(manifest: RunManifest) -> str:
    """Format results in SonarQube generic test execution XML schema."""
    passed = not manifest.failure_mode or manifest.failure_mode == FailureMode.PASSED
    inner = f'<testCase name="{manifest.run_id}" duration="{int(manifest.duration_ms)}"/>' if passed else f'<testCase name="{manifest.run_id}" duration="{int(manifest.duration_ms)}"><failure message="{manifest.failure_mode.value}"/></testCase>'
    return f'<testExecutions version="1"><file path="sandbox://task">{inner}</file></testExecutions>'

def generate_testrail_result_json(manifest: RunManifest, test_id: int = 1) -> dict:
    """Format task results for TestRail API add_result endpoint."""
    status_id = 1 if not manifest.failure_mode or manifest.failure_mode == FailureMode.PASSED else 5
    return {
        "test_id": test_id,
        "status_id": status_id,
        "comment": manifest.failure_reason or "Execution clean",
        "elapsed": f"{max(1, int(manifest.duration_ms / 1000))}s"
    }

def generate_status_badge_svg(status: str, label: str = "termbox") -> str:
    """Generate SVG status badge for GitHub READMEs or PR comments."""
    color = "#22c55e" if status.upper() in ("PASSED", "COMPLETED") else "#ef4444"
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="20"><rect width="50" height="20" fill="#1e293b"/><rect x="50" width="50" height="20" fill="{color}"/><text x="25" y="14" fill="#fff" font-size="11" text-anchor="middle">{label}</text><text x="75" y="14" fill="#fff" font-size="11" text-anchor="middle">{status}</text></svg>'

def format_multi_run_markdown_matrix(manifests: list[RunManifest]) -> str:
    """Generate Markdown evaluation summary comparison table."""
    lines = ["| Run ID | Status | Mode | Duration | Command |", "| :--- | :--- | :--- | :--- | :--- |"]
    for m in manifests:
        mode = m.failure_mode.value if m.failure_mode else "PASSED"
        lines.append(f"| `{m.run_id}` | `{m.status.value}` | `{mode}` | {m.duration_ms:.1f}ms | `{m.task.main_cmd[:25]}` |")
    return "\n".join(lines)

def encode_ndjson_event(event_type: str, payload: dict) -> str:
    """Encode single NDJSON event line."""
    import json
    return json.dumps({"event": event_type, "data": payload}) + "\n"

def generate_tap14_report(manifest: RunManifest) -> str:
    """Generate Test Anything Protocol (TAP) version 14 string."""
    passed = not manifest.failure_mode or manifest.failure_mode == FailureMode.PASSED
    ok_str = "ok" if passed else "not ok"
    lines = [
        "TAP version 14",
        "1..1",
        f"{ok_str} 1 - {manifest.run_id}",
        f"  ---",
        f"  duration_ms: {manifest.duration_ms:.1f}",
        f"  mode: {manifest.failure_mode.value if manifest.failure_mode else 'PASSED'}",
        f"  ..."
    ]
    return "\n".join(lines)

def sanitize_cdata_text(text: str) -> str:
    """Escape CDATA termination sequence in XML output."""
    return text.replace("]]>", "]]]]><![CDATA[>")

def format_teamcity_inspection(type_id: str, message: str, file_path: str = "main.py") -> str:
    """Generate TeamCity inspection message."""
    return f"##teamcity[inspectionType id='{type_id}' name='{type_id}' category='Security' description='Termbox finding']\n##teamcity[inspection typeId='{type_id}' message='{message}' file='{file_path}']"

def sign_webhook_payload(payload_bytes: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature string for webhook security."""
    import hmac
    import hashlib
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

def generate_jenkins_test_xml(manifest: RunManifest) -> str:
    """Generate Jenkins JUnit plugin compliant XML report."""
    failed = manifest.failure_mode and manifest.failure_mode != FailureMode.PASSED
    return f'<?xml version="1.0" encoding="UTF-8"?><testsuite name="jenkins.runner" tests="1" failures="{1 if failed else 0}"><testcase classname="termbox.task" name="{manifest.run_id}" time="{manifest.duration_ms / 1000.0:.3f}"/></testsuite>'

def format_travis_log_section(section_name: str, content: str) -> str:
    """Format log with Travis CI fold markers (travis_fold:start/end)."""
    return f"travis_fold:start:{section_name}\ntravis_time:start:{section_name}\n{content}\ntravis_time:end:{section_name}\ntravis_fold:end:{section_name}"

def format_github_action_error(title: str, message: str, file: str = "main.py", line: int = 1) -> str:
    """Generate GitHub Actions workflow command error annotation string."""
    return f"::error file={file},line={line},title={title}::{message}"

def format_github_action_warning(title: str, message: str, file: str = "main.py", line: int = 1) -> str:
    """Generate GitHub Actions workflow command warning annotation string."""
    return f"::warning file={file},line={line},title={title}::{message}"

def generate_codecov_report(manifest: RunManifest, coverage_pct: float = 100.0) -> dict:
    """Construct Codecov custom upload payload."""
    return {
        "version": "1.0",
        "run_id": manifest.run_id,
        "coverage": coverage_pct,
        "status": "passed" if manifest.exit_code == 0 else "failed",
    }
