# Knowledge Graph Generator

Generate an interactive, collapsible knowledge graph from Markdown files.

---

## 🚀 Usage

```bash
python kg_generator.py <folder>
```

Example:

```bash
python kg_generator.py ./notes
```

---

## 📁 Markdown Format

```md
# Node Title

## Summary
Line 1  
Line 2  

## Relationships
- performs -> [1] Child Node
```

---

## ✨ Features

- Collapsible graph UI
- Click node to expand/collapse
- Side panel with copyable summary
- Line-by-line summary display
- GraphML export

---

## 📤 Output

```
graph_output/
├── collapsible_graph.html
└── graph.graphml
```

---

## 📦 Requirements

```bash
pip install networkx
```

---

## 🧠 Notes

- `# Title` → node name  
- `## Summary` → shown in UI  
- `## Relationships` → edges  
- `[1], [2]` → optional ordering  
