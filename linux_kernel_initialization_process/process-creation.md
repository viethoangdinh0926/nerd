# Process Creation

## Type
concept

## Domain
systems

## Summary
- Establishes the first kernel processes that form the foundation of process management
- Creates PID 0 (idle task) which runs when no other tasks are scheduled on a CPU
- Creates PID 1 (init placeholder) which will later become the first user-space process (`/init`)
- Creates PID 2 (`kthreadd`) which is responsible for managing and spawning kernel threads
- Initializes core task structures and scheduling context for process execution
- Enables the scheduler to begin managing and switching between tasks
- Forms the base of both kernel threads and user-space process hierarchy

---

## Relationships
- creates -> [1] PID 0 (Idle Task)
- creates -> [2] PID 1 (Init Placeholder)
- creates -> [3] PID 2 (kthreadd)
