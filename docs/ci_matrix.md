# Enterprise CI/CD Reporting Matrix

| Platform | Output Format | Endpoint |
| :--- | :--- | :--- |
| GitHub Actions | Markdown Step Summary | `/runs/{id}/export/github` |
| GitLab CI | JUnit XML | `/runs/{id}/export/gitlab` |
| CircleCI | JUnit XML | `/runs/{id}/export/circleci` |
| Azure DevOps | Test Run JSON | `/runs/{id}/export/azure` |
| Allure 2.x | Test Result JSON | `/runs/{id}/export/allure` |
| SonarQube | Generic XML | `/runs/{id}/export/sonarqube` |
