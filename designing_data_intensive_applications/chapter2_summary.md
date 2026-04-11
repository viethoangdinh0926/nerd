Perfect—this is where Chapter 2 gets *really* powerful. We’ll go beneath the surface and treat data models like **systems internals**, similar to how you’ve been learning the Linux kernel.

---

# 🧠 Chapter 2 Deep Dive: Internals

We’ll go layer by layer:

1. **Physical storage (how data actually sits on disk)**
2. **Query execution (how your query runs)**
3. **Joins & distributed pain**
4. **Document vs relational under the hood**
5. **Schema evolution & encoding**
6. **Real-world system design implications**

---

# 🧱 1. Relational Model Internals

## 🗄️ How rows are stored

In systems like **PostgreSQL**:

### Row layout (simplified)

```
| header | column1 | column2 | column3 | ... |
```

* Stored in **pages (usually 8KB)**
* Multiple rows per page
* Each row has:

  * tuple header (visibility, transaction info)
  * actual column values

### Key concept: **MVCC (Multi-Version Concurrency Control)**

👉 Instead of updating rows in-place:

* DB creates **new versions**
* Old versions stay until cleaned (VACUUM)

### Why this matters:

* Reads don’t block writes
* Enables snapshot isolation

---

## 🔍 How indexes work (B-Trees)

Most relational DBs use **B-Trees**:

* Sorted structure
* Logarithmic lookup: `O(log n)`

### Internally:

* Root → internal nodes → leaf nodes
* Leaf nodes contain **pointers to rows**

👉 Important:

* Index ≠ data
* It’s a **separate structure**

---

# ⚙️ 2. Query Execution Pipeline

When you run:

```sql
SELECT * FROM users WHERE age > 30;
```

### Step-by-step:

1. **Parser**

   * SQL → AST (Abstract Syntax Tree)

2. **Planner / Optimizer**

   * Chooses:

     * index scan vs full scan
     * join order
     * algorithms

3. **Executor**

   * Actually runs the plan

---

## 🧠 Example Execution Plans

### Full table scan

* Reads every row
* Cheap for small tables

### Index scan

* Uses B-tree
* Faster if selective

👉 The optimizer decides based on:

* statistics (cardinality, distribution)

---

# 🔗 3. Join Algorithms (critical for systems design)

## 🟦 Nested Loop Join

```
for each row in A:
    for each row in B:
        check match
```

* Simple
* Very slow: O(n²)

---

## 🟩 Hash Join

* Build hash table on smaller table
* Probe with larger table

```
hash(B)
for row in A:
    lookup in hash(B)
```

* Much faster: ~O(n)

---

## 🟨 Sort-Merge Join

* Sort both tables
* Merge like merge-sort

---

## 🚨 Why joins break in distributed systems

Across nodes:

* Data is **not co-located**
* Requires:

  * network shuffle
  * massive data movement

👉 This is why:

* NoSQL avoids joins
* Or pushes joins to application

---

# 🧩 4. Document Model Internals

Let’s use **MongoDB**

## 📦 Storage (BSON)

Documents stored as:

```
length | field1 | field2 | ...
```

* Binary JSON (BSON)
* Self-describing (field names included)

---

## ⚡ Key difference vs relational

### Relational:

```
users table
orders table
JOIN needed
```

### Document:

```json
{
  "user": "Viet",
  "orders": [...]
}
```

👉 Stored **together physically**

---

## 🧠 Locality advantage

* One disk read → full object
* No join needed

BUT:

👉 Writes become expensive if document grows
👉 Duplication risk

---

# ⚖️ 5. Embedding vs Referencing (deep trade-off)

## Embedding (document model)

```
User
 └── Orders (inside)
```

### Pros:

* Fast reads
* No joins

### Cons:

* Duplication
* Hard updates

---

## Referencing (relational style)

```
User → Order (foreign key)
```

### Pros:

* Normalized
* Easy updates

### Cons:

* Join cost

---

## 🔥 Deep insight

This is fundamentally:

> **Read optimization vs Write optimization**

---

# 🧬 6. Schema Evolution & Encoding

This is one of the most underrated parts of the book.

---

## 🧾 Problem: Data changes over time

Example:

```json
{"name": "Viet"}
```

Later:

```json
{"first_name": "Viet", "last_name": "Nguyen"}
```

---

## 🧠 Compatibility types

### Backward compatibility

* New code reads old data

### Forward compatibility

* Old code reads new data

---

## 🔧 Encoding formats

### JSON

* Human-readable
* Large, slow

### Avro / Protobuf

* Binary
* Schema-based
* Much smaller

---

## ⚙️ Why this matters

In distributed systems:

* Services run **different versions**
* Data must still be readable

👉 This is critical for:

* microservices
* event-driven systems (Kafka)

---

# 🌐 7. Real System Design Implications

## 🏗️ Example: E-commerce system

### Bad design:

* Fully normalized
* Heavy joins across services

👉 Result:

* Slow
* Hard to scale

---

### Good design:

* PostgreSQL → core data
* Redis → caching
* Elasticsearch → search

👉 Each model used for:

* its strength

---

# 🧠 8. Mental Model Upgrade (important)

After this chapter, you should think:

> “Where does this data live physically, and how will it be accessed?”

Not:

> “Which DB should I use?”

---

# 🧪 9. Advanced Self-Test

Try answering:

1. Why does MVCC improve read performance?
2. Why are B-tree indexes bad for write-heavy workloads?
3. Why does embedding improve locality?
4. Why do joins become network problems in distributed DBs?
5. Why is schema evolution harder in binary formats?

---

# 🚀 Next Level (based on your learning style)

I can take you deeper in *kernel-level style*:

### Option 1

👉 Walk through:

* PostgreSQL heap + index page layout
* Visibility map
* VACUUM internals

### Option 2

👉 Build a **mini database engine in Python**

* row store
* index
* query executor

### Option 3

👉 Generate **knowledge graph nodes (.md)**
for your visualization system

---

Just tell me what direction you want:

* “Postgres internals deep dive”
* “Build mini DB”
* “Continue Chapter 3 (Storage & Retrieval)”

and we’ll keep going 🔥
