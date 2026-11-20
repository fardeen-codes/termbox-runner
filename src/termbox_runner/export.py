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
