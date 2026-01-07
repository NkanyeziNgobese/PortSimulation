from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd


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


def compare_kpis(
    baseline_df: pd.DataFrame, after_df: pd.DataFrame
) -> Tuple[Dict[str, object], pd.DataFrame]:
    rows: List[dict] = []
    for metric in COMPARE_METRICS:
        base_stats = _series_stats(baseline_df[metric]) if metric in baseline_df.columns else {}
        after_stats = _series_stats(after_df[metric]) if metric in after_df.columns else {}
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

    comparison_df = pd.DataFrame(rows)
    comparison = {
        "baseline_rows": int(len(baseline_df)),
        "after_rows": int(len(after_df)),
        "metrics": rows,
    }
    return comparison, comparison_df
