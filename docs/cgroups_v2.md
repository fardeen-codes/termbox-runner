# Cgroups v2 Architecture & Resource Enforcement

## Memory Controllers
- `memory.max`: Hard out-of-memory boundary triggering OS OOM killer.
- `memory.high`: Throttling boundary preventing aggressive memory consumption without SIGKILL.
- `memory.swap.max`: Cap on anonymous page swapping to disk.

## CPU Controllers
- `cpu.max`: Quota and period specification (`quota period`).
- `cpu.weight`: Proportional share weighting (1-10000).

## I/O Weight
- `io.weight`: Proportional disk bandwidth allocator.
