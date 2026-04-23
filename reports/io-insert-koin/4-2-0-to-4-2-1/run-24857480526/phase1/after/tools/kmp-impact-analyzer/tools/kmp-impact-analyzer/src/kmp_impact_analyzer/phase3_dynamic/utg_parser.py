"""Parse DroidBot UTG (UI Transition Graph) output."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import UTGEdge, UTGGraph, UTGNode
from ..utils.log import get_logger

log = get_logger(__name__)


def _extract_screen_name(activity: str) -> str:
    """Extract a readable screen name from an activity class name."""
    if not activity:
        return "unknown"
    parts = activity.rsplit(".", 1)
    name = parts[-1] if len(parts) > 1 else activity
    return name.replace("Activity", "").replace("Fragment", "") or name


def parse_utg(droidbot_output_dir: Path) -> UTGGraph:
    """Parse the UTG from a DroidBot output directory."""
    utg_file = droidbot_output_dir / "utg.js"
    if not utg_file.exists():
        # Try utg.json as alternative
        utg_file = droidbot_output_dir / "utg.json"

    if not utg_file.exists():
        log.warning(f"No UTG file found in {droidbot_output_dir}")
        return UTGGraph()

    content = utg_file.read_text(encoding="utf-8", errors="replace")

    # DroidBot outputs as "var utg = {...}" - strip the JS wrapper
    if content.startswith("var "):
        eq_idx = content.index("=")
        content = content[eq_idx + 1 :].strip().rstrip(";")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse UTG: {e}")
        return UTGGraph()

    nodes: list[UTGNode] = []
    edges: list[UTGEdge] = []

    for node_data in data.get("nodes", []):
        activity = node_data.get("activity", node_data.get("foreground_activity", ""))
        state_str = node_data.get("state_str", "")
        state_id = node_data.get("id", node_data.get("state_str", ""))
        screen_name = _extract_screen_name(activity)

        nodes.append(
            UTGNode(
                state_id=str(state_id),
                activity=activity,
                state_str=state_str,
                screen_name=screen_name,
            )
        )

    for edge_data in data.get("edges", []):
        edges.append(
            UTGEdge(
                source=str(edge_data.get("from", "")),
                target=str(edge_data.get("to", "")),
                action=edge_data.get("label", edge_data.get("action", "")),
            )
        )

    log.info(f"Parsed UTG: {len(nodes)} nodes, {len(edges)} edges")
    return UTGGraph(nodes=nodes, edges=edges)
