# Linux Kernel Init

## Type
system

## Domain
systems

## Summary
End-to-end flow of Linux kernel initialization from bootloader handoff to user space readiness.

---

## Relationships
- performs -> [1] Bootloader Handoff
- performs -> [2] Early Kernel Entry
- performs -> [3] Early Memory Setup
- performs -> [4] start_kernel()
- performs -> [5] Device Discovery
- performs -> [6] Driver Initialization
- performs -> [7] Root Filesystem Strategy
- performs -> [8] Initramfs Execution
- performs -> [9] Process Creation
- performs -> [10] rest_init()
- performs -> [11] Kernel Threads Execution
- performs -> [12] Late Initcalls
- performs -> [13] Early User Space (/init)
- performs -> [14] Root Switch
- performs -> [15] Real Init System
- performs -> [16] User Space Initialization
- performs -> [17] System Ready
