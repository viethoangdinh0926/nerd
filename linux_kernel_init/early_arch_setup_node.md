# Early Architecture Setup (head_64.S)

## Summary
early_arch_setup_summary.md

## Relationships
- more details -> GDT
- initializes -> Early Page Tables
- enables -> Paging Mechanism (CR3, CR0, CR4)
- switches to -> Virtual Address Space
- prepares -> Kernel Stack
- clears -> BSS Section
- prepares -> Transition to start_kernel()
