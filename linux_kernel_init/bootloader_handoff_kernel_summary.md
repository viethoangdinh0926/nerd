Let’s zoom in on that first phase carefully:

# 1. Bootloader hands control to kernel

This step is the transition from “firmware/bootloader world” into “kernel world.” It is not a single jump. It is a chain of smaller stages where each stage prepares just enough state for the next one.

On a modern x86_64 Linux system using GRUB, the flow is roughly:

```text
Power on
→ firmware (BIOS or UEFI)
→ bootloader
→ bootloader loads kernel + initramfs
→ bootloader passes boot parameters
→ bootloader transfers control to kernel entry code
→ kernel early assembly starts executing
```

Now let’s unpack that in detail.

---

# A. What exists before the kernel runs

Before Linux starts, the CPU is not “in Linux mode.” The machine begins in firmware-controlled execution.

## BIOS path

Older systems start in BIOS real mode:

* CPU begins in 16-bit real mode
* firmware initializes minimal hardware
* BIOS finds a boot device
* BIOS loads boot code from that device
* bootloader stages then continue from there

## UEFI path

Modern systems often use UEFI:

* firmware loads an EFI executable bootloader from the EFI System Partition
* bootloader runs in the UEFI environment
* bootloader gets richer firmware services and memory information

Linux supports both, but the important idea is the same:

**the bootloader is the last non-kernel program that prepares the machine and then jumps into the kernel image.**

---

# B. What the bootloader must do

The bootloader is responsible for turning files on disk into bytes in RAM and presenting the kernel with enough machine context to begin.

At a high level, it does five important things:

1. Find and load the kernel image
2. Optionally load initramfs/initrd
3. Gather and pass boot parameters
4. Put the CPU in the expected execution environment
5. Transfer control to the kernel entry point

Each of these has a lot inside it.

---

# C. Loading the kernel image

## 1. The kernel on disk is not just raw executable code

The Linux kernel file you usually boot is something like:

* `vmlinuz`
* `bzImage`

This is not just a flat binary dropped into memory and run directly as-is in the simplest sense. On x86, the bootable kernel image has a specific boot protocol structure that the bootloader understands.

For x86 Linux, the image contains:

* a boot header
* setup code
* protected-mode / 64-bit startup code
* compressed kernel payload
* metadata about loading

GRUB reads this image from the filesystem and places the relevant pieces into memory according to Linux’s x86 boot protocol.

## 2. Why the image is compressed

The real kernel image is large, so Linux stores it compressed. The bootloader usually loads the compressed kernel image into memory. Then Linux’s own decompressor stub later unpacks the real kernel into its final location in RAM.

So the very first code Linux executes is often:

* tiny setup code
* decompression logic
* then the real kernel startup path

That is why “load kernel” does not always mean “load final uncompressed kernel into its permanent memory position.”

---

# D. Loading initramfs / initrd

The bootloader may also load an initial RAM filesystem:

* initramfs
* historically initrd

This is a separate blob in memory, not part of the main kernel image.

## What it is for

It gives the kernel an early temporary root filesystem so early userspace can:

* load needed drivers
* assemble RAID
* unlock encrypted disks
* activate LVM
* mount the real root filesystem

Without this, the kernel would need every required storage and filesystem driver built in.

## What the bootloader does with it

The bootloader:

* reads the initramfs file from disk
* places it somewhere in RAM
* passes its address and size to the kernel through boot parameters

The kernel does not “discover” it magically. The bootloader explicitly tells the kernel where it is.

---

# E. Passing boot parameters

This is one of the most important jobs.

The kernel needs information about:

* command-line arguments
* available physical memory
* location of initramfs
* video/graphics mode info in some cases
* bootloader type and protocol details
* machine-specific boot data

This is passed through a boot data structure.

## 1. Kernel command line

The bootloader passes a string like:

```text
root=/dev/nvme0n1p2 ro quiet splash loglevel=3
```

This string controls kernel behavior very early. Examples:

* `root=...` tells Linux which device should become the real root filesystem
* `ro` means mount root read-only initially
* `console=...` selects console device
* `init=...` overrides the first userspace program
* `mem=...` can limit usable RAM
* `nokaslr`, `noapic`, `debug`, etc. change early boot behavior

The kernel parses parts of this very early, before most subsystems exist.

## 2. Memory map

The kernel needs to know which physical memory ranges are usable and which are reserved.

