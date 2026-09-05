When people say “kernel image area,” they mean the memory that comes directly from the **compiled kernel binary** (e.g., `vmlinux`) and is laid out into sections like `.text`, `.rodata`, `.data`, `.bss`, plus a few special sections.

> **Only static, compile-time objects live here. Anything dynamically allocated at runtime does *not* live in the kernel image.**

Let’s break it down precisely.

---

# 🧠 1. What “kernel image area” really contains

The kernel image is an ELF binary mapped into memory with sections:

```text
.text     → executable code
.rodata   → read-only data
.data     → initialized globals
.bss      → zero-initialized globals
.init     → init-only (freed later)
```

👉 Data structures live mostly in **.data, .bss, .rodata**

---

# 🧭 2. Categories of data structures in kernel image

## 🟦 A. Core global kernel objects

These represent the “root” of major subsystems.

### Examples

* initial process:

  ```c
  struct task_struct init_task;
  ```
* initial memory descriptor:

  ```c
  struct mm_struct init_mm;
  ```
* initial namespaces, creds, etc.

👉 These are **bootstrap objects**—everything else grows from them.

---

## 🟩 B. System-wide descriptor tables

Low-level CPU structures:

* GDT (Global Descriptor Table)
* IDT (Interrupt Descriptor Table)
* TSS templates (per-CPU copies later)

These are defined statically and later replicated or relocated.

---

## 🟨 C. Syscall and interrupt tables

### Examples

```c
sys_call_table[]
```

* maps syscall number → handler

```c
idt_table[]
```

* maps interrupt vector → entry stub

---

## 🟥 D. Static configuration tables

* CPU feature tables
* architecture-specific constants
* device IDs and lookup tables

Often in `.rodata`

---

## 🟪 E. Scheduler global structures (templates)

* scheduler class structures:

```c
struct sched_class fair_sched_class;
struct sched_class rt_sched_class;
```

* default runqueue templates (actual per-CPU copies live elsewhere)

---

## 🟫 F. Filesystem and VFS globals

* superblock type tables
* filesystem registration structures

```c
struct file_system_type ext4_fs_type;
```

---

## 🟧 G. Networking protocol tables

* protocol handlers:

```c
struct proto tcp_prot;
struct net_protocol ip_protocol;
```

* dispatch tables for packet handling

---

## ⬛ H. Kernel symbol tables

* used for debugging:

```text
kallsyms
```

* maps addresses → symbol names

---

## 🟦 I. Static locks and synchronization primitives

* global spinlocks
* mutex initializers

```c
DEFINE_SPINLOCK(global_lock);
```

---

## 🟩 J. Static caches and allocators (definitions)

* slab cache descriptors (not the memory they manage)

```c
struct kmem_cache *task_struct_cachep;
```

---

## 🟨 K. Init-only structures (`.init`)

* early boot data
* setup tables

👉 Freed after boot

---

# ⚙️ 3. What does NOT live in kernel image

Important contrast:

| Structure                      | Where it lives    |
| ------------------------------ | ----------------- |
| `task_struct` (most processes) | physmap (kmalloc) |
| page tables (runtime)          | physmap           |
| `sk_buff`                      | physmap           |
| page cache                     | physmap           |
| large buffers                  | vmalloc           |

👉 Only **initial or template instances** live in kernel image

---

# 🧠 4. Why these live in kernel image

Because they are:

* known at **compile time**
* needed **immediately at boot**
* often **singletons or templates**

---

# 🔍 5. Example: process system

```text
init_task (kernel image)
   ↓ fork/clone
new task_struct (kmalloc → physmap)
```

👉 kernel image holds the **first instance**, not the rest

---

# 🔍 6. Example: syscall handling

```text
sys_call_table (kernel image)
   ↓
dispatch → sys_read / sys_write
```

👉 table is static, handlers are code in `.text`

---

# 🧠 7. Mental model

```text
kernel image =
  "blueprints + root objects + static tables"

runtime memory (physmap/vmalloc) =
  "actual working data"
```

---

# ⚡ 8. Key insight

> **Kernel image holds “definitions and anchors,” not the bulk of runtime data.**

---

# ✅ Final takeaway

Data structures in kernel image include:

* core bootstrap objects (`init_task`, `init_mm`)
* syscall and interrupt tables
* protocol and filesystem registration structures
* scheduler class definitions
* global locks and configuration tables
* debugging symbol tables

👉 They are:

* static
* global
* foundational

---

# 🔥 One-line summary

> **The kernel image area contains static, compile-time data structures such as core system objects, dispatch tables, protocol definitions, and global configuration—serving as the foundation from which dynamic runtime structures are created elsewhere.**

---

If you want, we can go deeper into:

* exact layout of `init_task` and how it seeds all processes
* how `sys_call_table` is built and used at runtime
* or how kernel image sections map to page table permissions (RO, NX, etc.)
