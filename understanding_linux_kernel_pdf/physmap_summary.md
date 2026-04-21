## 🧠 What “physmap” (direct map) is

> **Physmap** is a **linear (direct) virtual mapping of all physical RAM** into kernel space.

It gives the kernel a simple rule:

[
\text{virt} = \text{phys} + \text{PAGE_OFFSET}
]

So the kernel can access *any* RAM page with a fast, constant-time translation.

---

## 🧭 Where it sits (x86-64, typical)

![Image](https://images.openai.com/static-rsc-4/uKhCRH2L-PHV85jZwU52sqhR-VLH0zNSS1oWtRISQQ3EM4ekz2O9LYjmjOuhI9x5qZm757WzwHLVQbaZ4WMAn4SE10JPemc1ZQlo7JP3RmuwqmXvlFSqols8TRtM11E6PaDf5LwvWmi-sY1XAYESzzZN_Mu0EqWZm5AqDaKrtURNHOh0G2vLBdBc4pIWipa0?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/dxIBoyltvF4JIt-UXpbZm5dziFkQGZY-hYzHn813jtNiXm8FaqoWzFi-hMsONdPIsDBLwBoyQAc4GY6sH9GtznLE1raaZeSYDjcr81uHjXQmmCkcRa5qMhMeq5WaeNIiSfTfwtDMu2g6M6L1fz9NI_IyoZBmz4BgpcU5xGXBOa5QM_wj-EtwbxzNWDsTUuGZ?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/pLP4zKWx6yqHP6_gGKoHPbipCL5-2Z4LYR3UEvuS-_c69wrPoxZIHMKLvmdV07Pddcq567Hv9E2NjXyp-ZFvPjH71N2scQZI3SPrMwvjiTZOijKupV-KR6i6SNZmGAuv5wPNiS5zYkbFzWrT2VBCkcamby_wNImSA7zCHAWhAkPg3R6FEpWdtfU_2-50Nu5l?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/c6M38MTHpLz8vGb6vLU0V1QlGoG9Imm0KNVNqH_S4Oko5qF_wnBrEsas7dq-wsXMVpe2ayzH0-85Q6HCe6ntqhG4uXE71IONikucxOWAoNrHRztvWxHv2vqJMyqLKtXAZU1iiFsRqSWBP029vp6wDuR3mQEtLh9mExBp1qI7PZmkuoCT3Qo91S9KPbYSC5LI?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/U-v84jUB97zLGQdIWUZSvThf84Y9iVSkgtRvwa1D_kF5InWD5R8VlssA2k_wGFL9cmQ8nLT5tQVJNPa2I_d_NoVvfFpxrCkbktNqk_J_axpIcDG16XLc8wCNozhBFEokn7kX6KsDSzA_JnNxFSEbCQKq3Cy7zWqogWiJyQn3fNYTi9DSZ3trje0M8H9M8d9E?purpose=fullsize)

Typical range:

```text
ffff888000000000  ──► start of physmap (PAGE_OFFSET)
   ...              (linear mapping of all RAM)
```

> Exact base varies (KASLR), but the idea is consistent.

---

## 🔑 Key properties

### 1) **1:1 linear mapping (by offset)**

* Every physical page has a corresponding kernel virtual address
* No per-object mapping needed

### 2) **Covers *all* RAM**

* If the machine has 64 GB RAM → physmap spans 64 GB (virtually)

### 3) **Always present**

* Built during early boot and kept for the system’s lifetime

### 4) **Kernel-only**

* Not accessible from user mode

---

## ⚙️ How it’s built (boot time)

During early init:

1. Firmware/bootloader provides memory map (E820)
2. Kernel sets up page tables
3. Creates a **large-page mapping** for RAM:

   * often 2 MB or 1 GB pages

```text
physical RAM ───────────────► mapped into physmap
```

👉 Large pages = fewer TLB entries → faster

---

## 🧩 What lives in physmap

Not a “section” with code—rather a **view of RAM**. It includes:

* Page frames used by:

  * slab/slub allocators
  * page cache
  * kernel stacks
  * user pages (when accessed by kernel)
* Any physically allocated memory

---

## 🔄 Core helpers/macros

Kernel code frequently converts between phys/virt:

```c
void *v = phys_to_virt(phys_addr);
phys_addr_t p = virt_to_phys(v);
```

These work **because of physmap**.

---

## ⚡ Why physmap is critical

### Fast access

No need to:

* call `vmalloc`
* set up mappings
* manage page tables per allocation

---

### Simple memory model

Kernel can treat RAM like a big array:

```c
char *p = phys_to_virt(page_frame_addr);
p[0] = 42;
```

---

### Foundation for allocators

* **buddy allocator** hands out physical pages
* physmap lets kernel immediately use them via a virtual address

---

## 🧠 physmap vs vmalloc (important contrast)

| Feature             | physmap     | vmalloc                  |
| ------------------- | ----------- | ------------------------ |
| Mapping             | linear      | arbitrary                |
| Physical contiguity | required    | not required             |
| Speed               | fast        | slower                   |
| Use case            | general RAM | large fragmented regions |

---

## 🔍 Advanced details

### Huge pages

* physmap often uses:

  * 1 GB pages (if supported)
  * otherwise 2 MB pages
* reduces TLB pressure

---

### KASLR interaction

* physmap base may shift
* mapping remains linear

---

### KPTI (Meltdown mitigation)

* physmap may be **partially unmapped in user page tables**
* still fully present in kernel mode

---

### `struct page` relationship

Each physical page has metadata in **vmemmap**:

```text
phys page ↔ struct page (vmemmap)
         ↔ virtual mapping (physmap)
```

---

## 🧠 Mental model

Think:

```text
physmap = giant window where kernel sees all RAM laid out linearly
```

---

## ✅ Final takeaway

* Physmap is a **direct linear mapping of physical memory**
* Enables:

  * fast memory access
  * simple phys↔virt translation
* Backbone of:

  * memory allocators
  * page management
  * most kernel data access

---

## 🔥 One-line summary

> **Physmap is a high-performance linear mapping that lets the kernel treat all physical memory as directly addressable virtual memory.**

---

If you want, we can go deeper into:

* actual page table entries used for physmap
* how buddy allocator + physmap interact step-by-step
* or how NUMA affects physmap layout
