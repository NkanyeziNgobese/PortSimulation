# ====================================================================================================
# Fork Point: Diagnose stage (Option B agent loop)
#
# In the 6-stage "Bounded Agentic Bottleneck Loop", this module corresponds to:
# - DIAGNOSE: take baseline evidence (KPIs) and turn it into a transparent bottleneck report.
#
# Inputs this module can handle:
# - `kpis.csv` produced by the demo runner (`scripts/run_simulation.py`)
# - A small exported web JSON payload (either a list of records, or {records/data, columns})
#
# Output (diagnostics dict) is intentionally simple and auditable:
# - `stage_rankings`: per-stage mean wait + "contribution" score (see below)
# - `summary_stats`: mean and p95 of `total_time` (tail matters for congestion)
# - `missing_columns`: explicit report of what inputs were absent
# - `confidence`: a downgrade when required columns are missing (or 0.0 when unusable)
#
# Governance / safety notes (why this is interview-friendly):
# - `schema_version` is an explicit contract for downstream tools/tests.
# - Missing-columns reporting makes it obvious when a recommendation is under-informed.
# - Confidence is computed from coverage, so low-quality inputs lead to "no-apply" upstream.
# ====================================================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd


# `schema_version` is a stability contract: downstream steps can branch on it if the payload changes.
SCHEMA_VERSION = "agentic_v1"

# Candidate bottleneck stages: columns that represent "waiting time" at different parts of the process.
# These are the columns we try to rank by contribution to `total_time`.
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

# Optional context columns: extra evidence for explanation (queue snapshots / occupancy),
# but not strictly required to compute bottleneck contributions.
OPTIONAL_CONTEXT = [
    "scanner_queue_len_at_pickup",
    "loader_queue_len_at_pickup",
    "occupancy_at_yard_to_scan",
    "occupancy_at_yard_to_truck",
]


