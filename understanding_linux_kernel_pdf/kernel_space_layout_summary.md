Here’s a **clean, ordered view of kernel virtual address space (x86-64)** from **lowest → highest addresses**.
I’ll keep it accurate to how Linux actually lays things out (with typical ranges; exact values vary due to KASLR/config).

---

# 🧭 Kernel virtual address space (ascending order)

![Image](https://images.openai.com/static-rsc-4/dxIBoyltvF4JIt-UXpbZm5dziFkQGZY-hYzHn813jtNiXm8FaqoWzFi-hMsONdPIsDBLwBoyQAc4GY6sH9GtznLE1raaZeSYDjcr81uHjXQmmCkcRa5qMhMeq5WaeNIiSfTfwtDMu2g6M6L1fz9NI_IyoZBmz4BgpcU5xGXBOa5QM_wj-EtwbxzNWDsTUuGZ?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/Hkf38jODw9N9rmtqMgE9kL3xjUcxNKBUhn5bccUM4XHOOJO2647gF8ttBBJb_TTn03dDUbWxkvHQ9TQ1ALyFWFwcs9jmc6sns1y0C1WdJH7zi64xI7HEr6yodjTfjJQo8dyxTZjODs6WwgbUIeuzE2JtkB7Qr5NGaeRZKxOAoSBjPUZMJbJESDBsErcoYIn7?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/uKhCRH2L-PHV85jZwU52sqhR-VLH0zNSS1oWtRISQQ3EM4ekz2O9LYjmjOuhI9x5qZm757WzwHLVQbaZ4WMAn4SE10JPemc1ZQlo7JP3RmuwqmXvlFSqols8TRtM11E6PaDf5LwvWmi-sY1XAYESzzZN_Mu0EqWZm5AqDaKrtURNHOh0G2vLBdBc4pIWipa0?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/cyuaUvFBWd_OO6wPeUrmjoVO-X_UOnxafGn82qF5qJ4Zn1JyBiqaFrT5NRnCqfzC2Tzj8d_hGIAT2j2miBApKTaqq_R_8n2mNYPrmHXTgEs-vZr88Lqtf6ISeb_scbH87XWL3_-b6PWsjRtanKYDoPeDInYMD-5sBKXvIVZ011QX6psYSpiECHFl1oCtvsPy?purpose=fullsize)

---

## 🟦 1. Kernel base (start of kernel space)

```text
ffff800000000000
```

* Boundary between user and kernel space
* Not heavily used directly

---

## 🟩 2. Direct map (physmap)

```text
ffff888000000000  → ~ffffc87fffffffff
```

* Linear mapping of **all physical RAM**
* Used constantly for:

  * memory access
  * allocators
  * page cache

---

## 🟨 3. vmemmap (struct page array)

```text
ffffea0000000000  → ...
```

* Array of `struct page`
* Metadata for every physical page

---

## 🟥 4. Per-CPU area

```text
fffffe0000000000  → ...
```

* CPU-local variables
* scheduler data
* interrupt state

---

## 🟪 5. vmalloc / vmap area

```text
ffffc90000000000  → ...
```

* Virtually contiguous allocations
* Non-contiguous physical memory
* Used for large buffers

---

## 🟫 6. Module area

```text
ffffffffa0000000  → ...
```

* Loadable kernel modules (`.ko`)
* Dynamic code/data

---

## 🟧 7. Kernel image (core kernel)

```text
ffffffff81000000  → ...
```

Sections:

* `.text` (code)
* `.rodata`
* `.data`
* `.bss`

---

## ⬛ 8. Fixmap area

```text
ffffffffffd00000  → ...
```

* Fixed virtual addresses
* APIC, IO mappings, early boot

---

## 🟦 9. CPU entry / trampoline area

```text
near top of address space
```

* syscall entry/exit
* interrupt entry
* KPTI trampolines

---

## 🟩 10. Top of virtual address space

```text
ffffffffffffffff
```

---

# ⚠️ Important notes

## 1. Order vs numeric values

Some regions (like kernel image vs modules) may appear “out of order” if you only look at prefixes.

👉 The list above is **true ascending order by address**.

---

## 2. KASLR shifts things

* kernel image base changes
* physmap base may shift
* relative layout stays consistent

---

## 3. Regions are huge

* physmap → tens of TB
* vmalloc → large sparse region
* vmemmap → proportional to RAM

---

# 🧠 Mental model

```text
low kernel addr
   ↓
[ physmap ]
[ vmemmap ]
[ per-CPU ]
[ vmalloc ]
[ modules ]
[ kernel image ]
[ fixmap / entry ]
   ↑
high kernel addr
```

---

# ✅ Final takeaway

Kernel virtual space is organized (low → high):

1. physmap (RAM mapping)
2. vmemmap (page metadata)
3. per-CPU area
4. vmalloc
5. modules
6. kernel image
7. fixmap / entry areas

Each region serves a **very specific purpose** in kernel operation.

---

# 🔥 One-line summary

> **Kernel virtual address space is a structured high-half layout, starting with direct RAM mapping (physmap) and progressing through metadata, dynamic mappings, modules, core kernel, and finally fixed and entry regions.**

---

If you want, I can:

* map your exact system layout from `/proc/kallsyms`
* show exact numeric ranges for your kernel config
* or explain how page tables map each region step-by-step
