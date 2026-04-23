"""Compare two UTGs to find screen-level differences."""

from __future__ import annotations

from ..contracts import ScreenDiff, UTGGraph


def compare_utgs(before: UTGGraph, after: UTGGraph) -> list[ScreenDiff]:
    """Compare before/after UTGs and return screen differences."""
    before_screens = {n.screen_name for n in before.nodes if n.screen_name}
    after_screens = {n.screen_name for n in after.nodes if n.screen_name}

    diffs: list[ScreenDiff] = []

    # Screens present in BEFORE but missing in AFTER
    for screen in sorted(before_screens - after_screens):
        diffs.append(
            ScreenDiff(
                screen_name=screen,
                status="missing",
                details=f"Screen '{screen}' present in before but missing in after",
            )
        )

    # Screens present in AFTER but not in BEFORE
    for screen in sorted(after_screens - before_screens):
        diffs.append(
            ScreenDiff(
                screen_name=screen,
                status="new",
                details=f"Screen '{screen}' is new in after version",
            )
        )

    # Screens present in both — check for behavior changes
    for screen in sorted(before_screens & after_screens):
        before_edges = _get_screen_edges(before, screen)
        after_edges = _get_screen_edges(after, screen)
        if before_edges != after_edges:
            diffs.append(
                ScreenDiff(
                    screen_name=screen,
                    status="changed",
                    details=(
                        f"Screen '{screen}' has different transitions: "
                        f"before={len(before_edges)}, after={len(after_edges)}"
                    ),
                )
            )

    return diffs


def _get_screen_edges(utg: UTGGraph, screen_name: str) -> set[tuple[str, str]]:
    """Get all edges (action, target_screen) leaving from a screen."""
    screen_state_ids = {n.state_id for n in utg.nodes if n.screen_name == screen_name}
    screen_id_to_name = {n.state_id: n.screen_name for n in utg.nodes}

    edges: set[tuple[str, str]] = set()
    for edge in utg.edges:
        if edge.source in screen_state_ids:
            target_name = screen_id_to_name.get(edge.target, edge.target)
            edges.add((edge.action, target_name))
    return edges
