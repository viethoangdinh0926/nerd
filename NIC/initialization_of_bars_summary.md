Great question — this gets into the **core PCIe enumeration + resource allocation protocol** between hardware, firmware, and the OS.

Short answer:

👉 The kernel and NIC do **not “negotiate” dynamically**  
👉 The **kernel (or firmware) unilaterally assigns BAR addresses**, and the NIC just accepts them

Now let’s go step‑by‑step so it’s crystal clear.

***

# ✅ 1. What the NIC exposes initially

When a NIC powers on:

* Its PCIe config space contains **BAR registers**
* But each BAR initially contains **no valid address**

Instead, BARs are in a **“size discovery mode”**

***

# ✅ 2. How the kernel discovers BAR size

The kernel (or BIOS/UEFI before it) uses a standard PCI procedure:

### 🔍 Size probing algorithm

For each BAR:

```text
1. Save original BAR value
2. Write 0xFFFFFFFF to BAR
3. Read it back
4. Mask bits → determine required size
5. Restore original value
```

Why this works:

* The device **hard-wires certain bits to 0**
* That reveals the size of the required memory region

Example:

```
Read back: 0xFFFF0000
→ Size = 64 KB
```

***

# ✅ 3. Who decides the actual address?

👉 The **kernel (or firmware)** decides

It:

1. Collects all devices' BAR size requirements

2. Allocates ranges in:
   * Physical memory space (MMIO)
   * Or I/O port space (rare)

3. Ensures:
   * No overlap
   * Alignment requirements satisfied

***

# ✅ 4. Programming the NIC’s BAR

Once the kernel decides:

```text
"NIC BAR0 should live at 0xF7200000"
```

It writes directly into the device:

```text
PCI config write → BAR0 = 0xF7200000
```

This happens over PCIe config transactions.

***

# ✅ 5. What the NIC does with that

After the write:

👉 The NIC internally configures:

```
"If host accesses address 0xF7200000 → route to my register block"
```

No negotiation — just configuration.

***

# ✅ 6. How communication actually works afterward

When the driver writes:

```c
writel(value, mapped_addr + offset);
```

It becomes:

```
CPU issues memory write → 0xF7200000 + offset
→ PCIe transaction (Memory Write TLP)
→ NIC receives it
→ Decodes address offset
→ Updates register
```

***

# ✅ 7. Important: this is standardized

This works because PCIe defines:

* Configuration space format
* BAR behavior
* Address decoding rules

So:

✅ Any OS can configure any compliant NIC  
✅ Any NIC must obey the BAR programming model

***

# ✅ 8. Role of BIOS/UEFI vs Linux kernel

Two possibilities:

### 🟢 Firmware does it (common on PCs)

* BIOS assigns BARs during boot
* Linux just reuses or adjusts them

### 🔵 Kernel does it

* Happens if:
  * `pci=realloc` is used
  * Hotplug devices
  * Resource conflicts

***

# ✅ 9. No "agreement protocol"

This is key:

There is **no back-and-forth negotiation** like:

❌ "NIC, do you agree with this address?"

Instead:

✅ Kernel writes → NIC must accept

The only "input" the NIC gives is:

* BAR size (via probing)
* BAR type (memory vs I/O, 32 vs 64 bit)

***

# ✅ 10. Visual flow

```
[ NIC powers on ]
    ↓
BAR = unassigned

[ Kernel probes ]
    ↓
"Needs 128KB MMIO"

[ Kernel allocates ]
    ↓
0xF7200000 chosen

[ Kernel writes BAR ]
    ↓
NIC registers mapped there

[ Runtime ]
CPU → memory access → PCIe → NIC
```

***

# 🧠 Deep insight

BARs are essentially:

> "Windows into the device’s internal register space"

The kernel chooses where that window appears in the system’s address map.

***

# ✅ 11. Extra: what if kernel assigns wrong address?

If something goes wrong:

* Device won’t respond correctly
* Driver fails to initialize
* Kernel logs errors:

```bash
dmesg | grep pci
```

***

# 🚀 Final mental model

Think of it like this:

* NIC says: **"I need 128KB window"**
* Kernel says: **"You get 0xF7200000"**
* NIC says: **"Cool, I'll listen there now"**

No negotiation — just **standardized configuration + compliance**.

***

If you want to go even deeper, I can walk you through:

* actual PCI config space layout
* how MSI-X tables are mapped via BARs
* or a real Linux `pci_enable_device()` flow

Just say 👍
