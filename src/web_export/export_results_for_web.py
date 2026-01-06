import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = ROOT / "durban_port_simulation.ipynb"
OUTPUT_DIR = ROOT / "outputs" / "web"

REQUIRED_METRICS = [
    "total_time",
    "yard_dwell",
    "scan_wait",
    "loading_wait",
    "gate_wait",
]


def _should_skip_cell(source):
    """Skip notebook cells that only generate plots or visuals."""
    skip_markers = [
        "Plot metrics and save figures per run",
        "Compare Baseline vs Improved Dwell",
        "plt.",
        "sns.",
    ]
    return any(marker in source for marker in skip_markers)


def _patch_arrival_paths(env):
    """Fall back to synthetic arrival profiles when processed CSVs are missing."""
    for key in ("TRUCK_ARRIVAL_DATA_PATH", "TRUCK_ARRIVAL_DATA_FALLBACK_PATH"):
        path_value = env.get(key)
        if not path_value:
            continue
        path = ROOT / str(path_value)
        if not path.exists():
            print(f"Warning: {key}={path_value} not found. Using synthetic arrival profile.")
            env[key] = None


def _execute_notebook_until_dfs(nb_path):
    """Execute notebook code cells until df and df_improved are produced."""
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    env = {"__name__": "__main__", "__file__": str(nb_path)}

    for idx, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if not source.strip():
            continue
        if _should_skip_cell(source):
            continue

        # Patch arrival profile paths right before they are used.
        if "load_teu_arrival_profile(" in source and "def load_teu_arrival_profile" not in source:
            _patch_arrival_paths(env)

        exec(compile(source, f"nb_cell_{idx}", "exec"), env)

        if "df" in env and "df_improved" in env:
            if isinstance(env["df"], pd.DataFrame) and isinstance(env["df_improved"], pd.DataFrame):
                break

    return env.get("df", pd.DataFrame()), env.get("df_improved", pd.DataFrame())


def _to_records(df):
    """Convert a dataframe to JSON-ready records."""
    if df.empty:
        return []
    # pandas handles NaN->null; json.loads makes it Python-native.
    return json.loads(df.to_json(orient="records"))


def _infer_unit(col):
    col_lower = col.lower()
    if col_lower.endswith("_days") or col_lower.endswith("days"):
        return "days"
    if col_lower.endswith("_hours") or col_lower.endswith("hours"):
        return "hours"
    if any(token in col_lower for token in ["time", "wait", "delay", "start", "end", "entry", "exit", "queue", "dwell"]):
        return "minutes"
    if "queue_len" in col_lower or "queue_length" in col_lower or col_lower.endswith("_count") or col_lower.startswith("num_"):
        return "count"
    if "teu" in col_lower:
        return "TEU"
    if col_lower in {"container_id", "truck_id", "vessel_id"}:
        return "id"
    if col_lower in {"flow_type", "pier"}:
        return "category"
    if any(token in col_lower for token in ["prob", "share", "ratio", "availability", "util", "occupancy"]):
        return "ratio"
    return "unitless"


def _build_metadata(columns, run_timestamp):
    metrics = {}
    for col in columns:
        metrics[col] = {
            "unit": _infer_unit(col),
            "source_anchor": {
                "type": "ASSUMPTION",
                "reference": "durban_port_simulation.ipynb: Simulation Logic",
            },
        }

    return {
        "exported_at": run_timestamp,
        "scenarios": [
            {"key": "baseline", "name": "Baseline", "run_timestamp": run_timestamp},
            {"key": "improved", "name": "Improved Dwell", "run_timestamp": run_timestamp},
        ],
        "metrics": metrics,
    }


def _validate_required_metrics(df, label):
    missing = [m for m in REQUIRED_METRICS if m not in df.columns]
    if missing:
        print(f"Warning: {label} is missing required metrics: {', '.join(missing)}")
    return missing


def _print_schema_summary(label, df):
    print(f"{label} rows: {len(df)}")
    print(f"{label} columns: {len(df.columns)}")
    if df.columns.tolist():
        preview = ", ".join(df.columns.tolist()[:12])
        print(f"{label} columns (first 12): {preview}")


def main():
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        # Ensure notebook imports resolve to local modules (vessel_params, etc.).
        sys.path.insert(0, str(ROOT))
    if not NOTEBOOK_PATH.exists():
        raise FileNotFoundError(f"Notebook not found at {NOTEBOOK_PATH}")

    baseline_df, improved_df = _execute_notebook_until_dfs(NOTEBOOK_PATH)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    _validate_required_metrics(baseline_df, "Baseline")
    _validate_required_metrics(improved_df, "Improved")

    baseline_payload = {
        "scenario": "baseline",
        "run_timestamp": run_timestamp,
        "row_count": len(baseline_df),
        "columns": baseline_df.columns.tolist(),
        "records": _to_records(baseline_df),
    }
    improved_payload = {
        "scenario": "improved",
        "run_timestamp": run_timestamp,
        "row_count": len(improved_df),
        "columns": improved_df.columns.tolist(),
        "records": _to_records(improved_df),
    }

    all_columns = sorted(set(baseline_df.columns) | set(improved_df.columns))
    metadata_payload = _build_metadata(all_columns, run_timestamp)

    (OUTPUT_DIR / "baseline.json").write_text(
        json.dumps(baseline_payload, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "improved.json").write_text(
        json.dumps(improved_payload, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata_payload, indent=2), encoding="utf-8"
    )

    print(f"Wrote outputs to {OUTPUT_DIR}")
    _print_schema_summary("Baseline", baseline_df)
    _print_schema_summary("Improved", improved_df)


if __name__ == "__main__":
    main()
