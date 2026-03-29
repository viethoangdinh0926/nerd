# rest_init()

## Type
concept

## Domain
systems

## Summary
- Represents the transition point where the kernel finishes initialization and starts normal task scheduling
- Creates `kthreadd` (PID 2), the kernel thread responsible for managing and spawning other kernel threads
- Creates the `kernel_init` thread, which will continue initialization and eventually launch user-space (`/init`)
- Activates the scheduler, allowing task switching and concurrent execution to begin
- Moves execution from a single boot context into a multi-tasking environment
- Marks the point where the kernel begins operating as a fully scheduled system rather than linear boot code

---

## Relationships
- performs -> [1] kthreadd Creation
- performs -> [2] kernel_init Thread Creation
- performs -> [3] Scheduler Activation
