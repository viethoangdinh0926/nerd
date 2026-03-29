# Early Kernel Entry

## Type
concept

## Domain
systems

## Summary
- Represents the very first execution phase of the kernel immediately after control is handed off by the bootloader
- Sets up the CPU execution mode (typically transitioning into 64-bit long mode if not already done)
- Establishes a temporary stack to allow safe function calls and early code execution
- Initializes descriptor tables (GDT/IDT) required for memory segmentation and interrupt handling
- Builds early page tables to enable virtual memory and basic address translation
- Performs the transition from physical addressing to virtual addressing space
- Jumps to the main kernel startup code (e.g., `startup_64` → `start_kernel`)
- Prepares the minimal low-level execution environment required before higher-level kernel initialization begins

---

## Relationships
- performs -> [1] CPU Mode Setup
- performs -> [2] Temporary Stack Setup
- performs -> [3] Descriptor Tables Setup
- performs -> [4] Early Page Tables Setup
- performs -> [5] Virtual Address Transition
- performs -> [6] Jump to Startup Code
