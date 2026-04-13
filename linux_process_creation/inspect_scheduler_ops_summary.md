Excellent choice. `perf sched` is one of the best ways to **see scheduler behavior instead of only reading code**.

## What `perf sched` gives you

`perf sched` records scheduler trace events for a workload, then lets you inspect them with views like `latency`, `map`, `script`, `replay`, and `timehist`. The current man page specifically documents `record`, `latency`, and `map`, and the perf documentation also documents `timehist` as a scheduler-analysis view. ([man7.org][1])

The most useful mental model is:

```text
record  -> capture scheduler events
script  -> raw chronological trace
timehist -> per-event timeline with wait/sched-delay/run-time
latency -> per-task latency summary
map     -> compact CPU/task switch map
```

For learning the kernel, `timehist` is usually the best first stop because it shows when a task slept, woke up, waited on the runqueue, and actually ran. The perf docs describe it as showing wait time, scheduling delay, and run time for each scheduling event. ([Ubuntu Manpages][2])

## First, verify perf is available

Run:

```bash
perf --version
perf sched --help
```

If `perf sched` is installed, you should see the subcommands described in the manual. ([man7.org][1])

## Your first useful workflow

Start with a simple workload so the output is easy to reason about:

```bash
perf sched record -- sleep 1
perf sched timehist
```

That exact pattern is documented in the perf scheduler docs. ([man7.org][1])

What you are doing conceptually:

```text
sleep 1
  -> task blocks
  -> scheduler runs something else
  -> timer wakes sleep
  -> task becomes runnable
  -> task is scheduled again
```

`timehist` lets you see that chain in timestamps.

## A better learning example

Use a CPU-bound workload and a blocking workload side by side. For example:

```bash
perf sched record -- sh -c 'yes > /dev/null & pid1=$!; sleep 1; kill $pid1'
perf sched timehist
```

This will produce many scheduler events because `yes` stays runnable, while `sleep` blocks and wakes. The output will make the difference between:

* runnable but waiting,
* sleeping,
* running,

much more concrete.

## How to read `perf sched timehist`

The documented meaning is:

* **wait time**: time between a task being scheduled out and being scheduled in again
* **sched delay**: time between wakeup and actually getting CPU
* **run time**: how long it ran before scheduling out again. ([Ubuntu Manpages][2])

That maps nicely to kernel concepts:

```text
sleep/wakeup path:
  TASK_INTERRUPTIBLE or similar
      ↓ wakeup
  TASK_RUNNING
      ↓ enqueue on rq
  waits on runqueue
      ↓ pick_next_task()
  on_cpu = 1
```

So when `sched delay` is large, it often means:

```text
task woke up
but sat runnable on the runqueue
before the scheduler chose it
```

That is one of the best direct windows into scheduler operation.

## The three most useful views

### 1. `timehist`

Best for learning task life cycle event by event.

```bash
perf sched timehist
```

Use this to answer:

* When did the task wake?
* How long did it wait before getting CPU?
* How long did it run?

Documented in perf scheduler documentation. ([Ubuntu Manpages][2])

### 2. `latency`

Best for summarizing which tasks suffered the worst scheduling delays.

```bash
perf sched latency
```

The man page describes it as reporting per-task scheduling latencies and other scheduling properties. ([man7.org][1])

Use it to answer:

* Which task had the biggest wakeup-to-run delay?
* Are there outliers?
* Is one thread consistently starved?

### 3. `map`

Best for visually understanding context switches across CPUs.

```bash
perf sched map
```

The docs describe it as a textual context-switching outline, with columns for CPUs and short task markers. ([Ubuntu Manpages][2])

Use it to answer:

* Which CPU ran which task?
* Are tasks bouncing between CPUs?
* Is one CPU mostly idle?

## A practical lab sequence

### Lab 1: blocking task

```bash
perf sched record -- sleep 1
perf sched timehist
perf sched latency
```

What to notice:

