Yes. The timer and scheduler are initialized in **layers**, not in one call. In `start_kernel()`, Linux first brings up the **scheduler core**, then the **timer frameworks** that feed it, and only later enables the full interrupt-driven, multi-tasking world. In current mainline, `start_kernel()` includes `sched_init();`, and later the time path includes `timekeeping_init(); time_init();` with a note that some work must happen only after timekeeping exists. The file also explicitly tracks that early boot runs on only the boot CPU with IRQs disabled. ([GitHub][1])

A useful mental model is to separate three different things that people often blur together:

1. **Scheduler core**: runqueues, policies, task accounting, context-switch machinery.
2. **Timekeeping**: “what time is it?” from a chosen clocksource.
3. **Clock events / ticks / hrtimers**: “when should the next timer interrupt happen?” and “deliver me an event at time X.”

Linux’s own timer docs make exactly that distinction: **clock sources** provide a monotonically increasing time base, while **clock event devices** generate interrupts for periodic ticks, per-CPU accounting, profiling, and high-resolution next-event delivery. ([Kernel Documentation][2])

## Big picture call flow

At a high level, the scheduler/timer-related path during early boot is roughly:

```text
start_kernel()
  -> sched_init()
  -> ... interrupt/softirq foundations ...
  -> hrtimers_init()
  -> timekeeping_init()
  -> time_init()          [arch-specific late timer/hardware hookup]
  -> ... rest_init()
  -> first scheduling / idle loop / normal timer interrupts
```

That ordering matters: the kernel first creates the **data structures** needed to schedule work, then initializes the **software timer infrastructure**, then initializes the **actual notion of time** and the architecture-specific timer hardware hookup. ([GitHub][1])

## 1. What `sched_init()` is really doing

`sched_init()` is the point where Linux turns “a single boot CPU running one thread” into “a kernel that knows how to represent runnable work.” It lives in `kernel/sched/core.c`, which is explicitly the “Core kernel CPU scheduler code.” That file defines the per-CPU **runqueue** object, `struct rq`, as `DEFINE_PER_CPU_SHARED_ALIGNED(struct rq, runqueues)`, which is the scheduler’s central per-CPU state. ([GitHub][3])

The most important idea is that Linux scheduling is **per-CPU first**. Each CPU gets its own runqueue, and that runqueue will hold the currently running task, the idle task, and scheduler-class-specific structures such as the CFS runqueue and real-time state. `sched_init()` is where those runqueue structures are initialized into a known state before normal scheduling begins. That design is why later scheduling decisions are mostly local to a CPU, with migrations as a separate concern. ([GitHub][3])

Conceptually, `sched_init()` does four big things:

* initializes each CPU’s runqueue and its lock,
* binds the initial tasking state to the boot CPU,
* initializes scheduler classes and accounting structures,
* prepares later timer-driven callbacks like per-task `task_tick()` processing.

You can see the last point in the scheduler core itself: when high-resolution scheduling ticks are enabled, the scheduler uses an hrtimer callback that locks the runqueue, updates the runqueue clock, and calls the current scheduling class’s `task_tick()` method. ([GitHub][3])

## 2. What the scheduler needs before it can actually preempt tasks

Even after `sched_init()`, Linux still does **not** immediately behave like a fully live multitasking system. The scheduler has its core structures, but it still needs:

* interrupts and softirqs,
* timer infrastructure,
* a stable time source,
* later, actual runnable kernel threads.

That is why `start_kernel()` does not jump straight from `sched_init()` to “time slice somebody.” Instead, it keeps building the environment the scheduler depends on. The file-level early-boot invariant in `init/main.c` makes this explicit: until that early state is cleared, Linux still assumes IRQs must remain disabled. ([GitHub][4])

## 3. Where timer initialization splits into two worlds

Linux timer bring-up is easier to understand if you split it into:

* **software timer frameworks**
* **hardware time / event hookup**

The software side includes the hrtimer subsystem and softirq plumbing. The hardware side includes the selected clocksource, clockevent devices, and architecture-specific `time_init()` logic. Linux’s timer docs describe this separation very clearly: the **clocksource** side gives read access to time, while the **clockevent** side schedules interrupts for jiffies updates, local `update_process_times`, profiling, and next-event delivery. ([Kernel Documentation][2])

## 4. `hrtimers_init()`: setting up high-resolution software timers

`hrtimers_init()` initializes the high-resolution timer subsystem. In mainline, its body includes:

* preparing the current CPU’s hrtimer state,
* marking that CPU’s hrtimer state as started,
* and registering the **HRTIMER_SOFTIRQ** handler.

