"""Pydantic models for inter-phase JSON contracts."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Phase 1 — Shadow
# ---------------------------------------------------------------------------

class VersionChange(BaseModel):
    dependency_group: str
    version_key: str
    before: str
    after: str


class ShadowManifest(BaseModel):
    before_dir: str
    after_dir: str
    version_change: VersionChange
    init_script_injected: bool = False
    detekt_reports: dict[str, str] = Field(default_factory=dict)
    kover_reports: dict[str, str] = Field(default_factory=dict)
    compilation_after: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 2 — Static Analysis
# ---------------------------------------------------------------------------

class DeclarationKind(str, Enum):
    CLASS = "class"
    OBJECT = "object"
    INTERFACE = "interface"
    FUNCTION = "fun"
    TYPEALIAS = "typealias"
    PROPERTY = "property"


class KotlinDeclaration(BaseModel):
    kind: DeclarationKind
    name: str
    fqcn: str
    is_expect: bool = False
    is_actual: bool = False
    source_set: str = "common"
    file_path: str = ""


class FileParseResult(BaseModel):
    file_path: str
    package: str = ""
    imports: list[str] = Field(default_factory=list)
    declarations: list[KotlinDeclaration] = Field(default_factory=list)
    source_set: str = "common"


class SourceMetrics(BaseModel):
    rloc: int = 0
    functions: int = 0
    mcc: int = 1
    detekt_findings: int = 0
    test_coverage: float = -1.0  # -1 = not available, 0-100 = percentage
    metrics_source: str = "heuristic"  # "heuristic" | "detekt"


class ImpactRelation(str, Enum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    EXPECT_ACTUAL = "expect_actual"


class FileImpact(BaseModel):
    file_path: str
    relation: ImpactRelation
    distance: int = 0
    imports_from_dependency: list[str] = Field(default_factory=list)
    metrics: SourceMetrics = Field(default_factory=SourceMetrics)
    declarations: list[str] = Field(default_factory=list)
    source_set: str = "common"


class ExpectActualPair(BaseModel):
    expect_fqcn: str
    expect_file: str
    actual_files: list[str] = Field(default_factory=list)


class ImpactGraph(BaseModel):
    dependency_group: str
    version_before: str
    version_after: str
    seed_files: list[str] = Field(default_factory=list)
    impacted_files: list[FileImpact] = Field(default_factory=list)
    expect_actual_pairs: list[ExpectActualPair] = Field(default_factory=list)
    total_project_files: int = 0
    total_impacted: int = 0


# ---------------------------------------------------------------------------
# Phase 3 — Dynamic Analysis
# ---------------------------------------------------------------------------

class UTGNode(BaseModel):
    state_id: str = ""
    activity: str = ""
    state_str: str = ""
    screen_name: str = ""


class UTGEdge(BaseModel):
    source: str = ""
    target: str = ""
    action: str = ""


class UTGGraph(BaseModel):
    nodes: list[UTGNode] = Field(default_factory=list)
    edges: list[UTGEdge] = Field(default_factory=list)


class ScreenDiff(BaseModel):
    screen_name: str
    status: str  # "missing", "new", "changed"
    details: str = ""


class DynamicStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class UIRegressions(BaseModel):
    status: DynamicStatus = DynamicStatus.SKIPPED
    blocked_reason: str = ""
    before_screens: list[str] = Field(default_factory=list)
    after_screens: list[str] = Field(default_factory=list)
    diffs: list[ScreenDiff] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 4 — Consolidation
# ---------------------------------------------------------------------------

class ScreenMapping(BaseModel):
    screen_name: str
    mapped_files: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    method: str = ""


class TraceEntry(BaseModel):
    file_path: str
    relation: ImpactRelation
    distance: int = 0
    screens: list[str] = Field(default_factory=list)
    metrics: SourceMetrics = Field(default_factory=SourceMetrics)


class ConsolidatedResult(BaseModel):
    dependency_group: str
    version_before: str
    version_after: str
    static_impact: ImpactGraph
    dynamic_regressions: UIRegressions
    screen_mappings: list[ScreenMapping] = Field(default_factory=list)
    trace: list[TraceEntry] = Field(default_factory=list)
    impacted_screens: list[str] = Field(default_factory=list)
    total_impacted_files: int = 0
    total_impacted_screens: int = 0


# ---------------------------------------------------------------------------
# Phase 5 — Visualization (CodeCharta)
# ---------------------------------------------------------------------------

class CCAttribute(BaseModel):
    rloc: int = 0
    mcc: int = 1
    impacted: int = 0
    impact_direct: int = 0
    impact_transitive: int = 0
    screen_impacted: int = 0
    screen_names: int = 0


class CCNode(BaseModel):
    name: str
    type: str = "File"
    attributes: CCAttribute = Field(default_factory=CCAttribute)
    children: list[CCNode] = Field(default_factory=list)


class CCProject(BaseModel):
    project_name: str
    api_version: str = "1.3"
    nodes: list[CCNode] = Field(default_factory=list)
    attribute_types: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evaluation (OE5)
# ---------------------------------------------------------------------------

class EvaluationResult(BaseModel):
    scenario: str = ""
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    true_positives: list[str] = Field(default_factory=list)
    false_positives: list[str] = Field(default_factory=list)
    false_negatives: list[str] = Field(default_factory=list)
    screen_precision: float = 0.0
    screen_recall: float = 0.0
    screen_f1: float = 0.0
    screen_tp: list[str] = Field(default_factory=list)
    screen_fp: list[str] = Field(default_factory=list)
    screen_fn: list[str] = Field(default_factory=list)
