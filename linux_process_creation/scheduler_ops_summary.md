Great—now we’re stepping into the **core of the Linux kernel runtime**: how the scheduler actually operates. I’ll walk you through this like a **trace through kernel execution**, not just concepts.

---

# 🧠 Big Picture: What the Scheduler Does

At any moment, the Linux scheduler answers:

```text
Which task_struct runs on which CPU right now?
```

It continuously:

* picks the next task
* switches context
* enforces fairness / priority
* handles wakeups and sleeps

---

# 🧭 Core Scheduler Flow

```text
task blocks / wakes / timeslice expires
        ↓
scheduler invoked
        ↓
pick_next_task()
        ↓
context_switch()
        ↓
new task runs
```

---

# 🔥 Key Components

---

## 🧩 1. Runqueue (per CPU)

Each CPU has its own:

```c
struct rq {
    struct task_struct *curr;
    struct task_struct *idle;
    struct cfs_rq cfs;
    struct rt_rq rt;
}
```

👉 One scheduler per CPU → avoids global locking

---

## 🧠 Insight

> Linux scheduler is **per-CPU**, not global

---

# 🧩 2. Scheduler Classes

Each task belongs to a **scheduler class**:

| Class         | Purpose             |
| ------------- | ------------------- |
| CFS (default) | fair scheduling     |
| RT            | real-time (FIFO/RR) |
| DL            | deadline scheduling |

Each class implements:

```c
struct sched_class {
    pick_next_task()
    enqueue_task()
    dequeue_task()
    task_tick()
}
```

---

# 🔥 Scheduling Order (priority)

```text
DL > RT > CFS > IDLE
```

👉 Kernel checks classes in this order

---

# 🧩 3. Core Scheduling Loop

Inside kernel:

```c
schedule()
```

---

## Flow:

```c
schedule()
  ↓
pick_next_task()
  ↓
context_switch(prev, next)
```

---

# 🧠 Important

> `schedule()` is called everywhere:

* blocking syscalls
* interrupts
* explicit yield
* timer ticks

---

# 🔍 Let’s Dive Deeper

---

# 🧩 4. `pick_next_task()`

This is the heart of decision-making.

```c
next = class->pick_next_task(rq);
```

Kernel tries:

```text
deadline → RT → CFS → idle
```

---

# 🟦 CFS (Completely Fair Scheduler)

Most important for normal processes.

---

## 🧠 Core idea:

> Run the task that has used the **least CPU time**

---

## Data structure:

```text
Red-Black Tree (ordered by vruntime)
```

---

## 🧩 `sched_entity`

```c
struct sched_entity {
    u64 vruntime;
    struct rb_node run_node;
}
```

---

## 🧠 vruntime

```text
vruntime = actual_runtime / weight
```

* lower vruntime = higher priority
* weight based on nice value

---

## Picking next task:

```text
leftmost node in RB tree
```

👉 smallest vruntime wins

---

# 🧩 5. Enqueue / Dequeue

---

## When task becomes runnable:

```c
enqueue_task(rq, task)
```

* insert into RB tree
* update stats

---

## When task blocks:

```c
dequeue_task(rq, task)
```

* remove from RB tree

---

# 🧩 6. Time Slice (CFS)

CFS doesn’t use fixed time slices.

Instead:

```text
each task gets proportional CPU time
```

---

## Virtual runtime grows:

```text
running → vruntime increases
```

Eventually:

* task no longer smallest
* scheduler picks another

---

# 🧠 Insight

> CFS simulates an “ideal CPU” shared equally

---

# 🧩 7. Wakeup Path (VERY IMPORTANT)

When a task wakes up:

```c
try_to_wake_up()
```

---

## Steps:

1. Check `task->__state`
2. Set to `TASK_RUNNING`
3. Choose CPU
4. Enqueue task

---

## CPU selection uses:

* `wake_cpu`
* `recent_used_cpu`
* load balancing

---

# 🧠 Insight

> Wakeup path is as important as scheduling itself

---

# 🧩 8. Context Switch

```c
context_switch(prev, next)
```

---

## Steps:

```text
save prev->thread
load next->thread
switch stack
update CPU registers
```

---

## Assembly level:

```text
switch_to(prev, next)
```

---

# 🧠 Critical

> No memory copy — only register + pointer switch

---

# 🧩 9. Preemption

---

## When does preemption happen?

* higher priority task wakes up
* timer interrupt
* explicit yield

---

## Kernel checks:

```c
need_resched()
```

---

If true → call `schedule()`

---

# 🧠 Insight

> Preemption = interrupting current task

---

# 🧩 10. Timer Tick

Periodic interrupt:

```text
scheduler_tick()
```

---

## Does:

* update vruntime
* check time slice
* trigger reschedule

---

# 🧩 11. Load Balancing (multi-core)

---

## Problem:

Each CPU has its own runqueue

👉 imbalance can happen

---

## Solution:

```text
load_balance()
```

Moves tasks between CPUs

---

# 🧠 Insight

> Scheduler is decentralized but coordinated

---

# 🧩 12. Idle Task

If no runnable tasks:

```text
run idle task
```

---

## Idle task:

* per CPU
* does nothing (low power)

---

# 🔥 Putting It All Together

---

## Full Execution Flow

```text
Task runs
  ↓
Blocks (I/O, sleep)
  ↓
dequeue_task()
  ↓
Another task runs
  ↓
Wakeup happens
  ↓
enqueue_task()
  ↓
scheduler decides
  ↓
context_switch()
```

---

# 🧠 Deep System Insight

---

## 🔥 Why per-CPU runqueues?

* avoids lock contention
* scales to many cores

---

## 🔥 Why RB-tree?

* O(log n) insert/remove
* always sorted by vruntime

---

## 🔥 Why multiple scheduler classes?

* different workloads:

  * fairness (CFS)
  * real-time guarantees (RT)
  * deadlines (DL)

---

# ⚡ Mental Model Upgrade

Think of scheduler as:

```text
A distributed system inside the kernel
```

* each CPU = node
* runqueue = local queue
* load balancing = coordination

---

# 🚀 If you want to go deeper (highly recommended)

Based on your learning style:

---

## 🔍 Option 1

👉 Walk through:

* `kernel/sched/core.c`
* `schedule()` line-by-line

---

## 🧠 Option 2

👉 Deep dive:

* `sched_entity` + vruntime math
* fairness guarantees

---

## ⚙️ Option 3

👉 Assembly:

* `switch_to()`
* context switch internals

---

## 🔬 Option 4 (VERY powerful)

👉 Trace real execution:

* use `perf sched`
* visualize scheduling

---

Just tell me:
👉 “walk schedule() line-by-line”
👉 or “deep dive CFS math”
👉 or “context switch assembly”

and we’ll go even deeper 🔥
