# Device Discovery

## Type
concept

## Domain
systems

## Summary
- Discovers and identifies hardware devices present on the system during early kernel initialization
- Parses firmware-provided data (ACPI tables or Device Tree) to understand system topology and available devices
- Performs PCI enumeration to detect and configure devices on the PCI/PCIe bus
- Registers platform devices that are not discoverable via standard buses (e.g., embedded or SoC components)
- Builds an internal representation of hardware for the kernel’s driver model
- Prepares the system so appropriate drivers can be matched and initialized for each device
- Establishes the foundation for full hardware interaction and driver binding later in the boot process


---

## Relationships
- performs -> [1] ACPI/Device Tree Parsing
- performs -> [2] PCI Enumeration
- performs -> [3] Platform Device Registration
