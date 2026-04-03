# Linux Kernel Initialization

## Summary
linux_kernel_initialization_summary.md

## Relationships
- bootloader hands control to kernel -> [1] Bootloader hands control to kernel
- hands off to -> [2] Early Architecture Setup (head_64.S)
- initializes -> [3] Core Kernel Initialization (start_kernel)
- transitions to -> [4] Multitasking Initialization (rest_init)
- executes -> [5] Initramfs (Early User Space)
- mounts -> [6] Real Root Filesystem
- launches -> [7] User Space Init Process (PID 1)
