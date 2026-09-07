#!/usr/bin/env python3

import csv
import re
from pathlib import Path
from typing import Optional, Tuple, List


def normalize(text: str) -> str:
    """Normalize whitespace in text."""
    return re.sub(r"\s+", " ", text.strip())


def slugify_filename(title: str) -> str:
    """Convert title to a safe filename."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", title.strip())
    slug = slug.strip("._")
    return slug or "node"


def parse_person_names(last_name: str, middle_name: str, first_name: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse a person's names and return (formatted_name, last_name, middle_name, first_name), or None if empty."""
    last = last_name.strip() if last_name else ""
    middle = middle_name.strip() if middle_name else ""
    first = first_name.strip() if first_name else ""

    if not last and not middle and not first:
        return None

    parts = []
    if last:
        parts.append(last)
    if middle:
        parts.append(middle)
    if first:
        parts.append(first)

    formatted = " ".join(parts)
    return (formatted, last, middle, first)


def parse_csv_row(row: List[str]) -> List[Optional[Tuple[str, str, str, str]]]:
    """Parse a CSV row and return list of person name tuples (formatted, last, middle, first) per generation."""
    names = []
    for i in range(0, len(row), 3):
        if i + 2 < len(row):
            name = parse_person_names(row[i], row[i+1], row[i+2])
            names.append(name)
        else:
            names.append(None)
    return names


def find_consecutive_group(parsed_rows: List[List[Optional[str]]], start_idx: int, gen: int) -> int:
    """Find the size of a consecutive group of people in the same generation starting at start_idx."""
    group_size = 1
    i = start_idx + 1
    while i < len(parsed_rows):
        if gen < len(parsed_rows[i]) and parsed_rows[i][gen] is not None:
            group_size += 1
            i += 1
        else:
            break
    return group_size


def find_parent_row(rows: List[List[Optional[str]]], child_row_idx: int, child_gen: int) -> Optional[int]:
    """
    Find the parent row for a child based on the family tree structure.
    Children start at the same row as their parent and continue until a sibling
    or ancestor of the parent appears.
    """
    if child_gen == 0:
        return None

    # Find the closest non-empty row in the previous generation at or above this row
    for i in range(child_row_idx, -1, -1):
        if i < len(rows) and child_gen - 1 < len(rows[i]) and rows[i][child_gen - 1] is not None:
            return i

    return None


def build_family_tree(csv_path: Path) -> dict:
    """
    Build a family tree structure from the CSV file.
    Returns a dict with node information and relationships.
    """
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Skip header row if it looks like metadata (contains only numbers)
    if rows and all(cell.strip().isdigit() or not cell.strip() for cell in rows[0]):
        rows = rows[1:]

    # Parse each row into person names per generation
    parsed_rows = [parse_csv_row(row) for row in rows]

    # Find max generation
    max_gen = max(len(row) for row in parsed_rows) if parsed_rows else 0

    # Build nodes (individuals or couples)
    nodes = {}  # node_id -> node_info
    node_id_counter = 0

    # First pass: identify all nodes and their row ranges
    # Process each generation separately since the CSV now has multiple generations per row
    for gen in range(max_gen):
        i = 0
        while i < len(parsed_rows):
            row = parsed_rows[i]
            if gen >= len(row) or row[gen] is None:
                i += 1
                continue

            # Find the size of the consecutive group starting at this row
            group_size = find_consecutive_group(parsed_rows, i, gen)

            if group_size >= 2:
                # This is a group (couple of 2+ people)
                people = []
                for j in range(group_size):
                    people.append(parsed_rows[i + j][gen])

                # Create a node for this group (couple with first 2 people, rest as additional)
                person1 = people[0]
                person2 = people[1] if len(people) > 1 else None
                node_id = f"{slugify_filename(person1[0])}_{node_id_counter}"
                node_data = {
                    'type': 'couple',
                    'person1': person1,
                    'person2': person2,
                    'generation': gen,
                    'row_start': i,
                    'row_end': i + group_size - 1,  # Group spans group_size rows
                    'children': []
                }

                # Add additional people beyond the first two
                for j in range(2, len(people)):
                    node_data[f'person{j+1}'] = people[j]

                nodes[node_id] = node_data
                node_id_counter += 1
                i += group_size  # Skip all rows in the group
            else:
                # This is an individual
                person = row[gen]
                node_id = f"{slugify_filename(person[0])}_{node_id_counter}"
                nodes[node_id] = {
                    'type': 'individual',
                    'person': person,
                    'generation': gen,
                    'row_start': i,
                    'row_end': i,  # Individual spans 1 row
                    'children': []
                }
                node_id_counter += 1
                i += 1

    # Second pass: establish parent-child relationships
    # For each node in generation G, find its parent in generation G-1
    # The parent is the closest node in the previous generation at or above this row
    for node_id, node_info in nodes.items():
        gen = node_info['generation']
        row_start = node_info['row_start']

        if gen == 0:
            continue  # Root generation has no parents

        # Find the parent node in the previous generation
        # The parent is the closest node in gen-1 at or above this row
        best_parent = None
        best_parent_row = -1

        for potential_parent_id, potential_parent in nodes.items():
            if potential_parent['generation'] == gen - 1:
                # Check if this potential parent is at or above the child's row
                if potential_parent['row_start'] <= row_start:
                    # Find the closest parent (the one with the highest row_start that's still <= child's row_start)
                    if potential_parent['row_start'] > best_parent_row:
                        best_parent = potential_parent_id
                        best_parent_row = potential_parent['row_start']

        if best_parent:
            nodes[best_parent]['children'].append(node_id)
            node_info['parent'] = best_parent

    return nodes


