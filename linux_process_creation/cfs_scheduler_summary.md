Perfect—this is the **core scheduler you’ll encounter 99% of the time in Linux**. Let’s go deep, kernel-style.

---

# 🧠 What is CFS?

**Completely Fair Scheduler**

👉 Goal:

```text
Give each task a fair share of CPU time
```

---

# 🧭 Core Idea (THE KEY INSIGHT)

CFS tries to simulate:

```text
An ideal CPU where all tasks run simultaneously
```

Since that’s impossible, it approximates it by:

```text
Always run the task that has run the LEAST
```

---

# 🔥 The Central Concept: `vruntime`

---

## 🧩 Definition

```c
vruntime = actual_runtime * (weight normalization)
```

---

## 🧠 Meaning

* Tracks **how much CPU a task has “virtually” used**
* Smaller `vruntime` → task is “behind” → should run next

---

## ⚖️ Weight (nice value)

```text
nice ↓ → higher weight → slower vruntime growth → more CPU
nice ↑ → lower weight → faster vruntime growth → less CPU
```

---

# 🧱 Core Data Structures

---

## 🟦 1. `sched_entity`

```c
struct sched_entity {
    u64 vruntime;
    struct rb_node run_node;
    struct cfs_rq *cfs_rq;
};
```

👉 Represents a schedulable entity (task or group)

---

## 🟩 2. `cfs_rq` (runqueue)

```c
struct cfs_rq {
    struct rb_root_cached tasks_timeline;
    struct sched_entity *curr;
};
```

---

## 🧠 Data structure

```text
Red-Black Tree sorted by vruntime
```

---

# 🔥 Key Operation

```text
Pick LEFTMOST node → smallest vruntime
```

👉 That task runs next

---

# ⚙️ Scheduler Operations

---

# 🧩 1. Enqueue Task

```c
enqueue_task_fair(rq, p)
```

---

## Steps:

```text
Insert into RB-tree based on vruntime
Update min_vruntime
```

---

# 🧩 2. Pick Next Task

```c
pick_next_task_fair(rq)
```

---

## Logic:

```text
return leftmost node in RB-tree
```

---

# 🧠 Insight

> CFS is a “sorted timeline of CPU usage”

---

# 🧩 3. Execution

When task runs:

```text
vruntime increases
```

---

## Formula (simplified)

```text
vruntime += delta_exec * (1024 / weight)
```

---

# 🧠 Result

* CPU-heavy tasks → vruntime grows fast → get deprioritized
* idle/light tasks → vruntime stays low → get scheduled sooner

---

# 🧩 4. Preemption

---

## Rule:

```text
if (current.vruntime > next.vruntime)
    preempt
```

---

## Triggered by:

* timer tick
* wakeup of another task

---

# 🧩 5. Time Slice (CFS style)

No fixed slice like RR.

---

## Instead:

```text
time_slice = sched_period / num_tasks
```

---

## Example:

```text
2 tasks → each ~50%
4 tasks → each ~25%
```

---

# 🧠 Insight

> Time slice emerges from fairness, not fixed

---

# 🧩 6. Wakeup

---

## When task wakes:

```c
enqueue_task_fair()
```

---

## Special handling:

```text
Place near min_vruntime
```

---

## Why?

```text
Prevent waking task from being starved
```

---

# 🧠 Insight

> Wakeups are “boosted” to be fair

---

# 🧩 7. Sleep / Block

When task blocks:

```text
removed from RB-tree
```

---

When it returns:

* keeps old vruntime
* may get advantage

---

# 🧩 8. `min_vruntime`

```c
cfs_rq->min_vruntime
```

---

## Purpose:

```text
Track smallest vruntime in system
```

---

## Why needed?

```text
Keep vruntime values bounded
```

---

# 🧠 Insight

> Prevents overflow + maintains fairness baseline

---

# 🧩 9. Group Scheduling

---

## CFS supports hierarchy:

```text
Process groups → sched_entity
```

---

Example:

```text
Group A → 50% CPU
Group B → 50% CPU
```

Inside group:

* tasks share fairly

---

# 🧠 Insight

> CFS schedules groups like tasks

---

# 🧩 10. Load Balancing (multi-core)

---

## Each CPU has:

```text
its own cfs_rq
```

---

## Balancing:

```text
migrate tasks between CPUs
```

---

## Functions:

```text
load_balance()
```

---

# 🧠 Insight

> CFS is per-CPU but globally fair (approx)

---

# 🔬 Execution Timeline Example

---

## Tasks:

```text
A: vruntime = 10
B: vruntime = 20
C: vruntime = 30
```

---

## Execution:

```text
Pick A
A runs → vruntime = 25

Now:
B=20 → runs next
```

---

## Result:

```text
Tasks converge to equal vruntime
```

---

# ⚠️ Edge Cases

---

## Starvation?

```text
NO (by design)
```

---

## Interactive tasks

Short tasks:

```text
sleep → wake → low vruntime → run quickly
```

👉 Feels responsive

---

# 🧠 Deep Insights

---

## 🔥 Why RB-tree?

```text
Need sorted structure + fast insert/remove
```

---

## 🔥 Why vruntime instead of time slice?

```text
More precise fairness
```

---

## 🔥 Why per-CPU?

```text
Scales to many cores
```

---

# ⚡ Mental Model

Think of CFS as:

```text
A timeline of CPU usage
```

Each task moves forward:

```text
run → move right (vruntime increases)
```

Scheduler always picks:

```text
leftmost (least run)
```

---

# 🧠 Compare All Schedulers

| Scheduler | Model     | Guarantee           |
| --------- | --------- | ------------------- |
| CFS       | fairness  | equal CPU           |
| RT        | priority  | immediate execution |
| DL        | deadlines | timing guarantees   |

---

# 🚀 If you want to go deeper

Based on your kernel-level path:

---

## 🔍 Option 1

👉 Walk:

* `kernel/sched/fair.c`
* `pick_next_task_fair()` line-by-line

---

## 🧠 Option 2

👉 Deep dive:

* vruntime math
* weight calculation (nice levels)

---

## ⚙️ Option 3

👉 Trace with perf:

* see vruntime evolution in real runs

---

## 🔬 Option 4 (very powerful)

👉 Compare:

* same workload under CFS vs RT vs DL

---

Just tell me:
👉 “walk fair.c line-by-line”
👉 or “deep dive vruntime math”
👉 or “compare schedulers with perf traces”

and we go deeper 🔥
