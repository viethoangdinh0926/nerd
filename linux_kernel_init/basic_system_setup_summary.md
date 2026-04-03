Below I’m using **“basic system setup”** to mean the **early slice of `start_kernel()` before the heavier subsystem bring-up** like the full memory manager, scheduler, and later init threads. On current mainline Linux, that slice begins with stack/CPU/IRQ sanity and runs through command-line handling, early arch setup, boot-CPU setup, early per-CPU/NUMA setup, early randomness/logging/VFS scaffolding, exception-table sorting, and `trap_init()`. ([GitHub][1])

## What this phase is trying to accomplish

At the start of `start_kernel()`, Linux has control of the CPU, but the machine is still in a fragile bootstrap state. The goal of this phase is to establish a **known-safe execution environment** for the boot CPU, import **bootloader/firmware facts** into kernel-owned structures, preserve and parse the command line, and prepare just enough core infrastructure that later initialization can proceed deterministically. Interrupts are kept disabled at the start specifically because the kernel is not ready to handle arbitrary asynchronous events yet. ([GitHub][1])

## The very first lines in `start_kernel()`

The function starts by calling `set_task_stack_end_magic(&init_task)`, `smp_setup_processor_id()`, `debug_objects_early_init()`, `init_vmlinux_build_id()`, and `cgroup_init_early()`, then explicitly disables local interrupts and marks `early_boot_irqs_disabled = true`. In plain English, that means:

`set_task_stack_end_magic(&init_task)` plants a sentinel at the end of the boot task’s stack so later stack-overflow checks have something to verify. `smp_setup_processor_id()` gives the architecture a chance to identify which logical CPU is currently executing. `debug_objects_early_init()` turns on the earliest possible state for the kernel’s object-lifetime debugging framework. `init_vmlinux_build_id()` records the running kernel image’s build identity early. `cgroup_init_early()` sets up the earliest cgroup scaffolding before the rest of process and resource-accounting code comes online. Then `local_irq_disable()` and `early_boot_irqs_disabled = true` make the contract explicit: boot is still running in a non-interruptible phase. ([GitHub][1])

## `boot_cpu_init()` and `page_address_init()`

Next the kernel runs `boot_cpu_init()` and `page_address_init()`, then prints the kernel banner. `boot_cpu_init()` marks the current processor as the boot CPU and establishes its early per-CPU role in the CPU masks/CPU-state bookkeeping. `page_address_init()` prepares the early helpers used to translate between `struct page` and its kernel virtual address representation in architectures/configurations that need that support. Printing `linux_banner` immediately after that is partly practical: once console output is usable enough, the kernel announces exactly what image is running. ([GitHub][1])

## The big architecture handoff: `setup_arch(&command_line)`

This is the single largest call in the “basic system setup” part. `start_kernel()` itself is architecture-neutral, but `setup_arch()` is where the architecture imports and normalizes the machine-specific boot state. On x86, the function is documented right in `arch/x86/kernel/setup.c` as the place for architecture-specific boot-time initialization. ([GitHub][2])

For **x86/x86_64**, `setup_arch()` does the work that turns bootloader/firmware information into kernel-owned early state. The current source shows, among other things:

* **early memory reservations happen before memblock ingestion**, so memblock won’t overwrite something the kernel still needs from firmware/bootloader; the source comment says this explicitly and then calls `early_reserve_memory()` before `e820__memory_setup()`. ([GitHub][2])
* The kernel then imports the firmware-provided **physical memory map** with `e820__memory_setup()`. That is the raw platform memory topology Linux will use for early memory decisions on x86. ([GitHub][2])
* `parse_setup_data()` walks extra bootloader-supplied setup-data records chained off `boot_params.hdr.setup_data`, pulling in optional auxiliary boot records. ([GitHub][2])
* `copy_edd()` copies BIOS EDD disk info from `boot_params` into a safe kernel-owned structure. The source comment says exactly that. ([GitHub][2])
* `setup_initial_init_mm(_text, _etext, _edata, (void *)_brk_end)` establishes the initial `init_mm` description for the kernel’s own address space boundaries. ([GitHub][2])
* `x86_configure_nx()` configures execute-disable support early, before later early-parameter work that may need safe fixed mappings. The source comment explains that ordering. ([GitHub][2])
* `parse_early_param()` is called from x86 `setup_arch()` as well, so truly early parameters can affect architecture setup. ([GitHub][2])
* For initrd handling, x86 has both `early_reserve_initrd()` and `reserve_initrd()`. The source shows the initrd image and size are taken from boot parameters, and the memory backing the ramdisk is reserved so early allocators do not trample it. ([GitHub][2])