For x86 this commonly comes from:

* BIOS e820 map
* or UEFI memory map converted into Linux boot parameters

This map tells Linux things like:

* usable RAM ranges
* reserved firmware regions
* ACPI regions
* MMIO holes
* ROM / device reserved areas

Example conceptually:

```text
0x00000000 - 0x0009ffff  usable
0x000f0000 - 0x000fffff  reserved
0x00100000 - 0x7fffffff  usable
...
```

Linux cannot safely build page allocators until it knows this.

## 3. Boot parameter structure

On x86 Linux, bootloaders pass a structured block often centered around the `boot_params` layout defined by the Linux boot protocol.

This includes fields for:

* setup header info
* command line pointer
* initrd location and size
* memory map entries
* video info
* ACPI / EFI handoff details in some cases

So the kernel entry code is not starting from nothing. It receives a structured handoff package.

---

# F. Setting CPU state before jumping to the kernel

The kernel expects the CPU to be in a specific state when control is handed over. The bootloader must satisfy the Linux boot protocol requirements.

Exactly what is required depends on architecture and protocol stage, but conceptually the bootloader must ensure:

* interrupts are in a safe state
* control registers are set appropriately for handoff stage
* segment setup is sane
* memory containing boot parameters is accessible
* the CPU is in the expected execution mode for the entry point used

On x86_64, there are several conceptual layers here.

## 1. Real mode vs protected mode vs long mode

x86 CPUs have multiple execution modes.

### Real mode

The earliest x86 startup mode:

* 16-bit environment
* segmented addressing
* no paging
* extremely limited

### Protected mode

A more advanced mode:

* 32-bit protected execution
* descriptor tables and privilege model
* better addressing and control

### Long mode

64-bit x86 mode:

* 64-bit registers and addressing model
* paging required
* used by modern x86_64 kernels

The bootloader and kernel startup code cooperate to get from early machine state to full 64-bit kernel execution.

Depending on the exact handoff path:

* some early kernel setup code may still participate in the switch
* but by the time `startup_64` runs, the machine has entered the required 64-bit path

Your earlier summary said “bootloader sets CPU state: protected mode / long mode,” which is conceptually right, but in practice the transition may be shared between bootloader and kernel setup code depending on the boot protocol path. What matters is that the kernel entry code expects a defined state, not arbitrary firmware leftovers.

---

# G. How the kernel entry point is chosen

The bootloader does not just jump to a random byte in the kernel file. It follows the Linux boot protocol and jumps to the correct entry location.

For x86_64, this early path ultimately reaches code associated with:

* compressed kernel startup
* then later the real kernel startup assembly
* eventually `startup_64` in `arch/x86/kernel/head_64.S`

That symbol is part of the kernel’s early architecture-specific entry path after decompression / relocation stages are done.

So there are really multiple “entry points” in a broader sense:

* bootloader-visible boot entry
* decompressor/setup entry
* final early kernel 64-bit startup entry

When people say “GRUB jumps to `startup_64`,” they are simplifying the overall chain. The full story is:

* GRUB loads Linux according to the boot protocol
* control enters Linux early boot code
* decompression/relocation/setup occur as needed
* then the real kernel startup path reaches `startup_64`

---

# H. What happens conceptually at the moment of handoff

At the handoff instant, the bootloader has finished its job. Linux has not yet initialized itself. The machine is in a fragile transitional state.

The following are true or mostly true:

* the kernel image is somewhere in RAM
* the initramfs blob is in RAM if provided
* boot parameters are in RAM
* the CPU is set to the required handoff mode/state
* no Linux scheduler exists yet
* no Linux memory allocator is fully initialized yet
* no normal device drivers are active yet
* the kernel is about to begin self-initialization

So handoff means:

**“Here is the machine state and the boot data; Linux must now construct its own world from scratch.”**

---

# I. Why the memory map matters so much

This deserves special emphasis.

The kernel cannot safely use RAM unless it knows which regions are valid. If Linux guessed wrong, it could overwrite:

* firmware structures
* device MMIO windows
* reserved ACPI tables
* the initramfs
* the kernel image itself
* boot parameter structures

That is why the e820/UEFI memory map is foundational. Very early memory initialization depends on it.

Later, Linux uses this map to:

* mark reserved ranges
* build memblock structures
* initialize the buddy allocator
* set up page tables safely

So the bootloader is effectively giving Linux the first physical map of the world.

