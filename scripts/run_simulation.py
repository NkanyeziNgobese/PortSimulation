# ====================================================================================================
# Where this fits - Deterministic Demo Simulation Runner
#
# This script supports the Option B "Bounded Agentic Bottleneck Loop" in two places:
# - OBSERVE: run a baseline simulation and write evidence (KPIs + logs + plots)
# - RE-RUN: run an "after" simulation with the same seed + config overrides for a fair comparison
#
# What it takes in:
# - A scenario config dict (either from `src/sim/scenarios.py` or a JSON file)
# - A fixed `seed` (the determinism lever)
# - An output directory (where all artifacts are written)
# - Optional overrides JSON (validated/merged via `src/sim/overrides.py`)
#
# What it produces (file-based artifacts for auditability):
# - `kpis.csv` (row-level simulation outputs used to compute KPIs)
# - `metadata.json` (scenario name/description, seed, timestamp, git_commit, config_used, etc.)
# - `plots/*.png` (quick visuals for the demo)
# - `run.log` (console-style log for traceability)
#
# Why it's reviewer-friendly:
# - Demo mode uses synthetic arrivals (no external datasets)
# - A fixed seed makes baseline vs after comparisons meaningful
# - Everything is persisted as artifacts you can open and inspect
# ====================================================================================================

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CalledProcessError, check_output

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim import apply_overrides, get_scenario, run_simulation, scenario_from_dict, scenario_to_dict


# ----------------------------------------------------------------------------------------------------
# parse_args
# Purpose (simple): Define the CLI flags for running one deterministic demo simulation.
# Loop stage(s): Observe / Re-run (shared entrypoint)
# Inputs: Command-line args (`--scenario`, `--seed`, `--demo`, `--out`, optional `--config`/`--override`)
# Outputs: `argparse.Namespace`
# Why it matters in the interview: The orchestrator can call `run_demo(...)` directly, but this CLI
# makes it easy to reproduce a single run and inspect its artifacts.
# ----------------------------------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic demo simulation.")
    parser.add_argument("--scenario", choices=["baseline", "improved"], required=True)
    # Teaching note (seed + determinism):
    # - Simulations use randomness (arrivals, service times, dwell times, routing choices).
    # - A "seed" initializes the pseudo-random number generator (PRNG) so those "random" draws are repeatable.
    # - With the same code + same config + same seed, you get the same outputs (determinism).
    # - This is what makes baseline vs after a fair A/B comparison: only overrides change, not random noise.
    # - Nuance: same seed does NOT guarantee identical per-entity samples if a different config consumes RNG draws
    #   in a different order (for event-driven sims, capacity changes can change event ordering).
    # - Even with that nuance, fixing the seed makes comparisons far fairer and lets reviewers reproduce each run.
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--demo", action="store_true", help="Run the lightweight demo simulation.")
    parser.add_argument("--out", required=True, help="Output directory path.")
    parser.add_argument("--config", help="Optional JSON base config path.")
    parser.add_argument("--override", help="Optional JSON overrides path.")
    return parser.parse_args()


# ----------------------------------------------------------------------------------------------------
# get_git_commit
# Purpose (simple): Capture the current git commit hash for provenance (best-effort).
# Loop stage(s): Shared utility (metadata)
# Inputs: `root` (repo root Path)
# Outputs: commit SHA string, or None if git isn't available
# Why it matters in the interview: Helps prove which version of the code produced a given set of KPIs.
# ----------------------------------------------------------------------------------------------------
def get_git_commit(root: Path) -> str | None:
    try:
        return check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    except (CalledProcessError, FileNotFoundError):
        return None


# ----------------------------------------------------------------------------------------------------
# plot_histogram
# Purpose (simple): Save a quick histogram plot for a numeric column (if it exists).
# Loop stage(s): Observe / Re-run (artifact generation)
# Inputs: simulation DataFrame, column name, title/xlabel, output path
# Outputs: bool (True if plot saved, False if data missing)
# Why it matters in the interview: Gives a fast visual check alongside the CSV/JSON artifacts.
# ----------------------------------------------------------------------------------------------------
def plot_histogram(df: pd.DataFrame, column: str, title: str, xlabel: str, out_path: Path) -> bool:
    if df.empty or column not in df.columns:
        return False
    series = df[column].dropna()
    if series.empty:
        return False
    plt.figure(figsize=(10, 5))
    plt.hist(series, bins=30, edgecolor="black", alpha=0.8)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    return True


