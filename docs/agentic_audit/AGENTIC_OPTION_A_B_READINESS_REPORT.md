# AGENTIC OPTION A/B READINESS REPORT

## 1) Executive Verdict

- Option A readiness: Almost Ready
- Option B readiness: Not Ready

5 key blockers for A:

- Bottleneck signals are only available via notebook-driven exports (see `src/web_export/export_results_for_web.py`), not a stable API.
- No resource utilization metrics are recorded; only waits and point-in-time queue lengths are available.
- The dashboard stage list includes customs/rebook metrics, but those columns are missing from `outputs/web/*.json`.
- `outputs/web` schema is not versioned and can drift with notebook changes.
- No agent-facing diagnostics or recommendation artifacts exist yet.

5 key blockers for B:

- No config override mechanism exists for the demo CLI; `src/sim/scenarios.py` hardcodes parameters and `improved` == `baseline`.
- The notebook path has no explicit seeding (`rg` found no `random.seed` or `np.random.seed` in `durban_port_simulation.ipynb`).
- The demo runner has no hook to apply parameter deltas; auto-apply would require new wiring.
- No baseline-vs-after comparison artifact exists (only raw KPIs and plots).
- Guardrails and allowed action bounds are not codified anywhere.

Top 7 quick wins (lift):

- Add a small config override layer for demo runs so actions can be applied without code edits. (M)
- Emit a stable agentic diagnostics JSON (stage contributions, ranking, recommendations). (S)
- Add schema/version metadata to outputs for programmatic stability. (S)
- Record per-resource utilization or busy-time percent in `src/sim/model.py`. (M)
- Align dashboard stage metrics to only include columns that exist in `outputs/web`. (S)
- Add deterministic seeding for the notebook path or route agentic loops to the CLI only. (S)
- Add a simple compare artifact (baseline vs after KPI deltas) for Option B. (S)

## 2) What We Can Measure Today (Evidence)

| Signal | File/path | Data format | Stable for programmatic use? |
| --- | --- | --- | --- |
| Container-level timestamps + KPIs (e.g., `total_time`, `yard_dwell`, `scan_wait`) | `outputs/web/baseline.json`, `outputs/web/improved.json` | JSON with `columns` list (47 cols) and `records` list of dicts | Medium (notebook-driven export, no schema version) |
| Derived wait metrics (`scan_wait`, `yard_to_scan_wait`, `yard_to_truck_wait`, `loading_wait`, `gate_wait`, `pre_pickup_wait`, `ready_to_pickup_wait`, `yard_equipment_wait`) | `src/sim/metrics.py` and notebook `_metrics_to_dataframe` | DataFrame columns exported to JSON/CSV | Medium (flow-specific columns can be missing) |
| Queue length at pickup request | `outputs/web/*.json` | `scanner_queue_len_at_pickup`, `loader_queue_len_at_pickup` columns | Medium (point-in-time only) |
| Yard occupancy at move time | `outputs/web/*.json` | `occupancy_at_yard_to_scan`, `occupancy_at_yard_to_truck` columns | Medium |
| Flow segmentation | `outputs/web/*.json` | `flow_type`, `teu_size` columns | High |
| Tail metrics (p95/p99) | `simulation/interactive_port_congestion_simulator/app.js` | Computed from `total_time` at render time | Medium (computed, not stored) |
| Bottleneck ranking | `simulation/interactive_port_congestion_simulator/app.js` (`renderBottlenecks`) | Mean stage contribution vs mean `total_time` | Low (stage list includes missing metrics) |
| CLI demo KPIs | `scripts/run_simulation.py` output `kpis.csv` | CSV with same columns as `metrics_to_dataframe` | Medium (demo only) |

## 3) Can We Diagnose Bottlenecks Reliably?

Columns to compute a bottleneck score today:

- Denominator: `total_time` (mean or p95).
- Stage numerators: `scan_wait`, `yard_to_scan_wait`, `yard_to_truck_wait`, `loading_wait`, `gate_wait`, `pre_pickup_wait`, `ready_to_pickup_wait`, `yard_equipment_wait`.
- Optional context: `scanner_queue_len_at_pickup`, `loader_queue_len_at_pickup`, `occupancy_at_yard_to_scan`, `occupancy_at_yard_to_truck`.

Gaps that limit reliability:

