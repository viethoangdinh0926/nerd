Great—this is the most advanced scheduler in Linux. The **deadline scheduler** is where the kernel stops being “fair” and starts behaving like a **real-time system with guarantees**.

---

# 🧠 What is the Deadline Scheduler?

**Earliest Deadline First Scheduling** (EDF) implemented in Linux as **SCHED_DEADLINE**

👉 Goal:

```text
Ensure each task gets CPU before its deadline
```

---

# 🧭 Core Model (VERY IMPORTANT)

Each task defines 3 parameters:

```text
(runtime, deadline, period)
```

---

## 🧩 Meaning

| Parameter | Meaning                  |
| --------- | ------------------------ |
| runtime   | CPU time needed          |
| deadline  | must finish by this time |
| period    | repetition interval      |

---

## 🧠 Example

```text
Task A:
runtime = 10ms
deadline = 50ms
period = 50ms
```

👉 Means:

* needs 10ms CPU
* must complete every 50ms
* repeats forever

---

# 🔥 Core Scheduling Rule

```text
Run the task with the EARLIEST deadline
```

---

# 🧩 Internal Representation

In `task_struct`:

```c
struct sched_dl_entity dl;
```

---

## 🟦 Key fields inside `sched_dl_entity`

```c
struct sched_dl_entity {
    u64 runtime;      // remaining runtime
    u64 deadline;     // absolute deadline
    u64 period;
    u64 dl_runtime;   // reserved runtime
    u64 dl_deadline;
    u64 dl_period;
}
```

---

# 🧠 Critical distinction

| Field      | Meaning               |
| ---------- | --------------------- |
| `dl_*`     | configured parameters |
| `runtime`  | remaining budget      |
| `deadline` | absolute deadline     |

---

# 🧩 Runqueue Structure

Each CPU has:

```c
struct dl_rq {
    struct rb_root_cached rb_root;
}
```

---

## 🧠 Data structure

```text
Red-Black Tree (sorted by deadline)
```

---

## Picking next task:

```text
leftmost node = earliest deadline
```

---

# ⚙️ Scheduler Operations

---

# 🧩 1. Enqueue Task

```c
enqueue_task_dl(rq, p)
```

---

## Steps:

```text
Insert task into RB-tree (ordered by deadline)
Mark as runnable
```

---

# 🧩 2. Pick Next Task

```c
pick_next_task_dl(rq)
```

---

## Logic:

```text
return task with smallest deadline
```

---

# 🧠 Insight

> EDF guarantees optimal scheduling for single CPU if feasible

---

# 🧩 3. Runtime Accounting

Each task has **budget**:

```text
runtime decreases while running
```

---

## During execution:

```text
runtime -= elapsed_time
```

---

# 🧩 4. Budget Exhaustion

When:

```text
runtime <= 0
```

👉 Task is:

```text
throttled (cannot run)
```

---

## Then:

```text
wait until next period
```

---

# 🧠 Insight

> Prevents task from using more CPU than reserved

---

# 🧩 5. Deadline Update (Replenishment)

At period boundary:

```text
runtime = dl_runtime
deadline += dl_period
```

---

## Example

```text
t = 0: deadline = 50
t = 50: deadline = 100
t = 100: deadline = 150
```

---

# 🧩 6. Wakeup

When task wakes:

```c
enqueue_task_dl()
```

---

## If earlier deadline:

```text
preempt current task
```

---

# 🧠 Insight

> Deadline scheduler is **fully preemptive**

---

# 🧩 7. Preemption Rule

```text
if (new_task.deadline < current.deadline)
    preempt
```

---

# 🧩 8. Admission Control (VERY IMPORTANT)

Kernel checks:

```text
Total utilization ≤ CPU capacity
```

---

## Formula:

```text
Σ(runtime / period) ≤ 1
```

---

## Example

```text
Task A: 10/50 = 0.2
Task B: 20/50 = 0.4
Total = 0.6 → OK
```

---

## If > 1:

```text
reject task
```

---

# 🧠 Insight

> This guarantees deadlines are schedulable

---

# 🧩 9. Migration (multi-core)

---

## Problem:

EDF is optimal only for **single CPU**

---

## Linux solution:

* per-CPU runqueue
* push/pull tasks

---

## Functions:

```text
push_dl_task()
pull_dl_task()
```

---

# 🧠 Insight

> Multi-core EDF is approximate, not perfect

---

# 🧩 10. Interaction with Other Classes

Priority order:

```text
Deadline > RT > CFS
```

👉 Deadline tasks always win

---

# 🧠 Insight

> Deadline scheduler can starve normal tasks

---

# 🧩 11. Context Switch Flow

```text
schedule()
  ↓
pick_next_task_dl()
  ↓
context_switch()
```

---

# 🔬 Timeline Example

---

## Tasks:

```text
A: runtime=10, deadline=50
B: runtime=20, deadline=30
```

---

## Execution:

```text
t=0:
B runs (deadline=30)

t=20:
B done

t=20–30:
A runs

t=30:
B replenished → deadline=60

t=30:
Compare A(50) vs B(60) → A runs
```

---

# ⚠️ Edge Cases

---

## Deadline Miss

If task doesn’t finish before deadline:

```text
deadline miss
```

Linux:

* doesn’t kill task
* continues scheduling

---

## Overrun

If task exceeds runtime:

```text
throttled until next period
```

---

# 🧠 Deep System Insights

---

## 🔥 Why EDF?

* optimal for single CPU
* guarantees deadlines

---

## 🔥 Why runtime budget?

* prevents CPU hogging
* enforces fairness in RT context

---

## 🔥 Why admission control?

* prevents overload
* ensures guarantees

---

# ⚡ Mental Model

Think of deadline scheduler as:

```text
A reservation system for CPU time
```

Each task:

* books CPU time
* must finish before deadline
* cannot exceed reservation

---

# 🚀 If you want to go deeper

Given your kernel deep-dive path:

---

## 🔍 Option 1

👉 Walk through:

* `kernel/sched/deadline.c`
* line-by-line

---

## 🧠 Option 2

👉 Dive into:

* CBS (Constant Bandwidth Server)
* how runtime enforcement works

---

## ⚙️ Option 3

👉 Compare:

* CFS vs RT vs DL in real traces (perf)

---

## 🔬 Option 4

👉 Trace with perf:

* identify deadline preemption events

---

Just tell me:
👉 “walk deadline.c line-by-line”
👉 or “deep dive CBS algorithm”
👉 or “compare CFS vs DL with perf traces”

and we go even deeper 🔥
