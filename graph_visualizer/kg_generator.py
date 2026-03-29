#!/usr/bin/env python3

import argparse
import json
import re
from collections import deque
from pathlib import Path

import networkx as nx


ARROWS = ["→", "->", "=>"]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def parse_relation_line(line: str):
    for arrow in ARROWS:
        if arrow in line:
            left, right = line.split(arrow, 1)
            return normalize(left), normalize(right)
    return None


def parse_target(text: str):
    m = re.match(r"^\[(\d+)\]\s*(.+)$", text)
    if m:
        return int(m.group(1)), normalize(m.group(2))
    return -1, normalize(text)


def parse_markdown_file(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = None
    summary_lines = []
    current_section = None

    for line in lines:
        if line.startswith("# ") and not title:
            title = normalize(line[2:])
            continue

        if line.startswith("## "):
            current_section = normalize(line[3:]).lower()
            continue

        if current_section == "summary":
            stripped = line.strip()
            if stripped == "---":
                current_section = None
                continue
            if stripped:
                summary_lines.append(stripped)

    if not title:
        title = path.stem

    relationships = []
    in_relationships = False

    for line in lines:
        if line.startswith("## "):
            in_relationships = normalize(line[3:]).lower() == "relationships"
            continue

        if not in_relationships:
            continue

        stripped = line.strip()
        if not stripped.startswith("-"):
            if stripped and not stripped.startswith("---"):
                in_relationships = False
            continue

        parsed = parse_relation_line(stripped[1:].strip())
        if not parsed:
            continue

        relation, target_text = parsed
        order, target = parse_target(target_text)

        relationships.append(
            {
                "relation": relation,
                "target": target,
                "order": order,
            }
        )

    return title, summary_lines, relationships


def build_graph(folder: Path):
    graph = nx.DiGraph()

    md_files = sorted(folder.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"No .md files found in {folder}")

    for md_file in md_files:
        title, summary_lines, relationships = parse_markdown_file(md_file)

        if title not in graph:
            graph.add_node(title, source_file=md_file.name, summary_lines=summary_lines)
        else:
            graph.nodes[title]["source_file"] = md_file.name
            graph.nodes[title]["summary_lines"] = summary_lines

        for rel in relationships:
            target = rel["target"]
            if target not in graph:
                graph.add_node(target, source_file="", summary_lines=[])

            graph.add_edge(
                title,
                target,
                relation=rel["relation"],
                order=rel["order"],
            )

    return graph


def choose_root(graph: nx.DiGraph, requested_root: str | None):
    if requested_root:
        if requested_root not in graph:
            raise ValueError(f'Root "{requested_root}" not found in graph')
        return requested_root

    roots = sorted(n for n in graph.nodes if graph.in_degree(n) == 0)
    if roots:
        return roots[0]
    return sorted(graph.nodes)[0]


def ordered_children(graph: nx.DiGraph, node: str):
    children = list(graph.successors(node))
    children.sort(
        key=lambda child: (
            graph.edges[node, child].get("order", -1) == -1,
            graph.edges[node, child].get("order", -1),
            child.lower(),
        )
    )
    return children


def build_children_map(graph: nx.DiGraph):
    return {node: ordered_children(graph, node) for node in graph.nodes}


def compute_levels(graph: nx.DiGraph, root: str):
    levels = {root: 0}
    q = deque([root])

    while q:
        node = q.popleft()
        for child in ordered_children(graph, node):
            if child not in levels:
                levels[child] = levels[node] + 1
                q.append(child)

    max_level = max(levels.values(), default=0)
    for node in graph.nodes:
        if node not in levels:
            max_level += 1
            levels[node] = max_level

    return levels


def sanitize_graphml(graph: nx.DiGraph):
    safe = nx.DiGraph()

    for node, attrs in graph.nodes(data=True):
        clean_attrs = {}
        for k, v in attrs.items():
            if isinstance(v, (str, int, float, bool)):
                clean_attrs[k] = v
            elif v is not None:
                clean_attrs[k] = str(v)
        safe.add_node(node, **clean_attrs)

    for u, v, attrs in graph.edges(data=True):
        clean_attrs = {}
        for k, val in attrs.items():
            if isinstance(val, (str, int, float, bool)):
                clean_attrs[k] = val
            elif val is not None:
                clean_attrs[k] = str(val)
        safe.add_edge(u, v, **clean_attrs)

    return safe



def generate_html(graph: nx.DiGraph, root: str, depth: int, title: str):
    cmap = build_children_map(graph)
    levels = compute_levels(graph, root)

    level_buckets = {}
    for node in graph.nodes:
        level_buckets.setdefault(levels.get(node, 0), []).append(node)

    for level_nodes in level_buckets.values():
        level_nodes.sort(key=str.lower)

    x_spacing = 260
    y_spacing = 170

    positions = {}
    for level, level_nodes in sorted(level_buckets.items()):
        count = len(level_nodes)
        start_x = -((count - 1) * x_spacing) / 2
        for idx, node in enumerate(level_nodes):
            positions[node] = {
                "x": start_x + idx * x_spacing,
                "y": level * y_spacing,
            }

    nodes = []
    for node, attrs in graph.nodes(data=True):
        summary_lines = attrs.get("summary_lines", []) or []
        pos = positions.get(node, {"x": 0, "y": 0})
        nodes.append(
            {
                "id": node,
                "label": node,
                "level": levels.get(node, 0),
                "source_file": attrs.get("source_file", ""),
                "summary_lines": summary_lines,
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
                "x": pos["x"],
                "y": pos["y"],
            }
        )

    edges = []
    for u, v, d in graph.edges(data=True):
        label = d.get("relation", "")
        order = d.get("order", -1)
        if order != -1:
            label += f" [{order}]"

        edges.append(
            {
                "id": f"{u}->{v}",
                "from": u,
                "to": v,
                "label": label,
                "title": f"{u} → {v}<br>relation: {d.get('relation', '')}"
                + (f"<br>order: {order}" if order != -1 else ""),
            }
        )

    template = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>__TITLE__</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #fafafa;
    }
    #toolbar {
      padding: 10px 14px;
      border-bottom: 1px solid #ddd;
      background: white;
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }
    #main {
      display: flex;
      width: 100%;
      height: calc(100vh - 58px);
      min-height: 0;
    }
    #net {
      flex: 1 1 auto;
      min-width: 0;
      background: white;
    }
    #details {
      width: 360px;
      border-left: 1px solid #ddd;
      background: #fcfcfc;
      padding: 16px;
      overflow: auto;
      user-select: text;
      -webkit-user-select: text;
      white-space: normal;
    }
    #details h2 {
      margin: 0 0 8px 0;
      font-size: 22px;
    }
    #details .meta {
      color: #444;
      font-size: 14px;
      margin-bottom: 6px;
    }
    #details .section-title {
      margin-top: 16px;
      margin-bottom: 8px;
      font-weight: bold;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #444;
    }
    #details .summary-line {
      margin: 0 0 8px 0;
      line-height: 1.45;
    }
    #details .empty {
      color: #666;
      line-height: 1.5;
    }
    button {
      border: 1px solid #bbb;
      background: white;
      padding: 8px 12px;
      border-radius: 8px;
      cursor: pointer;
    }
    button:hover {
      background: #f2f2f2;
    }
    .hint {
      color: #555;
      font-size: 14px;
    }
    code {
      background: #f3f3f3;
      padding: 1px 4px;
      border-radius: 4px;
    }
  </style>
