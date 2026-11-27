# Multi-Tenant Container Sandbox Architecture

## Isolation Boundaries
- Strict User Namespaces mapping to unprivileged host UIDs.
- Read-only rootfs with memory-backed ephemeral `/tmp`.
- Dropped capabilities (`ALL`) preventing kernel exploits.
- Complete network isolation (`network_mode="none"`).
