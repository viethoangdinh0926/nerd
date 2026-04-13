Yes — both **CFS** and the **Deadline scheduler** use a **red-black tree**, but they use it for **different ordering keys** and **different scheduling goals**.

That distinction is the important part.

# Big picture

A red-black tree gives the scheduler:

* ordered tasks
* fast insert
* fast delete
* fast access to the leftmost node

In both schedulers, the kernel keeps runnable tasks in a per-CPU red-black tree and usually picks the **leftmost node** as the next task to run.

But:

* **CFS** orders by **virtual runtime**
* **Deadline** orders by **absolute deadline**

So the same data structure supports two different policies.

---

# 1. CFS red-black tree

## What the tree represents

For **CFS**, the tree is a timeline of how much CPU each task has effectively received.

Each runnable task has a `sched_entity`, and each `sched_entity` contains an RB-tree node.

Conceptually:

```c
struct sched_entity {
    struct rb_node run_node;
    u64 vruntime;
    ...
};
```

And the CFS runqueue has something like:

```c
struct cfs_rq {
    struct rb_root_cached tasks_timeline;
    ...
};
```

## Key used in the tree

The tree is ordered by:

```text
vruntime
```

where:

* smaller `vruntime` = task has had less CPU
* larger `vruntime` = task has had more CPU

## What leftmost means

The **leftmost node** is:

```text
task with smallest vruntime
```

That means:

```text
the task most entitled to run next
```

## Why CFS uses RB-tree

CFS wants fairness, not strict priority.

So it needs a structure that constantly answers:

```text
Which runnable task has received the least normalized CPU time?
```

The RB-tree is perfect for that because tasks wake, sleep, and re-enter often.

---

# 2. Deadline red-black tree

## What the tree represents

For **SCHED_DEADLINE**, the tree is not about fairness. It is about urgency.

Each runnable deadline task has a `sched_dl_entity`, and the runqueue contains an RB-tree of deadline entities.

Conceptually:

```c
struct sched_dl_entity {
    struct rb_node rb_node;
    u64 deadline;
    ...
};
```

And the deadline runqueue has something like:

```c
struct dl_rq {
    struct rb_root_cached root;
    ...
};
```

## Key used in the tree

The tree is ordered by:

```text
absolute deadline
```

where:

* smaller deadline = more urgent
* larger deadline = less urgent

## What leftmost means

The **leftmost node** is:

```text
task with earliest absolute deadline
```

That means:

```text
the task that must run first under EDF
```

## Why Deadline uses RB-tree

The Deadline scheduler wants to answer:

```text
Which runnable task has the earliest deadline?
```

Again, an RB-tree gives efficient insert, delete, and min lookup.

---

# 3. Same structure, different semantics

Here is the clean comparison:

| Scheduler | Tree key          | Leftmost node means | Scheduling goal            |
| --------- | ----------------- | ------------------- | -------------------------- |
| CFS       | `vruntime`        | least CPU received  | fairness                   |
| Deadline  | absolute deadline | earliest deadline   | real-time timing guarantee |

So:

* **CFS tree = fairness timeline**
* **Deadline tree = urgency timeline**

---

# 4. Visual example

## CFS

Suppose runnable tasks have:

```text
A: vruntime = 12
B: vruntime = 20
C: vruntime = 31
```

Tree ordering:

```text
A < B < C
```

The scheduler picks:

```text
A
```

because A has run the least.

---

## Deadline

Suppose runnable tasks have:

```text
A: deadline = 80
B: deadline = 40
C: deadline = 100
```

Tree ordering:

```text
B < A < C
```

The scheduler picks:

```text
B
```

because B’s deadline comes first.

---

# 5. Why both use `rb_root_cached`

Both schedulers benefit from caching the leftmost node.

Without caching, to get the minimum task you would walk all the way left in the tree.

With cached root:

```text
pick-next ≈ constant-time access to the minimum
```

while insert/delete still stay efficient.

So the pattern is basically:

* ordered balancing via RB-tree
* fast next-task lookup via cached leftmost pointer

---

# 6. What changes when a task runs

## In CFS

When a task runs:

```text
vruntime increases
```

So its position in the tree may need to change.

Typical pattern:

* remove entity from tree
* update runtime / vruntime
* reinsert if still runnable

That is how CFS keeps the ordering accurate.

## In Deadline

When a task runs:

* its remaining runtime budget decreases
* its absolute deadline usually stays the same for the current job

So the ordering is mostly driven by deadline, not by consumed runtime.

When a new period starts, the task gets:

* replenished runtime
* a new absolute deadline

and then it may be reinserted with the updated deadline.

---

# 7. Why RT scheduler is different

This is a useful contrast.

The **RT scheduler** does **not** use an RB-tree for its main runqueue logic.

Instead it uses:

```text
priority array + queue per priority
```

because RT scheduling is strict fixed-priority scheduling, so the main question is:

```text
What is the highest non-empty priority?
```

That is different from CFS and Deadline, where you need an ordered structure over a continuously changing scalar key.

---

# 8. Kernel-level intuition

Think of it like this:

## CFS

```text
RB-tree sorted by "who deserves CPU next"
```

## Deadline

```text
RB-tree sorted by "who is most urgent"
```

Same machinery, different meaning.

---

# 9. Deeper insight

The reason both schedulers converge on an RB-tree is that both need an **ordered set of runnable tasks**, but their ordering dimension differs:

* CFS uses a **historical fairness metric**
* Deadline uses a **future timing constraint**

That is a very elegant kernel design choice:

```text
same container abstraction
different scheduling policy
```

---

# 10. One-line summary

Both CFS and Deadline use a red-black tree, but:

* **CFS** orders tasks by **vruntime** to pick the fairest next task
* **Deadline** orders tasks by **absolute deadline** to pick the most urgent next task

If you want, I can go one level deeper and show the actual flow of **enqueue / dequeue / pick-next** for both schedulers side by side.
