## 🧠 What the **CPU entry / trampoline area** is

> A **small, specially mapped region at the very top of kernel virtual space** that contains the **entry/exit code paths** the CPU uses to transition between **user mode ↔ kernel mode** safely and quickly.

It’s called a **“trampoline”** because execution *lands there first*, then “jumps” into the full kernel.

---

## 🧭 Where it sits

![Image](https://images.openai.com/static-rsc-4/5lNJRdUckEMbNrDItKwg3DZEIQr60FD_SibwH6MHHmDlj726SgpF8cBz2yvBMosTDBHwzpG1LpM2cHmWKen6AKHSlrczYLtAHyp7cjy2Wd2acBS6cvmj2tRAvU7sXQ0u9b1NYGhLQLqDsMyX98d_3lrELfjR6EHi8tjq0tXU-hm2E9L0hutW77W0nyv8qAD7?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/U-v84jUB97zLGQdIWUZSvThf84Y9iVSkgtRvwa1D_kF5InWD5R8VlssA2k_wGFL9cmQ8nLT5tQVJNPa2I_d_NoVvfFpxrCkbktNqk_J_axpIcDG16XLc8wCNozhBFEokn7kX6KsDSzA_JnNxFSEbCQKq3Cy7zWqogWiJyQn3fNYTi9DSZ3trje0M8H9M8d9E?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/NoGIw-XDHZQTciXUDlyWOhXNrE4gKF_dlzOqlVot38U4AKVKd5mF9YOtsvY2cQbe6EPjXw5wVFO6LIX0i_IgtbfVZQ7j2pt97LXbExkId3-pmpWVyPiZf8XHk5SeAw_SXASFMCdXflev7fcEUdj15uzBMj8JdIYwmy3FpgSRVEEOv0lrARgnbnqKjZLF7Qf7?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/dxIBoyltvF4JIt-UXpbZm5dziFkQGZY-hYzHn813jtNiXm8FaqoWzFi-hMsONdPIsDBLwBoyQAc4GY6sH9GtznLE1raaZeSYDjcr81uHjXQmmCkcRa5qMhMeq5WaeNIiSfTfwtDMu2g6M6L1fz9NI_IyoZBmz4BgpcU5xGXBOa5QM_wj-EtwbxzNWDsTUuGZ?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/0TRLFs0IENwlGxDShzE0cwZhgKkC1vtN8S3XtSOB9VIhUZbnqi07Ylov9xFLz--J7KH3wcKp2doMbcyefBtU3QITidr4FR4pbpnN-aDmcWz-6VgkPbLC1vYsHQOWYeWDEXD23PrBChg78Y7LKn-FKaJ-aW1P0O3q0L31WBDNbysXzgcgOfpdw19DMLgGVL8b?purpose=fullsize)

Near the very top:

```text
... higher addresses
ffffffffffd00000  → Fixmap
ffffffffffe00000  → CPU entry / trampoline area   ← here
ffffffffffffffff  → top of VA space
```

> Exact addresses vary (KASLR/config), but it’s always **high, small, and special**.

---

## 🔑 Why it exists

### 1) **Safe entry from user mode (KPTI)**

With **KPTI (Kernel Page Table Isolation)**:

* User-mode page tables **do not map the full kernel**
* But the CPU still needs *some* code to enter the kernel

👉 The trampoline area is:

* **mapped in both user and kernel page tables (minimal!)**
* contains just enough code to:

  1. switch to the full kernel page table
  2. continue into the real kernel entry path

---

### 2) **Controlled, minimal surface**

* Only a **tiny amount of code/data** is exposed
* Reduces attack surface (Meltdown-class mitigations)

---

## ⚙️ What’s inside

### 🟦 Entry stubs

* System call entry (e.g., `SYSCALL` on x86-64)
* Interrupt/exception entry stubs

### 🟩 Trampoline code

* Switch CR3 (page table) from **user → kernel**
* Set up a safe stack
* Jump to full kernel entry (e.g., `entry_SYSCALL_64`)

### 🟨 Exit stubs

* Return path back to user mode
* Restore user registers/state
* Switch back to user page tables

### 🟥 Per-CPU entry data (small)

* Scratch space for transitions
* Pointers needed during entry

---

## 🔄 How it’s used (syscall path)

### Step-by-step

```text
User mode
  │
  │  syscall instruction
  ▼
CPU jumps to entry point (in trampoline area)
  │
  │  [Trampoline code runs]
  │   - switch CR3 → kernel page tables
  │   - switch to kernel stack (via TSS/GS)
  ▼
Full kernel entry code (.text)
  │
  │  do_syscall_64()
  │  ... work ...
  ▼
Return path
  │
  │  trampoline exit code:
  │   - restore user state
  │   - switch CR3 → user page tables
  ▼
User mode resumes
```

---

## ⚡ Key properties

### 🟦 Dual-mapped (critical)

* Present in:

  * **user page tables (minimal)**
  * **kernel page tables (full)**

👉 Enables safe transition across isolation boundary

---

### 🟩 Small and tightly controlled

* Only essential code
* No general kernel data

---

### 🟨 Per-CPU aware

* Uses per-CPU state (e.g., GS base on x86)
* Ensures correct stack/CPU context

---

### 🟥 Non-general-purpose

* You don’t allocate here
* Not used by normal kernel code

---

## 🔍 Relationship to other areas

| Area                 | Role                        |
| -------------------- | --------------------------- |
| Kernel image (.text) | full kernel logic           |
| Fixmap               | fixed mappings (APIC, etc.) |
| **CPU entry area**   | **transition gateway**      |
| Per-CPU area         | CPU-local data              |
| Physmap              | RAM access                  |

---

## 🧠 Mental model

```text
User space
   │
   ▼
[ Trampoline ]   ← tiny, safe gateway
   │
   ▼
[ Full kernel ]
```

---

## 🔐 Security angle (why it matters)

* Prevents user-mode from seeing full kernel mappings
* Ensures:

  * minimal exposure
  * controlled transitions
* Central to:

  * KPTI
  * Meltdown mitigations

---

## ✅ Final takeaway

* The CPU entry / trampoline area is a **tiny, high-address kernel region**
* Used for:

  * syscalls
  * interrupts
  * user ↔ kernel transitions
* Ensures:

  * safe switching of page tables
  * minimal exposure of kernel memory

---

## 🔥 One-line summary

> **The CPU entry/trampoline area is a small, dual-mapped kernel region that safely bridges user mode and kernel mode by switching page tables and jumping into the full kernel entry path.**

---

If you want, we can go even deeper into:

* exact assembly flow of `entry_SYSCALL_64`
* how CR3 switching works step-by-step
* or how GS/TSS are used during the transition
