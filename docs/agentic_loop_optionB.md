# Agentic Loop (Option B Demo): Observe -> Diagnose -> Decide -> Apply -> Re-run -> Compare

Option B runs a single, bounded intervention loop on the demo stack
(`src/sim` + `scripts/run_simulation.py`) and produces a before/after comparison.

## Steps

1) Observe: run the demo baseline and collect `kpis.csv`.
2) Diagnose: compute stage contribution shares from the KPI columns.
3) Decide: select up to two safe actions based on the top bottlenecks.
4) Apply: create overrides (no more than +1 per action, +2 total).
5) Re-run: run the demo again with the same seed.
6) Compare: compute mean/median/p90/p95 deltas for key KPIs.

## Guardrails

- Allowed params only: `num_scanners`, `num_loaders`, `yard_equipment_capacity`,
  `num_gate_in`, `num_gate_out`, `num_cranes`.
- Bounds: +1 per action, max +2 total, never below baseline.
- Forbidden changes: arrivals, flow mix, dwell distributions, vessel layer toggles,
  or any edits to `outputs/web` exports.
- One iteration only: baseline -> apply -> re-run -> stop.

## Claims boundary

Use language like: "simulation suggests..." and avoid operational advice.

## Output artifacts

- `baseline/metadata.json`: baseline run metadata + config used.
- `baseline/kpis.csv`: baseline KPI table (container-level metrics).
- `decision.json`: bottleneck ranking and bounded recommendations.
- `overrides.json`: applied overrides (if confidence is high enough).
- `after/metadata.json`: after-run metadata + config used.
- `after/kpis.csv`: after-run KPI table.
- `comparison.json`: structured KPI deltas (mean/median/p90/p95).
- `comparison.csv`: tabular version of KPI deltas.
- `agentic_summary.md`: short narrative of bottleneck, actions, and deltas.

## Failure modes + recovery

- Missing baseline outputs: stop and report missing `kpis.csv`.
- Missing required KPIs: lower confidence; avoid auto-apply.
- Low confidence (< 0.5): stop after decision and recommend re-running demo outputs.
- Action bounds exceeded: abort apply and report the constraint.
- Non-determinism: if the same seed produces inconsistent KPI outputs, flag as
  non-reproducible and stop.
- Output directory not writable: abort and report the path error.