# ----------------------------------------------------------------------------------------------------
# _load_json
# Purpose (simple): Load a JSON file into a dict.
# Loop stage(s): Shared utility (config loading)
# Inputs: path to a JSON file
# Outputs: dict
# Why it matters in the interview: The orchestrator writes `overrides.json`, and this helper reads it back.
# ----------------------------------------------------------------------------------------------------
def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------------------------------
# _build_config_dict
# Purpose (simple): Choose a base scenario config and optionally apply validated overrides.
# Loop stage(s): Observe / Re-run (shared config)
# Inputs: parsed CLI args (may include `--config` and `--override`)
# Outputs: dict config ready for `run_demo(...)`
# Why it matters in the interview: Demonstrates the separation of concerns - configs are plain dicts
# that can be merged safely, while the simulation core consumes a typed `ScenarioConfig`.
# ----------------------------------------------------------------------------------------------------
def _build_config_dict(args: argparse.Namespace) -> dict:
    # Base config comes either from a JSON file (explicit) or from a curated demo scenario (default).
    if args.config:
        base_config = _load_json(Path(args.config))
    else:
        base_config = scenario_to_dict(get_scenario(args.scenario, demo=True))

    # Overrides (if provided) are validated/merged via `apply_overrides` to keep the demo bounded/safe.
    if args.override:
        overrides = _load_json(Path(args.override))
        base_config = apply_overrides(base_config, overrides)

    return base_config


