"""Export formats for run manifests including SARIF v2.1.0 and JSONL."""

import json
from typing import Any, Dict, List
from termbox_runner.models import FailureMode, RunManifest


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