The snippet returned from the kernel source shows: `hrtimers_prepare_cpu(smp_processor_id()); hrtimers_cpu_starting(smp_processor_id()); open_softirq(HRTIMER_SOFTIRQ, ...)`. ([GitHub][5])

That means `hrtimers_init()` is not “starting the hardware timer” yet. It is building the **software machinery** for precise timers:

* per-CPU hrtimer bases,
* callback infrastructure,
* deferred processing path via softirq.

The kernel timer docs explain why this exists: hrtimers are designed around **time-ordered enqueueing** and nanosecond-based operation, not just the old timer-wheel tick model. ([Kernel Documentation][2])

## 5. Why the scheduler cares about hrtimers

The scheduler can use hrtimers for more accurate preemption points. In `kernel/sched/core.c`, when `CONFIG_SCHED_HRTICK` is enabled, the code explicitly says it uses **HR-timers to deliver accurate preemption points**. The hrtick callback runs in hardirq context, locks the runqueue, updates the runqueue clock, and calls the current task’s scheduler-class `task_tick()` method. ([GitHub][3])

So the relationship is:

* **generic timer subsystem** provides a precise callback mechanism,
* **scheduler** uses that mechanism when it wants precise preemption timing.

That is why timer initialization and scheduler initialization are tightly related but still separate. The scheduler does not own the timer subsystem; it consumes it. ([GitHub][3])

## 6. `timekeeping_init()`: establishing the kernel’s actual notion of time

`timekeeping_init()` is where Linux sets up the core **timekeeper**. In `kernel/time/timekeeping.c`, that function builds the initial `struct timekeeper` state, and internally it uses `tk_setup_internals()` to attach the active clocksource and compute the conversion parameters from hardware cycles to nanoseconds. The code comments for `tk_setup_internals()` explicitly say it “calculates a fixed cycle/nsec interval for a given clocksource.” ([GitHub][6])

This is one of the most important conceptual points in the whole boot path:

* the scheduler needs time,
* but “time” is not just an incrementing counter,
* Linux must first choose and configure a **clocksource**,
* then compute how to convert hardware cycles into nanoseconds accurately.

That is what `timekeeping_init()` is doing. It creates the kernel’s stable internal time base for monotonic and realtime clocks. The broader timekeeping docs then build on this with APIs like `ktime_get()`, `ktime_get_real()`, and related accessors. ([GitHub][6])

## 7. What `tk_setup_internals()` actually means

The timekeeping source is very revealing here. `tk_setup_internals()` stores the selected clocksource into the timekeeper’s read bases, captures the current cycle value, computes `cycle_interval`, `xtime_interval`, `raw_interval`, sets shift/mult factors, and resets NTP-related error fields. In plain language, it is building the conversion model:

```text
hardware cycles -> scaled nanoseconds -> kernel time values
```

Without that, the scheduler cannot do accurate time-slice accounting, sleep expiration, or precise timeout handling, because all of those ultimately need a coherent time base. ([GitHub][7])

## 8. `time_init()`: architecture-specific timer hookup

After `timekeeping_init()`, `start_kernel()` calls `time_init()`. This is the architecture-specific phase that hooks the generic time framework to the platform’s actual timer and clockevent hardware. The mainline `init/main.c` snippet shows `timekeeping_init(); time_init();` in that order, and Linux’s timer docs explain why: after the generic timekeeper exists, the architecture-specific code can register and select clock event devices used for periodic tick, per-CPU local timing, and high-resolution next events. ([GitHub][1])

On x86, this is where the platform-specific time code finalizes the relationship with devices such as LAPIC timer, HPET, TSC-deadline mechanisms, and other clockevent/clocksource choices. The exact hardware path depends on architecture and config, but the role is the same: connect the generic framework to the machine. ([Kernel Documentation][2])

## 9. How the periodic scheduler tick fits in

The classic scheduler picture is “timer interrupt fires, scheduler accounting happens.” Linux’s timer docs still describe that basic mechanism: clock event devices can be assigned to support the **system global periodic tick** for jiffies and **per-CPU local update_process_times**, profiling, and next-event functionality. ([Kernel Documentation][2])

That periodic or event-driven interrupt eventually feeds into scheduler accounting:

* update CPU time consumed by the current task,
* decrement or reevaluate time slice / virtual runtime state,
* run `task_tick()` for the current scheduler class,
* possibly set `TIF_NEED_RESCHED` so a reschedule happens on return from interrupt.

The exact call path differs by kernel config and timer mode, but conceptually that is how “timer drives scheduler fairness and preemption.” ([Kernel Documentation][2])

## 10. Why `softirq_init()` matters for timers

Even though your question is about scheduler/timer init, it is worth calling out softirqs because timer delivery is split between hardirq and deferred work. `hrtimers_init()` explicitly opens `HRTIMER_SOFTIRQ`, which means part of hrtimer processing is intentionally deferred into softirq context rather than done entirely in the immediate interrupt handler. ([GitHub][5])

