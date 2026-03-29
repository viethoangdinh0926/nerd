# Root Filesystem Strategy

## Type
concept

## Domain
systems

## Summary
- Determines how the system will obtain and mount its root filesystem during boot
- Selects initramfs as a temporary or minimal root environment when needed
- Selects disk-based root filesystem (e.g., local storage like SSD/HDD) for normal operation
- Selects network-based root (e.g., NFS) for diskless or remote-boot systems
- Decides the boot path based on configuration, kernel parameters, and available hardware
- Ensures the kernel can access a valid root filesystem to continue user-space startup
- Provides flexibility to support different deployment scenarios (embedded, cloud, diskless, etc.)

---

## Relationships
- selects -> [1] Initramfs
- selects -> [2] Disk Root
- selects -> [3] Network Root