- No resource utilization metrics (crane/scanner/loader/gate busy time).
- Queue lengths are only point-in-time snapshots, not time series.
- Stage waits are flow-specific; some stages do not exist for exports or transshipments.
- `customs_*` and `rebook_*` metrics appear in the dashboard list but are absent from `outputs/web` columns.
- Schema is notebook-dependent and not versioned.

Minimal additional instrumentation needed (plan only):

- Track resource utilization per resource (busy time / total time) in `src/sim/model.py` and notebook flow.
- Add queue length time series or aggregated queue stats (mean/max by stage).
- Add a schema version field and a documented stage list in `outputs/web/metadata.json`.

## 4) Candidate Action Set (What Interventions Are Actually Supported)

Actions below are verified in the demo stack (`src/sim`) unless noted.

| Parameter | Defined in | Consumed in | Affects sim today? | Suggested safe bounds |
| --- | --- | --- | --- | --- |
| `num_cranes` | `src/sim/scenarios.py` | `src/sim/model.py` (crane resource capacity) | Yes | +0 to +2 (demo: 1-4) |
| `yard_equipment_capacity` | `src/sim/scenarios.py` | `src/sim/model.py` (yard equipment resource) | Yes | +0 to +2 (demo: 1-6) |
| `num_scanners` | `src/sim/scenarios.py` | `src/sim/model.py` (scanner resource) | Yes | +0 to +2 (demo: 1-3) |
| `num_loaders` | `src/sim/scenarios.py` | `src/sim/model.py` (loader resource) | Yes | +0 to +2 (demo: 1-4) |
| `num_gate_in` | `src/sim/scenarios.py` | `src/sim/model.py` (gate-in resource) | Yes | +0 to +2 (demo: 1-3) |
| `num_gate_out` | `src/sim/scenarios.py` | `src/sim/model.py` (gate-out resource) | Yes | +0 to +2 (demo: 1-3) |
| `yard_capacity` | `src/sim/scenarios.py` | `src/sim/model.py` (container capacity + occupancy penalty) | Yes | +0 to +20% |
| `scan_time_mins` | `src/sim/scenarios.py` | `src/sim/model.py` (scan duration) | Yes | -0 to -20% |
| `loading_time_*` | `src/sim/scenarios.py` | `src/sim/model.py` (loading duration) | Yes | -0 to -20% |
| `gate_in_time_*` / `gate_out_time_*` | `src/sim/scenarios.py` | `src/sim/model.py` (gate durations) | Yes | -0 to -20% |
| `ship_interarrival_mean_mins`, `export_interarrival_mean_mins`, `hourly_truck_teu_rate` | `src/sim/scenarios.py` | `src/sim/model.py` (arrival generators) | Yes (but changes demand) | Forbidden for auto-apply |
| `USE_VESSEL_LAYER`, `ENABLE_ANCHORAGE_QUEUE`, `SHIFT_LENGTH_MINS` | `durban_port_simulation.ipynb` | notebook-only flow | Yes (not in CLI) | Not suitable for agentic loop |
| `customs_*`, `rebook_*` | `durban_port_simulation.ipynb` | helper funcs present, not wired in main flow (per limitations) | No (for outputs/web) | Not suitable |

## 5) Option A Design Fit (Recommend-only)

How Option A could work with current repo structures:

- Inputs: `outputs/web/baseline.json` (records + columns). Alternative: `outputs/demo_baseline/kpis.csv` from CLI demo.
- Run step: load records, compute stage contribution = mean(stage_wait) / mean(total_time).
- Diagnosis: rank stages by contribution and cross-check queue length/occupancy fields.
- Recommendation output: JSON (e.g., `decision.json`) with ranked stages, mapped actions, and bounds.
- Output location: `outputs/agentic_runs/<timestamp>/diagnostics.json` + `decision.json`.

Assessment:

- Recommendations can be generated without new simulation behavior.
- Missing: stable schema versioning, utilization metrics, and a defined action mapping file.

## 6) Option B Design Fit (Recommend + Auto-apply + Re-run Once)

How Option B would work:

- Baseline run: `scripts/run_simulation.py --demo --seed <seed>`.
- Diagnose: same as Option A.
- Apply: override 1-2 safe parameters (resource counts or small time reductions).
- Re-run: same seed, new params.
- Compare: compute KPI deltas (mean/median/p95 for `total_time`, `yard_dwell`, `scan_wait`, `loading_wait`, `gate_wait`).

Assessment:

