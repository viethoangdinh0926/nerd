Great question—NUMA doesn’t change the *idea* of physmap, but it strongly influences **how it’s laid out and used**.

> **Physmap is still a single linear mapping of all RAM, but that RAM is partitioned into NUMA nodes, and the kernel uses that structure for locality-aware allocation.**

---

# 🧠 1. Recap: what physmap does

Physmap:

```text
virtual = physical + offset
```

* one contiguous virtual region
* maps *all* physical memory

---

# 🔑 2. What NUMA introduces

In NUMA systems:

* RAM is split into **nodes**
* each node is closer to a specific CPU

```text
CPU 0 ↔ Node 0 RAM (fast)
CPU 1 ↔ Node 1 RAM (fast)
CPU 0 ↔ Node 1 RAM (slow)
```

---

# 🧭 3. How physmap looks with NUMA

![Image](https://images.openai.com/static-rsc-4/iIjMacSKkEXROd5LZLNpmYsxtTMB4mmRvDIyCeTNYLi571pfkMhWK8prR_DbFYtL0NdAw4A8KdIBp_gAEGXDnbinDvWiujWqLGtKVyUPQBngXyZMVU9B-Ca2fGXv_qJDxKYY0QlmhdgYavTTqJyOe1qdhowR9cjrf741aclJqBBEtt9u30Au7HJ7bdDTjItE?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/30W0Xf8rdmWYTPCPZIzTPwYUIpo-yQpaJtl6WOvLHSpvyVeSFw2igUdaGQbp7shmrQHIFuCEOYl3LYkgtz6xdKLYZYwE3rS8i_VwdG3pK1F6UmPGbaVJ9Pnls5tNGNGtL_VNIsFfkkAA4VJdFh2g3AgK1S6cYDHq2bBMHkyrpuZZBZjUa-YQiWJz9WF-r5TX?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/0s3isCqtcYOqpf0FQjNP8oD1wF0aJCYBrCiPKYMMdiS19wWZvfB_x4A6XT8BIAS9L9s1wTmTbtf67jnMxYdGQW2UwgCHFX6_DIseAZ9zFoqbV0Ya1_7VRpYUZrLSNXqe1IT_HPWANQmS21FXG9RflWnf9p83LPoSbcgsYlpWt_mTeBjT0NWl66amnFlI6UV9?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/Bx2Z35VIvq9Xhw_BhW_y0XjoZcrlnwg-kJsN2nz5ecI2_f6ewPX5uVLQZq14lHiTTQdGtsj8JK2IU9IL-PltqHE5KbBqzW3l6jPgYE-caWDWecBjyUBxCWCjOPrrw_1nSIfgalBa9U_D9sKkjLbnwLoUUIMJV_mliJBBkkNFSG5TBNHQUGMDUP6GLkddj3E7?purpose=fullsize)

Even with NUMA:

```text
physmap virtual space:
  [ Node 0 RAM ][ Node 1 RAM ][ Node 2 RAM ] ...
```

👉 Still **one contiguous virtual range**

But physically:

```text
Node 0 → physical range A
Node 1 → physical range B
Node 2 → physical range C
```

---

# ⚙️ 4. How kernel builds physmap with NUMA

During boot:

1. Firmware provides memory map (E820 + NUMA topology)
2. Kernel sees:

```text
Node 0: 0x0000 → 0x3fffffff
Node 1: 0x40000000 → 0x7fffffff
```

3. Kernel builds page tables:

```text
virt A → phys Node 0
virt B → phys Node 1
```

👉 All stitched into one linear mapping

---

# 🧩 5. What changes because of NUMA

## 🟦 1) Physical memory is discontinuous

* nodes may not be adjacent
* holes may exist

Physmap handles this by:

* leaving unmapped gaps or
* mapping sparse regions

---

## 🟩 2) Zones become per-node

Instead of:

```text
ZONE_NORMAL
```

You get:

```text
Node 0 → ZONE_NORMAL
Node 1 → ZONE_NORMAL
```

👉 Buddy allocator works per node

---

## 🟨 3) Allocation becomes NUMA-aware

When kernel allocates:

```c
kmalloc(...)
```

It prefers:

```text
local node → physmap region corresponding to that node
```

---

## 🟥 4) Same physmap, different latency

Important:

```text
same virtual address pattern
BUT different physical nodes → different access cost
```

👉 Physmap hides topology, but hardware does not

---

## 🟪 5) Per-CPU locality

Each CPU:

* prefers its node’s pages
* accesses physmap addresses that map to local RAM

---

# ⚡ 6. Example

Suppose:

```text
Node 0: phys 0x00000000 – 0x3fffffff
Node 1: phys 0x40000000 – 0x7fffffff
```

Physmap:

```text
ffff888000000000 → Node 0
ffff888040000000 → Node 1
```

Kernel accesses:

```c
ptr = phys_to_virt(0x40000000);
```

👉 lands in Node 1 region of physmap

---

# 🔍 7. Important insight

> Physmap does NOT enforce locality
> The allocator (NUMA-aware buddy) does

---

# 🧠 8. What physmap hides vs exposes

## Hides:

* complexity of mapping
* need for remapping

## Does NOT hide:

* memory latency differences
* NUMA topology

---

# ⚖️ 9. Summary of effects

| Aspect          | Without NUMA | With NUMA          |
| --------------- | ------------ | ------------------ |
| physmap         | linear       | still linear       |
| physical layout | uniform      | segmented by node  |
| allocation      | global       | per-node preferred |
| latency         | uniform      | variable           |

---

# 🧠 10. Mental model

```text
physmap = one long street
NUMA = different neighborhoods on that street
```

* addresses look continuous
* but travel time differs

---

# ✅ Final takeaway

* Physmap remains:

  * linear
  * global
* NUMA affects:

  * how physical memory is grouped
  * how allocations are chosen
* Kernel relies on:

  * NUMA-aware allocator to preserve locality

---

# 🔥 One-line summary

> **NUMA doesn’t change physmap’s linear mapping, but it divides the underlying physical memory into node-specific regions, making allocation and access locality-aware even though the virtual view remains contiguous.**

---

If you want, we can go deeper into:

* how zonelists encode NUMA preference
* how `alloc_pages_node()` works internally
* or how remote memory access penalty shows up in real workloads
