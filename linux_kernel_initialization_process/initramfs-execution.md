# Initramfs Execution

## Summary
- Executes the initramfs environment immediately after the kernel completes core initialization
- Unpacks the initramfs archive into a temporary in-memory filesystem
- Mounts this temporary root filesystem to provide an initial user-space environment
- Executes the `/init` program, which becomes the first user-space process
- Provides essential tools and scripts needed for early system setup (e.g., drivers, storage handling)
- Enables the system to prepare and locate the real root filesystem
- Acts as a bridge between kernel initialization and full user-space startup

---

## Relationships
- performs -> [1] Initramfs Unpack
- performs -> [2] Root Filesystem Mount (temporary)
- performs -> [3] Execute /init