def generate_markdown_files(nodes: dict, output_dir: Path):
    """Generate *_1.md and *_2.md files for all nodes."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for node_id, node_info in nodes.items():
        # Determine node title
        if node_info['type'] == 'couple':
            # Collect all people in the group
            people = [node_info['person1']]
            if node_info['person2']:
                people.append(node_info['person2'])
            # Add any additional people (person3, person4, etc.)
            person_num = 3
            while f'person{person_num}' in node_info:
                people.append(node_info[f'person{person_num}'])
                person_num += 1
            title = " & ".join(p[0] for p in people)
        else:
            title = node_info['person'][0]

        slug = slugify_filename(title)

        # Generate *_1.md (source file with relationships)
        source_file = f"{slug}_1.md"
        source_path = output_dir / source_file

        source_lines = [
            f"# {title}",
            "",
            "## Summary",
            "",
            f"{slug}_2.md",
            "",
            "---",
            "",
            "## Relationships",
        ]

        # Sort children by their row_start to maintain original CSV order
        sorted_children = sorted(node_info['children'], key=lambda child_id: nodes[child_id]['row_start'])

        for child_id in sorted_children:
            child_node = nodes[child_id]
            if child_node['type'] == 'couple':
                # Collect all people in the child group
                child_people = [child_node['person1']]
                if child_node['person2']:
                    child_people.append(child_node['person2'])
                # Add any additional people
                child_person_num = 3
                while f'person{child_person_num}' in child_node:
                    child_people.append(child_node[f'person{child_person_num}'])
                    child_person_num += 1
                child_title = " & ".join(p[0] for p in child_people)
            else:
                child_title = child_node['person'][0]
            source_lines.append(f"- parent of -> {child_title}")

        if not node_info['children']:
            source_lines.append("(No children)")

        source_lines.append("")
        source_path.write_text("\n".join(source_lines), encoding='utf-8')

        # Generate *_2.md (summary file with name details)
        summary_file = f"{slug}_2.md"
        summary_path = output_dir / summary_file

        summary_lines = [
            f"# {title}",
            "",
            "## Name Details",
        ]

        if node_info['type'] == 'couple':
            # Parse names for all people in the group
            people = [node_info['person1']]
            if node_info['person2']:
                people.append(node_info['person2'])
            # Add any additional people
            person_num = 3
            while f'person{person_num}' in node_info:
                people.append(node_info[f'person{person_num}'])
                person_num += 1

            # Add name details for each person
            for idx, person in enumerate(people, start=1):
                # person is a tuple: (formatted, last, middle, first)
                _, last, middle, first = person
                summary_lines.extend([
                    "",
                    f"### Person {idx}",
                    f"- **Last Name:** {last if last else 'N/A'}",
                    f"- **Middle Name:** {middle if middle else 'N/A'}",
                    f"- **First Name:** {first if first else 'N/A'}",
                ])
        else:
            # Individual
            # person is a tuple: (formatted, last, middle, first)
            _, last, middle, first = node_info['person']
            summary_lines.extend([
                f"- **Last Name:** {last if last else 'N/A'}",
                f"- **Middle Name:** {middle if middle else 'N/A'}",
                f"- **First Name:** {first if first else 'N/A'}",
            ])

        summary_lines.append("")
        summary_path.write_text("\n".join(summary_lines), encoding='utf-8')


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse a family tree CSV file and generate markdown files."
    )
    parser.add_argument(
        "csv_file",
        type=Path,
        help="Path to the CSV file containing the family tree",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write the generated markdown files",
    )

    args = parser.parse_args()

    csv_path = args.csv_file.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    print(f"Parsing CSV file: {csv_path}")
    nodes = build_family_tree(csv_path)

    print(f"Found {len(nodes)} nodes")
    print(f"  - Individuals: {sum(1 for n in nodes.values() if n['type'] == 'individual')}")
    print(f"  - Couples: {sum(1 for n in nodes.values() if n['type'] == 'couple')}")

    generate_markdown_files(nodes, output_dir)

    print(f"Generated markdown files in: {output_dir}")


if __name__ == "__main__":
    main()
