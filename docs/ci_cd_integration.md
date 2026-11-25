# CI/CD Agent Evaluation Harness Integration

## Overview
Termbox Runner integrates seamlessly with enterprise continuous integration environments:
- **GitHub Actions:** Native `$GITHUB_STEP_SUMMARY` Markdown formatting.
- **GitLab CI:** Standard JUnit test suite XML reports.
- **Bazel:** `test.xml` compliant schema output.
- **CTRF (Common Test Report Format):** Modern JSON schema for test reporting.

## Example GitHub Action
```yaml
name: Agent Evaluation
on: [push, pull_request]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Evaluation
        run: |
          RUN_ID=$(curl -s -X POST http://localhost:8000/runs -d '{"image":"python:3.12-slim","main_cmd":"pytest"}' | jq -r .run_id)
          curl -s "http://localhost:8000/runs/${RUN_ID}/export/github" >> $GITHUB_STEP_SUMMARY
```
