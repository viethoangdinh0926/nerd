## 🧠 What the **Fixmap** area is

> The **Fixmap** is a small, special region of kernel virtual memory that provides **compile-time fixed virtual addresses** for critical mappings.

Unlike most kernel memory, these addresses are:

* **constant and known ahead of time**
* **manually mapped by the kernel**

---

# 🧭 Where it sits

![Image](https://images.openai.com/static-rsc-4/U-v84jUB97zLGQdIWUZSvThf84Y9iVSkgtRvwa1D_kF5InWD5R8VlssA2k_wGFL9cmQ8nLT5tQVJNPa2I_d_NoVvfFpxrCkbktNqk_J_axpIcDG16XLc8wCNozhBFEokn7kX6KsDSzA_JnNxFSEbCQKq3Cy7zWqogWiJyQn3fNYTi9DSZ3trje0M8H9M8d9E?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/dxIBoyltvF4JIt-UXpbZm5dziFkQGZY-hYzHn813jtNiXm8FaqoWzFi-hMsONdPIsDBLwBoyQAc4GY6sH9GtznLE1raaZeSYDjcr81uHjXQmmCkcRa5qMhMeq5WaeNIiSfTfwtDMu2g6M6L1fz9NI_IyoZBmz4BgpcU5xGXBOa5QM_wj-EtwbxzNWDsTUuGZ?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/uKhCRH2L-PHV85jZwU52sqhR-VLH0zNSS1oWtRISQQ3EM4ekz2O9LYjmjOuhI9x5qZm757WzwHLVQbaZ4WMAn4SE10JPemc1ZQlo7JP3RmuwqmXvlFSqols8TRtM11E6PaDf5LwvWmi-sY1XAYESzzZN_Mu0EqWZm5AqDaKrtURNHOh0G2vLBdBc4pIWipa0?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/IKo9NtdfpzLJhAqjHfxD5AkZeUf1M6Rexz66eUKGvzy1uHZxtrl5_3YRpmlPrz-K0ZNqhVA5ifXzWRERNg-oVO1S5ZvEITK9gLz9DsEzOpCTORfi86TLcrJllj5xCOMDYy-P896Nub1wNALtxq4EVMr9rGlDZH_wEJt2YdZpsLvMR3NygO7Fozs4O-jJP3dL?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/xp0OzY9xMdOpeoz0TJu4IF-wfOd2NvuSADp29wjKtv92EANg_Zw8qZnTmNA29yRlJfEEk-sHl6lnfgkJ77xGBJIbUQ3aZlu8le3HJ-FifCJoFwPo183DZBbyaVWgjAqJvio0FkKATc1gZ7dj_f0ZUhmkrsUVbV1y-NKiLSMNmS50Gm18vDrUlSlMTPua2OnH?purpose=fullsize)

Near the very top of kernel space:

```text id="fx0"
... high addresses
ffffffffffd00000  → Fixmap region
ffffffffffffffff  → top of VA space
```

---

# 🔑 Core idea

```text id="fx1"
fixed virtual address
        ↓
mapped to specific physical address
```

👉 No allocation, no lookup—just a **known mapping slot**

---

# ⚙️ How it works

The kernel defines an enum of fixed slots:

```c id="fx2"
enum fixed_addresses {
    FIX_APIC_BASE,
    FIX_IO_APIC_BASE_0,
    FIX_TEXT_POKE0,
    ...
    __end_of_fixed_addresses
};
```

Each entry corresponds to:

```text id="fx3"
virtual address = FIXADDR_TOP - (index * PAGE_SIZE)
```

---

## Mapping a fixmap entry

```c id="fx4"
set_fixmap(FIX_APIC_BASE, phys_addr);
```

This installs a page-table entry:

```text id="fx5"
fixed VA → chosen physical address
```

---

# 🧩 What fixmap is used for

## 🟦 1. APIC / hardware registers

```text id="fx6"
FIX_APIC_BASE → local APIC MMIO
```

* CPU interrupt controller
* must be at known address

---

## 🟩 2. IO APIC

* interrupt routing hardware

---

## 🟨 3. Early boot mappings

Before full memory management is ready:

* temporary mappings
* early page tables

---

## 🟥 4. kmap / temporary mappings (historically)

* mapping high memory pages (32-bit)
* replaced by `kmap_local_page` in modern kernels

---

## 🟪 5. Text patching / debugging

```text id="fx7"
FIX_TEXT_POKE0
```

* used to modify kernel code safely

---

## 🟫 6. CPU entry / special pages

* entry code
* trampoline pages

---

# ⚡ Why fixmap exists

## 🔑 1. Predictability

Kernel can hardcode:

```c id="fx8"
void *apic = (void *)FIX_APIC_BASE;
```

No lookup needed

---

## 🔑 2. Early boot support

Before:

* vmalloc
* slab
* full page tables

Fixmap still works

---

## 🔑 3. Low overhead

* no allocation structures
* no VMA
* direct page-table manipulation

---

# 🔄 Fixmap vs other regions

| Feature  | Fixmap           | vmalloc             | physmap    |
| -------- | ---------------- | ------------------- | ---------- |
| Address  | fixed            | dynamic             | linear     |
| Size     | small            | large               | huge       |
| Use case | special mappings | general allocations | RAM access |
| Setup    | manual           | allocator           | boot-time  |

---

# ⚠️ Important constraints

* Very **limited size**
* Must be used carefully
* Each slot has a **specific purpose**

---

# 🧠 Mental model

Think:

```text id="fx9"
fixmap = reserved labeled sockets
         where kernel can plug specific mappings
```

---

# 🔍 Example

Mapping APIC:

```text id="fx10"
virtual: ffffffff... (FIX_APIC_BASE)
    ↓
physical: APIC MMIO address
```

Kernel can always access APIC via same VA

---

# ✅ Final takeaway

* Fixmap provides **fixed virtual addresses**
* Used for:

  * hardware mappings
  * early boot
  * special kernel operations
* Implemented via:

  * predefined slots
  * direct page-table entries

---

# 🔥 One-line summary

> **Fixmap is a small, predefined kernel memory region that provides constant virtual addresses for critical low-level mappings like hardware registers and early boot structures.**

---

If you want, we can go deeper into:

* how `set_fixmap()` manipulates page tables
* exact fixmap address calculations
* or how fixmap interacts with KPTI and security features