Conceptually, `setup_arch()` is where Linux stops treating the machine as “a CPU that happened to jump here” and starts treating it as “a specific x86 platform with a boot protocol, memory map, firmware tables, optional initrd, and architecture-defined safety constraints.” ([GitHub][2])

## `mm_core_init_early()`

Back in `start_kernel()`, `mm_core_init_early()` runs immediately after `setup_arch()`. This is still not the full memory-management bring-up. It is an early memory-core preparation step that must happen before later pieces that allocate or depend on early MM internals. The ordering in `start_kernel()` makes that role clear: it appears before jump labels, static calls, command-line storage allocation, per-CPU area setup, and before the later heavier `mm_core_init()`. ([GitHub][1])

## `jump_label_init()`, `static_call_init()`, `early_security_init()`

The next trio is subtle but important. The source comment says “Static keys and static calls are needed by LSMs,” and then the kernel executes `jump_label_init()`, `static_call_init()`, and `early_security_init()` in that order. This means the kernel is bringing up the low-overhead runtime patching mechanisms first, because the early security framework may rely on them. In practical terms:

* `jump_label_init()` enables the infrastructure behind **static keys / static branches**, so the kernel can later patch conditional fast paths efficiently.
* `static_call_init()` enables the infrastructure behind **static calls**, which are another early-time code-patching optimization used for fast indirect dispatch.
* `early_security_init()` brings up the earliest security-module plumbing before broader subsystem initialization starts depending on security hooks. ([GitHub][1])

## Bootconfig and preserving the command line

Then come `setup_boot_config()` and `setup_command_line(command_line)`.

### `setup_boot_config()`

If bootconfig is enabled, the kernel tries to find bootconfig data first in the initrd and then in an embedded blob, parses it, and synthesizes extra command-line fragments for the `kernel.*` and `init.*` namespaces. The current source explicitly says it cuts bootconfig data out of the initrd, parses it, and generates `extra_command_line` and `extra_init_args`. ([GitHub][3])

### `setup_command_line()`

This function is easy to underestimate, but it is crucial. The source comment explains the need to keep both the **untouched command line** and a **mutable copy**, because parsing is done in place and some subsystems need stable references later. The function allocates `saved_command_line` and `static_command_line` with `memblock_alloc_or_panic()`, prepends any bootconfig-generated extra command line, and appends extra init args in the right place relative to `" -- "` if needed. In other words, this function turns the bootloader’s command line into durable kernel-owned state for both `/proc/cmdline`-style reporting and mutable parsing. ([GitHub][3])

## CPU-count, per-CPU areas, and the boot CPU’s local infrastructure

After the command line is stabilized, `start_kernel()` runs:

* `setup_nr_cpu_ids()`
* `setup_per_cpu_areas()`
* `smp_prepare_boot_cpu()`
* `early_numa_node_init()`
* `boot_cpu_hotplug_init()`

This cluster is about giving the boot CPU and the kernel’s global CPU model enough structure to continue safely.

`setup_nr_cpu_ids()` finalizes how many CPU IDs the kernel should consider valid. `setup_per_cpu_areas()` allocates and maps the per-CPU memory areas so each CPU can later have its own fast local storage. `smp_prepare_boot_cpu()` lets the architecture perform boot-CPU-specific SMP setup. `early_numa_node_init()` seeds per-CPU NUMA-node information from the architecture’s early CPU-to-node mapping; the source says exactly that under `CONFIG_USE_PERCPU_NUMA_NODE_ID`. `boot_cpu_hotplug_init()` initializes the boot CPU’s hotplug state bookkeeping. ([GitHub][1])

## Printing and parsing the kernel command line

Once that infrastructure exists, the kernel prints the preserved command line and begins parsing it more fully.

### `print_kernel_cmdline(saved_command_line)`

This prints the command line, with optional wrapping based on a Kconfig length knob. The current source comment explains the wrapping behavior and prefix formatting. ([GitHub][3])

