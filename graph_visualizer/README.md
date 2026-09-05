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

## 📝 Generate Markdown from GraphML

Use `kg_source_generator.py` to turn a folder that contains `graph.graphml` into source and summary `.md` files.

```bash
python kg_source_generator.py <folder-with-graphml> --output-dir <markdown-output-folder>
```

Example:

```bash
python kg_source_generator.py ./graph_output --output-dir ./exported_md
```

- `<folder-with-graphml>` must contain a valid `graph.graphml` file (the same file written by `kg_generator.py` or by the graph UI).
- `--output-dir` is required. It is created if it does not exist.
- Every node becomes two files: a source `.md` (title, summary reference, relationships) and a summary `.md` (node content).
- File names come from each node's `source_file` and `summary_file` attributes when present; otherwise they are derived from the node title.

Typical workflow after editing the graph in the browser:

1. Save changes so `graph.graphml` is updated (or replace `graph_output/graph.graphml` with the downloaded file).
2. Run `kg_source_generator.py` on that folder to regenerate markdown.

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
