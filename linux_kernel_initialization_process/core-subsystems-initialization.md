# Core Subsystems Initialization

## Summary
- Initializes the kernel’s core subsystems that enable higher-level OS functionality after early boot
- Sets up the Virtual File System (VFS) to provide a unified interface for all file systems
- Initializes the block layer to handle disk I/O and storage device communication
- Brings up the driver model to manage devices, buses, and hardware abstraction
- Initializes IPC mechanisms (pipes, signals, shared memory) for process communication
- Sets up security frameworks (e.g., LSM) to enforce system security policies
- Initializes cgroups to enable resource management and isolation (used by containers)
- Sets up RCU (Read-Copy-Update) for efficient synchronization in the kernel
- Initializes workqueues to handle deferred and asynchronous kernel tasks
- Marks the transition from low-level bootstrapping to a fully functional kernel environment ready for user-space processes

---

## Relationships
- performs -> [1] VFS Initialization
- performs -> [2] Block Layer Initialization
- performs -> [3] Driver Model Initialization
- performs -> [4] IPC Initialization
- performs -> [5] Security Framework Initialization
- performs -> [6] Cgroups Initialization
- performs -> [7] RCU Initialization
- performs -> [8] Workqueue Initialization