# ----------------------------------------------------------------------------------------------------
# run_demo
# Purpose (simple): Turn a config dict + seed into reproducible, file-based simulation artifacts.
# Loop stage(s): Observe / Re-run
# Inputs: `config_dict` (scenario + any overrides), `seed` (determinism), `out_dir` (artifact root)
# Outputs: metadata dict (also written to `metadata.json`)
# Why it matters in the interview:
# - This is what the orchestrator calls for both baseline and after runs.
# - After it returns, the orchestrator continues with Diagnose/Decide/Apply/Compare using the KPIs and metadata.
# ----------------------------------------------------------------------------------------------------
def run_demo(config_dict: dict, seed: int, out_dir: Path) -> dict:
    # Convert dict -> ScenarioConfig (schema guarantee + convenient attribute access in the core).
    config = scenario_from_dict(config_dict)

    # Create output folders for this run (plots/ plus a stable set of file artifacts).
    plots_dir = out_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    # Configure logging (write to `run.log` and also stream to stdout for interactive runs).
    log_path = out_dir / "run.log"
    logger = logging.getLogger(f"demo_run_{out_dir.name}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    # Teaching note (provenance):
    # - We log the seed and also write it to metadata.json so this exact run can be replayed by a reviewer.
    logger.info("Starting demo run: scenario=%s seed=%s", config.name, seed)
    logger.info("Demo description: %s", config.description)

    # Run the simulation core deterministically (same config + same seed => comparable KPIs).
    # If we changed the seed between baseline and after, differences could be random variation instead
    # of a true effect of the overrides.
    # Nuance: even with the same seed, if overrides change event ordering, the order/number of RNG draws can change,
    # so exact per-entity samples may diverge across baseline vs after.
    df = run_simulation(config, seed=seed)
    logger.info("Completed simulation with %s container rows.", len(df))

    # Persist row-level outputs (the downstream KPI calculations read from this file).
    kpis_path = out_dir / "kpis.csv"
    df.to_csv(kpis_path, index=False)
    logger.info("Wrote KPIs to %s", kpis_path)

    # Generate plots: primary "total_time" distribution plus a queue-length plot (with a fallback).
    total_plot = plots_dir / "total_time_hist.png"
    ok_total = plot_histogram(
        df,
        "total_time",
        "Total Time Distribution (Demo)",
        "Minutes in system",
        total_plot,
    )
    if ok_total:
        logger.info("Saved plot %s", total_plot)
    else:
        logger.warning("Skipped total_time plot (missing data).")

    queue_plot = plots_dir / "scanner_queue_len_hist.png"
    ok_queue = plot_histogram(
        df,
        "scanner_queue_len_at_pickup",
        "Scanner Queue Length at Pickup Request (Demo)",
        "Queue length (count)",
        queue_plot,
    )
    if ok_queue:
        logger.info("Saved plot %s", queue_plot)
    else:
        logger.warning("Skipped scanner queue plot (missing data).")
        fallback_plot = plots_dir / "yard_equipment_wait_hist.png"
        ok_queue = plot_histogram(
            df,
            "yard_equipment_wait",
            "Yard Equipment Wait Distribution (Demo)",
            "Minutes waiting for yard equipment",
            fallback_plot,
        )
        if ok_queue:
            logger.info("Saved plot %s", fallback_plot)
        else:
            logger.warning("Skipped yard equipment wait plot (missing data).")

    # Build `metadata.json` for governance/traceability:
    # - seed + timestamp for reproducibility
    # - git_commit for provenance
    # - a small config summary for quick scanning
    # - the full `config_used` dict for exact replay
    #
    # Teaching note:
    # - Recording `seed` lets us replay the exact PRNG stream for this specific config.
    # - Recording `git_commit` tells us exactly which code produced these KPIs.
    # - For A/B comparisons, a fixed seed improves fairness even though per-entity samples may diverge if event ordering changes.
    metadata = {
        "scenario_name": config.name,
        "scenario_description": config.description,
        "seed": seed,
        "demo": True,
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_commit": get_git_commit(ROOT),
        "row_count": int(len(df)),
        "outputs": {
            "kpis_csv": str(kpis_path.as_posix()),
            "plots_dir": str(plots_dir.as_posix()),
            "run_log": str(log_path.as_posix()),
        },
        "config_summary": {
            "sim_time_mins": config.sim_time_mins,
            "max_dwell_mins": config.max_dwell_mins,
            "post_process_buffer_mins": config.post_process_buffer_mins,
            "flow_mix": {
                "import": config.p_import,
                "export": config.p_export,
                "transship": config.p_transship,
            },
            "resources": {
                "cranes": config.num_cranes,
                "yard_capacity": config.yard_capacity,
                "yard_equipment": config.yard_equipment_capacity,
                "scanners": config.num_scanners,
                "loaders": config.num_loaders,
                "gate_in": config.num_gate_in,
                "gate_out": config.num_gate_out,
            },
        },
        "config_used": config_dict,
    }

    metadata_path = out_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info("Wrote metadata to %s", metadata_path)

    logger.info("Demo run complete.")
    # Returning metadata lets the orchestrator (or tests) inspect what was actually executed.
    return metadata


# ----------------------------------------------------------------------------------------------------
# main
# Purpose (simple): CLI entrypoint for running one demo simulation from the command line.
# Loop stage(s): Observe / Re-run (CLI wrapper)
# Inputs: CLI args via `parse_args`
# Outputs: process exit code (0 on success)
# Why it matters in the interview: A single command produces an auditable artifact bundle under `--out`.
# ----------------------------------------------------------------------------------------------------
def main() -> int:
    args = parse_args()
    if not args.demo:
        print("Non-demo CLI runs are not implemented. Use --demo or the notebook.")
        return 2

    config_dict = _build_config_dict(args)
    run_demo(config_dict, seed=args.seed, out_dir=Path(args.out))
    return 0


# ----------------------------------------------------------------------------------------------------
# Closing notes (for interviews / demos)
#
# One-line takeaway:
# - This script turns a (config + seed) into reproducible simulation artifacts on disk.
#
# What it intentionally does NOT do:
# - It does not run non-demo scenarios, ingest external datasets, or do multi-run optimization loops.
#
# Governance / traceability:
# - `metadata.json` captures `config_used` and (best-effort) `git_commit`, so runs can be replayed and audited.
# ----------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    raise SystemExit(main())
