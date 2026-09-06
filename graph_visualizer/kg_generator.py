#!/usr/bin/env python3

import argparse
import http.server
import json
import re
import socketserver
from collections import deque
from functools import partial
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


def parse_target(text: str, fallback_order: int):
    # Ignore explicit [1], [2], etc. — always use inferred order
    m = re.match(r"^\[(\d+)\]\s*(.+)$", text)
    if m:
        return fallback_order, normalize(m.group(2))
    return fallback_order, normalize(text)


def read_summary_from_reference(node_path: Path, summary_ref: str):
    ref = summary_ref.strip()
    if not ref:
        return []

    summary_path = (node_path.parent / ref).resolve()

    try:
        summary_path.relative_to(node_path.parent.resolve())
    except ValueError:
        raise ValueError(
            f"Summary file '{ref}' in '{node_path.name}' must stay within the same folder tree"
        )

    if not summary_path.exists():
        raise FileNotFoundError(
            f"Summary file '{ref}' referenced by '{node_path.name}' was not found"
        )

    if summary_path.suffix.lower() != ".md":
        raise ValueError(
            f"Summary file '{ref}' referenced by '{node_path.name}' must be a .md file"
        )

    return summary_path.read_text(encoding="utf-8").splitlines()


def parse_markdown_file(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = None
    summary_ref = None
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
                summary_ref = stripped
                break

    if not title:
        title = path.stem

    summary_lines = read_summary_from_reference(path, summary_ref or "")

    relationships = []
    in_relationships = False
    relationship_index = 0

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

        relationship_index += 1
        relation, target_text = parsed
        order, target = parse_target(target_text, fallback_order=relationship_index)

        relationships.append(
            {
                "relation": relation,
                "target": target,
                "order": order,
            }
        )

    return title, (summary_ref or ""), summary_lines, relationships



def build_graph(folder: Path):
    graph = nx.DiGraph()

    md_files = sorted(folder.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"No .md files found in {folder}")

    for md_file in md_files:
        title, summary_file, summary_lines, relationships = parse_markdown_file(md_file)

        if title not in graph:
            graph.add_node(
                title,
                source_file=md_file.name,
                summary_file=summary_file,
                summary_lines=summary_lines,
                source_path=str(md_file.resolve()),
            )
        else:
            graph.nodes[title]["source_file"] = md_file.name
            graph.nodes[title]["summary_file"] = summary_file
            graph.nodes[title]["summary_lines"] = summary_lines
            graph.nodes[title]["source_path"] = str(md_file.resolve())

        for rel in relationships:
            target = rel["target"]
            if target not in graph:
                graph.add_node(target, source_file="", summary_file="", summary_lines=[])

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
        summary_lines = attrs.get("summary_lines")
        if isinstance(summary_lines, list):
            clean_attrs["summary"] = "\n".join(str(line) for line in summary_lines)
        elif attrs.get("summary") is not None:
            clean_attrs["summary"] = str(attrs.get("summary"))

        for k, v in attrs.items():
            if k in {"summary_lines", "summary", "source_path"}:
                continue
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




def slugify_filename(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", title.strip())
    slug = slug.strip("._")
    return slug or "node"


def make_unique_title(graph: nx.DiGraph, desired: str):
    base = normalize(desired)
    if not base:
        raise ValueError("Node title cannot be empty")
    if base not in graph:
        return base

    suffix = 2
    while f"{base} ({suffix})" in graph:
        suffix += 1
    return f"{base} ({suffix})"

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
    max_label_chars = 24
    for node, attrs in graph.nodes(data=True):
        summary_lines = attrs.get("summary_lines", []) or []
        pos = positions.get(node, {"x": 0, "y": 0})
        short_label = node if len(node) <= max_label_chars else node[: max_label_chars - 1].rstrip() + "…"
        nodes.append(
            {
                "id": node,
                "label": short_label,
                "full_label": node,
                "short_label": short_label,
                "title": node,
                "level": levels.get(node, 0),
                "source_file": attrs.get("source_file", ""),
                "source_path": attrs.get("source_path", ""),
                "summary_file": attrs.get("summary_file", ""),
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
                "relation": d.get("relation", ""),
                "order": order,
                "label": label,
                "full_label": label,
                "title": f"{u} → {v}<br>relation: {d.get('relation', '')}"
                + (f"<br>order: {order}" if order != -1 else ""),
                "base_color": "#848484",
                "incoming_color": "#2563eb",
                "outgoing_color": "#dc2626",
            }
        )

    template = r"""<!DOCTYPE html>
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
    #splitter {
      width: 8px;
      cursor: col-resize;
      background: linear-gradient(to right, #f3f3f3, #e3e3e3, #f3f3f3);
      border-left: 1px solid #ddd;
      border-right: 1px solid #ddd;
      flex: 0 0 auto;
    }
    #splitter:hover {
      background: linear-gradient(to right, #ececec, #d8d8d8, #ececec);
    }
    #details {
      width: 360px;
      min-width: 220px;
      max-width: 70vw;
      background: #fcfcfc;
      padding: 16px;
      overflow: auto;
      user-select: text;
      -webkit-user-select: text;
      white-space: normal;
      flex: 0 0 auto;
    }
    #details h2 {
      margin: 0 0 8px 0;
      font-size: 22px;
    }
    #details .panel-field {
      border: 1px solid #ddd;
      background: white;
      border-radius: 10px;
      padding: 12px;
      margin-top: 12px;
    }
    #details .meta-row {
      color: #444;
      font-size: 14px;
      margin-bottom: 6px;
      line-height: 1.45;
    }
    #details .meta-row:last-child {
      margin-bottom: 0;
    }
    #details .meta-label {
      font-weight: 700;
    }
    #details .section-title {
      margin-top: 0;
      margin-bottom: 10px;
      font-weight: bold;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #444;
    }
    #details .summary-markdown {
      line-height: 1.5;
      background: #000;
      color: #fff;
      padding: 12px;
      border-radius: 8px;
    }
    #details .summary-markdown > :first-child {
      margin-top: 0;
    }
    #details .summary-markdown > :last-child {
      margin-bottom: 0;
    }
    #details .summary-markdown h1,
    #details .summary-markdown h2,
    #details .summary-markdown h3,
    #details .summary-markdown h4,
    #details .summary-markdown h5,
    #details .summary-markdown h6 {
      margin-top: 1em;
      margin-bottom: 0.5em;
      font-weight: 700;
    }
    #details .summary-markdown p,
    #details .summary-markdown ul,
    #details .summary-markdown ol,
    #details .summary-markdown blockquote,
    #details .summary-markdown pre {
      margin-top: 0;
      margin-bottom: 12px;
    }
    #details .summary-markdown ul,
    #details .summary-markdown ol {
      padding-left: 22px;
    }
    #details .summary-markdown pre {
      overflow: auto;
      padding: 12px;
      border-radius: 8px;
      background: #f3f3f3;
      color: #000;
      white-space: pre-wrap;
      tab-size: 4;
    }
    #details .summary-markdown code {
      background: #f3f3f3;
      color: #000;
      padding: 1px 4px;
      border-radius: 4px;
      white-space: pre-wrap;
    }
    #details .summary-markdown pre code {
      background: transparent;
      padding: 0;
      border-radius: 0;
      white-space: pre;
    }
    #details .summary-markdown blockquote {
      padding-left: 12px;
      border-left: 4px solid #ddd;
      color: #555;
    }
    #details .summary-markdown hr {
      border: none;
      border-top: 1px solid #ddd;
      margin: 16px 0;
    }
    #details .summary-markdown table {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 14px;
      line-height: 1.5;
      overflow-x: auto;
      display: block;
      background: #000;
      color: #fff;
    }
    #details .summary-markdown thead {
      background: #111;
      color: #fff;
    }
    #details .summary-markdown th,
    #details .summary-markdown td {
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid #333;
      color: #fff;
    }
    #details .summary-markdown th {
      font-weight: 600;
      letter-spacing: 0.02em;
    }
    .node-image {
      max-width: 100%;
      height: auto;
      border-radius: 4px;
      object-fit: contain;
    }
    #details .summary-markdown tbody tr:nth-child(even) {
      background: #0a0a0a;
    }
    #details .summary-markdown tbody tr:hover {
      background: #111827;
    }
    #details .summary-markdown td + td,
    #details .summary-markdown th + th {
      border-left: 1px solid #222;
    }
    #details .summary-markdown {
      overflow-x: auto;
    }
    #details .summary-markdown thead th {
      position: sticky;
      top: 0;
      z-index: 1;
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
    button.danger {
      border-color: #f1a0a0;
      color: #991b1b;
    }
    button.danger:hover {
      background: #fef2f2;
    }
    button.btn-cancel {
      border-color: #dc2626;
      background: #dc2626;
      color: #fff;
    }
    button.btn-cancel:hover {
      background: #b91c1c;
    }
    button.btn-save {
      border-color: #2563eb;
      background: #2563eb;
      color: #fff;
    }
    button.btn-save:hover {
      background: #1d4ed8;
    }
    .app-notice {
      display: none;
      padding: 10px 14px;
      border-bottom: 1px solid #a7f3d0;
      background: #ecfdf5;
      color: #065f46;
      font-size: 14px;
      line-height: 1.45;
    }
    .app-notice.visible {
      display: block;
    }
    .app-notice.error {
      background: #fef2f2;
      border-bottom-color: #fecaca;
      color: #991b1b;
    }
    .hint {
      color: #555;
      font-size: 14px;
    }

    .form-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }
    .form-grid label {
      font-size: 14px;
      color: #222;
      display: block;
    }
    .form-grid input,
    .form-grid textarea,
    .form-grid select {
      width: 100%;
      margin-top: 6px;
      border: 1px solid #bbb;
      border-radius: 8px;
      padding: 8px 10px;
      font: inherit;
      background: #fff;
    }
    .form-grid textarea {
      min-height: 140px;
      resize: vertical;
    }
    .dialog-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 14px;
    }
    .modal-overlay {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 30;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background: rgba(0,0,0,0.35);
    }
    .modal-overlay.open {
      display: flex;
    }
    .dialog-card {
      padding: 18px;
      background: #fff;
      border: 1px solid #ccc;
      border-radius: 14px;
      width: min(720px, 92vw);
      max-height: calc(100vh - 48px);
      overflow: auto;
      box-shadow: 0 18px 50px rgba(0,0,0,0.2);
    }
    .dialog-title {
      margin: 0 0 12px 0;
      font-size: 22px;
    }
    .dialog-help {
      color: #555;
      font-size: 14px;
      line-height: 1.45;
      margin-bottom: 14px;
    }
    .status-box {
      margin-top: 12px;
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 14px;
      line-height: 1.45;
      display: none;
    }
    .status-box.error {
      display: block;
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #991b1b;
    }
    .status-box.success {
      display: block;
      background: #ecfdf5;
      border: 1px solid #a7f3d0;
      color: #065f46;
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
    <button onclick="setSelectedAsRoot()">Set selected as root</button>
    <button onclick="restoreOriginalTree()">Restore original tree</button>
    <button onclick="fitGraph()">Fit</button>
    <button onclick="openCreateChildDialog()">Add child node</button>
    <button onclick="openUpdateNodeDialog()">Update node</button>
    <button class="danger" onclick="openDeleteNodeDialog()">Delete node</button>
    <span class="hint">Click a node to select it. Clicking a node that is not currently in focus expands it. Clicking the same in-focus node again collapses it. The clicked node is highlighted, incoming and outgoing edges use different colors, node labels are shortened by default, and the selected node shows its full name. The graph auto-reorganizes after each click for a clearer layout while keeping children below parents and sibling edge order left-to-right. Shift-click only shows details. Update node can change any selected node. The original root can only change title and summary. Delete applies only to a selected non-root node.</span>
  </div>
  <div id="appNotice" class="app-notice" hidden></div>

  <div id="main">
    <div id="net"></div>
    <div id="splitter" title="Drag to resize details panel"></div>
    <aside id="details">
      <div class="empty">
        Click a node to see its metadata and summary here.<br><br>
        You can highlight and copy text from both fields.
      </div>
    </aside>
  </div>


  <div id="createChildDialog" class="modal-overlay">
    <div class="dialog-card">
      <h3 class="dialog-title">Add child node</h3>
      <div class="dialog-help">Select a parent node first. Source and summary markdown file names are automatically generated using random UUIDs and are guaranteed to be unique. Saving updates graph.graphml only.</div>
      <form id="createChildForm" class="form-grid">
        <label>Parent node
          <input id="childParentNode" name="parentNode" type="text" readonly>
        </label>
        <label>Child node title
          <input id="childNodeTitle" name="childNodeTitle" type="text" required>
        </label>
        <label>Explain the relationship of this node's parent to itself
          <input id="childEdgeRelation" name="childEdgeRelation" type="text" placeholder="performs" required>
        </label>
        <label>What number child this node is
          <input id="childEdgeOrder" name="childEdgeOrder" type="number" min="1" step="1" required>
        </label>
        <label>Notes
          <textarea id="childSummaryContent" name="childSummaryContent" placeholder="# Summary
Write markdown here..."></textarea>
        </label>
        <label>Image (JPEG or PNG, max 10MB)
          <input id="childImage" name="childImage" type="file" accept="image/jpeg,image/png">
        </label>
        <div class="dialog-actions">
          <button type="button" class="btn-cancel" onclick="closeCreateChildDialog()">Cancel</button>
          <button type="button" class="btn-save" id="createChildSaveButton">Create child</button>
        </div>
        <div id="createChildStatus" class="status-box"></div>
      </form>
    </div>
  </div>

  <div id="updateNodeDialog" class="modal-overlay">
    <div class="dialog-card">
      <h3 class="dialog-title">Update node</h3>
      <div class="dialog-help" id="updateNodeHelp">Select a node first. Non-root nodes can change title, incoming edge label, sibling order, and summary markdown. The original root can only change title and summary. An invalid edge order places a non-root node at the end of its parent's children. Saving updates graph.graphml only.</div>
      <form id="updateNodeForm" class="form-grid">
        <label id="updateParentField">Parent node
          <input id="updateParentNode" name="parentNode" type="text" readonly>
        </label>
        <label>Node title
          <input id="updateNodeTitle" name="nodeTitle" type="text" required>
        </label>
        <label id="updateRelationField">Explain the relationship of this node's parent to itself
          <input id="updateEdgeRelation" name="edgeRelation" type="text">
        </label>
        <label id="updateOrderField">What number child this node is
          <input id="updateEdgeOrder" name="edgeOrder" type="text" placeholder="1">
        </label>
        <label>Notes
          <textarea id="updateSummaryContent" name="summaryContent"></textarea>
        </label>
        <label>Image (JPEG or PNG, max 10MB)
          <input id="updateImage" name="updateImage" type="file" accept="image/jpeg,image/png">
          <div id="currentImagePreview" style="margin-top: 8px;"></div>
        </label>
        <div class="dialog-actions">
          <button type="button" class="btn-cancel" onclick="closeUpdateNodeDialog()">Cancel</button>
          <button type="button" class="btn-save" id="updateNodeSaveButton">Save changes</button>
        </div>
        <div id="updateNodeStatus" class="status-box"></div>
      </form>
    </div>
  </div>

  <div id="deleteNodeDialog" class="modal-overlay">
    <div class="dialog-card">
      <h3 class="dialog-title">Delete node</h3>
      <div id="deleteNodeMessage" class="dialog-help"></div>
      <div class="dialog-actions">
        <button type="button" onclick="closeDeleteNodeDialog()">Cancel</button>
        <button type="button" class="danger" id="deleteNodeConfirmButton">Delete</button>
      </div>
    </div>
  </div>

  <div id="conflictDialog" class="modal-overlay">
    <div class="dialog-card">
      <h3 class="dialog-title">Someone else changed the graph</h3>
      <div class="dialog-help">
        graph.graphml was modified by another editor after you loaded this page, so your
        change was not saved. Reload to get their version and redo your edit, or overwrite
        their changes with the graph as it looks in this browser.
      </div>
      <div class="dialog-actions">
        <button type="button" id="conflictReloadButton">Reload their version</button>
        <button type="button" class="danger" id="conflictOverwriteButton">Overwrite their changes</button>
      </div>
    </div>
  </div>

  <script>
    const ROOT = __ROOT__;
    let ORIGINAL_ROOT = ROOT;
    const INIT_DEPTH = __DEPTH__;
    let nodesData = __NODES__;
    let edgesData = __EDGES__;
    let children = __CHILDREN__;
    let graphEtag = null;

    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();
    const detailsEl = document.getElementById("details");
    const splitterEl = document.getElementById("splitter");

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
          keyboard: false
        },
        nodes: {
          shape: "dot",
          size: 18,
          borderWidth: 2,
          borderWidthSelected: 4,
          widthConstraint: {
            maximum: 190
          },
          margin: {
            top: 10,
            right: 10,
            bottom: 10,
            left: 10
          },
          color: {
            border: "#666666",
            background: "#ffffff",
            highlight: {
              border: "#f59e0b",
              background: "#fff7ed"
            },
            hover: {
              border: "#f59e0b",
              background: "#fff7ed"
            }
          },
          font: {
            size: 18,
            multi: false
          }
        },
        edges: {
          arrows: {
            to: { enabled: true }
          },
          color: {
            color: "#848484",
            highlight: "#848484",
            hover: "#848484",
            inherit: false
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
    const expandedNodes = new Set();
    let pointerMovedDuringDrag = false;
    let currentRoot = ORIGINAL_ROOT;
    let selectedNodeId = ORIGINAL_ROOT;
    let currentLevels = {};
    let activeNodeIds = new Set();
    const createChildDialogEl = document.getElementById("createChildDialog");
    const createChildFormEl = document.getElementById("createChildForm");
    const createChildStatusEl = document.getElementById("createChildStatus");
    const updateNodeDialogEl = document.getElementById("updateNodeDialog");
    const updateNodeFormEl = document.getElementById("updateNodeForm");
    const updateNodeStatusEl = document.getElementById("updateNodeStatus");
    const deleteNodeDialogEl = document.getElementById("deleteNodeDialog");
    const deleteNodeMessageEl = document.getElementById("deleteNodeMessage");

    function setCreateChildStatus(message, kind = "error") {
      createChildStatusEl.textContent = message || "";
      createChildStatusEl.className = "status-box" + (message ? ` ${kind}` : "");
    }

    function setUpdateNodeStatus(message, kind = "error") {
      updateNodeStatusEl.textContent = message || "";
      updateNodeStatusEl.className = "status-box" + (message ? ` ${kind}` : "");
    }

    function notifyMainUi(message, kind = "success") {
      const noticeEl = document.getElementById("appNotice");
      if (!noticeEl) return;
      noticeEl.hidden = !message;
      noticeEl.textContent = message || "";
      noticeEl.className = "app-notice" + (message ? ` visible${kind === "error" ? " error" : ""}` : "");
    }

    function openOverlay(el) {
      el.classList.add("open");
    }

    function closeOverlay(el) {
      el.classList.remove("open");
    }

    function closeCreateChildDialog() {
      setCreateChildStatus("");
      closeOverlay(createChildDialogEl);
    }

    function closeUpdateNodeDialog() {
      setUpdateNodeStatus("");
      closeOverlay(updateNodeDialogEl);
    }

    function closeDeleteNodeDialog() {
      closeOverlay(deleteNodeDialogEl);
    }

    function preventGraphKeyCapture(el) {
      if (!el) return;
      el.addEventListener("keydown", function(event) {
        event.stopPropagation();
      });
      el.addEventListener("keyup", function(event) {
        event.stopPropagation();
      });
      el.addEventListener("keypress", function(event) {
        event.stopPropagation();
      });
    }

    function installDialogFieldGuards() {
      const guardedSelectors = [
        "#childParentNode",
        "#childNodeTitle",
        "#childEdgeRelation",
        "#childEdgeOrder",
        "#childSourceFile",
        "#childSummaryFile",
        "#childSummaryContent",
        "#updateParentNode",
        "#updateNodeTitle",
        "#updateEdgeRelation",
        "#updateEdgeOrder",
        "#updateSummaryContent"
      ];

      for (const selector of guardedSelectors) {
        preventGraphKeyCapture(document.querySelector(selector));
      }
    }

    function normalizeText(text) {
      return String(text || "").replace(/\s+/g, " ").trim();
    }

    function generateUUID() {
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
    }

    function uniqueMarkdownFileName(desired, usedNames) {
      let name = String(desired || "node.md").trim();
      if (!name.toLowerCase().endsWith(".md")) {
        name += ".md";
      }
      if (!usedNames.has(name.toLowerCase())) {
        usedNames.add(name.toLowerCase());
        return name;
      }
      const stem = name.slice(0, -3);
      let suffix = 2;
      while (usedNames.has(`${stem}_${suffix}.md`.toLowerCase())) {
        suffix += 1;
      }
      name = `${stem}_${suffix}.md`;
      usedNames.add(name.toLowerCase());
      return name;
    }

    function usedMarkdownFileNames() {
      const used = new Set();
      for (const node of nodeMap.values()) {
        if (node.source_file) used.add(String(node.source_file).toLowerCase());
        if (node.summary_file) used.add(String(node.summary_file).toLowerCase());
      }
      return used;
    }

    function sanitizeMarkdownFileName(name, label) {
      const value = String(name || "").trim();
      if (!value) {
        throw new Error(`${label} cannot be empty.`);
      }
      const base = value.split(/[/\\]/).pop();
      if (!/^[A-Za-z0-9._-]+$/.test(base)) {
        throw new Error(`${label} may only contain letters, numbers, dot, underscore, and hyphen.`);
      }
      if (!base.toLowerCase().endsWith(".md")) {
        throw new Error(`${label} must end with .md.`);
      }
      if (base === "." || base === "..") {
        throw new Error(`${label} is not a valid file name.`);
      }
      return base;
    }

    function assertUnusedMarkdownFileName(fileName, usedNames, label) {
      if (usedNames.has(fileName.toLowerCase())) {
        throw new Error(`${label} "${fileName}" is already used in graph.graphml.`);
      }
    }

    function escapeXml(text) {
      return String(text ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&apos;");
    }

    function buildGraphmlText() {
      const lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="d0" for="node" attr.name="source_file" attr.type="string" />',
        '  <key id="d1" for="node" attr.name="summary_file" attr.type="string" />',
        '  <key id="d2" for="node" attr.name="summary" attr.type="string" />',
        '  <key id="d5" for="node" attr.name="image" attr.type="string" />',
        '  <key id="d3" for="edge" attr.name="relation" attr.type="string" />',
        '  <key id="d4" for="edge" attr.name="order" attr.type="long" />',
        '  <graph edgedefault="directed">'
      ];

      for (const [id, node] of nodeMap.entries()) {
        const summary = (node.summary_lines || []).join("\n");
        lines.push(`    <node id="${escapeXml(id)}">`);
        lines.push(`      <data key="d0">${escapeXml(node.source_file || "")}</data>`);
        lines.push(`      <data key="d1">${escapeXml(node.summary_file || "")}</data>`);
        lines.push(`      <data key="d2">${escapeXml(summary)}</data>`);
        lines.push(`      <data key="d5">${escapeXml(node.image || "")}</data>`);
        lines.push("    </node>");
      }

      for (const edge of edgesData) {
        const order = Number.isInteger(edge.order) ? edge.order : -1;
        lines.push(`    <edge source="${escapeXml(edge.from)}" target="${escapeXml(edge.to)}">`);
        lines.push(`      <data key="d3">${escapeXml(edge.relation || "")}</data>`);
        lines.push(`      <data key="d4">${order}</data>`);
        lines.push("    </edge>");
      }

      lines.push("  </graph>");
      lines.push("</graphml>");
      return lines.join("\n") + "\n";
    }

    function downloadGraphml(xml) {
      const blob = new Blob([xml], { type: "application/xml" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "graph.graphml";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    class GraphConflictError extends Error {}
    class GraphReloadedError extends Error {}

    async function putGraphml(xml, etag) {
      const headers = { "Content-Type": "text/plain" };
      if (etag) headers["If-Match"] = etag;
      const response = await fetch(new URL("graph.graphml", window.location.href), {
        method: "PUT",
        headers,
        body: xml
      });
      if (response.status === 409) {
        graphEtag = response.headers.get("ETag") || graphEtag;
        throw new GraphConflictError("graph.graphml changed since you loaded it.");
      }
      if (!response.ok) {
        throw new Error(`Server refused the save (HTTP ${response.status}).`);
      }
      graphEtag = response.headers.get("ETag") || graphEtag;
      return "saved";
    }

    async function persistGraphml() {
      const xml = buildGraphmlText();
      try {
        return await putGraphml(xml, graphEtag);
      } catch (error) {
        if (error instanceof GraphConflictError) {
          const choice = await askConflictResolution();
          if (choice === "overwrite") {
            return await putGraphml(xml, "*");
          }
          await reloadGraphml();
          throw new GraphReloadedError(
            "Someone else changed the graph, so your edit was not saved. Their version is now loaded."
          );
        }
        if (error instanceof GraphReloadedError) throw error;
        // file:// pages and static servers cannot overwrite graph.graphml in place
      }
      downloadGraphml(xml);
      return "downloaded";
    }

    function askConflictResolution() {
      const dialogEl = document.getElementById("conflictDialog");
      const reloadButton = document.getElementById("conflictReloadButton");
      const overwriteButton = document.getElementById("conflictOverwriteButton");
      openOverlay(dialogEl);

      return new Promise(resolve => {
        function finish(choice) {
          reloadButton.removeEventListener("click", onReload);
          overwriteButton.removeEventListener("click", onOverwrite);
          closeOverlay(dialogEl);
          resolve(choice);
        }
        function onReload() { finish("reload"); }
        function onOverwrite() { finish("overwrite"); }
        reloadButton.addEventListener("click", onReload);
        overwriteButton.addEventListener("click", onOverwrite);
      });
    }

    async function reloadGraphml() {
      const success = await loadGraphmlOnStartup();
      if (success) {
        initFromLoadedGraphml();
      }
      return success;
    }

    function initFromLoadedGraphml() {
      // Prefer the original root if it exists and is still a root (in_degree === 0),
      // otherwise fall back to the first node with no incoming edges.
      let foundRoot = null;
      if (nodeMap.has(ORIGINAL_ROOT) && nodeMap.get(ORIGINAL_ROOT).in_degree === 0) {
        foundRoot = ORIGINAL_ROOT;
      } else {
        for (const [id, node] of nodeMap.entries()) {
          if (node.in_degree === 0) {
            foundRoot = id;
            break;
          }
        }
      }
      initFromRoot(foundRoot || ORIGINAL_ROOT);
    }

    function recomputeLevels() {
      // BFS to compute levels from root
      const visited = new Set();
      const queue = [];
      
      // Find root (node with in_degree 0)
      for (const [id, node] of nodeMap.entries()) {
        if (node.in_degree === 0) {
          queue.push(id);
          currentLevels[id] = 0;
          visited.add(id);
          break;
        }
      }
      
      while (queue.length > 0) {
        const current = queue.shift();
        const currentLevel = currentLevels[current] || 0;
        
        const childIds = children[current] || [];
        childIds.forEach(childId => {
          if (!visited.has(childId)) {
            currentLevels[childId] = currentLevel + 1;
            visited.add(childId);
            queue.push(childId);
          }
        });
      }
      
      // Update node levels
      for (const [id, node] of nodeMap.entries()) {
        node.level = currentLevels[id] || 0;
      }
    }

    async function loadGraphmlOnStartup() {
      try {
        const response = await fetch(new URL("graph.graphml", window.location.href), {
          cache: "no-store"
        });
        if (!response.ok) return false;
        graphEtag = response.headers.get("ETag");
        const xml = await response.text();
        
        // Parse the GraphML and update the graph data
        const parser = new DOMParser();
        const doc = parser.parseFromString(xml, "application/xml");
        
        // Clear current data
        nodeMap.clear();
        edgesData.length = 0;
        Object.keys(children).forEach(key => delete children[key]);
        Object.keys(currentLevels).forEach(key => delete currentLevels[key]);
        activeNodeIds.clear();
        expandedNodes.clear();
        
        // Parse nodes
        const nodes = doc.querySelectorAll("node");
        nodes.forEach(node => {
          const id = node.getAttribute("id");
          const sourceFile = node.querySelector('data[key="d0"]')?.textContent || "";
          const summaryFile = node.querySelector('data[key="d1"]')?.textContent || "";
          const summary = node.querySelector('data[key="d2"]')?.textContent || "";
          const image = node.querySelector('data[key="d5"]')?.textContent || "";
          
          nodeMap.set(id, {
            id: id,
            label: id.length <= 24 ? id : id.slice(0, 23).trimEnd() + "…",
            full_label: id,
            short_label: id.length <= 24 ? id : id.slice(0, 23).trimEnd() + "…",
            title: id,
            level: 0,
            source_file: sourceFile,
            source_path: "",
            summary_file: summaryFile,
            summary_lines: summary.split("\n"),
            image: image,
            in_degree: 0,
            out_degree: 0,
            x: 0,
            y: 0
          });
        });
        
        // Parse edges
        const edges = doc.querySelectorAll("edge");
        edges.forEach(edge => {
          const from = edge.getAttribute("source");
          const to = edge.getAttribute("target");
          const relation = edge.querySelector('data[key="d3"]')?.textContent || "";
          const order = parseInt(edge.querySelector('data[key="d4"]')?.textContent || "-1");
          
          if (!children[from]) children[from] = [];
          children[from].push(to);
          
          edgesData.push({
            id: `${from}->${to}`,
            from: from,
            to: to,
            relation: relation,
            order: order,
            label: `${relation} [${order}]`,
            full_label: `${relation} [${order}]`,
            title: `${from} → ${to}<br>relation: ${relation}<br>order: ${order}`,
            base_color: "#848484",
            incoming_color: "#2563eb",
            outgoing_color: "#dc2626"
          });
          
          // Update degrees
          if (nodeMap.has(to)) {
            nodeMap.get(to).in_degree++;
          }
          if (nodeMap.has(from)) {
            nodeMap.get(from).out_degree++;
          }
        });
        
        // Recompute levels
        recomputeLevels();
        
        return true;
      } catch (error) {
        console.log("Could not load graph.graphml on startup, using embedded data:", error.message);
        return false;
      }
    }

    function removeInsertedChildState(parentId, childId, edgeId) {
      nodeMap.delete(childId);
      children[parentId] = (children[parentId] || []).filter(id => id !== childId);
      edges.remove(edgeId);
      const edgeIndex = edgesData.findIndex(item => item.id === edgeId);
      if (edgeIndex !== -1) {
        edgesData.splice(edgeIndex, 1);
      }
      delete currentLevels[childId];
      activeNodeIds.delete(childId);
      expandedNodes.delete(childId);
      renumberOutgoingEdges(parentId);
      updateParentDegrees(parentId);
    }

    function renumberOutgoingEdges(parentId) {
      const ordered = (children[parentId] || []).slice();
      ordered.forEach((childId, index) => {
        const edgeId = `${parentId}->${childId}`;
        const edge = edges.get(edgeId);
        if (!edge) return;
        const relation = edge.relation || edge.label || "";
        edges.update({
          id: edgeId,
          order: index + 1,
          label: `${relation} [${index + 1}]`,
          full_label: `${relation} [${index + 1}]`,
          title: `${parentId} → ${childId}<br>relation: ${relation}<br>order: ${index + 1}`
        });
      });

      for (let i = 0; i < edgesData.length; i++) {
        const edge = edgesData[i];
        if (edge.from !== parentId) continue;
        const newOrder = ordered.indexOf(edge.to);
        if (newOrder === -1) continue;
        edge.order = newOrder + 1;
        edge.label = `${edge.relation} [${edge.order}]`;
        edge.full_label = edge.label;
        edge.title = `${parentId} → ${edge.to}<br>relation: ${edge.relation}<br>order: ${edge.order}`;
      }
    }

    function insertChildAtOrder(parentId, childId, requestedOrder) {
      const siblings = (children[parentId] || []).slice();
      const boundedOrder = Math.max(1, Math.min(requestedOrder, siblings.length + 1));
      siblings.splice(boundedOrder - 1, 0, childId);
      children[parentId] = siblings;
      renumberOutgoingEdges(parentId);
      return boundedOrder;
    }

    function updateParentDegrees(parentId) {
      const node = nodeMap.get(parentId);
      if (!node) return;
      node.out_degree = (children[parentId] || []).length;
      nodes.update({ id: parentId, out_degree: node.out_degree });
    }

    function openCreateChildDialog() {
      if (!selectedNodeId || !nodeMap.has(selectedNodeId)) {
        window.alert("Select a parent node first.");
        return;
      }
      const parent = nodeMap.get(selectedNodeId);
      document.getElementById("childParentNode").value = parent.full_label || parent.id;
      document.getElementById("childNodeTitle").value = "";
      document.getElementById("childEdgeRelation").value = "";
      document.getElementById("childEdgeOrder").value = String((children[selectedNodeId] || []).length + 1);
      document.getElementById("childSummaryContent").value = "";
      setCreateChildStatus("");
      openOverlay(createChildDialogEl);
      setTimeout(() => {
        const titleInput = document.getElementById("childNodeTitle");
        if (titleInput) {
          titleInput.focus();
        }
      }, 0);
    }

    async function createChildNodeFromForm(event) {
      event.preventDefault();
      try {
        const parentId = selectedNodeId;
        if (!parentId || !nodeMap.has(parentId)) {
          throw new Error("Select a valid parent node first.");
        }

        const nodeTitle = normalizeText(document.getElementById("childNodeTitle").value);
        const relation = normalizeText(document.getElementById("childEdgeRelation").value);
        const requestedOrder = Number(document.getElementById("childEdgeOrder").value);
        const summaryContent = document.getElementById("childSummaryContent").value.replace(/\r?\n/g, "\n").trim();
        const imageFile = document.getElementById("childImage").files[0];

        if (!nodeTitle) throw new Error("Child node title cannot be empty.");
        if (!relation) throw new Error("Edge relation cannot be empty.");
        if (!Number.isInteger(requestedOrder) || requestedOrder < 1) throw new Error("Edge order must be a positive integer.");
        if (nodeMap.has(nodeTitle)) throw new Error("A node with this title already exists.");

        // Handle image upload if present
        let imageUrl = null;
        if (imageFile) {
          if (imageFile.size > 10 * 1024 * 1024) {
            throw new Error("Image size exceeds 10MB limit.");
          }
          if (!["image/jpeg", "image/png"].includes(imageFile.type)) {
            throw new Error("Only JPEG and PNG images are allowed.");
          }
          
          const formData = new FormData();
          formData.append("file", imageFile);
          
          try {
            const uploadResponse = await fetch(new URL("upload-image", window.location.href), {
              method: "POST",
              body: formData
            });
            if (!uploadResponse.ok) {
              const errorData = await uploadResponse.json();
              throw new Error(errorData.detail || "Failed to upload image");
            }
            const uploadResult = await uploadResponse.json();
            imageUrl = uploadResult.url;
          } catch (uploadError) {
            throw new Error(`Image upload failed: ${uploadError.message}`);
          }
        }

        // Automatically generate unique file names using UUIDs
        const usedNames = usedMarkdownFileNames();
        const uuid = generateUUID();
        const sourceFileName = uniqueMarkdownFileName(`${uuid}_1.md`, usedNames);
        const summaryFileName = uniqueMarkdownFileName(`${uuid}_2.md`, usedNames);
        const parentNode = nodeMap.get(parentId);
        const childLevel = (parentNode?.level || 0) + 1;
        const childShortLabel = nodeTitle.length <= 24 ? nodeTitle : nodeTitle.slice(0, 23).trimEnd() + "…";
        const newNode = {
          id: nodeTitle,
          label: childShortLabel,
          full_label: nodeTitle,
          short_label: childShortLabel,
          title: nodeTitle,
          level: childLevel,
          source_file: sourceFileName,
          source_path: "",
          summary_file: summaryFileName,
          summary_lines: summaryContent.split("\n"),
          image: imageUrl,
          in_degree: 1,
          out_degree: 0,
          x: (parentNode?.x || 0) + 260,
          y: (parentNode?.y || 0) + 170
        };

        nodeMap.set(nodeTitle, newNode);
        const actualOrder = insertChildAtOrder(parentId, nodeTitle, requestedOrder);
        const newEdge = {
          id: `${parentId}->${nodeTitle}`,
          from: parentId,
          to: nodeTitle,
          relation: relation,
          order: actualOrder,
          label: `${relation} [${actualOrder}]`,
          full_label: `${relation} [${actualOrder}]`,
          title: `${parentId} → ${nodeTitle}<br>relation: ${relation}<br>order: ${actualOrder}`,
          base_color: "#848484",
          incoming_color: "#2563eb",
          outgoing_color: "#dc2626"
        };
        edgesData.push(newEdge);
        edges.add(newEdge);
        renumberOutgoingEdges(parentId);
        updateParentDegrees(parentId);

        try {
          const persistMode = await persistGraphml();
          
          activeNodeIds.add(nodeTitle);
          currentLevels[nodeTitle] = childLevel;
          expandedNodes.add(parentId);

          updateVisibleNodes();
          syncEdges();
          selectedNodeId = nodeTitle;
          renderDetails(nodeTitle);
          relayout(true);
          closeOverlay(createChildDialogEl);
          notifyMainUi(
            persistMode === "saved"
              ? `Added ${nodeTitle} and updated graph.graphml.`
              : `Added ${nodeTitle}. Downloaded updated graph.graphml.`
          );
        } catch (error) {
          // After a conflict reload the in-memory graph is already the server's
          // version, so there is nothing local left to roll back.
          if (!(error instanceof GraphReloadedError)) {
            removeInsertedChildState(parentId, nodeTitle, newEdge.id);
          }
          throw error;
        }
      } catch (error) {
        if (error instanceof GraphReloadedError) {
          closeOverlay(createChildDialogEl);
          notifyMainUi(error.message, "error");
          return;
        }
        setCreateChildStatus(error.message || String(error), "error");
      }
    }

    function findParentId(nodeId) {
      let fallback = null;
      for (const [parentId, kids] of Object.entries(children)) {
        if (!(kids || []).includes(nodeId)) continue;
        if (activeNodeIds.has(parentId)) return parentId;
        if (fallback === null) fallback = parentId;
      }
      return fallback;
    }

    function assertNonRootSelected() {
      if (!selectedNodeId || !nodeMap.has(selectedNodeId)) {
        throw new Error("Select a non-root node first.");
      }
      if (selectedNodeId === ORIGINAL_ROOT) {
        throw new Error("The root node cannot be updated or deleted.");
      }
      const parentId = findParentId(selectedNodeId);
      if (!parentId) {
        throw new Error("The selected node has no parent, so it cannot be updated or deleted.");
      }
      return parentId;
    }

    function resolveSiblingOrder(rawValue, childCount) {
      const parsed = Number(String(rawValue ?? "").trim());
      if (!Number.isInteger(parsed) || parsed < 1 || parsed > childCount) {
        return childCount;
      }
      return parsed;
    }

    function getEdgeRecord(fromId, toId) {
      const edgeId = `${fromId}->${toId}`;
      return edges.get(edgeId) || edgesData.find(item => item.id === edgeId) || null;
    }

    function makeEdgeRecord(fromId, toId, relation, order) {
      return {
        id: `${fromId}->${toId}`,
        from: fromId,
        to: toId,
        relation: relation,
        order: order,
        label: `${relation} [${order}]`,
        full_label: `${relation} [${order}]`,
        title: `${fromId} → ${toId}<br>relation: ${relation}<br>order: ${order}`,
        base_color: "#848484",
        incoming_color: "#2563eb",
        outgoing_color: "#dc2626"
      };
    }

    function removeEdgeData(edgeId) {
      edges.remove(edgeId);
      const index = edgesData.findIndex(item => item.id === edgeId);
      if (index !== -1) {
        edgesData.splice(index, 1);
      }
    }

    function renameNodeInMemory(oldId, newId) {
      if (oldId === newId) return;

      const stored = nodeMap.get(oldId);
      if (!stored) {
        throw new Error(`Missing node data for ${oldId}.`);
      }

      const shortLabel = newId.length <= 24 ? newId : newId.slice(0, 23).trimEnd() + "…";
      nodeMap.delete(oldId);
      nodeMap.set(newId, {
        ...stored,
        id: newId,
        label: shortLabel,
        full_label: newId,
        short_label: shortLabel,
        title: newId
      });

      if (Object.prototype.hasOwnProperty.call(children, oldId)) {
        children[newId] = children[oldId];
        delete children[oldId];
      }

      for (const parentKey of Object.keys(children)) {
        children[parentKey] = (children[parentKey] || []).map(id => (id === oldId ? newId : id));
      }

      for (const edge of edgesData) {
        if (edge.from !== oldId && edge.to !== oldId) continue;
        if (edge.from === oldId) edge.from = newId;
        if (edge.to === oldId) edge.to = newId;
        edge.id = `${edge.from}->${edge.to}`;
        const order = edge.order;
        const relation = edge.relation || "";
        edge.label = order && order !== -1 ? `${relation} [${order}]` : relation;
        edge.full_label = edge.label;
        edge.title = `${edge.from} → ${edge.to}<br>relation: ${relation}` + (order && order !== -1 ? `<br>order: ${order}` : "");
      }

      if (nodes.get(oldId)) {
        nodes.remove(oldId);
        nodes.add(nodeMap.get(newId));
      }

      if (selectedNodeId === oldId) selectedNodeId = newId;
      if (currentRoot === oldId) currentRoot = newId;
      if (ORIGINAL_ROOT === oldId) ORIGINAL_ROOT = newId;
      if (expandedNodes.has(oldId)) {
        expandedNodes.delete(oldId);
        expandedNodes.add(newId);
      }
      if (activeNodeIds.has(oldId)) {
        activeNodeIds.delete(oldId);
        activeNodeIds.add(newId);
      }
      if (Object.prototype.hasOwnProperty.call(currentLevels, oldId)) {
        currentLevels[newId] = currentLevels[oldId];
        delete currentLevels[oldId];
      }
      if (hidden.has(oldId)) {
        hidden.delete(oldId);
        hidden.add(newId);
      }
    }

    function applyUpdatedNodeInMemory(parentId, oldId, newId, relation, order, summaryLines, imageUrl = null) {
      renameNodeInMemory(oldId, newId);

      if (parentId) {
        const siblings = (children[parentId] || []).filter(id => id !== newId);
        const boundedOrder = Math.max(1, Math.min(order, siblings.length + 1));
        siblings.splice(boundedOrder - 1, 0, newId);
        children[parentId] = siblings;

        const edge = edgesData.find(item => item.from === parentId && item.to === newId);
        if (edge) {
          edge.relation = relation;
        } else {
          edgesData.push(makeEdgeRecord(parentId, newId, relation, boundedOrder));
        }

        renumberOutgoingEdges(parentId);
      }

      const stored = nodeMap.get(newId);
      if (stored) {
        stored.summary_lines = summaryLines;
        if (imageUrl !== null) {
          stored.image = imageUrl;
        }
      }
    }

    function applyDeletedNodeInMemory(parentId, deletedId) {
      const parentKids = (children[parentId] || []).filter(id => id !== deletedId);
      const formerChildren = (children[deletedId] || []).slice();
      const promoted = formerChildren.filter(id => id !== parentId && !parentKids.includes(id));

      removeEdgeData(`${parentId}->${deletedId}`);

      for (const childId of formerChildren) {
        const oldEdge = getEdgeRecord(deletedId, childId);
        removeEdgeData(`${deletedId}->${childId}`);

        if (promoted.includes(childId)) {
          const relation = normalizeText((oldEdge && oldEdge.relation) || "related");
          edgesData.push(makeEdgeRecord(parentId, childId, relation, 0));
        } else {
          const childNode = nodeMap.get(childId);
          if (childNode) {
            childNode.in_degree = Math.max(0, (childNode.in_degree || 1) - 1);
            if (nodes.get(childId)) {
              nodes.update({ id: childId, in_degree: childNode.in_degree });
            }
          }
        }
      }

      children[parentId] = parentKids.concat(promoted);
      delete children[deletedId];

      nodeMap.delete(deletedId);
      if (nodes.get(deletedId)) {
        nodes.remove(deletedId);
      }
      hidden.delete(deletedId);
      expandedNodes.delete(deletedId);
      activeNodeIds.delete(deletedId);
      delete currentLevels[deletedId];

      renumberOutgoingEdges(parentId);
      updateParentDegrees(parentId);
    }

    function setUpdateEdgeFieldsVisible(visible) {
      for (const id of ["updateParentField", "updateRelationField", "updateOrderField"]) {
        const field = document.getElementById(id);
        if (field) {
          field.style.display = visible ? "" : "none";
        }
      }
    }

    function openUpdateNodeDialog() {
      try {
        if (!selectedNodeId || !nodeMap.has(selectedNodeId)) {
          throw new Error("Select a node first.");
        }
        const parentId = findParentId(selectedNodeId);
        const isRootUpdate = selectedNodeId === ORIGINAL_ROOT || !parentId;
        const node = nodeMap.get(selectedNodeId);
        const parent = parentId ? nodeMap.get(parentId) : null;
        const edge = parentId ? getEdgeRecord(parentId, selectedNodeId) : null;
        const order = parentId ? (children[parentId] || []).indexOf(selectedNodeId) + 1 : 0;

        document.getElementById("updateParentNode").value = parent?.full_label || parentId || "";
        document.getElementById("updateNodeTitle").value = node?.full_label || selectedNodeId;
        document.getElementById("updateEdgeRelation").value = edge ? normalizeText(edge.relation || "") : "";
        document.getElementById("updateEdgeOrder").value = order > 0 ? String(order) : "";
        document.getElementById("updateSummaryContent").value = (node?.summary_lines || []).join("\n");
        
        // Show current image preview if exists
        const imagePreview = document.getElementById("currentImagePreview");
        if (node?.image) {
          imagePreview.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
              <img src="${node.image}" alt="Current image" style="max-width: 100px; max-height: 100px; border-radius: 4px; object-fit: contain;">
              <span style="font-size: 12px; color: #666;">Current image (will be replaced if you upload a new one)</span>
            </div>
          `;
        } else {
          imagePreview.innerHTML = "";
        }
        
        setUpdateEdgeFieldsVisible(!isRootUpdate);
        setUpdateNodeStatus("");
        notifyMainUi("");
        openOverlay(updateNodeDialogEl);
        setTimeout(() => {
          const titleInput = document.getElementById("updateNodeTitle");
          if (titleInput) {
            titleInput.focus();
          }
        }, 0);
      } catch (error) {
        window.alert(error.message || String(error));
      }
    }

    async function updateNodeFromForm(event) {
      event.preventDefault();
      try {
        if (!selectedNodeId || !nodeMap.has(selectedNodeId)) {
          throw new Error("Select a node first.");
        }
        const oldId = selectedNodeId;
        const parentId = findParentId(oldId);
        const isRootUpdate = oldId === ORIGINAL_ROOT || !parentId;

        const nodeTitle = normalizeText(document.getElementById("updateNodeTitle").value);
        const relation = normalizeText(document.getElementById("updateEdgeRelation").value);
        const rawOrder = document.getElementById("updateEdgeOrder").value;
        const summaryContent = document.getElementById("updateSummaryContent").value.replace(/\r?\n/g, "\n").trim();
        const imageFile = document.getElementById("updateImage").files[0];

        if (!nodeTitle) throw new Error("Node title cannot be empty.");
        if (nodeTitle !== oldId && nodeMap.has(nodeTitle)) {
          throw new Error("A node with this title already exists.");
        }
        if (!isRootUpdate && !relation) {
          throw new Error("Edge relation cannot be empty.");
        }

        // Handle image upload if present
        let imageUrl = null;
        const currentNode = nodeMap.get(oldId);
        const oldImageUrl = currentNode?.image || null;
        
        if (imageFile) {
          if (imageFile.size > 10 * 1024 * 1024) {
            throw new Error("Image size exceeds 10MB limit.");
          }
          if (!["image/jpeg", "image/png"].includes(imageFile.type)) {
            throw new Error("Only JPEG and PNG images are allowed.");
          }
          
          const formData = new FormData();
          formData.append("file", imageFile);
          
          try {
            const uploadResponse = await fetch(new URL("upload-image", window.location.href), {
              method: "POST",
              body: formData
            });
            if (!uploadResponse.ok) {
              const errorData = await uploadResponse.json();
              throw new Error(errorData.detail || "Failed to upload image");
            }
            const uploadResult = await uploadResponse.json();
            imageUrl = uploadResult.url;
            
            // Delete old image if it exists and is different from the new one
            if (oldImageUrl && oldImageUrl !== imageUrl) {
              try {
                await fetch(new URL("delete-image", window.location.href), {
                  method: "DELETE",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ image_url: oldImageUrl })
                });
              } catch (deleteError) {
                console.warn("Failed to delete old image:", deleteError.message);
              }
            }
          } catch (uploadError) {
            throw new Error(`Image upload failed: ${uploadError.message}`);
          }
        }

        const childCount = parentId ? (children[parentId] || []).length : 1;
        const actualOrder = parentId ? resolveSiblingOrder(rawOrder, childCount) : 1;

        applyUpdatedNodeInMemory(
          isRootUpdate ? null : parentId,
          oldId,
          nodeTitle,
          relation,
          actualOrder,
          summaryContent.split("\n"),
          imageUrl !== null ? imageUrl : oldImageUrl
        );
        const persistMode = await persistGraphml();

        selectedNodeId = nodeTitle;
        updateVisibleNodes();
        syncEdges();
        renderDetails(nodeTitle);
        relayout(true);
        closeUpdateNodeDialog();
        notifyMainUi(
          persistMode === "saved"
            ? `Updated ${nodeTitle} and wrote graph.graphml.`
            : `Updated ${nodeTitle}. Downloaded updated graph.graphml.`
        );
      } catch (error) {
        if (error instanceof GraphReloadedError) {
          closeUpdateNodeDialog();
          notifyMainUi(error.message, "error");
          return;
        }
        setUpdateNodeStatus(error.message || String(error), "error");
      }
    }

    function openDeleteNodeDialog() {
      try {
        const parentId = assertNonRootSelected();
        const node = nodeMap.get(selectedNodeId);
        const parent = nodeMap.get(parentId);
        const childCount = (children[selectedNodeId] || []).length;
        const title = node?.full_label || selectedNodeId;
        const parentTitle = parent?.full_label || parentId;
        deleteNodeMessageEl.textContent = childCount
          ? `Delete "${title}"? Its ${childCount} child node(s) will be moved under "${parentTitle}".`
          : `Delete "${title}"? This cannot be undone from this view.`;
        openOverlay(deleteNodeDialogEl);
      } catch (error) {
        window.alert(error.message || String(error));
      }
    }

    async function confirmDeleteSelectedNode() {
      try {
        const parentId = assertNonRootSelected();
        const deletedId = selectedNodeId;
        const wasCurrentRoot = currentRoot === deletedId;

        applyDeletedNodeInMemory(parentId, deletedId);
        await persistGraphml();

        closeOverlay(deleteNodeDialogEl);
        if (wasCurrentRoot || !nodeMap.has(currentRoot)) {
          initFromRoot(parentId);
        } else {
          applyLayoutForRoot(currentRoot);
          selectedNodeId = parentId;
          updateVisibleNodes();
          syncEdges();
          renderDetails(parentId);
          relayout(true);
        }
      } catch (error) {
        if (error instanceof GraphReloadedError) {
          closeOverlay(deleteNodeDialogEl);
          notifyMainUi(error.message, "error");
          return;
        }
        window.alert(error.message || String(error));
      }
    }

    function refreshNodeLabels() {
      const updates = nodes.getIds().map(id => {
        const stored = nodeMap.get(id);
        if (!stored) return null;
        return {
          id,
          label: id === selectedNodeId ? stored.full_label : stored.short_label,
          title: stored.full_label,
        };
      }).filter(Boolean);

      if (updates.length) {
        nodes.update(updates);
      }
    }

    function refreshEdgeHighlights() {
      const updates = edges.getIds().map(id => {
        const edge = edges.get(id);
        if (!edge) return null;

        let color = edge.base_color || "#848484";
        let width = 1.5;

        if (selectedNodeId) {
          if (edge.from === selectedNodeId) {
            color = edge.outgoing_color || "#dc2626";
            width = 3;
          } else if (edge.to === selectedNodeId) {
            color = edge.incoming_color || "#2563eb";
            width = 3;
          }
        }

        return {
          id,
          color: {
            color: color,
            highlight: color,
            hover: color,
            inherit: false,
          },
          width: width,
        };
      }).filter(Boolean);

      if (updates.length) {
        edges.update(updates);
      }
    }

    function spreadLevelPositions() {
      const minGap = 230;
      const levelGroups = {};

      for (const id of nodes.getIds()) {
        const stored = nodeMap.get(id);
        if (!stored) continue;
        const level = stored.level || 0;
        if (!levelGroups[level]) {
          levelGroups[level] = [];
        }
        levelGroups[level].push(stored);
      }

      for (const level of Object.keys(levelGroups)) {
        const items = levelGroups[level].sort((a, b) => a.x - b.x);
        if (!items.length) continue;

        const originalCenter = items.reduce((acc, item) => acc + item.x, 0) / items.length;

        for (let i = 1; i < items.length; i++) {
          const prev = items[i - 1];
          const cur = items[i];
          if (cur.x - prev.x < minGap) {
            cur.x = prev.x + minGap;
          }
        }

        const adjustedCenter = items.reduce((acc, item) => acc + item.x, 0) / items.length;
        const shift = originalCenter - adjustedCenter;

        for (const item of items) {
          item.x += shift;
        }
      }
    }

    function escapeHtml(text) {
      return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function renderInlineMarkdown(text) {
      let html = escapeHtml(text);
      html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
      html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
      return html;
    }

    function leadingSpaceCount(text) {
      const match = String(text || "").match(/^[ \t]*/);
      if (!match) return 0;
      return match[0].replace(/\t/g, "    ").length;
    }

    function renderMarkdown(summaryLines) {
      const lines = summaryLines || [];
      const out = [];
      let inCodeBlock = false;
      let codeLines = [];
      let inBlockquote = false;
      let quoteLines = [];
      let paragraphLines = [];
      const listStack = [];

      function isTableRow(line) {
        return /^\s*\|.*\|\s*$/.test(line);
      }

      function isTableSeparator(line) {
        return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
      }

      function splitTableRow(line) {
        return line
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map(cell => cell.trim());
      }

      function closeListsToDepth(targetDepth = 0) {
        while (listStack.length > targetDepth) {
          const top = listStack.pop();
          if (top.hasOpenItem) {
            out.push(`</li></${top.type}>`);
          } else {
            out.push(`</${top.type}>`);
          }
        }
      }

      function openListContainer(type) {
        out.push(`<${type}>`);
        listStack.push({ type, hasOpenItem: false });
      }

      function startListItem(type, depth) {
        while (listStack.length > depth) {
          const top = listStack.pop();
          if (top.hasOpenItem) {
            out.push(`</li></${top.type}>`);
          } else {
            out.push(`</${top.type}>`);
          }
        }

        while (listStack.length < depth) {
          openListContainer(type);
        }

        const current = listStack[listStack.length - 1];
        if (!current || current.type !== type) {
          if (current) {
            if (current.hasOpenItem) {
              out.push(`</li></${current.type}>`);
            } else {
              out.push(`</${current.type}>`);
            }
            listStack.pop();
          }
          openListContainer(type);
        }

        const active = listStack[listStack.length - 1];
        if (active.hasOpenItem) {
          out.push(`</li><li>`);
        } else {
          out.push(`<li>`);
          active.hasOpenItem = true;
        }
      }

      function flushParagraph() {
        if (!paragraphLines.length) return;
        const text = paragraphLines
          .map(line => line.trim() ? line.trim() : "")
          .join(" ")
          .trim();
        if (text) {
          out.push(`<p>${renderInlineMarkdown(text)}</p>`);
        }
        paragraphLines = [];
      }

      function flushBlockquote() {
        if (!inBlockquote) return;
        const content = quoteLines.map(line => renderInlineMarkdown(line)).join("<br>");
        out.push(`<blockquote>${content}</blockquote>`);
        inBlockquote = false;
        quoteLines = [];
      }

      function flushCodeBlock() {
        if (!inCodeBlock) return;
        out.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        inCodeBlock = false;
        codeLines = [];
      }

      function flushNonListBlocks() {
        flushParagraph();
        flushBlockquote();
      }

      for (let i = 0; i < lines.length; i++) {
        const rawLine = lines[i];
        const line = rawLine ?? "";
        const trimmed = line.trim();

        if (line.startsWith("```")) {
          flushNonListBlocks();
          closeListsToDepth(0);
          if (inCodeBlock) {
            flushCodeBlock();
          } else {
            inCodeBlock = true;
          }
          continue;
        }

        if (inCodeBlock) {
          codeLines.push(line);
          continue;
        }

        if (!trimmed) {
          flushNonListBlocks();
          closeListsToDepth(0);
          continue;
        }

        if (/^\s*(?:---|\*\*\*|___)\s*$/.test(line)) {
          flushNonListBlocks();
          closeListsToDepth(0);
          out.push("<hr>");
          continue;
        }

        if (isTableRow(line) && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
          flushNonListBlocks();
          closeListsToDepth(0);

          const headers = splitTableRow(line);
          const rows = [];
          i += 2;

          while (i < lines.length && isTableRow(lines[i])) {
            rows.push(splitTableRow(lines[i]));
            i++;
          }
          i--;

          let tableHtml = "<table><thead><tr>";
          for (const header of headers) {
            tableHtml += `<th>${renderInlineMarkdown(header)}</th>`;
          }
          tableHtml += "</tr></thead><tbody>";

          for (const row of rows) {
            tableHtml += "<tr>";
            for (let c = 0; c < headers.length; c++) {
              const cell = row[c] ?? "";
              tableHtml += `<td>${renderInlineMarkdown(cell)}</td>`;
            }
            tableHtml += "</tr>";
          }

          tableHtml += "</tbody></table>";
          out.push(tableHtml);
          continue;
        }

        const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
        if (headingMatch) {
          flushNonListBlocks();
          closeListsToDepth(0);
          const level = headingMatch[1].length;
          out.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
          continue;
        }

        const blockquoteMatch = line.match(/^>\s?(.*)$/);
        if (blockquoteMatch) {
          flushParagraph();
          closeListsToDepth(0);
          inBlockquote = true;
          quoteLines.push(blockquoteMatch[1]);
          continue;
        } else {
          flushBlockquote();
        }

        const ulMatch = line.match(/^(\s*)[-*+]\s*(.*)$/);
        if (ulMatch) {
          const content = ulMatch[2].trim();
          if (!content) {
            flushParagraph();
            closeListsToDepth(0);
            continue;
          }
          flushParagraph();
          const indent = leadingSpaceCount(ulMatch[1]);
          const depth = Math.floor(indent / 2) + 1;
          startListItem("ul", depth);
          out.push(renderInlineMarkdown(content));
          continue;
        }

        const olMatch = line.match(/^(\s*)\d+\.\s*(.*)$/);
        if (olMatch) {
          const content = olMatch[2].trim();
          if (!content) {
            flushParagraph();
            closeListsToDepth(0);
            continue;
          }
          flushParagraph();
          const indent = leadingSpaceCount(olMatch[1]);
          const depth = Math.floor(indent / 2) + 1;
          startListItem("ol", depth);
          out.push(renderInlineMarkdown(content));
          continue;
        }

        closeListsToDepth(0);
        paragraphLines.push(line);
      }

      flushParagraph();
      closeListsToDepth(0);
      flushBlockquote();
      flushCodeBlock();

      return out.join("\n");
    }

    function renderDetails(id) {
      const node = nodeMap.get(id);
      if (!node) {
        detailsEl.innerHTML = '<div class="empty">Node details unavailable.</div>';
        return;
      }

      const fullName = node.full_label || node.label || id;
      const summaryHtml = renderMarkdown(node.summary_lines || []);

      detailsEl.innerHTML = `
        <h2>${escapeHtml(fullName)}</h2>

        <div class="panel-field">
          <div class="section-title">Node metadata</div>
          <div class="meta-row"><span class="meta-label">Node:</span> ${escapeHtml(fullName)}</div>
          <div class="meta-row"><span class="meta-label">Source file:</span> ${node.source_file ? `<code>${escapeHtml(node.source_file)}</code>` : 'N/A'}</div>
          <div class="meta-row"><span class="meta-label">Summary file:</span> ${node.summary_file ? `<code>${escapeHtml(node.summary_file)}</code>` : 'N/A'}</div>
          <div class="meta-row"><span class="meta-label">In-degree:</span> ${node.in_degree}</div>
          <div class="meta-row"><span class="meta-label">Out-degree:</span> ${node.out_degree}</div>
          <div class="meta-row"><span class="meta-label">Level:</span> ${node.level}</div>
          ${node.image ? `<div class="meta-row"><span class="meta-label">Image:</span> <img src="${escapeHtml(node.image)}" alt="Node image" class="node-image"></div>` : ''}
        </div>

        <div class="panel-field">
          <div class="section-title">Summary content</div>
          ${summaryHtml ? `<div class="summary-markdown">${summaryHtml}</div>` : '<div class="empty">No summary available for this node.</div>'}
        </div>
      `;
    }

    function subtreeNodesOf(id) {
      const result = [id];
      const stack = [id];
      const seen = new Set([id]);

      while (stack.length) {
        const cur = stack.pop();
        for (const child of (children[cur] || [])) {
          if (seen.has(child)) continue;
          seen.add(child);
          result.push(child);
          stack.push(child);
        }
      }

      return result;
    }

    function visibleChildrenOf(id) {
      return (children[id] || []).filter(child => activeNodeIds.has(child) && nodes.get(child));
    }

    function buildVisibleSubtreeInfo(rootId) {
      const subtreeWidth = {};
      const visibleSet = new Set(nodes.getIds());

      function visit(nodeId) {
        if (!visibleSet.has(nodeId)) {
          return 0;
        }

        const visibleKids = visibleChildrenOf(nodeId);
        if (!visibleKids.length) {
          subtreeWidth[nodeId] = 1;
          return 1;
        }

        let total = 0;
        for (const child of visibleKids) {
          total += visit(child);
        }
        subtreeWidth[nodeId] = Math.max(1, total);
        return subtreeWidth[nodeId];
      }

      visit(rootId);
      return { subtreeWidth, visibleSet };
    }

    function computeVisibleLayout(rootId) {
      const { subtreeWidth, visibleSet } = buildVisibleSubtreeInfo(rootId);
      const positions = {};
      const xSpacing = 260;
      const ySpacing = 170;

      function place(nodeId, centerX) {
        if (!visibleSet.has(nodeId)) return;

        positions[nodeId] = {
          x: centerX,
          y: (currentLevels[nodeId] || 0) * ySpacing,
        };

        const kids = visibleChildrenOf(nodeId);
        if (!kids.length) {
          return;
        }

        const totalWidthUnits = kids.reduce((acc, child) => acc + (subtreeWidth[child] || 1), 0);
        let leftEdge = centerX - ((totalWidthUnits - 1) * xSpacing) / 2;

        for (const child of kids) {
          const childUnits = subtreeWidth[child] || 1;
          const childCenterX = leftEdge + ((childUnits - 1) * xSpacing) / 2;
          place(child, childCenterX);
          leftEdge += childUnits * xSpacing;
        }
      }

      place(rootId, 0);

      const visibleNodes = Array.from(visibleSet);
      for (const nodeId of visibleNodes) {
        const stored = nodeMap.get(nodeId);
        const pos = positions[nodeId];
        if (!stored || !pos) continue;
        stored.x = pos.x;
        stored.y = pos.y;
        stored.level = currentLevels[nodeId] || 0;
      }
    }

    function reorganizeVisibleGraph(shouldFit = false) {
      computeVisibleLayout(currentRoot);
      spreadLevelPositions();

      const updates = nodes.getIds().map(id => {
        const stored = nodeMap.get(id);
        if (!stored) return null;
        return {
          id,
          x: stored.x,
          y: stored.y,
          level: stored.level,
          label: id === selectedNodeId ? stored.full_label : stored.short_label,
          title: stored.full_label,
        };
      }).filter(Boolean);

      if (updates.length) {
        nodes.update(updates);
      }

      refreshEdgeHighlights();
      network.setData({ nodes: nodes, edges: edges });

      if (selectedNodeId && nodes.get(selectedNodeId)) {
        network.selectNodes([selectedNodeId]);
      } else {
        network.unselectAll();
      }

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

    function computeLevelsForRoot(rootId) {
      const levels = { [rootId]: 0 };
      const queue = [rootId];

      while (queue.length) {
        const nodeId = queue.shift();
        for (const child of (children[nodeId] || [])) {
          if (!(child in levels)) {
            levels[child] = levels[nodeId] + 1;
            queue.push(child);
          }
        }
      }

      return levels;
    }

    function applyLayoutForRoot(rootId) {
      currentLevels = computeLevelsForRoot(rootId);
      activeNodeIds = new Set(subtreeNodesOf(rootId));

      for (const nodeId of activeNodeIds) {
        const stored = nodeMap.get(nodeId);
        if (stored) {
          stored.level = currentLevels[nodeId] || 0;
          stored.x = 0;
          stored.y = stored.level * 170;
        }
      }
    }

    function syncEdges() {
      const visible = new Set(nodes.getIds());
      const wanted = edgesData.filter(
        e => activeNodeIds.has(e.from) && activeNodeIds.has(e.to) && visible.has(e.from) && visible.has(e.to)
      );
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

      refreshEdgeHighlights();
    }

    function relayout(shouldFit = false) {
      reorganizeVisibleGraph(shouldFit);
    }

    function showNode(id) {
      if (!activeNodeIds.has(id)) {
        return;
      }
      if (!nodes.get(id)) {
        const node = nodeMap.get(id);
        if (node) {
          nodes.add(node);
        }
      }
    }

    function computeWantedVisibleNodes() {
      const wanted = new Set();

      for (const nodeId of activeNodeIds) {
        if ((currentLevels[nodeId] || 0) <= INIT_DEPTH) {
          wanted.add(nodeId);
        }
      }

      wanted.add(currentRoot);

      let changed = true;
      while (changed) {
        changed = false;
        for (const nodeId of Array.from(wanted)) {
          if (!expandedNodes.has(nodeId)) continue;
          for (const child of (children[nodeId] || []).filter(child => activeNodeIds.has(child))) {
            if (!wanted.has(child)) {
              wanted.add(child);
              changed = true;
            }
          }
        }
      }

      return wanted;
    }

    function updateVisibleNodes() {
      const wanted = computeWantedVisibleNodes();

      for (const nodeId of Array.from(nodes.getIds())) {
        if (!wanted.has(nodeId)) {
          nodes.remove(nodeId);
          hidden.add(nodeId);
        }
      }

      for (const nodeId of wanted) {
        hidden.delete(nodeId);
        showNode(nodeId);
      }

      return wanted;
    }

    function descendantsOf(id) {
      const result = [];
      const stack = [...(children[id] || [])];
      const seen = new Set();

      while (stack.length) {
        const cur = stack.pop();
        if (seen.has(cur) || !activeNodeIds.has(cur)) continue;
        seen.add(cur);
        result.push(cur);
        for (const child of (children[cur] || [])) {
          stack.push(child);
        }
      }

      return result;
    }

    function hideSubtree(id) {
      expandedNodes.delete(id);
      updateVisibleNodes();
      syncEdges();
      relayout(false);
    }

    function expandOneLevel(id) {
      expandedNodes.add(id);
      updateVisibleNodes();
      syncEdges();
      relayout(false);
    }

    function toggleNode(id) {
      const directChildren = (children[id] || []).filter(child => activeNodeIds.has(child));
      if (!directChildren.length) return;

      if (expandedNodes.has(id)) {
        hideSubtree(id);
      } else {
        expandOneLevel(id);
      }
    }

    function initFromRoot(rootId) {
      currentRoot = rootId;
      selectedNodeId = rootId;
      hidden.clear();
      expandedNodes.clear();
      nodes.clear();
      edges.clear();
      applyLayoutForRoot(rootId);

      updateVisibleNodes();
      syncEdges();
      relayout(true);
      renderDetails(rootId);
    }

    function expandAll() {
      hidden.clear();
      for (const nodeId of activeNodeIds) {
        expandedNodes.add(nodeId);
      }
      updateVisibleNodes();
      syncEdges();
      relayout(true);
    }

    function collapseAll() {
      expandedNodes.clear();
      selectedNodeId = currentRoot;
      updateVisibleNodes();
      syncEdges();
      renderDetails(currentRoot);
      relayout(true);
    }

    function setSelectedAsRoot() {
      if (!selectedNodeId || !nodeMap.has(selectedNodeId)) {
        return;
      }
      initFromRoot(selectedNodeId);
    }

    function restoreOriginalTree() {
      initFromRoot(ORIGINAL_ROOT);
    }

    function fitGraph() {
      network.fit({
        animation: {
          duration: 250,
          easingFunction: "easeInOutQuad"
        }
      });
    }


    function installSplitter() {
      let resizing = false;

      splitterEl.addEventListener("mousedown", function(event) {
        resizing = true;
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
        event.preventDefault();
      });

      window.addEventListener("mousemove", function(event) {
        if (!resizing) return;
        const minWidth = 220;
        const maxWidth = Math.floor(window.innerWidth * 0.7);
        const newWidth = window.innerWidth - event.clientX;
        const clamped = Math.max(minWidth, Math.min(maxWidth, newWidth));
        detailsEl.style.width = `${clamped}px`;
        network.redraw();
      });

      window.addEventListener("mouseup", function() {
        if (!resizing) return;
        resizing = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
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
        spreadLevelPositions();
        refreshNodeLabels();
        const updates = nodes.getIds().map(id => {
          const stored = nodeMap.get(id);
          if (!stored) return null;
          return {
            id,
            x: stored.x,
            y: stored.y,
            label: id === selectedNodeId ? stored.full_label : stored.short_label,
            title: stored.full_label,
          };
        }).filter(Boolean);
        if (updates.length) {
          nodes.update(updates);
        }
      }
    });

    network.on("release", function(params) {
      const nodeId = params.pointer && params.pointer.DOM
        ? network.getNodeAt(params.pointer.DOM)
        : null;

      if (!nodeId) {
        if (selectedNodeId && nodes.get(selectedNodeId)) {
          network.selectNodes([selectedNodeId]);
          refreshEdgeHighlights();
        }
        pointerMovedDuringDrag = false;
        return;
      }

      if (pointerMovedDuringDrag) {
        if (selectedNodeId && nodes.get(selectedNodeId)) {
          network.selectNodes([selectedNodeId]);
          refreshEdgeHighlights();
        }
        pointerMovedDuringDrag = false;
        return;
      }

      const wasSelectedBeforeClick = selectedNodeId === nodeId;
      selectedNodeId = nodeId;
      renderDetails(nodeId);

      const shiftKey = !!(
        params.event &&
        (
          (params.event.srcEvent && params.event.srcEvent.shiftKey) ||
          params.event.shiftKey
        )
      );

      if (!shiftKey) {
        const directChildren = (children[nodeId] || []).filter(child => activeNodeIds.has(child));

        if (directChildren.length) {
          if (wasSelectedBeforeClick && expandedNodes.has(nodeId)) {
            hideSubtree(nodeId);
          } else {
            expandOneLevel(nodeId);
          }
        }
      }

      relayout(false);
      pointerMovedDuringDrag = false;
    });

    network.on("click", function(params) {
      if (params.nodes && params.nodes.length) {
        return;
      }

      if (selectedNodeId && nodes.get(selectedNodeId)) {
        network.selectNodes([selectedNodeId]);
        refreshEdgeHighlights();
      }
    });

    network.on("deselectNode", function() {
      if (selectedNodeId && nodes.get(selectedNodeId)) {
        network.selectNodes([selectedNodeId]);
        refreshEdgeHighlights();
      }
    });

    installDialogFieldGuards();
    createChildFormEl.addEventListener("submit", createChildNodeFromForm);
    updateNodeFormEl.addEventListener("submit", updateNodeFromForm);
    document.getElementById("createChildSaveButton").addEventListener("click", createChildNodeFromForm);
    document.getElementById("updateNodeSaveButton").addEventListener("click", updateNodeFromForm);
    document.getElementById("deleteNodeConfirmButton").addEventListener("click", confirmDeleteSelectedNode);
    installSplitter();
    
    // Try to load from graph.graphml first, fall back to embedded data
    (async () => {
      const loadedFromFile = await loadGraphmlOnStartup();
      if (loadedFromFile) {
        initFromLoadedGraphml();
      } else {
        // Use embedded data
        initFromRoot(ORIGINAL_ROOT);
      }
    })();
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


class GraphOutputHandler(http.server.SimpleHTTPRequestHandler):
    def do_PUT(self):
        if self.path.split("?", 1)[0] != "/graph.graphml":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        Path(self.directory, "graph.graphml").write_bytes(self.rfile.read(length))
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve_output(output_dir: Path, port: int):
    handler = partial(GraphOutputHandler, directory=str(output_dir))
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Open http://127.0.0.1:{port}/graph.html")
        print("Create, update, and delete will overwrite graph.graphml in this folder.")
        httpd.serve_forever()


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
        default="Knowledge Graph",
        help="HTML title",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve the output folder so the graph page can overwrite graph.graphml in place",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to use with --serve",
    )
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = build_graph(folder)
    root = choose_root(graph, args.root)

    html = generate_html(graph, root, args.depth, args.title)

    html_path = output_dir / "graph.html"
    graphml_path = output_dir / "graph.graphml"

    html_path.write_text(html, encoding="utf-8")
    nx.write_graphml(sanitize_graphml(graph), graphml_path)

    print(f"Root: {root}")
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Saved HTML: {html_path}")
    print(f"Saved GraphML: {graphml_path}")

    if args.serve:
        serve_output(output_dir, args.port)


if __name__ == "__main__":
    main()
