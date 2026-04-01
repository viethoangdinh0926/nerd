# Boot Parameter Setup

## Summary
Boot parameters are prepared by firmware and the bootloader, then passed to the Linux kernel at startup to describe the system environment. These parameters include the kernel command line, memory map, and hardware information.

The process begins with firmware (BIOS or UEFI), which performs hardware initialization and may collect basic system information. Control is then transferred to the bootloader (e.g., GRUB or systemd-boot), which is responsible for loading the kernel image and preparing boot parameters.

The bootloader constructs the kernel command line, a string of configuration options (e.g., root filesystem, debug flags), and places it in memory. It also gathers or forwards the memory map, which describes usable and reserved physical memory regions. In BIOS systems, this is typically obtained via the E820 interface, while in UEFI systems it is retrieved from UEFI firmware services.

Hardware and platform information are packaged differently depending on architecture:
- On x86 systems, the bootloader fills a `boot_params` structure (defined in the kernel) that includes memory maps, command line pointers, and other metadata.
- On ARM and other architectures, hardware description is typically provided via a Device Tree blob (DTB), which the bootloader loads into memory and passes to the kernel.

The bootloader then transfers control to the kernel entry point, passing pointers (via registers) to these data structures. For example, on x86_64, a pointer to the `boot_params` structure is passed in a register during early startup (`head_64.S`). The kernel parses these inputs during early initialization to configure memory management, device drivers, and system behavior.

---

## Relationships
- prepares -> [1] Firmware initializes hardware and provides initial system data
- loads -> [2] Bootloader loads kernel image into memory
- constructs -> [3] Kernel command line string with boot options
- provides -> [4] Memory map (e.g., E820 or UEFI memory descriptors)
- packages -> [5] Hardware info via boot_params or Device Tree
- passes -> [6] Bootloader passes pointers to kernel entry via registers
- initializes -> [7] Kernel parses parameters during early boot to configure system
