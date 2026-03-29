# start_kernel()

## Summary
- Serves as the main entry point of the Linux kernel after early architecture-specific setup
- Orchestrates the overall kernel initialization process by invoking major subsystems in sequence
- Performs early generic initialization (boot params, CPU features, interrupts, logging, timing)
- Initializes full memory management (page allocator, zones, virtual memory structures)
- Sets up interrupt infrastructure to handle hardware interrupts and exceptions
- Initializes the scheduler to enable task management and multitasking
- Brings up core subsystems (VFS, drivers, IPC, security, cgroups, workqueues, RCU)
- Acts as the central coordinator that transitions the kernel from early boot to a fully functional system
- Prepares the environment for process creation and eventual transition to user space

---

## Relationships
- performs -> [1] Early Generic Initialization
- performs -> [2] Memory Management Initialization
- performs -> [3] Interrupt Infrastructure
- performs -> [4] Scheduler Initialization
- performs -> [5] Core Subsystems Initialization
