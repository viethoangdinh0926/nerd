#!/usr/bin/env python3

import argparse
import ast
import re
from pathlib import Path

import networkx as nx


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def slugify_filename(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(title).strip())
    slug = slug.strip("._")
    return slug or "node"


def parse_summary(value) -> str:
    if value is None:
        return ""

    text = str(value)
    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = ast.literal_eval(stripped)
            if isinstance(parsed, list):
                return "\n".join("" if item is None else str(item) for item in parsed)
        except (ValueError, SyntaxError):
            pass
    return text


def safe_markdown_name(name: str, fallback: str) -> str:
    candidate = Path(str(name or "").strip()).name
    if not candidate or candidate in {".", ".."}:
        candidate = fallback
    if not candidate.lower().endswith(".md"):
        candidate += ".md"
    return candidate


def unique_name(desired: str, used: set[str]) -> str:
    name = desired
    if name not in used:
        used.add(name)
        return name

    stem = name[:-3] if name.lower().endswith(".md") else name
    suffix = 2
    while f"{stem}_{suffix}.md" in used:
        suffix += 1
    name = f"{stem}_{suffix}.md"
    used.add(name)
    return name


def edge_order(graph: nx.DiGraph, parent, child) -> int:
    raw = graph.edges[parent, child].get("order", -1)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


def ordered_children(graph: nx.DiGraph, node: str):
    children = list(graph.successors(node))
    children.sort(
        key=lambda child: (
            edge_order(graph, node, child) == -1,
            edge_order(graph, node, child),
            str(child).lower(),
        )
    )
    return children


def find_graphml(folder: Path) -> Path:
    graphml_path = folder / "graph.graphml"
    if not graphml_path.is_file():
        raise FileNotFoundError(f"No graph.graphml found in {folder}")
    return graphml_path


def load_graph(graphml_path: Path) -> nx.DiGraph:
    graph = nx.read_graphml(graphml_path)
    if not isinstance(graph, nx.DiGraph):
        graph = graph.to_directed()
    return graph


def build_source_markdown(title: str, summary_file: str, graph: nx.DiGraph) -> str:
    lines = [
        f"# {title}",
        "",
        "## Type",
        "concept",
        "",
        "## Domain",
        "general",
        "",
        "## Summary",
        summary_file,
        "",
        "---",
        "",
        "## Relationships",
    ]

    for child in ordered_children(graph, title):
        relation = normalize(str(graph.edges[title, child].get("relation", "") or "related"))
        lines.append(f"- {relation} -> {child}")

    lines.append("")
    return "\n".join(lines)


def generate_sources(graph: nx.DiGraph, output_dir: Path):
    used_names: set[str] = set()
    written = []

    for node, attrs in graph.nodes(data=True):
        title = str(node)
        slug = slugify_filename(title)
        source_file = unique_name(
            safe_markdown_name(attrs.get("source_file", ""), f"{slug}.md"),
            used_names,
        )
        summary_file = unique_name(
            safe_markdown_name(attrs.get("summary_file", ""), f"{slug}_summary.md"),
            used_names,
        )

        summary_text = parse_summary(attrs.get("summary", attrs.get("summary_lines")))
        if summary_text and not summary_text.endswith("\n"):
            summary_text += "\n"

        source_path = output_dir / source_file
        summary_path = output_dir / summary_file
        source_path.write_text(
            build_source_markdown(title, summary_file, graph),
            encoding="utf-8",
        )
        summary_path.write_text(summary_text, encoding="utf-8")
        written.append((source_file, summary_file))

    return written


def main():
    parser = argparse.ArgumentParser(
        description="Generate source and summary markdown files from a folder that contains graph.graphml."
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing a valid graph.graphml file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Folder to write generated .md files into",
    )
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    if not folder.is_dir():
        raise NotADirectoryError(f"Folder not found: {folder}")

    graphml_path = find_graphml(folder)
    graph = load_graph(graphml_path)
    if graph.number_of_nodes() == 0:
        raise ValueError(f"{graphml_path} does not contain any nodes")

    output_dir.mkdir(parents=True, exist_ok=True)
    written = generate_sources(graph, output_dir)

    print(f"Read GraphML: {graphml_path}")
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Wrote {len(written)} source files and {len(written)} summary files to {output_dir}")


if __name__ == "__main__":
    main()
