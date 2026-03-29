# Kernel Threads Execution

## Type
concept

## Domain
systems

## Summary
- Represents execution of kernel-managed background threads after core initialization
- Runs workqueue threads to process deferred and asynchronous kernel tasks
- Executes memory reclaim threads to manage and free memory under pressure
- Runs RCU (Read-Copy-Update) threads to handle deferred synchronization and callbacks
- Performs scheduler load balancing across CPUs to distribute workload efficiently
- Enables continuous background maintenance of kernel subsystems
- Supports system stability and performance without direct user-space involvement

---

## Relationships
- runs -> [1] Workqueues
- runs -> [2] Memory Reclaim
- runs -> [3] RCU
- runs -> [4] Load Balancing
