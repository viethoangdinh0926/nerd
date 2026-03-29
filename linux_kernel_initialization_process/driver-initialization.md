# Driver Initialization

## Summary
- Initializes kernel drivers responsible for controlling and interacting with hardware devices
- Registers drivers with the kernel’s driver model so they can be associated with devices
- Matches drivers to discovered devices based on identifiers (e.g., PCI IDs, device tree compatibility)
- Probes devices by invoking driver-specific initialization routines
- Allocates and initializes device objects (e.g., `/dev` entries, kernel structures)
- Establishes communication paths between the kernel and hardware through drivers
- Ensures devices are fully operational and ready for use by the system and user-space processes

---

## Relationships
- performs -> [1] Driver Registration
- performs -> [2] Device Matching
- performs -> [3] Device Probing
- performs -> [4] Device Object Creation