### `parse_early_param()`

This is for parameters that must take effect very early. The implementation copies `boot_command_line` into a temporary buffer and parses it with `parse_args(..., do_early_param)`. `do_early_param()` walks the registered setup entries and runs handlers for parameters marked `early`. So this is the stage where things like early console or other “must happen before normal init” options get applied. ([GitHub][3])

### `parse_args("Booting kernel", static_command_line, ..., &unknown_bootoption)`

This is the broader parameter pass over the mutable command-line copy. Known kernel parameters are consumed; unknown options are handed to `unknown_bootoption()`, which either ignores well-known bootloader identifiers and obsolete/module-style options, or queues leftovers to be passed to userspace init. That is why Linux can warn, “Unknown kernel command line parameters … will be passed to user space.” ([GitHub][3])

### `parse_args("Setting init args", after_dashes, ...)` and extra init args

Anything after `" -- "` is treated as arguments for `/init` or the eventual init process, not as kernel options. Bootconfig-generated `init.*` arguments are parsed the same way afterward. This is how the kernel cleanly separates **kernel parameters** from **init/userspace parameters**. ([GitHub][1])

## Early randomness, early logging, and early VFS scaffolding

After parameter parsing, `start_kernel()` executes:

* `random_init_early(command_line)`
* `setup_log_buf(0)`
* `vfs_caches_init_early()`

`random_init_early(command_line)` performs architecture and non-timekeeping RNG initialization before allocator-heavy later phases. The source comment says exactly that. `setup_log_buf(0)` brings up the kernel log buffer early so printk traffic has a proper backing store. `vfs_caches_init_early()` initializes the earliest VFS caches before the full filesystem layer comes online. The source comment immediately before `setup_log_buf(0)` and `vfs_caches_init_early()` notes these use large bootmem allocations and therefore must happen before page-allocator initialization. ([GitHub][1])

## `sort_main_extable()`

This sorts the kernel’s built-in exception table so later fault-fixup lookups are efficient and correct. Exception tables are how the kernel says, “if this probe/copy/access faults here, recover by resuming there.” Sorting them early ensures later lookup helpers can binary-search or otherwise efficiently walk them. In `start_kernel()`, this happens before `trap_init()`, which is a sensible ordering: get the fixup metadata organized before expanding the exception/trap machinery. ([GitHub][1])

## `trap_init()`

This is the tail end of the “basic system setup” slice you asked about. `trap_init()` is an architecture hook; on x86 it initializes the core exception/trap handling structures such as the early IDT entries and exception handlers. `start_kernel()` calls it after the early command-line, logging, VFS, and exception-table work, but before the later scheduler/timer/RCU and full interrupt bring-up. In other words, the kernel is still not “fully interrupt-ready,” but it is making the synchronous CPU exception path real. ([GitHub][3])

## What “basic system setup” leaves true when it finishes

By the end of this slice, Linux has done these foundational things:

* verified the boot task’s stack sentinel and identified the boot CPU;
* forced interrupts to remain disabled while bootstrap is still fragile;
* imported architecture-specific boot state via `setup_arch()`, including the memory map and bootloader setup data on x86;
* preserved, printed, and parsed the kernel command line, including early params and init args;
* allocated per-CPU areas and seeded early NUMA/CPU topology state;
* initialized very early security, logging, VFS cache scaffolding, RNG seeding, exception-table organization, and early trap handling. ([GitHub][1])

What it has **not** done yet is equally important: the full allocator stack, full scheduler bring-up, timer/tick infrastructure, broader IRQ enablement, full device-driver initialization, and the eventual `rest_init()` transition to PID 1 and `kthreadd` all come later. ([GitHub][1])

If you want, I can do the next pass as a **line-by-line walkthrough of the current `start_kernel()` body**, stopping at each function call and explaining the invariants before and after it.

[1]: https://raw.githubusercontent.com/torvalds/linux/master/init/main.c "raw.githubusercontent.com"
[2]: https://github.com/torvalds/linux/blob/master/arch/x86/kernel/setup.c "linux/arch/x86/kernel/setup.c at master · torvalds/linux · GitHub"
[3]: https://github.com/torvalds/linux/blob/master/init/main.c "linux/init/main.c at master · torvalds/linux · GitHub"
