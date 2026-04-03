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
            )
        else:
            graph.nodes[title]["source_file"] = md_file.name
            graph.nodes[title]["summary_file"] = summary_file
            graph.nodes[title]["summary_lines"] = summary_lines

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
                "label": label,
                "title": f"{u} → {v}<br>relation: {d.get('relation', '')}"
                + (f"<br>order: {order}" if order != -1 else ""),
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
      white-space: pre-wrap;
      tab-size: 4;
    }
    #details .summary-markdown code {
      background: #f3f3f3;
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
    <button onclick="setSelectedAsRoot()">Set selected as root</button>
    <button onclick="restoreOriginalTree()">Restore original tree</button>
    <button onclick="fitGraph()">Fit</button>
    <span class="hint">Click a node to select it and expand/collapse it. The visible graph auto-reorganizes after each click for a clearer layout while keeping children below parents and sibling edge order left-to-right. Shift-click only shows details.</span>
  </div>

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

  <script>
    const ROOT = __ROOT__;
    const ORIGINAL_ROOT = ROOT;
    const INIT_DEPTH = __DEPTH__;
    const nodesData = __NODES__;
    const edgesData = __EDGES__;
    const children = __CHILDREN__;

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
    let currentRoot = ORIGINAL_ROOT;
    let selectedNodeId = ORIGINAL_ROOT;
    let currentLevels = {};
    let activeNodeIds = new Set();

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

      for (const rawLine of lines) {
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
          out.push("<hr>");
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

      const summaryHtml = renderMarkdown(node.summary_lines || []);

      detailsEl.innerHTML = `
        <h2>${escapeHtml(node.label)}</h2>

        <div class="panel-field">
          <div class="section-title">Node metadata</div>
          <div class="meta-row"><span class="meta-label">Node:</span> ${escapeHtml(node.label)}</div>
          <div class="meta-row"><span class="meta-label">Source file:</span> ${node.source_file ? `<code>${escapeHtml(node.source_file)}</code>` : 'N/A'}</div>
          <div class="meta-row"><span class="meta-label">Summary file:</span> ${node.summary_file ? `<code>${escapeHtml(node.summary_file)}</code>` : 'N/A'}</div>
          <div class="meta-row"><span class="meta-label">In-degree:</span> ${node.in_degree}</div>
          <div class="meta-row"><span class="meta-label">Out-degree:</span> ${node.out_degree}</div>
          <div class="meta-row"><span class="meta-label">Level:</span> ${node.level}</div>
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

      function place(nodeId, leftUnits) {
        if (!visibleSet.has(nodeId)) return;

        const widthUnits = subtreeWidth[nodeId] || 1;
        const centerUnits = leftUnits + (widthUnits - 1) / 2;
        positions[nodeId] = {
          x: centerUnits * xSpacing,
          y: (currentLevels[nodeId] || 0) * ySpacing,
        };

        let cursor = leftUnits;
        for (const child of visibleChildrenOf(nodeId)) {
          const childWidth = subtreeWidth[child] || 1;
          place(child, cursor);
          cursor += childWidth;
        }
      }

      place(rootId, 0);

      const visibleNodes = Array.from(visibleSet);
      const xs = visibleNodes
        .filter(id => positions[id])
        .map(id => positions[id].x);

      const minX = xs.length ? Math.min(...xs) : 0;
      const maxX = xs.length ? Math.max(...xs) : 0;
      const offsetX = -((minX + maxX) / 2);

      for (const nodeId of visibleNodes) {
        const stored = nodeMap.get(nodeId);
        const pos = positions[nodeId];
        if (!stored || !pos) continue;
        stored.x = pos.x + offsetX;
        stored.y = pos.y;
        stored.level = currentLevels[nodeId] || 0;
      }
    }

    function reorganizeVisibleGraph(shouldFit = false) {
      computeVisibleLayout(currentRoot);

      const updates = nodes.getIds().map(id => {
        const stored = nodeMap.get(id);
        return stored ? { id, x: stored.x, y: stored.y, level: stored.level } : null;
      }).filter(Boolean);

      if (updates.length) {
        nodes.update(updates);
      }

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
      const directChildren = (children[id] || []).filter(child => activeNodeIds.has(child));
      for (const child of directChildren) {
        hidden.delete(child);
        showNode(child);
      }
      syncEdges();
      relayout(false);
    }

    function toggleNode(id) {
      const directChildren = (children[id] || []).filter(child => activeNodeIds.has(child));
      if (!directChildren.length) return;

      const hasVisibleChild = directChildren.some(child => nodes.get(child));
      if (hasVisibleChild) {
        hideSubtree(id);
      } else {
        expandOneLevel(id);
      }
    }

    function initFromRoot(rootId) {
      currentRoot = rootId;
      selectedNodeId = rootId;
      hidden.clear();
      nodes.clear();
      edges.clear();
      applyLayoutForRoot(rootId);

      for (const nodeId of activeNodeIds) {
        if ((currentLevels[nodeId] || 0) <= INIT_DEPTH) {
          showNode(nodeId);
        } else {
          hidden.add(nodeId);
        }
      }

      syncEdges();
      relayout(true);
      renderDetails(rootId);
    }

    function expandAll() {
      hidden.clear();
      for (const nodeId of activeNodeIds) {
        showNode(nodeId);
      }
      syncEdges();
      relayout(true);
    }

    function collapseAll() {
      for (const id of [...nodes.getIds()]) {
        if (id !== currentRoot) {
          nodes.remove(id);
          hidden.add(id);
        }
      }
      syncEdges();
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
        toggleNode(nodeId);
      }

      relayout(false);
      pointerMovedDuringDrag = false;
    });

    installSplitter();
    initFromRoot(ORIGINAL_ROOT);
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
        default="Knowledge Graph",
        help="HTML title",
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


if __name__ == "__main__":
    main()
