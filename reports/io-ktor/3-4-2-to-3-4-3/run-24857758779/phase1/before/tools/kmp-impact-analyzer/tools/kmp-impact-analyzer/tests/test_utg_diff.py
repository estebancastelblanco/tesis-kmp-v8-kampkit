"""Tests for UTG diff comparison."""

from kmp_impact_analyzer.contracts import UTGEdge, UTGGraph, UTGNode
from kmp_impact_analyzer.phase3_dynamic.utg_diff import compare_utgs


def test_missing_screen():
    before = UTGGraph(
        nodes=[
            UTGNode(state_id="1", activity="com.app.HomeActivity", screen_name="Home"),
            UTGNode(state_id="2", activity="com.app.SettingsActivity", screen_name="Settings"),
        ],
        edges=[],
    )
    after = UTGGraph(
        nodes=[
            UTGNode(state_id="1", activity="com.app.HomeActivity", screen_name="Home"),
        ],
        edges=[],
    )
    diffs = compare_utgs(before, after)
    assert len(diffs) == 1
    assert diffs[0].status == "missing"
    assert diffs[0].screen_name == "Settings"


def test_new_screen():
    before = UTGGraph(nodes=[
        UTGNode(state_id="1", screen_name="Home"),
    ], edges=[])
    after = UTGGraph(nodes=[
        UTGNode(state_id="1", screen_name="Home"),
        UTGNode(state_id="2", screen_name="Profile"),
    ], edges=[])
    diffs = compare_utgs(before, after)
    assert any(d.status == "new" and d.screen_name == "Profile" for d in diffs)


def test_no_changes():
    utg = UTGGraph(nodes=[
        UTGNode(state_id="1", screen_name="Home"),
    ], edges=[])
    diffs = compare_utgs(utg, utg)
    assert len(diffs) == 0