---

# J. What “basic memory map” means here

When we say “basic memory map,” that does not mean Linux already has full memory management running. It means Linux has enough firmware-reported physical memory layout information to begin building memory management.

Think of it like this:

* firmware/bootloader says: “these physical ranges exist; some are RAM, some are reserved”
* early Linux says: “okay, I will trust this enough to bootstrap my allocators”
* later Linux builds:

  * memblock data
  * page structures
  * zones
  * buddy allocator
  * full paging state

So the bootloader does not fully initialize Linux memory management. It passes the raw terrain map Linux needs.

---

# K. What “jumps to kernel entry point” literally means

At the CPU level, this is an actual control transfer:

* a jump or equivalent transfer of instruction pointer
* into the memory location where Linux startup code resides

After that instruction executes:

* the bootloader is no longer in control
* Linux code is executing on the CPU
* from this point on, any mistake is now the kernel’s problem

This is the boundary between:

* pre-kernel boot environment
* kernel-owned initialization

That boundary is sharp.

---

# L. What the kernel assumes at handoff

The early Linux entry code assumes:

* boot parameters are valid and where expected
* the kernel image is correctly loaded
* the CPU mode/protocol requirements were obeyed
* required registers/state are set correctly
* the stack / segment / paging preconditions required by that entry stage are satisfied

If the bootloader violates the protocol, Linux may:

* hang immediately
* print nothing
* triple fault and reset
* crash much later in confusing ways

That is why the Linux boot protocol is strict.

---

# M. What `startup_64` is about

By the time execution reaches `startup_64`, Linux is in its early architecture-specific kernel setup phase.

This code is responsible for things like:

* establishing early page table usage for the kernel
* switching into the kernel’s own virtual address environment
* setting up very early execution context
* preparing to enter C code later

So `startup_64` is not “Linux fully running.” It is “Linux now begins constructing the environment it needs to become fully running.”

The bootloader gets Linux to the door. `startup_64` walks through it.

---

# N. A more precise end-to-end micro-sequence

Here is the phase as a tighter ordered sequence:

## 1. Firmware chooses boot path

BIOS or UEFI transfers control to the bootloader.

## 2. Bootloader reads configuration

GRUB reads menu entries and boot config.

## 3. Bootloader loads kernel image from disk into RAM

Usually a Linux x86 bootable compressed image.

## 4. Bootloader loads initramfs into RAM

Optional but common.

## 5. Bootloader builds boot parameter data

Includes command line, memory map, initramfs location, and protocol info.

## 6. Bootloader prepares CPU/handoff state

Enough for Linux boot protocol expectations.

## 7. Bootloader transfers control into Linux early startup code

Linux begins executing.

## 8. Linux early setup/decompressor runs

If compressed image path applies.

## 9. Linux reaches architecture-specific early kernel startup

Eventually into `startup_64`.

---

# O. Common misconception

A very common misunderstanding is:

“GRUB loads the kernel and then Linux is basically running.”

Not really.

After GRUB hands off, Linux still must do enormous amounts of setup:

* its own page tables
* memory allocators
* CPU feature setup
* IDT/GDT refinements
* scheduler structures
* interrupt initialization
* VFS
* driver framework
* init process launch

So the bootloader handoff is only the start of Linux’s self-construction.

---

# P. Mental model

A good mental model is:

* **Firmware** wakes up the machine
* **Bootloader** loads files and passes machine facts
* **Kernel early assembly** creates minimal safe execution state
* **Kernel C initialization** builds the operating system

So in this specific first step, the bootloader is acting like a launch platform:
it loads the payload, provides coordinates, sets initial conditions, and ignites the first stage.

---

# Q. Condensed technical summary

In great-detail-but-short form:

The bootloader locates the Linux kernel image on disk, loads it into RAM according to the Linux x86 boot protocol, optionally loads initramfs into RAM, gathers the kernel command line and system memory map, packages that boot information into boot parameter structures, prepares the CPU into the required handoff state, and transfers control into Linux’s early startup code. Linux then uses that bootloader-provided context to decompress itself if needed, establish its own early memory and paging environment, and eventually reach `startup_64` in `arch/x86/kernel/head_64.S`.

If you want, next I can break this same step down into:

* **exactly what GRUB does internally**
  or
* **what the kernel image format/boot protocol fields look like**
  or
* **the precise path from GRUB handoff to `startup_64` step by step**
