# Collapsible Knowledge Graph (with Copyable Node Details)

This tool generates an interactive, collapsible knowledge graph from a folder of Markdown (`.md`) files.

Each node represents a concept, and relationships between nodes are visualized as a directed graph. Clicking a node reveals its details (including summary) in a **copyable side panel**.

---

## ✨ Features

- 🌳 Hierarchical, collapsible graph visualization
- 🖱 Click nodes to expand/collapse children
- 📄 Right-side panel shows node details (copyable text)
- 🧠 Parses structured Markdown into graph data
- 🔎 Summary displayed line-by-line
- 🔄 Expand all / Collapse all controls
- 📦 Exports GraphML for further analysis

---

## 📁 Expected Markdown Format

Each node should be defined in a `.md` file like this:

```md
# Node Title

## Summary
Line 1 of summary  
Line 2 of summary  

---

## Relationships
- performs -> [1] Child Node A
- performs -> [2] Child Node B
```

### Notes:
- `# Title` → becomes the node ID
- `## Summary` → shown in the UI (right panel)
- `## Relationships` → defines edges
- `[1]`, `[2]` → optional ordering of children

---

## 🚀 Usage

```bash
python interactive_knowledge_graph_copyable_panel.py <folder>
```

### Example:

```bash
python interactive_knowledge_graph_copyable_panel.py ./notes
```

---

## ⚙️ Options

```bash
--root <node>        Set custom root node
--depth <n>          Initial visible depth (default: 1)
--output-dir <dir>   Output directory (default: ./graph_output)
--title <string>     HTML page title
```

---

## 📤 Output

After running, you’ll get:

```
graph_output/
├── collapsible_graph.html   # Interactive UI
└── graph.graphml            # Graph data (for tools like Gephi)
```

---

## 🖥 How to Use the UI

- Click a node:
  - Expands/collapses its children
  - Shows details in the right panel

- Shift + Click a node:
  - Shows details without expanding/collapsing

- Right panel:
  - Fully selectable text (copy/paste supported)
  - Displays:
    - Node name
    - In/out degree
    - Source file
    - Summary (line-by-line)

- Toolbar buttons:
  - Expand all
  - Collapse all
  - Fit graph to screen

---

## 🧠 How It Works

1. Parses all `.md` files in the folder
2. Extracts:
   - Title → node
   - Summary → node metadata
   - Relationships → edges
3. Builds a directed graph using `networkx`
4. Generates an interactive HTML using `vis-network`
5. Adds a custom side panel for copyable content

---

## 📦 Dependencies

Install required package:

```bash
pip install networkx
```

No frontend setup required — the HTML uses CDN for visualization.

---

## 🛠 Tips

- Keep summaries concise for better readability
- Use consistent naming across nodes
- Avoid circular dependencies unless intentional
- Use ordering `[1], [2]` to control child layout

---

## 🔮 Possible Enhancements

- Search/filter nodes
- Highlight paths
- Editable graph UI
- Markdown rendering in summary
- Export to JSON
