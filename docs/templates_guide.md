# Benchmark Templates Authoring Guide

## Structure
Every template defines:
- `id`: Unique identifier (e.g. `express-api`).
- `name`: Human-readable benchmark title.
- `category`: Grouping (Web, Security, Database, JVM, Functional).
- `task`: TaskSubmission containing container image, main command, and resource limits.