That split exists because Linux wants interrupt handlers to stay short and deterministic. So timer expiry can involve:

* minimal hardirq-side bookkeeping,
* followed by deferred processing in softirq context,
* which then wakes tasks, runs callbacks, or triggers rescheduling paths.

This matters because the scheduler is tightly coupled to wakeups and timeout expiry. ([GitHub][5])

## 11. How the runqueue clock ties timekeeping to scheduling

One subtle but very important bridge is the **runqueue clock**. In the scheduler code, the hrtick path calls `update_rq_clock(rq)` before invoking `task_tick()`. That tells you the scheduler does not directly consume “wall clock time”; it maintains per-runqueue timing/accounting derived from the kernel’s timing infrastructure. ([GitHub][3])

So the dependency chain is:

```text
clocksource/timekeeper
   -> timer/clockevent delivery
      -> scheduler tick / hrtick callback
         -> update_rq_clock()
            -> scheduler-class task_tick()
```

That is the cleanest way to understand how `start_kernel()`’s time and scheduler calls fit together. ([GitHub][3])

## 12. What is initialized first: timer or scheduler?

In terms of *core structures*, the scheduler comes first: `start_kernel()` sets up scheduling structures with `sched_init()` before later initializing the timekeeping path. In terms of *useful runtime behavior*, the scheduler cannot really function as a preemptive, timer-driven scheduler until the timekeeping and clockevent side is up. ([GitHub][1])

So the answer is:

* **scheduler structures first**
* **time frameworks next**
* **actual timer-driven scheduling behavior after that**

That ordering avoids circular dependency. The scheduler needs timers to run normally, but the timer callbacks themselves eventually call into scheduler code. ([GitHub][1])

## 13. What changes after `rest_init()`

Even after all this initialization, Linux still is not “fully live” until `rest_init()` creates the first real kernel threads and enters the normal scheduling world. Before that, much of boot is still single-threaded initialization. After that, the initialized scheduler and timer infrastructure start serving real concurrency. ([GitHub][1])

## A compact diagram

```text
start_kernel()
  |
  +-- sched_init()
  |     +-- init per-CPU runqueues
  |     +-- init scheduler classes/accounting
  |     +-- prepare scheduler core state
  |
  +-- softirq / interrupt foundations
  |
  +-- hrtimers_init()
  |     +-- init per-CPU hrtimer bases
  |     +-- start hrtimer CPU state
  |     +-- register HRTIMER_SOFTIRQ
  |
  +-- timekeeping_init()
  |     +-- build core timekeeper
  |     +-- choose/setup clocksource internals
  |     +-- compute cycles->ns conversion
  |
  +-- time_init()
  |     +-- arch/platform timer hookup
  |     +-- register/select clockevent devices
  |
  +-- later timer interrupts / hrtick callbacks
        +-- update_rq_clock()
        +-- sched_class->task_tick()
        +-- possible reschedule
```

That is the whole story in one view. ([GitHub][5])

## Best files to read next

For this topic, I’d read them in this order:

`init/main.c` → `kernel/sched/core.c` → `kernel/time/hrtimer.c` → `kernel/time/timekeeping.c` → your architecture’s `time_init()` implementation.

That sequence follows the actual dependency chain you asked about. ([GitHub][1])

The next useful deep dive is to trace one concrete path end-to-end:

**“a timer interrupt arrives → how does Linux update time and decide whether to reschedule?”**

[1]: https://github.com/torvalds/linux/blob/master/init/main.c?utm_source=chatgpt.com "linux/init/main.c at master · torvalds/linux"
[2]: https://docs.kernel.org/timers/highres.html?utm_source=chatgpt.com "High resolution timers and dynamic ticks design notes"
[3]: https://github.com/torvalds/linux/blob/master/kernel/sched/core.c?utm_source=chatgpt.com "linux/kernel/sched/core.c at master · torvalds/linux"
[4]: https://github.com/torvalds/linux/blob/master/init/main.c "linux/init/main.c at master · torvalds/linux · GitHub"
[5]: https://github.com/torvalds/linux/blob/master/kernel/time/hrtimer.c?utm_source=chatgpt.com "linux/kernel/time/hrtimer.c at master"
[6]: https://github.com/torvalds/linux/blob/master/kernel/time/timekeeping.c?utm_source=chatgpt.com "linux/kernel/time/timekeeping.c at master"
[7]: https://github.com/torvalds/linux/blob/master/kernel/time/timekeeping.c "linux/kernel/time/timekeeping.c at master · torvalds/linux · GitHub"