- Deterministic seeding exists in the demo stack (`src/sim/model.py`), not in the notebook path.
- No parameter override mechanism exists today, so auto-apply cannot happen without new wiring.
- Outputs to compare exist (demo `kpis.csv`), but there is no built-in comparison artifact.

## 7) Guardrails & Governance (Must-have for Deloitte)

- Allowed actions: resource counts (`num_scanners`, `num_loaders`, `yard_equipment_capacity`, `num_gate_in`, `num_gate_out`, `num_cranes`) and small time reductions (`scan_time_mins`, `loading_time_*`, `gate_*_time_*`).
- Bounds: max +2 resources or -20% time change per action; max 2 actions per run.
- Forbidden changes: arrival rates, flow mix, dwell distributions, vessel layer toggles, or data/profile rewrites.
- Runtime limits: demo mode only; one re-run; hard stop if runtime exceeds a set limit.
- Claims boundary: output phrased as "simulation suggests", not operational advice.
- Human-in-the-loop: Option B requires explicit confirmation before apply and re-run.

## 8) Failure Modes + Recovery Plan

| Failure mode | Detection | Recovery behavior |
| --- | --- | --- |
| Missing baseline outputs | File not found for `outputs/web/baseline.json` or `kpis.csv` | Stop and report missing files; instruct to run export or demo |
| Missing required metrics | Column not present (`total_time`, `scan_wait`, etc.) | Skip metric, log warning, downgrade confidence |
| Parameter override not found | Config key not in `ScenarioConfig` | Abort apply step; report invalid action |
| Non-deterministic results | Same seed yields materially different KPIs | Warn and mark run as non-reproducible; avoid auto-apply |
| Over-budget runtime | Runtime exceeds limit | Abort re-run, save partial diagnostics |
| Schema mismatch between runs | Baseline and after columns differ | Compare intersection only; log mismatch |
| Empty result set | `row_count == 0` | Abort with diagnostic; no recommendations |
| Output directory not writable | Exception on write | Abort and surface error path |

## 9) Minimal Implementation Plan (No code, just steps)

1) Add `src/agent/diagnose.py` to compute stage contributions from a dataframe or JSON records.
2) Add `src/agent/actions.py` with an allowed action map and safe bounds.
3) Add `configs/agent_params.json` for default bounds and stage-to-action mapping.
4) Extend `scripts/run_simulation.py` (or add `scripts/run_agentic_demo.py`) with `--agent-mode` and `--apply` flags.
5) Emit artifacts under `outputs/agentic_runs/<timestamp>/`: `diagnostics.json`, `decision.json`, `comparison.json`.
6) Add a smoke test to run demo baseline and validate the three artifacts exist.
7) Add docs: `docs/agentic_loop.md` describing guardrails and example outputs.

## 10) Appendix

Key files inspected:

- `durban_port_simulation.ipynb` (main model, parameters, metrics; no explicit seeding found)
- `scripts/run_simulation.py` (demo CLI entrypoint)
- `src/sim/model.py` (SimPy model, deterministic seeding for demo)
- `src/sim/scenarios.py` (demo scenario config and parameters)
- `src/sim/metrics.py` (derived KPI columns)
- `src/web_export/export_results_for_web.py` (notebook-driven export to `outputs/web`)
- `outputs/web/baseline.json`, `outputs/web/improved.json`, `outputs/web/metadata.json` (exported metrics)
- `simulation/interactive_port_congestion_simulator/app.js` (dashboard KPIs and bottleneck ranking)
- `README.md` (entrypoints and run guidance)

Commands executed:

- `Get-ChildItem -Force`
- `Get-ChildItem -Force -Path docs\agentic_audit`
- `rg --files -g '*.*' src`
- `Get-Content -Path src\sim\scenarios.py`
- `Get-Content -Path src\sim\model.py`
- `Get-Content -Path src\sim\metrics.py`
- `Get-Content -Path src\web_export\export_results_for_web.py`
- `Get-Content -Path simulation\interactive_port_congestion_simulator\app.js`
- `Get-Content -Path scripts\run_simulation.py`
- `Get-Content -Path README.md`
- `rg -n "customs|rebook" durban_port_simulation.ipynb`
- `rg -n "USE_VESSEL_LAYER|SHIFT_LENGTH_MINS|ENABLE_ANCHORAGE_QUEUE" durban_port_simulation.ipynb`
- `rg -n "random\.seed|np\.random\.seed" durban_port_simulation.ipynb`
- `python -` (read `outputs/web/*.json` schema and limitations)

Errors encountered: none
