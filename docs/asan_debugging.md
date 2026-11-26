# AddressSanitizer (ASan) & Memory Safety Debugging

## Overview
Termbox Runner classifies compiler memory safety issues into distinct diagnostics:
- `heap-buffer-overflow`: Access beyond allocated heap boundary.
- `use-after-free`: Dereferencing pointers after memory deallocation.
- `memory leaks`: Allocated memory never freed before process termination.

## Compiler Flags
When compiling C/C++ benchmark harnesses:
```bash
gcc -fsanitize=address,undefined -g -O1 harness.c -o harness
```
