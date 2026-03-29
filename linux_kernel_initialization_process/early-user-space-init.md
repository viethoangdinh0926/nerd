# Early User Space (/init)

## Type
concept

## Domain
systems

## Summary
- Represents the first user-space program (`/init`) executed from initramfs after the kernel finishes early initialization
- Loads necessary kernel modules required for accessing hardware and storage devices
- Discovers available storage devices (disks, partitions, etc.) needed for the root filesystem
- Sets up complex storage configurations such as LVM or RAID if present
- Mounts the real root filesystem that will replace the temporary initramfs environment
- Prepares the system for transition from initramfs to the actual root filesystem (`switch_root`/`pivot_root`)
- Bridges the gap between kernel initialization and the full user-space environment
- Hands off control to the main init system (e.g., `systemd`) after root filesystem is ready

---

## Relationships
- performs -> [1] Module Loading
- performs -> [2] Storage Discovery
- performs -> [3] Volume Setup (LVM/RAID)
- performs -> [4] Root Filesystem Mount
