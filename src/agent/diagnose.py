from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd


SCHEMA_VERSION = "agentic_v1"
STAGE_CANDIDATES = [
    "scan_wait",
    "yard_to_scan_wait",
    "yard_to_truck_wait",
    "loading_wait",
    "gate_wait",
    "pre_pickup_wait",
    "ready_to_pickup_wait",
    "yard_equipment_wait",
]
OPTIONAL_CONTEXT = [
    "scanner_queue_len_at_pickup",
    "loader_queue_len_at_pickup",
    "occupancy_at_yard_to_scan",
    "occupancy_at_yard_to_truck",
]


def _safe_mean(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    values = series.dropna()
    if values.empty:
        return None
    return float(values.mean())


def _safe_p95(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    values = series.dropna()
    if values.empty:
        return None
    return float(values.quantile(0.95))


def load_kpis_csv(input_path: Path) -> pd.DataFrame:
    return pd.read_csv(input_path)


def load_web_json(input_path: Path) -> pd.DataFrame:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records: List[dict] = []
    columns: Optional[List[str]] = None
    if isinstance(payload, dict):
        records = payload.get("records") or payload.get("data") or []
        columns = payload.get("columns")
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError(f"Unsupported JSON structure in {input_path}")
    df = pd.DataFrame(records)
    if columns:
        df = df.reindex(columns=columns)
    return df

def _coverage_ratio(df: pd.DataFrame, required_cols: Iterable[str]) -> float:
    required = list(required_cols)
    if not required:
        return 0.0
    present = [col for col in required if col in df.columns]
    return len(present) / len(required)


def _diagnose_dataframe(df: pd.DataFrame, input_source: str) -> Dict[str, object]:
    row_count = int(len(df))
    required_cols = ["total_time"] + STAGE_CANDIDATES
    missing_required = [col for col in required_cols if col not in df.columns]
    missing_optional = [col for col in OPTIONAL_CONTEXT if col not in df.columns]
    missing_columns = sorted(set(missing_required + missing_optional))

    mean_total = _safe_mean(df["total_time"]) if "total_time" in df.columns else None
    p95_total = _safe_p95(df["total_time"]) if "total_time" in df.columns else None

    stage_rankings = []
    for stage in STAGE_CANDIDATES:
        if stage not in df.columns:
            continue
        notes: List[str] = []
        contribution = None
        stage_series = df[stage]
        mean_wait = _safe_mean(stage_series)
        if "total_time" not in df.columns:
            notes.append("missing_total_time")
        else:
            subset = df[["total_time", stage]].dropna()
            mean_total_stage = _safe_mean(subset["total_time"])
            if mean_total_stage is None or mean_total_stage <= 0:
                notes.append("missing_total_time")
            elif mean_wait is None:
                notes.append("no_data")
            else:
                contribution = mean_wait / mean_total_stage
        stage_rankings.append(
            {
                "stage": stage,
                "mean_wait": mean_wait,
                "contribution": contribution,
                "notes": ", ".join(notes),
            }
        )

    stage_rankings.sort(
        key=lambda item: (
            item["contribution"] is None,
            -(item["contribution"] or 0.0),
        )
    )

    context_stats: Dict[str, Optional[float]] = {}
    for col in OPTIONAL_CONTEXT:
        if col in df.columns:
            context_stats[col] = _safe_mean(df[col])

    if row_count == 0 or "total_time" not in df.columns:
        confidence = 0.0
    else:
        confidence = round(_coverage_ratio(df, required_cols), 2)

    return {
        "schema_version": SCHEMA_VERSION,
        "input_source": input_source,
        "row_count": row_count,
        "missing_columns": missing_columns,
        "summary_stats": {
            "mean_total_time": mean_total,
            "p95_total_time": p95_total,
        },
        "context_stats": context_stats,
        "stage_rankings": stage_rankings,
        "confidence": confidence,
    }


def diagnose_kpis_path(input_path: str | Path) -> Dict[str, object]:
    path = Path(input_path)
    df = load_kpis_csv(path)
    return _diagnose_dataframe(df, str(path))


def diagnose_dataframe(df: pd.DataFrame, input_source: str = "dataframe") -> Dict[str, object]:
    return _diagnose_dataframe(df, input_source)


def diagnose(input_value: str | Path | pd.DataFrame) -> Dict[str, object]:
    if isinstance(input_value, pd.DataFrame):
        return _diagnose_dataframe(input_value, "dataframe")
    path = Path(input_value)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return diagnose_kpis_path(path)
    if suffix == ".json":
        df = load_web_json(path)
        return _diagnose_dataframe(df, str(path))
    raise ValueError("Unsupported input format; use kpis.csv or web JSON.")