* `sleep` spends most of its life blocked
* wakeup happens near the timer expiration
* scheduling delay should usually be small on an idle machine

### Lab 2: CPU-bound task

```bash
perf sched record -- yes > /dev/null
# stop it with Ctrl+C after a short time
perf sched timehist
```

What to notice:

* lots of runtime slices
* fewer true sleeps
* repeated re-entry to CPU

### Lab 3: CPU contention

```bash
perf sched record -- sh -c 'yes > /dev/null & yes > /dev/null & wait'
# stop after a few seconds with Ctrl+C
perf sched latency
perf sched map
```

What to notice:

* more runqueue waiting
* increased scheduling delay
* visible alternation between runnable tasks

### Lab 4: multi-threaded user program

Record a build or test run:

```bash
perf sched record -- make -j4
perf sched timehist
perf sched latency
```

This is useful because real workloads produce wakeup chains, CPU contention, and blocking on I/O or futexes.

## When to use `perf script`

If you want the lower-level chronological event stream:

```bash
perf script
```

`perf script` reads recorded traces and shows a detailed trace of the workload. ([man7.org][3])

This is useful when you want to correlate scheduler events directly rather than through the `sched` summaries.

## Why `perf sched` is better than only reading source

Reading `schedule()`, `try_to_wake_up()`, and CFS code tells you the rules. `perf sched` shows you the rules in motion:

* enqueue
* wakeup
* runqueue wait
* context switch
* CPU runtime

That is why it is so effective for learning.

## How this maps to kernel internals you’ve been studying

Here is the bridge from the tool to the code:

```text
perf sched record
  -> captures scheduler trace events

perf sched timehist
  -> reconstructs:
     sched-out to next sched-in    = wait time
     wakeup to sched-in            = scheduling delay
     sched-in to sched-out         = run time
```

Those correspond to the structures and fields we discussed:

```text
task_struct->__state   -> sleeping / runnable state transitions
task_struct->on_rq     -> waiting on runqueue
task_struct->on_cpu    -> currently executing
sched_entity           -> CFS placement and fairness
rq / cfs_rq            -> per-CPU queueing
```

The CFS design docs explain that runnable tasks are tracked in a time-ordered red-black tree, and the scheduler picks the leftmost eligible entity. ([man7.org][4])

## Caveat: overhead

Scheduler events can be very frequent. Recording them can create noticeable overhead, especially on busy systems. Brendan Gregg calls out that `perf sched` uses a dump-and-post-process approach and that scheduler events can occur at very high rates, increasing CPU, memory, and disk overhead. ([Brendan Gregg][5])

So for learning:

* keep the recording short
* use small workloads first
* avoid production machines unless you know the impact is acceptable

## Best starter commands to memorize

```bash
perf sched record -- sleep 1
perf sched timehist
perf sched latency
perf sched map
perf script
```

That set is enough to start building intuition about:

* sleep/wakeup,
* runqueue delay,
* context switches,
* CPU placement.

## What I recommend next

The best next step is a guided exercise where we take one `perf sched timehist` output and decode it line by line back into kernel behavior: “this task slept here, woke here, waited on rq here, ran here.”

[1]: https://man7.org/linux/man-pages/man1/perf-sched.1.html?utm_source=chatgpt.com "perf-sched(1) - Linux manual page"
[2]: https://manpages.ubuntu.com/manpages/bionic/man1/perf-sched.1.html?utm_source=chatgpt.com "perf-sched - Tool to trace/measure scheduler properties ..."
[3]: https://man7.org/linux/man-pages/man1/perf-script.1.html?utm_source=chatgpt.com "perf-script(1) - Linux manual page"
[4]: https://man7.org/linux/man-pages/man1/perf-timechart.1.html?utm_source=chatgpt.com "perf-timechart(1) - Linux manual page"
[5]: https://www.brendangregg.com/blog/2017-03-16/perf-sched.html?utm_source=chatgpt.com "perf sched for Linux CPU scheduler analysis"
