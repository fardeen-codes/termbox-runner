# Valgrind Memcheck Sandboxed Debugging

## Capabilities
Termbox Runner classifies Valgrind diagnostic reports:
- `Invalid read of size`: Out of bounds read in heap, stack, or freed memory.
- `Invalid write of size`: Memory corruption on write.
- `definitely lost in loss record`: Memory leak where no pointer to heap block exists.
