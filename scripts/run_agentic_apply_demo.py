# ====================================================================================================
# Interview Walkthrough - Bounded Agentic Bottleneck Loop (Option B Demo)
#
# This script is the Option B "orchestrator": it wires together the simulation runner + a small agent
# pipeline to do one bounded "recommend -> apply -> re-run -> compare" pass.
#
# Loop stages (one pass):
#   1) Observe  -> run a baseline simulation and collect KPIs
#   2) Diagnose -> analyze KPIs to find the biggest time contributors (bottlenecks)
#   3) Decide   -> recommend a small, guardrailed set of actions
#   4) Apply    -> convert actions into concrete config overrides (still guardrailed)
#   5) Re-run   -> run the simulation again with the same seed + overrides
#   6) Compare  -> compute KPI deltas and write a human-readable summary
#
# Where this sits in the system:
# - Orchestrates `scripts/run_simulation.py` (runs the sim and writes outputs)
# - Uses `src/agent/*` for `diagnose_kpis_path`, `recommend`, `apply_actions`, `compare_kpis`
# - The simulation core lives under `src/sim/*` and is called indirectly by the runner.
#
# Key artifacts under the output directory (`--out`):
# - `decision.json` (diagnostics + agent decision + guardrails)
# - `overrides.json` (applied config changes; only if we actually apply)
# - `comparison.json`, `comparison.csv` (baseline vs after KPIs; only if re-run happens)
# - `agentic_summary.md` (scroll-friendly demo summary)
# - `baseline/` and `after/` runs with `metadata.json`, `kpis.csv`, plots, `run.log`, etc.
#
# Guardrails (intentional bounds for a demo):
# - Bounded actions only (apply at most `--max-actions`, and keep deltas within guardrails)
# - Deterministic comparison (baseline and after use the same seed)
# - Single iteration (no repeated search / optimization loop)
# - Low confidence (< 0.5) -> no-apply (still writes decision + summary)
#
# Teaching notes (3 ideas that make this demo credible in an interview):
# - Seed + determinism:
#   - A "seed" is a number that initializes the pseudo-random number generator (PRNG).
#   - Determinism here means: same code + same config + same seed => reproducible outputs.
#   - We reuse the SAME seed for baseline and after so this is a fair A/B comparison where only the
#     overrides change (not the random noise).
#   - Nuance: same seed does NOT guarantee identical per-entity samples if overrides change event ordering
#     and therefore change the order/number of RNG draws.
# - Confidence:
#   - In this demo, "confidence" means data completeness (schema/column coverage), NOT model accuracy.
#   - Low confidence means we do not have enough evidence to recommend/apply changes.
# - Tail metrics (p95):
#   - Congestion creates long tails (a few cases get very delayed).
#   - We report mean and p95 together to show both the typical case and the painful tail.
# ====================================================================================================

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_simulation
from src.agent.apply import apply_actions
from src.agent.compare import compare_kpis
from src.agent.diagnose import diagnose_kpis_path
from src.agent.recommend import recommend
from src.sim import get_scenario, scenario_to_dict

