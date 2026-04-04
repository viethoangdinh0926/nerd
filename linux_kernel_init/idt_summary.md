The **Interrupt Descriptor Table (IDT)** is one of the most fundamental CPU data structures in x86/x86_64. It is the mechanism that connects:

> **events (exceptions/interrupts)** → **actual code execution in the kernel**

Let’s go deep and build it from first principles.

---

# 🧠 What is the IDT?

The IDT is a **CPU-resident table of descriptors** that tells the processor:

> “When interrupt/exception vector *N* happens, jump to *this handler*”

---

## 📍 Conceptually

```text
Event occurs (interrupt or exception)
        ↓
CPU gets vector number (0–255)
        ↓
Look up IDT[vector]
        ↓
Jump to handler defined in that entry
```

---

# 🔢 Size and structure

* IDT has **256 entries**
* Each entry corresponds to a **vector number (0–255)**

```text
Vector range:
0–31   → CPU exceptions
32–255 → interrupts (hardware/software)
```

---

# 🧩 IDT entry format (x86_64)

Each entry is an **Interrupt Gate Descriptor** (16 bytes)

## Structure:

```text
+------------------------+
| Offset [15:0]          |
| Segment Selector       |
| IST (3 bits)           |
| Type & Attributes      |
| Offset [31:16]         |
| Offset [63:32]         |
| Reserved               |
+------------------------+
```

---

## 🔍 Field breakdown

### 1. Offset (handler address)

Split into 3 parts:

```text
offset_low   (bits 0–15)
offset_mid   (bits 16–31)
offset_high  (bits 32–63)
```

👉 Combined → full 64-bit function pointer

---

### 2. Segment Selector

* Points to a **code segment in GDT**
* Usually kernel code segment

---

### 3. IST (Interrupt Stack Table)

Used for **special stack switching**

```text
0 → use current stack
1–7 → use IST[n] from TSS
```

👉 Used for:

* double fault
* NMI
* critical exceptions

---

### 4. Type & Attributes

Important bits:

```text
P (Present)     → must be 1
DPL (Privilege) → who can call this
Type            → interrupt gate / trap gate
```

---

## 🔑 Gate types

### Interrupt Gate

* clears IF (interrupt flag)
* disables further interrupts

👉 used for hardware interrupts

---

### Trap Gate

* does NOT clear IF
* interrupts stay enabled

👉 used for exceptions (e.g., breakpoint)

---

# 📍 Where IDT lives

The CPU stores a pointer to IDT in a special register:

## 🧠 IDTR (Interrupt Descriptor Table Register)

```text
IDTR = {
  base → address of IDT
  limit → size of table
}
```

---

## 🔧 Loaded using:

```asm
lidt [idtr]
```

---

# ⚙️ How IDT is used (step-by-step)

---

# 1. Event occurs

Examples:

* divide by zero → vector 0
* page fault → vector 14
* timer interrupt → vector 32
* keyboard → vector ~33

---

# 2. CPU determines vector number

```text
vector = event type
```

---

# 3. CPU indexes IDT

```text
entry = IDT[vector]
```

---

# 4. CPU validates entry

Checks:

* Present bit
* privilege level rules
* gate type

If invalid:
→ **#GP fault**
→ possibly double fault

---

# 5. Stack switching (if needed)

If:

* privilege level changes (user → kernel)
* or IST is used

Then CPU:

* switches stack
* loads new RSP

---

# 6. CPU pushes state

Automatically pushes:

```text
RIP
CS
RFLAGS
(optional) SS + RSP (if privilege change)
(optional) error code (for some exceptions)
```

---

# 7. Jump to handler

```text
RIP = handler address from IDT
```

Now execution is inside kernel handler.

---

# 8. Handler executes

Typical flow:

```text
assembly stub
  ↓
save registers
  ↓
call C handler
  ↓
process event
```

---

# 9. Return from interrupt

```asm
iretq
```

CPU restores:

* RIP
* CS
* RFLAGS
* stack if needed

---

# 🔥 Example: Page Fault

---

## Step-by-step

1. Access invalid memory
2. CPU raises `#PF` (vector 14)
3. CPU:

   ```text
   entry = IDT[14]
   ```
4. Switch to kernel stack
5. Push:

   ```text
   RIP, CS, RFLAGS, error code
   ```
6. Jump to:

   ```text
   page_fault handler
   ```
7. Kernel:

   * inspects fault
   * maybe allocates page
   * or kills process

---

# 🔥 Example: Timer Interrupt

---

1. Timer fires
2. Interrupt controller sends vector (e.g., 32)
3. CPU:

   ```text
   entry = IDT[32]
   ```
4. Jump to interrupt handler
5. Kernel:

   * updates time
   * runs scheduler tick
   * handles deferred work

---

# 🧠 IDT vs GDT (important distinction)

| Table | Purpose                              |
| ----- | ------------------------------------ |
| GDT   | defines memory segments              |
| IDT   | defines interrupt/exception handlers |

---

# 🧩 Relationship to TSS

TSS provides:

* stack pointers for privilege levels
* IST stacks

IDT entries can reference IST → which comes from TSS

---

# ⚠️ What happens if IDT is wrong

This is critical:

## ❌ Missing entry

→ CPU cannot handle event
→ #GP → possibly crash

---

## ❌ Bad handler address

→ jump to invalid memory
→ page fault → double fault → triple fault
→ system reset

---

## ❌ Double fault failure

→ triple fault
→ CPU resets immediately

---

# 🔥 Why IDT is critical

Without IDT:

* kernel cannot:

  * handle faults
  * handle interrupts
  * respond to hardware
  * survive errors

It is the **entry point of all asynchronous and fault events**

---

# 🧠 Mental model

```text
Event happens
   ↓
CPU looks up IDT
   ↓
Find handler
   ↓
Switch context
   ↓
Execute kernel code
```

---

# ⚡ Ultra-condensed summary

The IDT is a 256-entry table that maps interrupt/exception vectors to handler addresses. Each entry defines where the CPU should jump when an event occurs, along with privilege and stack behavior. When an interrupt or exception happens, the CPU indexes into the IDT, validates the entry, optionally switches stacks, saves execution state, and transfers control to the kernel handler.

---

If you want next level, I can:

* walk through **actual Linux `trap_init()` + IDT setup code**
* show **bit-level encoding of IDT entries**
* or generate a **knowledge node for IDT**