</head>
<body>
  <div id="toolbar">
    <button onclick="expandAll()">Expand all</button>
    <button onclick="collapseAll()">Collapse all</button>
    <button onclick="fitGraph()">Fit</button>
    <span class="hint">Drag nodes freely in any direction. Click a node to expand/collapse it. Shift-click a node to show its details without toggling.</span>
  </div>

  <div id="main">
    <div id="net"></div>
    <aside id="details">
      <div class="empty">
        Click a node to see its details here.<br><br>
        You can highlight and copy text from this panel.
      </div>
    </aside>
  </div>

  <script>
    const ROOT = __ROOT__;
    const INIT_DEPTH = __DEPTH__;
    const nodesData = __NODES__;
    const edgesData = __EDGES__;
    const children = __CHILDREN__;
    const levels = __LEVELS__;

    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();
    const detailsEl = document.getElementById("details");

    const network = new vis.Network(
      document.getElementById("net"),
      { nodes, edges },
      {
        layout: {
          improvedLayout: false
        },
        physics: false,
        interaction: {
          hover: false,
          dragNodes: true,
          dragView: true,
          zoomView: true,
          navigationButtons: true,
          keyboard: true
        },
        nodes: {
          shape: "dot",
          size: 18,
          font: {
            size: 18
          }
        },
        edges: {
          arrows: {
            to: { enabled: true }
          },
          smooth: {
            enabled: true,
            type: "cubicBezier",
            roundness: 0.2
          },
          font: {
            size: 12,
            align: "middle"
          }
        }
      }
    );

    const nodeMap = new Map(nodesData.map(n => [n.id, n]));
    const hidden = new Set();
    let pointerMovedDuringDrag = false;

    function escapeHtml(text) {
      return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function renderDetails(id) {
      const node = nodeMap.get(id);
      if (!node) {
        detailsEl.innerHTML = '<div class="empty">Node details unavailable.</div>';
        return;
      }

      const summary = (node.summary_lines || [])
        .map(line => `<div class="summary-line">${escapeHtml(line)}</div>`)
        .join("");

      detailsEl.innerHTML = `
        <h2>${escapeHtml(node.label)}</h2>
        <div class="meta">in-degree: ${node.in_degree}</div>
        <div class="meta">out-degree: ${node.out_degree}</div>
        ${node.source_file ? `<div class="meta">file: <code>${escapeHtml(node.source_file)}</code></div>` : ""}
        <div class="section-title">Summary</div>
        ${summary || '<div class="empty">No summary available for this node.</div>'}
      `;
    }

    function syncEdges() {
      const visible = new Set(nodes.getIds());
      const wanted = edgesData.filter(e => visible.has(e.from) && visible.has(e.to));
      const wantedIds = new Set(wanted.map(e => e.id));

      for (const id of edges.getIds()) {
        if (!wantedIds.has(id)) {
          edges.remove(id);
        }
      }

      for (const e of wanted) {
        if (!edges.get(e.id)) {
          edges.add(e);
        }
      }
    }

    function relayout(shouldFit = false) {
      network.setData({ nodes: nodes, edges: edges });
      if (shouldFit) {
        setTimeout(() => {
          network.fit({
            animation: {
              duration: 250,
              easingFunction: "easeInOutQuad"
            }
          });
        }, 30);
      }
    }

    function showNode(id) {
      if (!nodes.get(id)) {
        const node = nodeMap.get(id);
        if (node) {
          nodes.add(node);
        }
      }
    }

    function descendantsOf(id) {
      const result = [];
      const stack = [...(children[id] || [])];
      const seen = new Set();

      while (stack.length) {
        const cur = stack.pop();
        if (seen.has(cur)) continue;
        seen.add(cur);
        result.push(cur);
        for (const child of (children[cur] || [])) {
          stack.push(child);
        }
      }

      return result;
    }

    function hideSubtree(id) {
      const desc = descendantsOf(id);
      for (const d of desc) {
        hidden.add(d);
        if (nodes.get(d)) {
          nodes.remove(d);
        }
      }
      syncEdges();
      relayout(false);
    }

    function expandOneLevel(id) {
      const directChildren = children[id] || [];
      for (const child of directChildren) {
        hidden.delete(child);
        showNode(child);
      }
      syncEdges();
      relayout(false);
    }

    function toggleNode(id) {
      const directChildren = children[id] || [];
      if (!directChildren.length) return;

      const hasVisibleChild = directChildren.some(child => nodes.get(child));
      if (hasVisibleChild) {
        hideSubtree(id);
      } else {
        expandOneLevel(id);
      }
    }

    function init() {
      for (const node of nodesData) {
        if ((levels[node.id] || 0) <= INIT_DEPTH) {
          nodes.add(node);
        } else {
          hidden.add(node.id);
        }
      }
      syncEdges();
      relayout(true);
      renderDetails(ROOT);
    }

    function expandAll() {
      hidden.clear();
      for (const node of nodesData) {
        showNode(node.id);
      }
      syncEdges();
      relayout(true);
    }

    function collapseAll() {
      for (const id of [...nodes.getIds()]) {
        if (id !== ROOT) {
          nodes.remove(id);
          hidden.add(id);
        }
      }
      syncEdges();
      relayout(true);
    }

    function fitGraph() {
      network.fit({
        animation: {
          duration: 250,
          easingFunction: "easeInOutQuad"
        }
      });
    }

    network.on("dragStart", function() {
      pointerMovedDuringDrag = false;
    });

    network.on("dragging", function() {
      pointerMovedDuringDrag = true;
    });

    network.on("dragEnd", function(params) {
      if (params.nodes && params.nodes.length) {
        for (const nodeId of params.nodes) {
          const pos = network.getPositions([nodeId])[nodeId];
          const stored = nodeMap.get(nodeId);
          if (stored && pos) {
            stored.x = pos.x;
            stored.y = pos.y;
          }
        }
      }
    });

    network.on("release", function(params) {
      const nodeId = params.pointer && params.pointer.DOM
        ? network.getNodeAt(params.pointer.DOM)
        : null;

      if (!nodeId) {
        pointerMovedDuringDrag = false;
        return;
      }

      if (pointerMovedDuringDrag) {
        pointerMovedDuringDrag = false;
        return;
      }

      renderDetails(nodeId);

      const shiftKey = !!(
        params.event &&
        (
          (params.event.srcEvent && params.event.srcEvent.shiftKey) ||
          params.event.shiftKey
        )
      );

      if (!shiftKey) {
        toggleNode(nodeId);
      }

      pointerMovedDuringDrag = false;
    });

    init();
  </script>
</body>
</html>"""

    return (
        template
        .replace("__TITLE__", json.dumps(title)[1:-1])
        .replace("__ROOT__", json.dumps(root))
        .replace("__DEPTH__", str(depth))
        .replace("__NODES__", json.dumps(nodes))
        .replace("__EDGES__", json.dumps(edges))
        .replace("__CHILDREN__", json.dumps(cmap))
        .replace("__LEVELS__", json.dumps(levels))
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate a collapsible interactive knowledge graph from markdown files."
    )
    parser.add_argument("folder", type=Path, help="Folder containing .md files")
    parser.add_argument("--root", type=str, default=None, help="Root node title")
    parser.add_argument("--depth", type=int, default=1, help="Initial visible depth")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./graph_output"),
        help="Output folder",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Collapsible Knowledge Graph",
        help="HTML title",
    )
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = build_graph(folder)
    root = choose_root(graph, args.root)

    html = generate_html(graph, root, args.depth, args.title)

    html_path = output_dir / "collapsible_graph.html"
    graphml_path = output_dir / "graph.graphml"

    html_path.write_text(html, encoding="utf-8")
    nx.write_graphml(sanitize_graphml(graph), graphml_path)

    print(f"Root: {root}")
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Saved HTML: {html_path}")
    print(f"Saved GraphML: {graphml_path}")


if __name__ == "__main__":
    main()
