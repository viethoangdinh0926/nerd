# Bootloader Handoff

## Type
concept

## Domain
systems

## Summary
- Final step where the bootloader (e.g. GRUB bootloader) transfers control to the Linux kernel
- Kernel image (`vmlinuz`) is already loaded into memory and ready to execute
- Initramfs (early root filesystem) is loaded into memory for early user-space support
- Boot parameters (kernel command line, memory map, hardware info) are prepared and passed to the kernel
- CPU is placed in a known state (correct mode, interrupts typically disabled)
- Bootloader performs a jump to the kernel’s entry point (e.g. `startup_64`)
- Control fully shifts from bootloader to kernel — bootloader is no longer involved
- Kernel begins early initialization (setting up memory, paging, scheduler, devices)


---

## Relationships
- performs -> [1] Kernel Loading
- performs -> [2] Initramfs Loading
- performs -> [3] Boot Parameter Setup
- performs -> [4] Minimal Environment Setup
- performs -> [5] Control Transfer
