Absolutely — let’s zoom in on the **state and scheduling part** of `task_struct`, and treat it like a real kernel-internals walkthrough rather than a summary.

One important note first: “**State & scheduling**” is a conceptual grouping. In the actual current `task_struct`, the runnability state fields `__state` and `saved_state` appear **just before** the comment that marks the randomizable portion, and the main scheduler fields appear shortly after. The source explicitly says only “scheduling-critical items” should live above that boundary. ([GitHub][1])

## The fields to focus on

From the current `sched.h`, the core fields in this area are:

```c
unsigned int __state;
unsigned int saved_state;

int on_cpu;
struct __call_single_node wake_entry;
unsigned int wakee_flips;
unsigned long wakee_flip_decay_ts;
struct task_struct *last_wakee;
int recent_used_cpu;
int wake_cpu;
int on_rq;

int prio;
int static_prio;
int normal_prio;
unsigned int rt_priority;

struct sched_entity se;
struct sched_rt_entity rt;
struct sched_dl_entity dl;
struct sched_dl_entity *dl_server;
const struct sched_class *sched_class;

unsigned int policy;
unsigned long max_allowed_capacity;
int nr_cpus_allowed;
const cpumask_t *cpus_ptr;
cpumask_t *user_cpus_ptr;
cpumask_t cpus_mask;
void *migration_pending;
unsigned short migration_disabled;
unsigned short migration_flags;
```

These are all present in the current tree around the scheduling portion of `task_struct`. ([GitHub][1])

---

## 1. `__state`: “is this task runnable, sleeping, stopped, or dead?”

This is the **task-state bitmask** the scheduler and wakeup paths care about. The kernel docs in `sched.h` explicitly distinguish `task->__state` from `task->exit_state`: `__state` is about **runnability**, while `exit_state` is about **exiting**. ([GitHub][1])

Examples defined in the source include:

* `TASK_RUNNING`
* `TASK_INTERRUPTIBLE`
* `TASK_UNINTERRUPTIBLE`
* `TASK_WAKING`
* `TASK_NEW`
* `TASK_DEAD`
* `TASK_RTLOCK_WAIT` ([GitHub][1])

### How to think about it

`__state` answers:

* Can this task be chosen to run now?
* Is it blocked waiting for an event?
* Is it in some special scheduler transition?

The subtle thing is that `TASK_RUNNING` is defined as `0`. So “running” here really means **not sleeping in a blocked state**. A task with `TASK_RUNNING` may be:

* currently executing on a CPU, or
* runnable and waiting on a runqueue. ([GitHub][1])

### Why this field is so sensitive

The state-setting macros in `sched.h` show that changing task state is tied to memory ordering and wakeup correctness. `set_current_state()` uses `smp_store_mb(...)`, and `set_special_state()` serializes with `pi_lock` to avoid races with wakeups. ([GitHub][1])

So this is not “just a status variable.” It is part of a carefully synchronized protocol between:

* the task going to sleep,
* another CPU waking it,
* and the scheduler deciding whether to enqueue it. ([GitHub][1])

---

## 2. `saved_state`: PREEMPT_RT lock-wait preservation

`saved_state` exists so PREEMPT_RT lock substitutions can preserve the task’s prior sleep state while the task temporarily waits in `TASK_RTLOCK_WAIT`. The source comments spell this out directly. ([GitHub][1])

### Why this exists

Without `saved_state`, a task sleeping on some condition and then blocking on an RT lock could lose the original meaning of its blocked state.

The pattern in the source is:

* save the old state into `saved_state`
* set `__state = TASK_RTLOCK_WAIT`
* after lock acquisition, restore `__state = saved_state`
* then reset `saved_state = TASK_RUNNING` ([GitHub][1])

### Mental model

Think of `saved_state` as:

> “the task’s real blocked state, temporarily parked while an RT lock wait overlays it.”

---

## 3. `on_cpu`: “is this task currently executing?”

`on_cpu` tells the scheduler whether the task is actually **running on a CPU right now**. It is different from `__state` and `on_rq`. The source comments around the scheduler bits discuss ordering involving `p->on_rq` and `p->on_cpu`, especially in wakeup races and remote wakeups. ([GitHub][1])

### Distinction

* `__state == TASK_RUNNING` means runnable/not blocked
* `on_rq` means it is enqueued on a runqueue
* `on_cpu` means it is actively executing right now

That distinction is crucial because a task can be runnable without being on-core at this instant.

---

## 4. `on_rq`: “is this task queued on a runqueue?”

