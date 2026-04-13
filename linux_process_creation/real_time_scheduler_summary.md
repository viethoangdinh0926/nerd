Perfect—now we’re stepping into the **Real-Time (RT) scheduler**, which sits between CFS and Deadline in complexity, but is **very different in behavior**.

---

# 🧠 What is the Real-Time Scheduler?

Linux RT scheduler implements:

* **FIFO scheduling** → `SCHED_FIFO`
* **Round-robin scheduling** → `SCHED_RR`

👉 Goal:

```text
Run highest-priority task immediately, with strict guarantees
```

---

# 🧭 Core Model

Unlike CFS (fairness) or DL (deadlines), RT scheduler is:

```text
Priority-based + deterministic
```

---

## 🧩 Key Rule

```text
Higher priority ALWAYS runs first
```

---

## Priority range:

```text
0–99 (RT priorities)
```

* 99 = highest priority
* > all CFS tasks

---

# 🔥 Scheduling Order

```text
Deadline > RT > CFS > Idle
```

👉 RT tasks preempt everything below them

---

# 🧩 Internal Representation

In `task_struct`:

```c
struct sched_rt_entity rt;
unsigned int rt_priority;
```

---

# 🧱 Runqueue Structure

Each CPU has:

```c
struct rt_rq {
    struct rt_prio_array active;
}
```

---

## 🟦 `rt_prio_array`

```text
Array of 100 queues (one per priority)
```

---

### Structure:

```text
priority 99 → queue
priority 98 → queue
...
priority 0  → queue
```

---

# 🧠 Key Insight

> RT scheduler = array of FIFO queues indexed by priority

---

# ⚙️ Core Operations

---

# 🧩 1. Enqueue Task

```c
enqueue_task_rt(rq, p)
```

---

## Steps:

```text
Insert into queue of its priority
Mark runnable
```

---

# 🧩 2. Pick Next Task

```c
pick_next_task_rt(rq)
```

---

## Logic:

```text
Find highest non-empty priority queue
Pick first task in that queue
```

---

# 🧠 Complexity

```text
O(1) scheduling
```

👉 No tree traversal like CFS

---

# 🧩 3. Execution Policies

---

# 🟦 SCHED_FIFO

## Behavior:

```text
Run until:
- blocks
- yields
- preempted by higher priority
```

---

## ❗ No time slice

👉 Task can run forever

---

# 🟩 SCHED_RR

## Behavior:

```text
Run for fixed time slice
Then rotate within same priority
```

---

## Time slice:

```text
sched_rr_timeslice (default ~100ms)
```

---

# 🔁 Example

```text
Priority 50 queue:

A → B → C
```

---

## FIFO:

```text
A runs until done/block
```

---

## RR:

```text
A → B → C → A → B → C ...
```

---

# 🧩 4. Preemption

---

## Rule:

```text
If higher priority task becomes runnable → IMMEDIATE preemption
```

---

## Example:

```text
Running: priority 40
New task: priority 60

→ switch immediately
```

---

# 🧠 Insight

> RT scheduler is aggressively preemptive

---

# 🧩 5. Wakeup Path

```c
try_to_wake_up()
```

---

## For RT tasks:

```text
Insert into priority queue
Check priority vs current
Preempt if higher
```

---

# 🧩 6. Time Slice Handling (RR only)

On timer tick:

```c
task_tick_rt()
```

---

## Logic:

```text
if (timeslice expired):
    move task to end of queue
```

---

# 🧩 7. Throttling (VERY IMPORTANT)

---

## Problem:

RT tasks can starve system

---

## Solution:

```text
RT bandwidth control
```

---

## Kernel parameters:

```text
sched_rt_runtime_us
sched_rt_period_us
```

---

## Example:

```text
period = 1s
runtime = 950ms
```

👉 RT tasks can use max 95% CPU

---

# 🧠 Insight

> Prevents RT tasks from freezing system

---

# 🧩 8. Migration (multi-core)

---

## Problem:

RT tasks must be load balanced

---

## Mechanism:

```text
push_rt_task()
pull_rt_task()
```

---

## Uses:

* CPU affinity
* load balancing

---

# 🧩 9. Context Switch Flow

```text
schedule()
  ↓
pick_next_task_rt()
  ↓
context_switch()
```

---

# 🔬 Timeline Example

---

## Tasks:

```text
A: prio 50
B: prio 60
C: prio 50
```

---

## Execution:

```text
t=0: A runs
t=1: B wakes → preempts A
t=2: B blocks
t=2: A resumes
t=3: C enters queue (same prio as A)
```

---

## FIFO:

```text
A continues, C waits
```

---

## RR:

```text
A → C → A → C ...
```

---

# ⚠️ Key Differences vs Other Schedulers

---

## 🟦 vs CFS

| Feature    | RT       | CFS      |
| ---------- | -------- | -------- |
| fairness   | ❌        | ✅        |
| starvation | possible | avoided  |
| complexity | O(1)     | O(log n) |

---

## 🟨 vs Deadline

| Feature           | RT            | Deadline           |
| ----------------- | ------------- | ------------------ |
| guarantees        | priority only | deadline guarantee |
| admission control | ❌             | ✅                  |
| model             | simple        | mathematical       |

---

# 🧠 Deep Insights

---

## 🔥 Why O(1)?

```text
array of queues + bitmap
```

→ constant time lookup

---

## 🔥 Why starvation possible?

```text
higher priority always wins
```

→ lower tasks may never run

---

## 🔥 Why two policies (FIFO vs RR)?

* FIFO → deterministic
* RR → fairness within same priority

---

# ⚡ Mental Model

Think of RT scheduler as:

```text
Strict priority queues with immediate preemption
```

---

# 🚀 If you want to go deeper

Given your trajectory, next levels:

---

## 🔍 Option 1

👉 Walk:

* `kernel/sched/rt.c` line-by-line

---

## 🧠 Option 2

👉 Deep dive:

* priority inversion
* priority inheritance

---

## ⚙️ Option 3

👉 Compare with perf traces:

* RT vs CFS vs DL behavior

---

## 🔬 Option 4

👉 Kernel debugging:

* trace `enqueue_task_rt()`
* trace `pick_next_task_rt()`

---

Just tell me:
👉 “walk rt.c line-by-line”
👉 or “priority inversion deep dive”
👉 or “compare RT vs DL vs CFS in perf traces”

and we go even deeper 🔥
