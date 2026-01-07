# Agentic Loop (Option A): Observe -> Diagnose -> Recommend

This repo supports a recommend-only agentic loop that reads existing outputs,
computes bottleneck signals, and emits bounded recommendations without changing
simulation behavior.

## Signals used
- Total time in system: `total_time` (mean, p95).
- Stage waits: `scan_wait`, `yard_to_scan_wait`, `yard_to_truck_wait`,
  `loading_wait`, `gate_wait`, `pre_pickup_wait`, `ready_to_pickup_wait`,
  `yard_equipment_wait`.
- Optional context (if present): `scanner_queue_len_at_pickup`,
  `loader_queue_len_at_pickup`, `occupancy_at_yard_to_scan`,
  `occupancy_at_yard_to_truck`.

## Diagnostics logic
- Contribution per stage = mean(stage_wait) / mean(total_time).
- Rank stages by contribution, using only columns that exist in the input.
- If required columns are missing, confidence is lowered and recommendations
  may be withheld.

## Recommendations (no auto-apply)
- Recommendations only use safe resource parameters:
  `num_scanners`, `num_loaders`, `yard_equipment_capacity`,
  `num_gate_in`, `num_gate_out`, `num_cranes`.
- Bounds: +0..+2 resources (recommend-only).

## Guardrails
- Forbidden changes: arrival rates, flow mix, dwell distributions, vessel layer
  toggles, and any data/profile rewrites.
- Runtime limits: diagnostics only; no simulation re-run in Option A.
- Claims boundary: "simulation suggests..." not operational advice.

## Limitations
- No resource utilization tracking is recorded in current outputs.
- Queue lengths are point-in-time snapshots, not time series.
- Some stage waits are flow-specific and may be missing in certain runs.
- Notebook-driven exports can drift in schema without explicit versioning.