`on_rq` tracks whether the task is currently on a CPU runqueue. The scheduler documentation explains that when a task enters runnable state, `enqueue_task()` puts it into the scheduler’s structure, and `dequeue_task()` removes it when it is no longer runnable. For CFS, that structure is a red-black tree. ([Kernel.org][2])

### Mental model

* `on_rq = 1` means “scheduler may pick this task”
* `on_rq = 0` means “not currently queued for execution”

For CFS specifically, enqueuing means the task’s `sched_entity` is inserted into the runqueue RB tree. ([Kernel.org][2])

---

## 5. `wake_entry`, `wakee_flips`, `wakee_flip_decay_ts`, `last_wakee`, `recent_used_cpu`, `wake_cpu`

These are wakeup-placement and affinity heuristics.

The source comment near `recent_used_cpu` explains the idea: waker/wakee relationships can push tasks between CPUs, and tracking a recently used CPU helps the scheduler quickly find a recently used CPU that may be idle. ([GitHub][1])

### What these fields are doing conceptually

When task A wakes task B, the scheduler tries to answer:

* Should B run on the current CPU?
* Should B be placed near the task that woke it?
* Is there a recently used CPU likely to still be cache-friendly or idle?

So these fields help the wakeup path optimize:

* latency,
* CPU cache locality,
* and CPU selection. ([GitHub][1])

### The intuition

This is the kernel trying to exploit the fact that producer/consumer or request/worker pairs often wake each other repeatedly. If it notices stable wake relationships, it tries not to scatter them randomly across CPUs.

---

## 6. Priorities: `prio`, `static_prio`, `normal_prio`, `rt_priority`

These fields are easy to confuse, so here is the clean separation.

### `static_prio`

This is the baseline priority derived from normal scheduler attributes such as nice value for regular tasks.

### `normal_prio`

This is the task’s “effective normal” priority after policy-specific adjustments.

### `prio`

This is the **current scheduler-visible priority** used for ordering and dispatch decisions.

### `rt_priority`

This is the user-assigned real-time priority for RT policies. ([GitHub][1])

### Mental model

Think of it as layers:

```text
user nice / RT params
        ↓
   static_prio / rt_priority
        ↓
    normal_prio
        ↓
        prio   ← the value the scheduler really uses now
```

### Why multiple fields?

Because the kernel needs to preserve:

* the original/base scheduling attributes,
* the current interpreted priority,
* and the immediate priority used in scheduling decisions.

If there were only one number, the scheduler would lose information about what was base policy versus what was temporarily in effect.

---

## 7. `policy` and `sched_class`: “what kind of scheduler owns this task?”

The current `task_struct` has both:

* `unsigned int policy`
* `const struct sched_class *sched_class` ([GitHub][1])

These are related but not identical.

### `policy`

This is the task’s scheduling policy, such as:

* normal/fair scheduling,
* batch,
* idle,
* FIFO real-time,
* round-robin real-time,
* deadline.

The policy is the **configured scheduling behavior**.

### `sched_class`

This is the scheduler’s **implementation vtable** for that task.

It tells the kernel which class methods to call for this task, such as:

* enqueue
* dequeue
* check preemption
* pick next task
* task tick ([Kernel.org][2])

### Why both exist?

Because “policy” is the abstract contract, while `sched_class` is the actual code path.

A task with a normal policy is typically handled by the fair class; an RT task uses the RT class; a deadline task uses the DL class. The class pointer is how the generic scheduler core dispatches to the right algorithms.

---

## 8. Per-class entities: `se`, `rt`, `dl`, `dl_server`, and optionally `scx`

`task_struct` embeds the per-class state objects directly:

* `struct sched_entity se`
* `struct sched_rt_entity rt`
* `struct sched_dl_entity dl`
* `struct sched_dl_entity *dl_server`
* optionally `struct sched_ext_entity scx` when enabled. ([GitHub][1])

### Why embed all of them?

Because the scheduler core wants a task to be quickly usable by whichever scheduling class applies, without separately allocating class-specific objects.

### What each means

#### `se`

Used by the fair scheduler. The CFS documentation explains that runnable tasks are enqueued into a red-black tree, and the scheduler picks the most eligible task from that structure. `sched_entity` is the object CFS manipulates to do that. ([Kernel.org][2])

#### `rt`

Used by the real-time scheduler.

#### `dl`

Used by the deadline scheduler. The deadline docs describe deadline-specific states and runtime/bandwidth behavior for deadline tasks. ([Kernel Documentation][3])

#### `dl_server`

