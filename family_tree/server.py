#!/usr/bin/env python3
"""
FastAPI server for family tree graph visualization.
Serves the graph_output folder and handles graph.graphml updates.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from pathlib import Path
from typing import Optional
import asyncio
import hashlib
import os
import shutil
import csv
import io

app = FastAPI(title="Family Tree Graph Server")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)

# Get the graph_output directory
graph_output_dir = Path(__file__).parent / "graph_output"
if not graph_output_dir.exists():
    graph_output_dir.mkdir(parents=True, exist_ok=True)

# Mount the graph_output directory as static files with cache control
app.mount("/static", StaticFiles(directory=str(graph_output_dir)), name="static")

# Ensure images directory exists
images_dir = graph_output_dir / "images"
if not images_dir.exists():
    images_dir.mkdir(parents=True, exist_ok=True)

@app.get("/")
async def read_index():
    """Serve the index.html file."""
    index_file = graph_output_dir / "graph.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "graph.html not found"}

# Serializes the read-compare-write cycle on graph.graphml so two concurrent
# writers can never both pass the version check.
graphml_lock = asyncio.Lock()


def graphml_etag(graphml_file: Path) -> str:
    """Content hash of graph.graphml, used as its optimistic-locking version."""
    if not graphml_file.exists():
        return '"empty"'
    digest = hashlib.sha256(graphml_file.read_bytes()).hexdigest()
    return f'"{digest[:32]}"'


@app.get("/graph.graphml")
async def read_graphml():
    """Serve the graph.graphml file along with its current version (ETag)."""
    graphml_file = graph_output_dir / "graph.graphml"
    if not graphml_file.exists():
        return {"error": "graph.graphml not found"}
    async with graphml_lock:
        content = graphml_file.read_bytes()
        etag = graphml_etag(graphml_file)
    return Response(
        content=content,
        media_type="application/xml",
        headers={"ETag": etag, "Cache-Control": "no-store"},
    )

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """
    Handle image uploads for node metadata.
    Accepts JPEG or PNG files up to 10MB.
    """
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are allowed")
    
    # Validate file size (10MB = 10 * 1024 * 1024 bytes)
    MAX_SIZE = 10 * 1024 * 1024
    file_content = await file.read()
    if len(file_content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    
    # Generate unique filename
    import uuid
    file_extension = ".jpg" if file.content_type == "image/jpeg" else ".png"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = images_dir / unique_filename
    
    # Save the file
    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return {
            "status": "success",
            "filename": unique_filename,
            "url": f"/static/images/{unique_filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

@app.delete("/delete-image")
async def delete_image(image_url: str = Body(..., embed=True)):
    """
    Delete an image file from the images directory.
    """
    try:
        # Extract filename from URL
        # URL format: /static/images/filename.jpg
        if not image_url.startswith("/static/images/"):
            raise HTTPException(status_code=400, detail="Invalid image URL format")
        
        filename = image_url.split("/")[-1]
        file_path = images_dir / filename
        
        if file_path.exists():
            file_path.unlink()
            return {"status": "success", "message": f"Deleted {filename}"}
        else:
            return {"status": "success", "message": f"File {filename} not found, nothing to delete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete image: {str(e)}")

@app.put("/graph.graphml")
async def save_graphml(
    content: str = Body(..., media_type="text/plain"),
    if_match: Optional[str] = Header(None),
):
    """
    Handle PUT requests to save graph.graphml file.

    Uses optimistic locking: the client echoes back the ETag it last read via
    If-Match. If the file changed in the meantime the write is rejected with
    409 so the client can reload or deliberately overwrite. `If-Match: *`
    forces an unconditional write.
    """
    graphml_file = graph_output_dir / "graph.graphml"

    async with graphml_lock:
        current_etag = graphml_etag(graphml_file)

        if if_match and if_match != "*" and if_match != current_etag:
            print(f"Version conflict: client={if_match}, server={current_etag}")
            raise HTTPException(
                status_code=409,
                detail="graph.graphml was modified by someone else since you loaded it.",
                headers={"ETag": current_etag},
            )

        try:
            # Write to a temp file and rename so readers never see a partial file.
            temp_file = graphml_file.with_suffix(".graphml.tmp")
            temp_file.write_text(content, encoding="utf-8")
            os.replace(temp_file, graphml_file)
            new_etag = graphml_etag(graphml_file)
        except Exception as e:
            print(f"Error saving graph.graphml: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save graph.graphml: {str(e)}")

    print(f"Successfully saved graph.graphml ({len(content)} bytes, etag {new_etag})")
    return Response(
        content='{"status": "success", "message": "graph.graphml saved successfully"}',
        media_type="application/json",
        headers={"ETag": new_etag},
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "graph_output_dir": str(graph_output_dir)}


def parse_name_parts(name: str, summary: str = "") -> tuple:
    """
    Parse a full name into (last_name, middle_name, first_name).
    If summary is provided, try to extract name details from it first.
    """
    if summary:
        last, middle, first = parse_name_from_summary(summary)
        if last and first:
            return (last, middle, first)

    # Fallback to parsing the name string
    parts = name.strip().split()
    if len(parts) == 0:
        return ("", "", "")
    elif len(parts) == 1:
        return (parts[0], "", "")
    elif len(parts) == 2:
        return (parts[0], "", parts[1])
    else:
        return (parts[0], " ".join(parts[1:-1]), parts[-1])


def parse_name_from_summary(summary_text: str) -> tuple:
    """
    Parse last name, middle name, and first name from summary content.
    Expected format in summary:
    - **Last Name:** value
    - **Middle Name:** value
    - **First Name:** value
    """
    import re

    last_name = ""
    middle_name = ""
    first_name = ""

    # Parse Last Name
    last_match = re.search(r'\*\*Last Name:\*\*\s*(.+?)(?:\n|$)', summary_text)
    if last_match:
        last_name = last_match.group(1).strip()

    # Parse Middle Name
    middle_match = re.search(r'\*\*Middle Name:\*\*\s*(.+?)(?:\n|$)', summary_text)
    if middle_match:
        middle_name = middle_match.group(1).strip()

    # Parse First Name
    first_match = re.search(r'\*\*First Name:\*\*\s*(.+?)(?:\n|$)', summary_text)
    if first_match:
        first_name = first_match.group(1).strip()

    return last_name, middle_name, first_name


def graph_to_csv(graphml_file: Path) -> tuple:
    """
    Convert the graph.graphml file back to CSV format.
    The CSV format has 3 columns per generation (last, middle, first name).

    Returns a tuple of (csv_content, error_message).
    If error_message is not None, csv_content will be None.

    Note: This is a best-effort reconstruction. The graph format doesn't preserve
    the original row positions from the CSV, so the exported CSV may have a different
    layout than the original, though the family relationships will be preserved.
    """
    import networkx as nx
    import re

    # Load the graph
    graph = nx.read_graphml(graphml_file)
    if not isinstance(graph, nx.DiGraph):
        graph = graph.to_directed()

    # Filter out summary file nodes (nodes that look like *_1_2, *_2_2, etc.)
    # These are artifacts from the markdown generation and shouldn't be in the CSV
    def is_summary_node(node_name: str) -> bool:
        return bool(re.search(r'_\d+_\d+$', node_name))

    filtered_nodes = [n for n in graph.nodes if not is_summary_node(n)]
    graph = graph.subgraph(filtered_nodes).copy()

    # Check if all nodes have name details in their summary
    missing_name_nodes = []
    for node, attrs in graph.nodes(data=True):
        summary = attrs.get('summary', '')
        if not summary:
            missing_name_nodes.append(node)
            continue

        # Check if node is a couple
        if " & " in node:
            # Need name details for both people
            parts = node.split(" & ")
            if len(parts) == 2:
                # Check if summary has "Person 1" and "Person 2" sections
                if "### Person 1" not in summary or "### Person 2" not in summary:
                    missing_name_nodes.append(node)
                    continue

                # Check if Person 1 has all name fields
                person1_section = summary.split("### Person 1")[1].split("### Person 2")[0] if "### Person 2" in summary else summary.split("### Person 1")[1]
                p1_last, p1_middle, p1_first = parse_name_from_summary(person1_section)
                if not p1_last or not p1_first:
                    missing_name_nodes.append(node)
                    continue

                # Check if Person 2 has all name fields
                person2_section = summary.split("### Person 2")[1] if "### Person 2" in summary else ""
                p2_last, p2_middle, p2_first = parse_name_from_summary(person2_section)
                if not p2_last or not p2_first:
                    missing_name_nodes.append(node)
                    continue
        else:
            # Individual - check if has all name fields
            last, middle, first = parse_name_from_summary(summary)
            if not last or not first:
                missing_name_nodes.append(node)
                continue

    if missing_name_nodes:
        error_msg = (
            "Cannot export CSV: The following nodes are missing name details in their Detail Information:\n\n"
            + "\n".join(f"- {node}" for node in missing_name_nodes[:10])
            + ("\n..." if len(missing_name_nodes) > 10 else "")
            + "\n\nTo fix this:\n"
            "1. Click on each node in the graph\n"
            "2. Click 'Update node'\n"
            "3. In the Detail Information section, add:\n"
            "   - **Last Name:** [last name]\n"
            "   - **Middle Name:** [middle name or leave empty]\n"
            "   - **First Name:** [first name]\n"
            "4. For couples, add separate sections for Person 1 and Person 2"
        )
        return None, error_msg

    # Find the root node (node with no incoming edges)
    roots = [n for n in graph.nodes if graph.in_degree(n) == 0]
    if not roots:
        roots = list(graph.nodes)
    root = roots[0]

    # Build a hierarchical structure from the graph
    # We need to reconstruct the row-based structure from the parent-child relationships

    # First, assign generations based on distance from root
    generations = {}
    queue = [(root, 0)]
    while queue:
        node, gen = queue.pop(0)
        if node not in generations:
            generations[node] = gen
            # Get children (nodes this node points to)
            children = list(graph.successors(node))
            for child in children:
                queue.append((child, gen + 1))

    # Group nodes by generation
    gen_to_nodes = {}
    for node, gen in generations.items():
        gen_to_nodes.setdefault(gen, []).append(node)

    # Sort nodes within each generation to maintain some order
    for gen in gen_to_nodes:
        gen_to_nodes[gen].sort()

    # Build the row structure using a depth-first traversal to preserve family grouping
    max_gen = max(gen_to_nodes.keys()) if gen_to_nodes else 0

    # Build a tree structure for better row ordering
    def build_tree(node, gen):
        children = []
        for child in graph.successors(node):
            if child in generations and generations[child] == gen + 1:
                children.append(build_tree(child, gen + 1))
        return {
            'node': node,
            'gen': gen,
            'children': children,
            'summary': graph.nodes[node].get('summary', '')
        }

    tree = build_tree(root, 0)

    # Flatten the tree into rows, preserving family grouping
    rows = []

    def flatten_tree(tree_node, row_index):
        node = tree_node['node']
        gen = tree_node['gen']
        children = tree_node['children']
        summary = tree_node['summary']

        # Check if this is a couple (node name contains "&")
        if " & " in node:
            # This is a couple - split into two rows
            parts = node.split(" & ")
            if len(parts) == 2:
                person1, person2 = parts

                # Extract name details from summary for both people
                p1_last, p1_middle, p1_first = parse_name_from_summary(summary.split("### Person 1")[1].split("### Person 2")[0] if "### Person 2" in summary else summary.split("### Person 1")[1] if "### Person 1" in summary else "")
                p2_last, p2_middle, p2_first = parse_name_from_summary(summary.split("### Person 2")[1] if "### Person 2" in summary else "")

                # Use extracted names if available, otherwise fall back to node name parsing
                if p1_last and p1_first:
                    person1 = f"{p1_last} {p1_middle} {p1_first}".strip()
                if p2_last and p2_first:
                    person2 = f"{p2_last} {p2_middle} {p2_first}".strip()

                if children:
                    # Couple has children: first parent shares row with first child
                    # Process first child to get its first person
                    first_child = children[0]
                    first_child_node = first_child['node']
                    first_child_gen = first_child['gen']
                    first_child_summary = first_child['summary']

                    # Check if first child is a couple
                    if " & " in first_child_node:
                        first_child_parts = first_child_node.split(" & ")
                        if len(first_child_parts) == 2:
                            # Extract name details from first child's summary
                            fc_p1_last, fc_p1_middle, fc_p1_first = parse_name_from_summary(first_child_summary.split("### Person 1")[1].split("### Person 2")[0] if "### Person 2" in first_child_summary else first_child_summary.split("### Person 1")[1] if "### Person 1" in first_child_summary else "")
                            fc_p2_last, fc_p2_middle, fc_p2_first = parse_name_from_summary(first_child_summary.split("### Person 2")[1] if "### Person 2" in first_child_summary else "")

                            # Use extracted names if available
                            if fc_p1_last and fc_p1_first:
                                first_child_person1 = f"{fc_p1_last} {fc_p1_middle} {fc_p1_first}".strip()
                            else:
                                first_child_person1 = first_child_parts[0]

                            if fc_p2_last and fc_p2_first:
                                first_child_person2 = f"{fc_p2_last} {fc_p2_middle} {fc_p2_first}".strip()
                            else:
                                first_child_person2 = first_child_parts[1]

                            # Row 1: First parent + first child's first person
                            rows.append({gen: person1, first_child_gen: first_child_person1, '_row': row_index})
                            # Row 2: Second parent
                            rows.append({gen: person2, '_row': row_index + 1})
                            row_index += 2
                            # Add first child's second person
                            rows.append({first_child_gen: first_child_person2, '_row': row_index})
                            row_index += 1
                            # Process remaining children of first child
                            for grandchild in first_child['children']:
                                row_index = flatten_tree(grandchild, row_index)
                            # Process remaining children
                            for child in children[1:]:
                                row_index = flatten_tree(child, row_index)
                        else:
                            # Malformed child couple, treat as individual
                            rows.append({gen: person1, first_child_gen: first_child_node, '_row': row_index})
                            rows.append({gen: person2, '_row': row_index + 1})
                            row_index += 2
                            for grandchild in first_child['children']:
                                row_index = flatten_tree(grandchild, row_index)
                            for child in children[1:]:
                                row_index = flatten_tree(child, row_index)
                    else:
                        # First child is individual
                        # Extract name details from first child's summary
                        fc_last, fc_middle, fc_first = parse_name_from_summary(first_child_summary)
                        if fc_last and fc_first:
                            first_child_node = f"{fc_last} {fc_middle} {fc_first}".strip()

                        # Row 1: First parent + first child
                        rows.append({gen: person1, first_child_gen: first_child_node, '_row': row_index})
                        # Row 2: Second parent
                        rows.append({gen: person2, '_row': row_index + 1})
                        row_index += 2
                        # Process remaining children of first child
                        for grandchild in first_child['children']:
                            row_index = flatten_tree(grandchild, row_index)
                        # Process remaining children
                        for child in children[1:]:
                            row_index = flatten_tree(child, row_index)
                else:
                    # Couple has no children: just add both parents
                    rows.append({gen: person1, '_row': row_index})
                    rows.append({gen: person2, '_row': row_index + 1})
                    row_index += 2
            else:
                # Malformed couple name, treat as individual
                if children:
                    # Individual with children: share row with first child
                    first_child = children[0]
                    first_child_node = first_child['node']
                    first_child_gen = first_child['gen']
                    first_child_summary = first_child['summary']

                    if " & " in first_child_node:
                        first_child_parts = first_child_node.split(" & ")
                        if len(first_child_parts) == 2:
                            # Extract name details from first child's summary
                            fc_p1_last, fc_p1_middle, fc_p1_first = parse_name_from_summary(first_child_summary.split("### Person 1")[1].split("### Person 2")[0] if "### Person 2" in first_child_summary else first_child_summary.split("### Person 1")[1] if "### Person 1" in first_child_summary else "")
                            fc_p2_last, fc_p2_middle, fc_p2_first = parse_name_from_summary(first_child_summary.split("### Person 2")[1] if "### Person 2" in first_child_summary else "")

                            if fc_p1_last and fc_p1_first:
                                first_child_person1 = f"{fc_p1_last} {fc_p1_middle} {fc_p1_first}".strip()
                            else:
                                first_child_person1 = first_child_parts[0]

                            if fc_p2_last and fc_p2_first:
                                first_child_person2 = f"{fc_p2_last} {fc_p2_middle} {fc_p2_first}".strip()
                            else:
                                first_child_person2 = first_child_parts[1]

                            rows.append({gen: node, first_child_gen: first_child_person1, '_row': row_index})
                            row_index += 1
                            rows.append({first_child_gen: first_child_person2, '_row': row_index})
                            row_index += 1
                            for grandchild in first_child['children']:
                                row_index = flatten_tree(grandchild, row_index)
                            for child in children[1:]:
                                row_index = flatten_tree(child, row_index)
                        else:
                            rows.append({gen: node, first_child_gen: first_child_node, '_row': row_index})
                            row_index += 1
                            for grandchild in first_child['children']:
                                row_index = flatten_tree(grandchild, row_index)
                            for child in children[1:]:
                                row_index = flatten_tree(child, row_index)
                    else:
                        # Extract name details from first child's summary
                        fc_last, fc_middle, fc_first = parse_name_from_summary(first_child_summary)
                        if fc_last and fc_first:
                            first_child_node = f"{fc_last} {fc_middle} {fc_first}".strip()

                        rows.append({gen: node, first_child_gen: first_child_node, '_row': row_index})
                        row_index += 1
                        for grandchild in first_child['children']:
                            row_index = flatten_tree(grandchild, row_index)
                        for child in children[1:]:
                            row_index = flatten_tree(child, row_index)
                else:
                    # Individual without children
                    rows.append({gen: node, '_row': row_index})
                    row_index += 1
        else:
            # Individual
            # Extract name details from summary
            ind_last, ind_middle, ind_first = parse_name_from_summary(summary)
            if ind_last and ind_first:
                node = f"{ind_last} {ind_middle} {ind_first}".strip()

            if children:
                # Individual with children: share row with first child
                first_child = children[0]
                first_child_node = first_child['node']
                first_child_gen = first_child['gen']
                first_child_summary = first_child['summary']

                if " & " in first_child_node:
                    first_child_parts = first_child_node.split(" & ")
                    if len(first_child_parts) == 2:
                        # Extract name details from first child's summary
                        fc_p1_last, fc_p1_middle, fc_p1_first = parse_name_from_summary(first_child_summary.split("### Person 1")[1].split("### Person 2")[0] if "### Person 2" in first_child_summary else first_child_summary.split("### Person 1")[1] if "### Person 1" in first_child_summary else "")
                        fc_p2_last, fc_p2_middle, fc_p2_first = parse_name_from_summary(first_child_summary.split("### Person 2")[1] if "### Person 2" in first_child_summary else "")

                        if fc_p1_last and fc_p1_first:
                            first_child_person1 = f"{fc_p1_last} {fc_p1_middle} {fc_p1_first}".strip()
                        else:
                            first_child_person1 = first_child_parts[0]

                        if fc_p2_last and fc_p2_first:
                            first_child_person2 = f"{fc_p2_last} {fc_p2_middle} {fc_p2_first}".strip()
                        else:
                            first_child_person2 = first_child_parts[1]

                        rows.append({gen: node, first_child_gen: first_child_person1, '_row': row_index})
                        row_index += 1
                        rows.append({first_child_gen: first_child_person2, '_row': row_index})
                        row_index += 1
                        for grandchild in first_child['children']:
                            row_index = flatten_tree(grandchild, row_index)
                        for child in children[1:]:
                            row_index = flatten_tree(child, row_index)
                    else:
                        # Extract name details from first child's summary
                        fc_last, fc_middle, fc_first = parse_name_from_summary(first_child_summary)
                        if fc_last and fc_first:
                            first_child_node = f"{fc_last} {fc_middle} {fc_first}".strip()

                        rows.append({gen: node, first_child_gen: first_child_node, '_row': row_index})
                        row_index += 1
                        for grandchild in first_child['children']:
                            row_index = flatten_tree(grandchild, row_index)
                        for child in children[1:]:
                            row_index = flatten_tree(child, row_index)
                else:
                    # Extract name details from first child's summary
                    fc_last, fc_middle, fc_first = parse_name_from_summary(first_child_summary)
                    if fc_last and fc_first:
                        first_child_node = f"{fc_last} {fc_middle} {fc_first}".strip()

                    rows.append({gen: node, first_child_gen: first_child_node, '_row': row_index})
                    row_index += 1
                    for grandchild in first_child['children']:
                        row_index = flatten_tree(grandchild, row_index)
                    for child in children[1:]:
                        row_index = flatten_tree(child, row_index)
            else:
                # Individual without children
                rows.append({gen: node, '_row': row_index})
                row_index += 1

        return row_index

    flatten_tree(tree, 0)

    # Now convert rows to CSV format
    # Each row needs to have entries for all generations up to max_gen
    # Each generation takes 3 columns (last, middle, first)

    csv_rows = []
    for row in rows:
        csv_row = []
        for gen in range(max_gen + 1):
            if gen in row:
                last, middle, first = parse_name_parts(row[gen])
                csv_row.extend([last, middle, first])
            else:
                csv_row.extend(["", "", ""])
        csv_rows.append(csv_row)

    # Write to CSV string
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(csv_rows)
    return output.getvalue(), None


@app.get("/export.csv")
async def export_csv():
    """
    Export the current graph as a CSV file in the original family tree format.
    """
    graphml_file = graph_output_dir / "graph.graphml"
    if not graphml_file.exists():
        raise HTTPException(status_code=404, detail="graph.graphml not found")

    try:
        csv_content, error_message = graph_to_csv(graphml_file)
        if error_message:
            # Return error as plain text for display in browser
            return Response(
                content=error_message,
                media_type="text/plain",
                status_code=400
            )
        print(f"CSV export: {len(csv_content)} bytes")
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=family_tree.csv"},
        )
    except Exception as e:
        import traceback
        print(f"Error exporting CSV: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to export CSV: {str(e)}")

def main():
    import uvicorn
    
    print(f"Starting Family Tree Graph Server...")
    print(f"Serving files from: {graph_output_dir}")
    print(f"Open your browser to: http://localhost:8000")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
