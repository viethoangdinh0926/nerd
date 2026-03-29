# Scheduler Initialization

## Type
concept

## Domain
systems

## Summary
- Initializes the kernel scheduler responsible for managing CPU time across tasks
- Sets up runqueues for each CPU to track runnable tasks
- Configures scheduling classes (e.g., CFS, real-time) to define scheduling policies
- Creates the idle task for each CPU to run when no other tasks are available
- Enables context switching so the CPU can switch between different tasks
- Establishes the foundation for multitasking and process scheduling
- Allows the system to begin executing multiple tasks efficiently across CPUs

---

## Relationships
- performs -> [1] Runqueue Setup
- performs -> [2] Scheduling Classes Setup
- performs -> [3] Idle Task Creation
- performs -> [4] Context Switching Enablement