Supports deadline-server behavior.

#### `scx`

Present when sched_ext is enabled.

### Mental model

The task carries all scheduler-specific “plug-ins” inside itself, and `sched_class` chooses which one is active.

---

## 9. CPU affinity and migration: `nr_cpus_allowed`, `cpus_ptr`, `user_cpus_ptr`, `cpus_mask`, `migration_pending`, `migration_disabled`, `migration_flags`, `max_allowed_capacity`

These fields control **where** the task may run and whether it may currently move.

They appear in the current `task_struct` directly after `policy`. ([GitHub][1])

### `cpus_mask` / `cpus_ptr`

These represent the allowed CPU set for the task.

### `nr_cpus_allowed`

How many CPUs are currently permitted.

### `user_cpus_ptr`

Tracks the user-requested CPU affinity separately from internal constraints.

### `migration_pending`

Migration bookkeeping.

### `migration_disabled`

Marks that migration is temporarily disabled.

### `migration_flags`

Additional migration state.

### `max_allowed_capacity`

A scheduler capacity constraint used in placement decisions. ([GitHub][1])

### Why these belong in scheduling

Because scheduling is not only “when does this task run?” but also “**on which CPU may it run?**”

The scheduler cannot place a task without consulting affinity and migration state.

---

## 10. How these fields work together in a real sleep/wakeup cycle

Here is the actual logic flow to build intuition.

### A. Task goes to sleep

It sets `__state` to something like `TASK_INTERRUPTIBLE` or `TASK_UNINTERRUPTIBLE` using the state macros. Those macros enforce the ordering needed so wakeups do not race incorrectly. ([GitHub][1])

### B. Scheduler removes it

The task is dequeued, so `on_rq` becomes false for that CPU’s runqueue. For fair scheduling, that means removing its `sched_entity` from the RB tree. ([Kernel.org][2])

### C. Another CPU wakes it

Wakeup logic checks whether the wakeup condition matches the task’s current `__state`. If so, the task becomes runnable again and is enqueued. The comments in `sched.h` explicitly describe wakeup behavior in terms of `p->__state`. ([GitHub][1])

### D. Placement decision

The scheduler uses:

* `policy`
* `sched_class`
* class-specific entity (`se` / `rt` / `dl`)
* affinity fields (`cpus_ptr`, `nr_cpus_allowed`, etc.)
* wakeup hints (`wake_cpu`, `recent_used_cpu`, `last_wakee`)
  to decide where to enqueue it. ([GitHub][1])

### E. Running

When chosen, it is no longer just runnable; it becomes the executing task, reflected by `on_cpu`. The scheduler core comments describe how normal scheduling state is serialized by the runqueue lock while picking and switching tasks. ([GitHub][4])

---

## 11. The shortest accurate mental model

This subsection of `task_struct` answers four scheduler questions:

```text
1. Is the task runnable or blocked?        -> __state, saved_state
2. Is it queued or currently executing?    -> on_rq, on_cpu
3. How important is it?                    -> prio, normal_prio, static_prio, rt_priority
4. Which scheduler logic and CPUs apply?   -> policy, sched_class, se/rt/dl, cpus_mask...
```

That is the core of Linux scheduling state in one picture. ([GitHub][1])

## 12. The subtle distinction most people miss

The three fields below are not interchangeable:

```text
__state   = sleep/run eligibility state
on_rq     = queued in scheduler data structure
on_cpu    = actively executing right now
```

A task may be:

* `TASK_RUNNING`
* `on_rq = 1`
* `on_cpu = 0`

That means: “runnable, waiting its turn.”

Or:

* `TASK_RUNNING`
* `on_rq = 0`
* `on_cpu = 1`

That means: “currently executing.”

That distinction is the backbone of understanding scheduler races and wakeups. ([GitHub][1])

If you want, next I can do a **field-by-field dive into `struct sched_entity se`**, which is the real heart of CFS.

[1]: https://github.com/torvalds/linux/blob/master/include/linux/sched.h "linux/include/linux/sched.h at master · torvalds/linux · GitHub"
[2]: https://www.kernel.org/doc/html/v6.1/scheduler/sched-design-CFS.html "CFS Scheduler — The Linux Kernel  documentation"
[3]: https://docs.kernel.org/scheduler/sched-deadline.html "Deadline Task Scheduling — The Linux Kernel  documentation"
[4]: https://github.com/torvalds/linux/blob/master/kernel/sched/core.c "linux/kernel/sched/core.c at master · torvalds/linux · GitHub"
