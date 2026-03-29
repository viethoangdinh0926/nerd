# Memory Management Initialization

## Summary
- Initializes the kernel’s full memory management system after early boot setup
- Discovers available physical memory using firmware-provided information (e.g., BIOS/UEFI memory map)
- Reserves critical memory regions (kernel image, initramfs, hardware-reserved areas)
- Sets up the page allocator to manage allocation and freeing of physical memory pages
- Initializes memory zones (e.g., DMA, Normal, HighMem) for different hardware and allocation needs
- Configures slab/SLUB allocators for efficient management of small kernel objects
- Finalizes virtual memory structures and mappings for stable kernel operation
- Enables dynamic memory allocation for both kernel subsystems and user-space processes

---

## Relationships
- performs -> [1] Physical Memory Discovery
- performs -> [2] Memory Reservation
- performs -> [3] Page Allocator Setup
- performs -> [4] Zone Initialization
- performs -> [5] Slab/SLUB Setup
- performs -> [6] Virtual Memory Finalization
