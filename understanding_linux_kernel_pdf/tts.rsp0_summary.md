This is the **missing link** that ties together:

* scheduler
* per-task kernel stacks
* TSS
* safe user → kernel transitions

Let’s walk it **precisely and concretely**.

---

# 🧭 Big Picture

> 🔥 Linux must ensure that when a task in user mode enters the kernel, the CPU lands on **that task’s kernel stack**.

That is achieved by:

```text
Context switch
   ↓
Update TSS.RSP0
   ↓
CPU uses TSS.RSP0 on next user→kernel entry
   ↓
Kernel runs on correct task’s kernel stack
```

---

# 🧱 1. Per-task Kernel Stack

Every process (`task_struct`) has:

```text
task_struct
   ↓
kernel stack (fixed size, e.g. 16KB)
```

---

## Memory layout (simplified)

```text
+----------------------+
| task_struct          |
| (or adjacent area)   |
+----------------------+
| kernel stack         |
| grows downward       |
+----------------------+
```

---

## Key idea

👉 Each task has its **own private kernel stack**

Used when:

* handling syscalls
* handling interrupts
* running kernel code on behalf of that task

---

# ⚡ 2. Where the Kernel Stack Pointer Comes From

Linux defines a helper:

```c
task_top_of_stack(task)
```

This returns:

```text
top of that task’s kernel stack
```

---

# 🧠 3. What TSS.RSP0 Must Contain

TSS field:

```text
RSP0 = kernel stack pointer for current task
```

---

## Why?

When CPU transitions:

```text
User (ring 3) → Kernel (ring 0)
```

CPU does:

```text
RSP ← TSS.RSP0
```

So if RSP0 is wrong → kernel runs on wrong stack → 💀 crash / security bug

---

# 🔥 4. Where Linux Updates TSS.RSP0

This happens during **context switch**

---

## Key function path

📂 `kernel/sched/core.c`

```c
context_switch()
   → switch_to()
       → __switch_to()
```

---

## Architecture-specific part

📂 `arch/x86/kernel/process.c`

```c
__switch_to(prev, next)
```

---

# 🧩 5. The Critical Line

Inside `__switch_to()` (x86):

```c
load_sp0(next);
```

---

## What it does

```c
tss->rsp0 = task_top_of_stack(next);
```

---

# 🧠 Translation

```text
Switching to new task
   ↓
Set TSS.RSP0 = new task’s kernel stack top
```

---

# ⚡ 6. Why This Happens on Context Switch

Because the CPU doesn’t know about tasks.

The CPU only knows:

```text
“When entering ring 0 → use TSS.RSP0”
```

So Linux must update that value **every time the running task changes**.

---

# 🔄 7. Full Context Switch Flow

Let’s walk it:

---

## Step 1: Scheduler picks next task

```text
prev → next
```

---

## Step 2: `__switch_to(prev, next)`

Linux switches:

* registers
* FPU state
* memory context (CR3)
* etc.

---

## Step 3: Update kernel stack for CPU entry

```text
TSS.RSP0 = next->kernel_stack_top
```

---

## Step 4: Now CPU is “armed”

Next time an interrupt/syscall happens:

```text
CPU will land on next task’s kernel stack
```

---

# 🧠 8. What Happens After Context Switch

Now imagine:

---

## Scenario

1. Task A is running in user mode
2. Scheduler switches to Task B
3. TSS.RSP0 now points to Task B stack

---

## Then interrupt occurs

```text
User mode (Task B)
   ↓
Interrupt
   ↓
CPU loads RSP0 (Task B stack)
   ↓
Kernel runs on Task B kernel stack
```

---

# 🔥 9. Why This Is Critical

Without updating TSS.RSP0:

👉 CPU would use the wrong stack

---

## Consequences

* stack corruption
* cross-task memory leaks
* privilege escalation
* kernel panic

---

# 🧠 10. Per-CPU TSS

Important detail:

👉 Each CPU has its own TSS

---

## Why?

Because:

```text
Each CPU runs a different task
```

So each CPU must have:

```text
its own RSP0 pointing to its current task
```

---

## Structure

```text
CPU0 → TSS0 → RSP0 → task A stack
CPU1 → TSS1 → RSP0 → task B stack
```

---

# ⚡ 11. Where TSS Lives in Linux

📂 `arch/x86/kernel/cpu/common.c`

Linux defines:

```c
struct tss_struct per_cpu(cpu_tss_rw, cpu);
```

---

So:

```text
each CPU has its own TSS
```

---

# 🧩 12. Subtle Detail: Stack Top vs Stack Base

Kernel stacks grow downward:

```text
High address → empty
Low address → used
```

---

## So:

```text
RSP0 = top of stack (high address)
```

---

Because:

```text
push → RSP decreases
```

---

# ⚡ 13. What About IST?

IST stacks are also stored in TSS:

```text
TSS.IST1 → special stack
```

---

These are:

* per CPU
* NOT per task

Used for:

* NMI
* double fault

---

# 🧠 Key difference

| Stack | Owned by |
| ----- | -------- |
| RSP0  | per task |
| IST   | per CPU  |

---

# 🔥 14. Interaction with Syscalls

Even though `syscall` path is optimized:

👉 Linux still ensures it switches to the correct per-task kernel stack

---

So the invariant holds:

```text
Kernel always runs on current task’s kernel stack
```

---

# 🧠 15. Final Mental Model

```text
Each task:
  has its own kernel stack

Scheduler:
  switches tasks

Context switch:
  updates TSS.RSP0

CPU:
  uses TSS.RSP0 on privilege entry

Result:
  kernel always executes on correct task stack
```

---

# 🔥 One-Line Summary

> TSS.RSP0 is the **hardware pointer to “where kernel execution for this task should start”**, and Linux updates it on every context switch.

---

# 🚀 Next-level deep dive (highly recommended)

Now that you understand this, the next powerful topics are:

👉 how `current` is derived from stack pointer
👉 how `pt_regs` is laid out on kernel stack
👉 full interrupt entry assembly walkthrough

These will complete your mental model of kernel execution.
