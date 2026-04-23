"""Evaluation scorer: Precision, Recall, F1 against ground truth."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..contracts import ConsolidatedResult, EvaluationResult, ImpactRelation


def _normalize_filename(path: str) -> str:
    """Normalize a file path to just the filename for comparison."""
    return Path(path).name


def score(consolidated: ConsolidatedResult, ground_truth_path: str) -> EvaluationResult:
    """Score pipeline results against a ground truth YAML file."""
    with open(ground_truth_path) as f:
        gt = yaml.safe_load(f) or {}

    # Ground truth sets
    gt_files_all = set(gt.get("impacted_files", []))
    gt_files_direct = set(gt.get("direct_files", []))
    gt_screens = set(gt.get("impacted_screens", []))

    # Pipeline results — normalize to filenames for comparison
    predicted_files = {
        _normalize_filename(fi.file_path) for fi in consolidated.static_impact.impacted_files
    }
    predicted_direct = {
        _normalize_filename(fi.file_path)
        for fi in consolidated.static_impact.impacted_files
        if fi.relation == ImpactRelation.DIRECT
    }
    predicted_screens = set(consolidated.impacted_screens)

    # Compute file-level metrics (all impacted)
    tp_files = predicted_files & gt_files_all
    fp_files = predicted_files - gt_files_all
    fn_files = gt_files_all - predicted_files

    precision = len(tp_files) / len(predicted_files) if predicted_files else 0.0
    recall = len(tp_files) / len(gt_files_all) if gt_files_all else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Compute screen-level metrics
    tp_screens = predicted_screens & gt_screens
    fp_screens = predicted_screens - gt_screens
    fn_screens = gt_screens - predicted_screens

    s_precision = len(tp_screens) / len(predicted_screens) if predicted_screens else 0.0
    s_recall = len(tp_screens) / len(gt_screens) if gt_screens else 0.0
    s_f1 = 2 * s_precision * s_recall / (s_precision + s_recall) if (s_precision + s_recall) > 0 else 0.0

    return EvaluationResult(
        scenario=gt.get("scenario_name", ""),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        true_positives=sorted(tp_files),
        false_positives=sorted(fp_files),
        false_negatives=sorted(fn_files),
        screen_precision=round(s_precision, 4),
        screen_recall=round(s_recall, 4),
        screen_f1=round(s_f1, 4),
        screen_tp=sorted(tp_screens),
        screen_fp=sorted(fp_screens),
        screen_fn=sorted(fn_screens),
    )
