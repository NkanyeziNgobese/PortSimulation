# ====================================================================================================
# Fork Point: Compare stage (Option B agent loop)
#
# This module corresponds to COMPARE:
# - Inputs: baseline and after KPI DataFrames (usually loaded from baseline/kpis.csv and after/kpis.csv)
# - Outputs:
#   1) `comparison` dict: JSON-friendly payload written to comparison.json
#   2) `comparison_df`: tabular view written to comparison.csv
#
# Why tails matter (p90/p95):
# - Congestion systems often have "long tails" (a few cases get very delayed).
# - Mean alone can hide that tail, so we report median + p90/p95 alongside the mean.
# ====================================================================================================

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd


# Headline metrics for before/after comparisons:
# - `total_time` is the main outcome (minutes in system).
# - The stage waits explain *why* total_time changed (where delay moved or improved).
COMPARE_METRICS = [
    "total_time",
    "scan_wait",
    "yard_to_scan_wait",
    "yard_to_truck_wait",
    "loading_wait",
    "gate_wait",
    "pre_pickup_wait",
    "ready_to_pickup_wait",
    "yard_equipment_wait",
]


# ----------------------------------------------------------------------------------------------------
# _series_stats
# Purpose (simple): Summarize a numeric series with mean/median and tail percentiles.
# Loop stage: Compare
# Inputs: `series` (pandas Series)
# Outputs: dict with keys mean/median/p90/p95 (values may be None)
# Interview explanation: "We summarize both central tendency and tail behavior for congestion."
# ----------------------------------------------------------------------------------------------------
def _series_stats(series: pd.Series) -> Dict[str, float | None]:
    values = series.dropna()
    if values.empty:
        return {"mean": None, "median": None, "p90": None, "p95": None}
    return {
        "mean": float(values.mean()),
        "median": float(values.median()),
        "p90": float(values.quantile(0.90)),
        "p95": float(values.quantile(0.95)),
    }


# ----------------------------------------------------------------------------------------------------
# compare_kpis
# Purpose (simple): Compute before/after summary stats and deltas for a fixed set of KPI metrics.
# Loop stage: Compare
# Inputs: `baseline_df` and `after_df` (KPI tables)
# Outputs: (comparison dict, comparison_df DataFrame)
# Interview explanation: "For each metric, we compute baseline stats, after stats, and deltas when both exist."
# ----------------------------------------------------------------------------------------------------
def compare_kpis(
    baseline_df: pd.DataFrame, after_df: pd.DataFrame
) -> Tuple[Dict[str, object], pd.DataFrame]:
    rows: List[dict] = []
    # Iterate a stable, ordered list of KPI metrics so the output is predictable run-to-run.
    for metric in COMPARE_METRICS:
        # Compute stats only if the column exists; missing columns yield empty stats.
        base_stats = _series_stats(baseline_df[metric]) if metric in baseline_df.columns else {}
        after_stats = _series_stats(after_df[metric]) if metric in after_df.columns else {}
        # Delta calculations are guarded: we only subtract when both baseline and after values exist.
        row = {
            "metric": metric,
            "baseline_mean": base_stats.get("mean"),
            "after_mean": after_stats.get("mean"),
            "delta_mean": (
                after_stats.get("mean") - base_stats.get("mean")
                if base_stats.get("mean") is not None and after_stats.get("mean") is not None
                else None
            ),
            "baseline_median": base_stats.get("median"),
            "after_median": after_stats.get("median"),
            "delta_median": (
                after_stats.get("median") - base_stats.get("median")
                if base_stats.get("median") is not None and after_stats.get("median") is not None
                else None
            ),
            "baseline_p90": base_stats.get("p90"),
            "after_p90": after_stats.get("p90"),
            "delta_p90": (
                after_stats.get("p90") - base_stats.get("p90")
                if base_stats.get("p90") is not None and after_stats.get("p90") is not None
                else None
            ),
            "baseline_p95": base_stats.get("p95"),
            "after_p95": after_stats.get("p95"),
            "delta_p95": (
                after_stats.get("p95") - base_stats.get("p95")
                if base_stats.get("p95") is not None and after_stats.get("p95") is not None
                else None
            ),
        }
        rows.append(row)

    # Build both forms:
    # - DataFrame: easy to export as CSV and scan in a spreadsheet
    # - dict: JSON-friendly structure for `comparison.json`
    comparison_df = pd.DataFrame(rows)
    comparison = {
        "baseline_rows": int(len(baseline_df)),
        "after_rows": int(len(after_df)),
        "metrics": rows,
    }
    return comparison, comparison_df


# Interview "return to orchestrator" note:
# - After this returns, the orchestrator writes comparison.json and comparison.csv,
#   then builds agentic_summary.md for a reviewer-friendly narrative.


# ----------------------------------------------------------------------------------------------------
# Closing notes (for interviews / demos)
#
# What this module proves:
# - Transparent before/after evaluation using simple, inspectable distribution summaries.
#
# Limitation:
# - These are summary statistics, not causal proof. They do not explain *why* a change worked.
#
# Why acceptable for Option B:
# - The demo is bounded and deterministic (same seed), so comparisons are meaningful and easy to audit.
# ----------------------------------------------------------------------------------------------------
