# Bootloader hands control to kernel

## Summary
bootloader_handoff_kernel_summary.md

## Relationships
- prepares -> [1] Kernel Image Loading
- prepares -> [2] Initramfs Loading
- provides -> [3] Boot Parameters (Command Line & Memory Map)
- initializes -> [4] CPU Execution State
- transfers control to -> [5] Kernel Entry (startup_64)
