# Early Architecture Setup (head_64.S)

## Summary
early_arch_setup_summary.md

## Relationships
- initializes -> [1] Early Page Tables
- enables -> [2] Paging Mechanism (CR3, CR0, CR4)
- switches to -> [3] Virtual Address Space
- prepares -> [4] Kernel Stack
- clears -> [5] BSS Section
- prepares -> [6] Transition to start_kernel()
