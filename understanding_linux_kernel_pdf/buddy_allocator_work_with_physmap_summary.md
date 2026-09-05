Here’s the step-by-step interaction:

> **Buddy allocator chooses which physical pages you get.
> Physmap gives the kernel a usable virtual address for those pages.**

So one decides **which RAM**, the other decides **how kernel code accesses that RAM**.

---

# 1. Boot: kernel builds both systems

During early boot, kernel:

* detects physical RAM
* initializes zones and buddy free lists
* builds the direct mapping page tables for physmap

So after boot:

* **buddy allocator** knows which page frames are free
* **physmap** already maps those page frames into kernel virtual space

---

# 2. Free memory is tracked as `struct page`

Every physical page frame has metadata in `vmemmap`:

* flags
* refcount
* zone
* order/free-list state

Buddy allocator operates on these `struct page` entries, not raw addresses.

Conceptually:

```text
physical page frame <-> struct page <-> physmap virtual address
```

---

# 3. Allocation request comes in

Example:

```c
void *p = kmalloc(4096, GFP_KERNEL);
```

or

```c
struct page *page = alloc_pages(GFP_KERNEL, 0);
```

The request reaches the page allocator.

---

# 4. Buddy allocator selects a zone

Kernel first decides which zone to allocate from:

* `ZONE_NORMAL`
* `ZONE_DMA32`
* `ZONE_DMA`
* etc.

Then it looks in that zone’s buddy free lists.

---

# 5. Buddy allocator finds a free block

Each zone has free lists by order:

* order 0 = 1 page
* order 1 = 2 pages
* order 2 = 4 pages
* ...

If an exact-size block is unavailable, buddy finds a larger block and splits it.

Example for 1 page request:

```text
order 3 block (8 pages)
 -> split to order 2 + order 2
 -> split one order 2 to order 1 + order 1
 -> split one order 1 to order 0 + order 0
 -> return one order 0 page
```

At this point buddy has chosen actual **physical page frame(s)**.

---

# 6. Returned result is initially page-based

The allocator now has either:

* a `struct page *`
* or a PFN / physical page behind that `struct page`

For example:

```c
struct page *page = alloc_pages(...);
```

This identifies the physical memory, but kernel code usually wants a normal pointer.

---

# 7. Physmap provides the kernel virtual address

Because all RAM is already direct-mapped in physmap, kernel converts the allocated page into a virtual address.

Common helpers:

```c
void *v = page_address(page);
```

or equivalently, conceptually:

```c
virt = phys + PAGE_OFFSET
```

This works because page tables already map physmap.

So after buddy picks the physical page, physmap makes it immediately accessible as a kernel pointer.

---

# 8. Kernel uses the memory through physmap

Now the kernel can do ordinary memory operations:

```c
memset(v, 0, PAGE_SIZE);
```

or SLUB can carve objects from that page.

Important point:

* **buddy chose the page**
* **physmap made it usable**

Buddy does not hand back “special physmap memory.” It hands back physical pages that already happen to be visible in physmap.

---

# 9. For `kmalloc`, SLUB sits in the middle

With `kmalloc`, the path is usually:

```text
kmalloc
 -> SLUB/SLAB allocator
 -> if needed, ask buddy for one or more pages
 -> pages are accessed through physmap
 -> carve out object
 -> return object pointer
```

So for small objects:

* buddy allocates backing pages
* physmap gives virtual access to those pages
* SLUB manages sub-page objects inside them

---

# 10. Freeing memory goes the other way

When memory is freed:

* kernel may turn pointer back into page metadata
* reference counts and slab metadata are updated
* buddy gets the page back
* buddy checks whether its adjacent buddy is also free
* if yes, it merges upward

Physmap does not need to change here, because the direct mapping remains permanent.

That is important:

> **buddy allocation state changes; physmap mapping usually does not**

The page becomes free, but it is still mapped in physmap.

---

# 11. Why this split is useful

This division of labor is clean:

Buddy allocator:

* manages availability
* splits/merges pages
* controls fragmentation

Physmap:

* gives constant-time access to any RAM page
* avoids creating/removing mappings on every allocation
* lets allocated pages be used immediately

Without physmap, after buddy picked a page, kernel would need to set up a mapping before using it.

---

# 12. Concrete example

Suppose kernel needs one 4 KB page.

Step-by-step:

1. `alloc_pages(GFP_KERNEL, 0)` is called.
2. Buddy checks `ZONE_NORMAL` order-0 list.
3. No exact page is free, but an order-2 block is free.
4. Buddy splits order-2 into smaller buddies until one order-0 page remains.
5. That page corresponds to physical address `0x12345000`.
6. Kernel uses physmap to access it at something like:

   ```text
   PAGE_OFFSET + 0x12345000
   ```
7. Kernel now has a virtual pointer and can write into it.
8. Later, `__free_pages()` returns it.
9. Buddy merges it back if adjacent buddy pages are free.

---

# Final mental model

Think of it like this:

* **Buddy allocator = warehouse manager** deciding which storage blocks are free
* **Physmap = hallway map** that lets workers walk directly to any block

Buddy answers:

> Which page frames do I own right now?

Physmap answers:

> What pointer can I use to touch them?

---

# One-line summary

> **Buddy allocator selects and manages physical page frames, while physmap gives the kernel a permanent direct virtual mapping so those selected pages can be accessed immediately as normal pointers.**

If you want, I can next walk through the same interaction for `kmalloc(100)` specifically, including where SLUB fits in.
