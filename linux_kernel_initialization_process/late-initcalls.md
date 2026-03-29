# Late Initcalls

## Type
concept

## Domain
systems

## Summary
- Executes the final stage of kernel initialization functions (late initcalls) before transitioning to user space
- Finalizes initialization of remaining kernel subsystems that depend on earlier setup
- Completes driver initialization for devices that require fully initialized kernel infrastructure
- Finishes filesystem-related setup needed before mounting and using filesystems
- Ensures all core kernel components and drivers are fully operational
- Prepares the system for launching the first user-space process (`/init`)
- Marks the transition from kernel initialization to user-space startup

---

## Relationships
- performs -> [1] Subsystem Finalization
- performs -> [2] Driver Finalization
- performs -> [3] Filesystem Setup
