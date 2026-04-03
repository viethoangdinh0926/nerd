# Linux Kernel Initialization

## Summary
linux_kernel_initialization_summary.md

## Relationships
- bootloader hands control to kernel -> [1] Bootloader hands control to kernel
- hands off to -> [2] Early Architecture Setup (head_64.S)
- initializes -> [3] Core Kernel Initialization (start_kernel)
- sets up -> [4] Memory Management System
- sets up -> [5] Interrupt Handling System
- initializes -> [6] Kernel Subsystems
- transitions to -> [7] Multitasking Initialization (rest_init)
- executes -> [8] Initramfs (Early User Space)
- mounts -> [9] Real Root Filesystem
- launches -> [10] User Space Init Process (PID 1)
