Great — **SLUB** is the allocator you’ll actually interact with in modern Linux, so this is a very valuable deep dive.

---

# 🧠 What is SLUB?

**SLUB (the “unqueued slab allocator”)** is Linux’s **object allocator** built on top of the page allocator.

> 🔥 It allocates **small kernel objects efficiently** (structs, buffers, etc.)

Examples of objects:

* `task_struct`
* `inode`
* `dentry`
* `file`
* networking structures

---

# 🚀 Why SLUB exists

The buddy allocator gives you:

```text
pages (4KB, 2MB, etc.)
```

But kernel often needs:

```text
small objects (32B, 128B, 512B...)
```

SLUB solves this by:

```text
page → divided into many objects
```

---

# 🧩 Core concepts

## 1) Cache (`kmem_cache`)

The central structure:

```c
struct kmem_cache
```

Each cache manages **one type of object**.

Example:

```text
task_struct cache
inode cache
dentry cache
```

---

## 2) Slab

A **slab = one or more pages** used to store objects.

```text
slab = page(s) → split into objects
```

Example:

```text
1 page (4KB)
→ 64 objects of size 64B
```

---

## 3) Object

The smallest allocation unit.

```text
object = one allocated chunk
```

---

# 🧠 Memory layout inside a slab

Example:

```text
[ obj ][ obj ][ obj ][ obj ][ obj ]...
```

SLUB avoids complex metadata — it stores minimal info.

Free objects are linked via pointers inside the objects themselves.

---

# 🔥 Key design difference (SLUB vs old SLAB)

Old SLAB:

* per-CPU queues
* complex metadata
* linked lists everywhere

SLUB:

* simpler
* fewer indirections
* better cache locality
* faster in practice

---

# 🚀 Allocation flow (step-by-step)

## Step 1 — Kernel requests object

Example:

```c
kmalloc(128)
```

or:

```c
kmem_cache_alloc(cache)
```

---

## Step 2 — Find cache

Kernel picks a cache:

```text
size 128 → kmalloc-128 cache
```

Caches are pre-created for common sizes.

---

## Step 3 — Try per-CPU slab (fast path)

Each CPU has a **current slab**:

```text
cpu_slab
```

If there is a free object:

```text
→ pop object
→ return immediately
```

🔥 This is extremely fast (no locking)

---

## Step 4 — If slab is full → get new slab

If current slab is exhausted:

1. allocate new page(s) from buddy allocator
2. initialize slab
3. attach to CPU
4. return object

---

## Step 5 — Return object

Object pointer is returned to kernel.

---

# 🔄 Free flow

When freeing:

```c
kfree(ptr)
```

---

## Step 1 — Find cache from pointer

SLUB determines:

```text
which slab this object belongs to
```

---

## Step 2 — Add to free list

Object is added back to slab’s free list.

Often:

```text
ptr->next = freelist
freelist = ptr
```

---

## Step 3 — Slab may become empty

If all objects are free:

* slab may be returned to buddy allocator
* or kept for reuse

---

# 🧠 Per-CPU optimization (critical)

Each CPU has:

```c
struct kmem_cache_cpu
```

This contains:

```text
freelist pointer
current slab
```

This allows:

```text
allocation = lock-free
```

Most allocations never touch global structures.

---

# 🔥 Why SLUB is fast

Key reasons:

### 1. Per-CPU freelist

No locking in fast path

---

### 2. Minimal metadata

No heavy bookkeeping

---

### 3. Cache locality

Objects from same slab are close in memory

---

### 4. Avoids fragmentation

Objects are tightly packed

---

# 🧩 Interaction with buddy allocator

SLUB does NOT manage physical pages directly.

Instead:

```text
SLUB → requests pages → buddy allocator
```

So:

```text
small alloc → SLUB
large alloc → buddy
```

---

# 🐧 Example sizes

Common kmalloc caches:

```text
kmalloc-32
kmalloc-64
kmalloc-128
kmalloc-256
kmalloc-512
kmalloc-1024
...
```

---

# 🔥 Debugging features

SLUB can enable debugging:

```text
slub_debug
```

Features:

* red zones
* poisoning
* double-free detection
* use-after-free detection

Very useful for kernel debugging.

---

# 🎯 Real-world example

Allocating a `task_struct`:

```text
kmem_cache_alloc(task_struct_cache)
```

Flow:

```text
CPU freelist → object
(no lock, no page alloc)
```

Very fast.

---

# 🧠 Mental model

Think:

```text
buddy allocator = gives pages
SLUB = slices pages into objects
```

---

# 🎯 One-line summary

> SLUB is a per-CPU optimized slab allocator that divides pages into small objects and provides fast, mostly lock-free allocation for kernel data structures.

---

# 🚀 If you want next level

I can walk you through:

* `kmem_cache` structure fields (line-by-line)
* SLUB fast path assembly
* `kmalloc` → `slab_alloc` call chain
* memory corruption detection internals

That’s where things get really interesting.
