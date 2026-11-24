# Container Isolation & Security Specification

## Seccomp Filter
Termbox Runner applies a default seccomp profile denying dangerous syscalls:
- `ptrace`: Prevents process inspection and memory injection.
- `personality`: Prevents execution domain alteration.
- `sys_chroot`: Blocks unauthorized root directory changes.

## AppArmor
Default profile `termbox-default` drops:
- `deny capability sys_admin`
- `deny raw` sockets

## Read-only Root Filesystem
Containers can enforce `read_only_rootfs: true`, mounting temporary write buffers via memory-backed tmpfs (`/tmp`).