# ----------------------------------------------------------------------------------------------------
# _safe_mean
# Purpose (simple): Compute a mean while safely handling empty / all-NaN series.
# Loop stage: Diagnose
# Inputs: `series` (pandas Series)
# Outputs: float mean, or None if unavailable
# Interview explanation: "This keeps the diagnosis robust when a run produces sparse columns."
# ----------------------------------------------------------------------------------------------------
def _safe_mean(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    values = series.dropna()
    if values.empty:
        return None
    return float(values.mean())


# ----------------------------------------------------------------------------------------------------
# _safe_p95
# Purpose (simple): Compute the 95th percentile while safely handling empty / all-NaN series.
# Loop stage: Diagnose
# Inputs: `series` (pandas Series)
# Outputs: float p95, or None if unavailable
# Interview explanation: "We use p95 to capture the 'long tail' typical in congestion systems."
# ----------------------------------------------------------------------------------------------------
def _safe_p95(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    values = series.dropna()
    if values.empty:
        return None
    return float(values.quantile(0.95))


# ----------------------------------------------------------------------------------------------------
# load_kpis_csv
# Purpose (simple): Load the row-level KPI output table from the simulation runner.
# Loop stage: Diagnose
# Inputs: `input_path` to `kpis.csv`
# Outputs: pandas DataFrame
# Interview explanation: "This is the baseline evidence: one row per simulated container/entity."
# ----------------------------------------------------------------------------------------------------
def load_kpis_csv(input_path: Path) -> pd.DataFrame:
    return pd.read_csv(input_path)


# ----------------------------------------------------------------------------------------------------
# load_web_json
# Purpose (simple): Load a lightweight web-export JSON payload into a DataFrame.
# Loop stage: Diagnose
# Inputs: JSON file path (either list[record] or {records/data, columns})
# Outputs: pandas DataFrame (reindexed to `columns` if provided)
# Interview explanation: "Same diagnosis logic can run on web exports without changing core code."
# ----------------------------------------------------------------------------------------------------
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


# ----------------------------------------------------------------------------------------------------
# _coverage_ratio
# Purpose (simple): Compute how many required columns are present (column coverage, not row coverage).
# Loop stage: Diagnose
# Inputs: DataFrame and iterable of required column names
# Outputs: float in [0, 1]
# Interview explanation: "This becomes the confidence score: missing required columns -> lower confidence."
# ----------------------------------------------------------------------------------------------------
def _coverage_ratio(df: pd.DataFrame, required_cols: Iterable[str]) -> float:
    required = list(required_cols)
    if not required:
        return 0.0
    present = [col for col in required if col in df.columns]
    return len(present) / len(required)


# ----------------------------------------------------------------------------------------------------
# _diagnose_dataframe
# Purpose (simple): Build a transparent bottleneck report from a KPI DataFrame.
# Loop stage: Diagnose
# Inputs: `df` (KPIs), `input_source` (path label for provenance)
# Outputs: diagnostics dict (schema_version, summary_stats, stage_rankings, missing_columns, confidence)
# Interview explanation: "We compute mean waits per stage and rank them by contribution to total_time."
# ----------------------------------------------------------------------------------------------------
def _diagnose_dataframe(df: pd.DataFrame, input_source: str) -> Dict[str, object]:
    row_count = int(len(df))

    # Required vs optional columns:
    # - required: `total_time` plus each candidate wait-stage column
    # - optional: extra context that helps explain *why* a stage is a bottleneck
    required_cols = ["total_time"] + STAGE_CANDIDATES
    missing_required = [col for col in required_cols if col not in df.columns]
    missing_optional = [col for col in OPTIONAL_CONTEXT if col not in df.columns]
    missing_columns = sorted(set(missing_required + missing_optional))
    # Teaching note (governance):
    # - We include `missing_columns` in the output so reviewers can see what evidence was available.
    # - Missing required columns can degrade confidence (and upstream can choose "no-apply").

    # Summary stats on overall time-in-system:
    # - mean_total_time is the average experience
    # - p95_total_time surfaces tail latency (congestion tends to create long tails)
    mean_total = _safe_mean(df["total_time"]) if "total_time" in df.columns else None
    p95_total = _safe_p95(df["total_time"]) if "total_time" in df.columns else None

    stage_rankings = []
    for stage in STAGE_CANDIDATES:
        if stage not in df.columns:
            continue

        # For each stage (e.g., scan_wait), compute its average wait and its share of total_time.
        # "Contribution" is defined as: mean(stage_wait) / mean(total_time), using rows where both exist.
        #
        # Teaching note:
        # - contribution = mean(stage_wait) / mean(total_time)
        # - This is a heuristic attribution (not causal proof). It helps prioritize which "knob" to try
        #   first when we only allow a small number of actions.
        # Example: mean total_time = 100 min and mean scan_wait = 30 min => contribution = 0.30 (30%).
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

    # Sorting behavior (stable expectations for the rest of the pipeline):
    # - stages with unknown contribution (None) go last
    # - otherwise sort by contribution descending (largest share of total_time first)
    stage_rankings.sort(
        key=lambda item: (
            item["contribution"] is None,
            -(item["contribution"] or 0.0),
        )
    )

    # Optional context stats: these are supporting evidence (queue length, yard occupancy), not required.
    context_stats: Dict[str, Optional[float]] = {}
    for col in OPTIONAL_CONTEXT:
        if col in df.columns:
            context_stats[col] = _safe_mean(df[col])

    # Confidence logic:
    # - In this demo, "confidence" is NOT predictive accuracy. It is a data completeness score.
    # - It is computed as coverage_ratio(required_cols) rounded, where required_cols includes:
    #   total_time + the stage wait columns.
    # - Confidence is forced to 0.0 when the input is unusable (no rows, or missing total_time).
    # - Missing stage columns degrades confidence because we cannot quantify some bottlenecks.
    # Example: if total_time exists and 6 of 8 stage columns exist, confidence ~ (1+6)/(1+8) = 7/9 ~ 0.78.
    if row_count == 0 or "total_time" not in df.columns:
        confidence = 0.0
    else:
        confidence = round(_coverage_ratio(df, required_cols), 2)

    # Return dict layout (kept stable for downstream steps and for demo auditability).
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


# ----------------------------------------------------------------------------------------------------
# diagnose_kpis_path
# Purpose (simple): Diagnose a `kpis.csv` file path produced by the demo simulation runner.
# Loop stage: Diagnose
# Inputs: `input_path` (str or Path to a CSV)
# Outputs: diagnostics dict
# Interview explanation: "This is the exact entrypoint the orchestrator uses after the baseline run."
# ----------------------------------------------------------------------------------------------------
def diagnose_kpis_path(input_path: str | Path) -> Dict[str, object]:
    path = Path(input_path)
    df = load_kpis_csv(path)
    return _diagnose_dataframe(df, str(path))


# ----------------------------------------------------------------------------------------------------
# diagnose_dataframe
# Purpose (simple): Diagnose an in-memory DataFrame (useful for notebooks/tests).
# Loop stage: Diagnose
# Inputs: `df`, optional `input_source` label
# Outputs: diagnostics dict
# Interview explanation: "Same logic, different input form; keeps the module easy to test."
# ----------------------------------------------------------------------------------------------------
def diagnose_dataframe(df: pd.DataFrame, input_source: str = "dataframe") -> Dict[str, object]:
    return _diagnose_dataframe(df, input_source)


# ----------------------------------------------------------------------------------------------------
# diagnose
# Purpose (simple): Convenience wrapper that accepts a DataFrame, CSV path, or web JSON path.
# Loop stage: Diagnose
# Inputs: `input_value` (DataFrame or file path)
# Outputs: diagnostics dict
# Interview explanation: "This is a small adapter so callers don't need to care about file formats."
# ----------------------------------------------------------------------------------------------------
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


# Interview "return to orchestrator" note:
# - After this module returns a diagnostics dict, the Option B orchestrator calls `recommend(...)` to
#   decide a bounded set of safe actions, then (optionally) applies overrides and re-runs.


# ----------------------------------------------------------------------------------------------------
# Closing notes (for interviews / demos)
#
# What this module proves:
# - You can diagnose bottlenecks transparently from outputs (stage waits + simple contribution math),
#   and you can surface data-quality confidence and missing-columns explicitly.
#
# Limitation (intentional for the demo):
# - This is not a full utilization/time-series analysis; it uses per-container waits and a few snapshot
#   columns (queue length, occupancy) when available.
#
# Why that's acceptable here:
# - Option B is a bounded, audit-friendly demo loop: we want explainable heuristics that are fast,
#   deterministic, and safe to gate (low confidence -> no apply).
# ----------------------------------------------------------------------------------------------------
