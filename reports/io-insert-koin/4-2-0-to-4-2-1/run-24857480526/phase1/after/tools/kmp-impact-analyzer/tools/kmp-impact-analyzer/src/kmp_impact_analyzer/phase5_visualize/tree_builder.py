"""Build hierarchical folder tree from file paths for CodeCharta."""

from __future__ import annotations

from pathlib import PurePosixPath

from ..contracts import CCAttribute, CCNode


def build_tree(file_attrs: dict[str, CCAttribute], project_name: str) -> CCNode:
    """Build a hierarchical CCNode tree from flat file paths + attributes."""
    root = CCNode(name=project_name, type="Folder", children=[])

    for file_path, attrs in sorted(file_attrs.items()):
        parts = PurePosixPath(file_path).parts
        current = root

        # Navigate/create folder hierarchy
        for i, part in enumerate(parts):
            is_file = i == len(parts) - 1
            existing = next((c for c in current.children if c.name == part), None)

            if existing is not None:
                current = existing
            else:
                node_type = "File" if is_file else "Folder"
                new_node = CCNode(
                    name=part,
                    type=node_type,
                    attributes=attrs if is_file else CCAttribute(),
                    children=[],
                )
                current.children.append(new_node)
                current = new_node

    return root
