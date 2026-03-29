# Kernel Loading

## Summary
- Handles expanding the compressed kernel image into its executable form in memory during early boot
- Decompresses the kernel (e.g., from `vmlinuz`) into a usable in-memory image
- Relocates the kernel to its correct physical/virtual memory location if needed
- Fixes up page tables to reflect the final memory layout of the kernel
- Switches execution from the temporary decompression code to the fully decompressed kernel
- Ensures the kernel is correctly positioned and ready for normal initialization
- Marks the transition from boot-time compressed image handling to actual kernel execution

---

## Relationships
- performs -> [1] Kernel Decompression
- performs -> [2] Kernel Relocation
- performs -> [3] Page Table Fixup
- performs -> [4] Switch to Final Kernel Image