# ----------------------------------------------------------------------------------------------------
# _default_out_dir
# Purpose (simple): Pick a timestamped output folder for this run.
# Loop stage(s): Observe/Compare (logging + artifact organization)
# Inputs: `root` (repo root Path)
# Outputs: Path to `outputs/agentic_demo_YYYYMMDD_HHMMSS`
# Why it matters: Keeps runs isolated, reproducible, and easy to inspect in a demo.
# ----------------------------------------------------------------------------------------------------
def _default_out_dir(root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return root / "outputs" / f"agentic_demo_{timestamp}"

# ----------------------------------------------------------------------------------------------------
# _load_kpis
# Purpose (simple): Load the KPI table produced by a simulation run.
# Loop stage(s): Observe/Compare
# Inputs: `path` to a `kpis.csv`
# Outputs: `pandas.DataFrame` of KPIs
# Why it matters: Standardizes how we read KPIs for diagnosis and comparisons.
# ----------------------------------------------------------------------------------------------------
def _load_kpis(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

# ----------------------------------------------------------------------------------------------------
# _write_json
# Purpose (simple): Persist a small dictionary payload as pretty-printed JSON.
# Loop stage(s): Decide/Apply/Compare (artifact writing)
# Inputs: `path` (where to write), `payload` (what to write)
# Outputs: None (writes a JSON file)
# Why it matters: Makes the demo auditable - you can open the files and see what the agent decided.
# ----------------------------------------------------------------------------------------------------
def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

# ----------------------------------------------------------------------------------------------------
# _format_value
# Purpose (simple): Format numeric values for the markdown summary.
# Loop stage(s): Compare (reporting)
# Inputs: `value` (float or None)
# Outputs: 2-decimal string (or "n/a")
# Why it matters: Keeps the summary readable and handles missing metrics gracefully.
# ----------------------------------------------------------------------------------------------------
def _format_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"

# ----------------------------------------------------------------------------------------------------
# _build_summary
# Purpose (simple): Write a single markdown page summarizing diagnostics, decisions, and outcomes.
# Loop stage(s): Compare (reporting)
# Inputs: `out_dir`, `diagnostics`, `decision`, `applied_actions`, `comparison` (optional)
# Outputs: None (writes `agentic_summary.md`)
# Why it matters: In an interview/demo, this is the fastest artifact to skim end-to-end.
# ----------------------------------------------------------------------------------------------------
def _build_summary(
    out_dir: Path,
    diagnostics: dict,
    decision: dict,
    applied_actions: list,
    comparison: dict | None,
) -> None:
    confidence = diagnostics.get("confidence")
    top_bottleneck = (decision.get("top_bottlenecks") or [None])[0] or {}
    bottleneck_stage = top_bottleneck.get("stage", "n/a")
    bottleneck_contrib = top_bottleneck.get("contribution")
    bottleneck_contrib_str = (
        f"{bottleneck_contrib * 100:.1f}%" if isinstance(bottleneck_contrib, (int, float)) else "n/a"
    )

    lines = [
        "# Agentic Summary (Option B Demo)",
        "",
        f"- Confidence: {confidence:.2f}" if isinstance(confidence, float) else "- Confidence: n/a",
        f"- Top bottleneck: `{bottleneck_stage}` ({bottleneck_contrib_str} of total_time)",
    ]

    guardrails = decision.get("guardrails", {})
    if guardrails:
        lines.append(
            "- Guardrails: "
            f"max_actions={guardrails.get('max_actions')}, "
            f"max_total_delta={guardrails.get('max_total_delta')}, "
            "forbidden=arrival rates/flow mix/dwell/vessel toggles/data rewrites"
        )

    if applied_actions:
        lines.append("- Applied actions:")
        for action in applied_actions:
            lines.append(
                f"  - {action.get('action')} -> {action.get('param')} "
                f"{action.get('baseline')} -> {action.get('applied')}"
            )
    else:
        lines.append("- Applied actions: none")

    if comparison:
        # Teaching note: tail metrics (p95) in plain English.
        # - p95 ("95th percentile") is the value X where 95% of cases are <= X.
        # - In congestion systems, averages can look OK while a small % suffer huge delays.
        # - We show mean (typical) AND p95 (tail) together.
        # Example: if 95% finish under 60 min but 5% take 180+ min, the mean can hide that pain,
        # while p95 makes it visible.
        metrics = comparison.get("metrics", [])
        total_row = next((row for row in metrics if row.get("metric") == "total_time"), {})
        lines.append(
            "- Baseline total_time mean/p95: "
            f"{_format_value(total_row.get('baseline_mean'))} / {_format_value(total_row.get('baseline_p95'))}"
        )
        lines.append(
            "- After total_time mean/p95: "
            f"{_format_value(total_row.get('after_mean'))} / {_format_value(total_row.get('after_p95'))}"
        )
        lines.append(
            "- Delta total_time mean/p95: "
            f"{_format_value(total_row.get('delta_mean'))} / {_format_value(total_row.get('delta_p95'))}"
        )

    summary_path = out_dir / "agentic_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

# ----------------------------------------------------------------------------------------------------
# run_agentic_demo
# Purpose (simple): Orchestrate a single, bounded "baseline -> diagnose -> decide -> apply -> re-run -> compare" loop.
# Loop stage(s): Observe/Diagnose/Decide/Apply/Re-run/Compare
# Inputs:
# - `out_dir`: root folder for all artifacts (baseline/, after/, and JSON/CSV/MD summaries)
# - `seed`: RNG seed reused across baseline and after runs (deterministic comparison)
# - `max_actions`: cap on how many parameter changes we are allowed to apply
# - `base_config`: optional explicit baseline config; otherwise load the repo's demo baseline scenario
# Outputs: A result dict for the CLI (decision, whether we applied, applied_actions, and summary path)
# Why it matters: This is the "Option B" demo loop in one place - a small, auditable, guardrailed agent workflow.
# ----------------------------------------------------------------------------------------------------
def run_agentic_demo(
    out_dir: Path,
    seed: int,
    max_actions: int,
    base_config: dict | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir = out_dir / "baseline"
    after_dir = out_dir / "after"

    # Observe: pick a baseline configuration (either provided explicitly, or the demo baseline scenario).
    if base_config is None:
        base_config = scenario_to_dict(get_scenario("baseline", demo=True))

    # Observe: run the baseline simulation and write `baseline/kpis.csv`, `baseline/metadata.json`, logs, plots.
    #
    # Teaching note (seed + determinism, with an important nuance):
    # - The simulation uses pseudo-random sampling (arrivals, dwell times, service times).
    # - `seed` initializes the pseudo-random number generator (PRNG).
    # - Determinism here means: same code + same config + same seed => reproducible outputs.
    # - We reuse the same seed for baseline and after to reduce random variation in the A/B comparison.
    # - Nuance: same seed does NOT guarantee identical per-container samples if overrides change event ordering
    #   and therefore change the order/number of RNG draws.
    # Talk-track: "We fix the seed to control randomness and make before/after runs comparable."
    run_simulation.run_demo(base_config, seed=seed, out_dir=baseline_dir)

    # Diagnose: read the baseline KPIs and produce a diagnostics payload (incl. confidence + bottlenecks).
    kpis_path = baseline_dir / "kpis.csv"
    diagnostics = diagnose_kpis_path(kpis_path)

    # Decide: turn diagnostics into a bounded recommendation set (and persist it for auditability).
    decision = recommend(diagnostics, max_actions=max_actions)
    _write_json(out_dir / "decision.json", decision)

    # Confidence gate (teaching note):
    # - "confidence" here is NOT model accuracy. It is a data completeness score computed in Diagnose.
    # - Roughly: confidence = coverage_ratio([total_time] + stage_wait_columns), rounded (see src/agent/diagnose.py).
    # - Confidence is forced to 0.0 when the input is unusable (no rows, or missing total_time).
    # - If KPI columns are missing (or there are zero rows), confidence is degraded.
    # - We stop early to avoid recommending/applying changes from incomplete evidence.
    # Example: if we have total_time + 6/8 stage wait columns, confidence ~ 0.78.
    summary_path = out_dir / "agentic_summary.md"
    if float(diagnostics.get("confidence", 0.0)) < 0.5:
        _build_summary(out_dir, diagnostics, decision, [], None)
        return {
            "decision": decision,
            "applied": False,
            "applied_actions": [],
            "summary_path": summary_path,
        }

    baseline_metadata = json.loads((baseline_dir / "metadata.json").read_text(encoding="utf-8"))
    baseline_config = baseline_metadata.get("config_used") or base_config

    # Apply: convert recommendations into concrete config overrides (bounded by `max_actions` and guardrails).
    overrides, applied_actions = apply_actions(
        baseline_config,
        decision.get("recommended_actions", []),
        max_actions=max_actions,
    )


    # Nothing to apply (or everything was blocked by guardrails) -> write summary and stop.
    if not overrides:
        _build_summary(out_dir, diagnostics, decision, applied_actions, None)
        return {
            "decision": decision,
            "applied": False,
            "applied_actions": applied_actions,
            "summary_path": summary_path,
        }

    # Apply: persist the overrides so we can inspect exactly what changed.
    _write_json(out_dir / "overrides.json", overrides)

    # Re-run: run the "after" simulation with the same seed and the updated configuration.
    #
    # Teaching note (A/B comparability, nuance):
    # - We reuse the same `seed` so baseline and after share a comparable randomness setup.
    # - Nuance: capacity changes can change event ordering, which can change the order/number of RNG draws,
    #   so per-container samples may not match exactly even with the same seed.
    config_after = dict(baseline_config)
    config_after.update(overrides)
    run_simulation.run_demo(config_after, seed=seed, out_dir=after_dir)

    # Compare: load KPI tables, compute deltas, and write comparison artifacts (JSON + CSV).
    baseline_df = _load_kpis(baseline_dir / "kpis.csv")
    after_df = _load_kpis(after_dir / "kpis.csv")
    comparison, comparison_df = compare_kpis(baseline_df, after_df)
    _write_json(out_dir / "comparison.json", comparison)
    comparison_df.to_csv(out_dir / "comparison.csv", index=False)

    # Compare/Report: generate a markdown summary that ties diagnostics -> actions -> outcomes together.
    _build_summary(out_dir, diagnostics, decision, applied_actions, comparison)
    return {
        "decision": decision,
        "applied": True,
        "comparison": comparison,
        "applied_actions": applied_actions,
        "summary_path": summary_path,
    }

# ----------------------------------------------------------------------------------------------------
# parse_args
# Purpose (simple): Define the CLI for the Option B demo.
# Loop stage(s): Orchestration (not part of the simulation loop itself)
# Inputs: Command-line args (`--seed`, `--max-actions`, `--out`)
# Outputs: `argparse.Namespace`
# Why it matters: Makes the demo repeatable with the same seed and bounded action budget.
# ----------------------------------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Option B agentic demo with auto-apply.")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--max-actions", type=int, default=2)
    parser.add_argument("--out", help="Output directory path.")
    return parser.parse_args()


# ----------------------------------------------------------------------------------------------------
# main
# Purpose (simple): CLI entrypoint that runs the demo and prints a short console summary.
# Loop stage(s): Orchestration
# Inputs: CLI args (via `parse_args`)
# Outputs: Process exit code (0 on success)
# Why it matters: One command produces a complete, interview-friendly artifact bundle under `--out`.
# ----------------------------------------------------------------------------------------------------
def main() -> int:
    args = parse_args()
    out_dir = Path(args.out) if args.out else _default_out_dir(ROOT)
    result = run_agentic_demo(out_dir=out_dir, seed=args.seed, max_actions=args.max_actions)
    applied_actions = result.get("applied_actions") or []
    summary_path = result.get("summary_path")
    print(f"Wrote agentic demo outputs to {out_dir}")
    if applied_actions:
        actions_text = "; ".join(
            f"{item.get('param')} {item.get('baseline')}->{item.get('applied')}"
            for item in applied_actions
        )
        print(f"Applied actions: {actions_text}")
    else:
        print("Applied actions: none")
    if summary_path:
        print(f"Agentic summary: {summary_path}")
    return 0


# ----------------------------------------------------------------------------------------------------
# Closing notes (for interviews / demos)
#
# What this script proves:
# - A bounded, auditable agent loop can identify bottlenecks from KPIs, propose limited changes, apply them,
#   and show before/after impact - all with artifacts you can inspect.
#
# What it intentionally does NOT do:
# - It does not change demand/arrivals/flow mix, toggle vessel behavior, rewrite input data, or run an
#   open-ended optimization search. It's one guardrailed iteration for a demo stack.
#
# One-line takeaway:
# - "We run baseline -> let the agent propose small config tweaks -> re-run deterministically -> quantify KPI deltas."
# ----------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    raise SystemExit(main())
