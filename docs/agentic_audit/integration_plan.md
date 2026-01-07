# Agentic Loop Integration Plan (Sketch)

Goal: add a small, reviewer-friendly agentic bottleneck loop without changing simulation behavior.

## Option A (Recommend-only)
1) Inputs
   - Primary: `outputs/web/baseline.json` (or `outputs/demo_baseline/kpis.csv` if demo run is used).
   - Use `columns` to validate schema.
2) Diagnose
   - Compute stage contributions using mean stage wait / mean total_time.
   - Reuse the same stage list as the web dashboard (`scan_wait`, `yard_to_scan_wait`, `yard_to_truck_wait`, `loading_wait`, `gate_wait`, `pre_pickup_wait`, `ready_to_pickup_wait`).
3) Recommendations
   - Map top stages to safe parameter changes (e.g., scanners, loaders, yard equipment, gates).
   - Emit JSON: `decision.json` with rationale and bounds.
4) Outputs
   - Store under `outputs/agentic_runs/<timestamp>/` with `diagnostics.json` + `decision.json`.

## Option B (Recommend + Apply + Re-run Once)
1) Baseline run
   - Use demo runner (`scripts/run_simulation.py --demo`) with a seed.
2) Diagnose
   - Same as Option A.
3) Apply
   - Change 1–2 safe parameters via a config override layer (new file suggested: `configs/demo_override.json`).
4) Re-run
   - Run demo again with the same seed + updated config.
5) Compare
   - Emit `comparison.json` with KPI deltas and a short summary.

## Suggested integration points (no code yet)
- New module: `src/agent/` with `diagnose.py`, `actions.py`, `runner.py`.
- New config: `configs/agent_params.json` (allowed actions + bounds).
- Extend demo CLI with `--agent-mode` and `--max-actions` (future change).

## Tests to add (future)
- `tests/test_agentic_recommend.py`: validates JSON outputs using existing demo KPIs.
- `tests/test_agentic_apply_demo.py`: runs demo twice and asserts comparison artifacts exist.

## Docs to add (future)
- `docs/agentic_loop.md`: process, guardrails, example outputs.
- Example artifacts: `docs/agentic_examples/decision.json`, `docs/agentic_examples/comparison.json`.
