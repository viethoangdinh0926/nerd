# Initramfs

## Summary {but provide as much detail as possible}
Temporary in-memory root filesystem used during early Linux boot to prepare the system before the real root filesystem is available
- Loaded by the bootloader together with the kernel into RAM and passed via boot parameters (address and size)
- Stored as a compressed cpio archive that the kernel decompresses during early initialization
- Extracted into a RAM-backed filesystem (ramfs/tmpfs) and mounted as the temporary root (`/`)
- Executes `/init` as the first user-space process, responsible for early system setup
- Loads kernel modules required for hardware access (e.g., storage controllers, filesystems)
- Discovers storage devices and prepares complex setups such as LVM, RAID, and encrypted volumes
- Locates and mounts the real root filesystem based on system configuration
- Transitions from initramfs to the real root filesystem using `switch_root` or `pivot_root`
- Provides flexibility by allowing a minimal kernel with modular driver loading instead of requiring all drivers to be built-in
- Acts as a bridge between kernel initialization and full user-space startup

---

## Relationships
- performs -> [1] Initramfs Unpack
- performs -> [2] Temporary Root Filesystem Mount
- executes -> [3] /init
- performs -> [4] Kernel Module Loading
- performs -> [5] Storage Discovery
- performs -> [6] Root Filesystem Mount
- performs -> [7] Root Filesystem Switch
