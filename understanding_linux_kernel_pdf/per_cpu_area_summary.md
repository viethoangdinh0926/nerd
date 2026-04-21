## 🧠 What the **per-CPU area** is

> The **per-CPU area** is a region of kernel virtual memory that gives **each CPU its own private copy of certain variables**.

Instead of sharing one variable across all CPUs (and locking it), the kernel keeps **N copies (one per CPU)**.

---

# 🧭 Where it lives

![Image](https://images.openai.com/static-rsc-4/MAZxMaABQaCc4ZCaeH0Iiz2adQrheteUIWm0X2O1q0_XZOXY_eOvXEDowtStadRoy33tBPfnpOyzz0CMl1S9FPKJv-UiYy6KqunrEnA_XoqI6dfuWv1YsjYu9PGBZ6vi-QMlH2B8S86vjbYZTPfC3V5zqs9IajK-2kNNqGxmJ0VAoHI8P5BurE67pEUCGI2l?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/pLP4zKWx6yqHP6_gGKoHPbipCL5-2Z4LYR3UEvuS-_c69wrPoxZIHMKLvmdV07Pddcq567Hv9E2NjXyp-ZFvPjH71N2scQZI3SPrMwvjiTZOijKupV-KR6i6SNZmGAuv5wPNiS5zYkbFzWrT2VBCkcamby_wNImSA7zCHAWhAkPg3R6FEpWdtfU_2-50Nu5l?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/NJg-DjrjnHlQGjNV1d-FXBE9VLvgQF0aPScR1zux4EzrIaVCfxbPDPK9d-SgBlMwWH6D1lYzV-EmVmHFfYJ7CVyasK93dQzucQMQ43VlyaGmRXCvnNbX6g_VbVlii7SUgOD4d7A8JqfvnFCZwC34jExRjFJmdKmDSnwKQMrLhPJhdSLnC79F5hiXjTZstGVD?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/F-Jhcf2PUpSYiQkFxjakNf0OSTK8N24WLZPlIqqnSTMBzB72ENYcyaZqOV6dXDX9yneAp0iF3bQfBljtFjapby9c6TKg5ggl_SxZVgq-gez55Fxkj_ZSyunYRtNKlUjoFSxdhq5YeJFs2eHb5y3IpATSwXdX6oFQl1_RGCiFtPvy1jXW7LZWXq2vBbGrYC1-?purpose=fullsize)

Conceptually:

```text id="pc0"
Kernel space
  ├── kernel image
  ├── physmap
  ├── vmalloc
  ├── modules
  └── per-CPU area   ← here
```

👉 Each CPU sees:

* same virtual address
* but mapped to **different physical memory**

---

# 🔑 Core idea (very important)

```text id="pc1"
same virtual address
        ↓
CPU 0 → memory A
CPU 1 → memory B
CPU 2 → memory C
```

👉 This is achieved via:

* **different page table mappings per CPU**
* or segment-base tricks (GS base on x86)

---

# ⚙️ How it’s defined

Kernel macro:

```c id="pc2"
DEFINE_PER_CPU(int, cpu_counter);
```

---

Access:

```c id="pc3"
this_cpu_inc(cpu_counter);     // fast, no locking
int val = per_cpu(cpu_counter, cpu_id);
```

---

# 🧩 What lives in per-CPU area

## 🟦 Scheduler data

* runqueues (`rq`)
* load tracking
* scheduling stats

---

## 🟩 Interrupt data

* IRQ counters
* softirq state

---

## 🟨 Kernel stacks (some architectures)

* interrupt stacks
* NMI stacks

---

## 🟥 CPU-local variables

* current task pointer
* preemption counters

---

## 🟪 Networking / subsystems

* per-CPU caches
* per-CPU buffers

---

# ⚡ Why per-CPU area exists

## 🚫 Without it

Shared variable:

```c id="pc4"
global_counter++;
```

Problem:

* requires locks
* cache contention
* slow on multi-core

---

## ✅ With per-CPU

```c id="pc5"
this_cpu_inc(counter);
```

Benefits:

* no locks
* no cache bouncing
* extremely fast

---

# 🔄 How access works (x86 example)

On x86:

* GS register points to per-CPU base:

```text id="pc6"
GS base → per-CPU region
```

Access becomes:

```text id="pc7"
mov %gs:offset → CPU-local variable
```

👉 No lookup, no overhead

---

# 🧠 Memory mapping trick

Even though code uses:

```c id="pc8"
this_cpu_var
```

Under the hood:

```text id="pc9"
virtual address + per-CPU offset
```

---

# ⚙️ Allocation model

## Static per-CPU

Defined at compile time:

```c id="pc10"
DEFINE_PER_CPU(...)
```

---

## Dynamic per-CPU

Allocated at runtime:

```c id="pc11"
alloc_percpu(type)
```

---

# ⚠️ Important constraints

* Cannot freely share between CPUs
* Must use APIs:

  * `get_cpu()`
  * `this_cpu_ptr()`

---

# 🧠 NUMA awareness

Per-CPU areas are:

* often allocated close to each CPU’s NUMA node
* improves locality

---

# 🔍 Example (scheduler)

Each CPU has its own:

```text id="pc12"
runqueue
  → list of runnable tasks
```

👉 No global scheduler lock needed

---

# ⚖️ Per-CPU vs global memory

| Feature          | Per-CPU     | Global |
| ---------------- | ----------- | ------ |
| Copies           | one per CPU | one    |
| Locking          | not needed  | needed |
| Cache contention | low         | high   |
| Access speed     | very fast   | slower |

---

# 🧠 Mental model

Think:

```text id="pc13"
per-CPU area =
  each CPU has its own private workspace
```

---

# 🔐 Security / isolation

* Not visible to user space
* Protected by kernel mode
* Different mapping per CPU

---

# ✅ Final takeaway

* Per-CPU area provides **CPU-local storage**
* Eliminates:

  * locking
  * contention
* Used heavily in:

  * scheduler
  * interrupts
  * performance-critical paths

---

# 🔥 One-line summary

> **The per-CPU area is a kernel memory region that gives each CPU its own private copy of variables, enabling lock-free, high-performance operations on multi-core systems.**

---

If you want, we can go deeper into:

* how GS base is set during context switch
* how per-CPU offsets are calculated
* or how Linux implements `this_cpu_*` macros at assembly level
