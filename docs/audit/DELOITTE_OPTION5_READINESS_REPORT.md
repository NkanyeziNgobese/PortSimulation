# Deloitte Option 5 Readiness Report - Durban Port Congestion Simulation

## 1) Executive Summary
This repo implements a SimPy discrete-event simulation of container congestion at the Durban Container Terminal, centered on `durban_port_simulation.ipynb` with optional vessel/berth logic (`vessel_layer.py`), a Truck Appointment System module (`truck_tas.py`), ingestion pipelines for unit-volume Excel and KPI PDF data (`scripts/ingest/`), and an interactive web dashboard that visualizes baseline vs improved results (`simulation/interactive_port_congestion_simulator/`). Outputs include per-run plots under `figures/run_YYYYMMDD_HHMMSS/` and JSON exports under `outputs/web/`.

Readiness verdict: Almost Ready.

Top 7 blockers to submission readiness:

| # | Blocker | Evidence |
| --- | --- | --- |
| 1 | Documented integrated dwell logic (customs holds, rebooking) is not implemented in the simulation flow | `durban_port_simulation.ipynb` defines `sample_customs_hold_delay` and rebook helpers but does not set customs or rebook timestamps in container processes; `customs` resource is unused; `dwell_params` is passed but not used |
| 2 | Source provenance for "SOURCE-ANCHORED" parameters is missing | `vessel_params.py` and `VESSEL_LAYER_NOTES.md` reference `/mnt/data/pasted.txt` with line refs marked TBD; file is not in repo |
| 3 | Reproducibility gaps (no pinned environment, no deterministic seeds) | No `requirements.txt` or `environment.yml`; no `random.seed` or `np.random.seed` in notebook |
| 4 | Data path mismatch for raw ingestion inputs | `scripts/ingest/config_unit_volume.yml` expects `data/reports/unit_volume_reports`, but raw files live under `$backup/data_reports/...`; KPI ingestion expects `data/reports/annual_results` while raw PDFs are under `$backup/data_reports/annual_results` |
| 5 | Entry point is notebook-only; CLI runner is missing and web export uses `exec` | Primary run is `durban_port_simulation.ipynb`; `src/web_export/export_results_for_web.py` executes notebook cells with `exec`, which is brittle for production reuse |
| 6 | Limited testing and CI | Only `scripts/ingest/smoke_test_port_terminals_kpis.py` exists; no simulation tests or CI config |
| 7 | Scenario management and experimental rigor are weak | Baseline/improved runs exist but parameter deltas are not fully wired; no replication, no confidence intervals, no calibration run to KPI data |

Top 7 quick wins (highest ROI):

| Quick win | Lift (S/M/L) | Notes |
| --- | --- | --- |
| Add `requirements.txt` with pinned versions and reference it in `README.md` | S | Improves reproducibility immediately |
| Add deterministic seeding and record the seed in run metadata | S | Use `random.seed` and `np.random.seed` once per run |
| Align docs with code by implementing customs/rebook logic or removing claims | M | Fixes credibility gap in experiments and scope |
| Add a CLI runner (e.g., `scripts/run_simulation.py`) for baseline/improved | M | Makes Option 5 reviewers able to run without Jupyter |
| Fix raw data path alignment and document data provenance | S | Update config paths or add a `data/README.md` mapping `$backup` to `data/reports` |
| Add a short results summary (markdown) based on existing `outputs/web` | S | Enables quick review without running notebook |
| Add minimal smoke tests and CI (short-run sim + ingestion) | M | Signals engineering hygiene |

## 2) Repo Map and Entry Points
High-level map:

```
.
+- durban_port_simulation.ipynb
+- README.md
+- VESSEL_LAYER_NOTES.md
+- vessel_layer.py
+- vessel_params.py
+- truck_tas.py
+- src/
¦  +- web_export/export_results_for_web.py
+- scripts/
¦  +- ingest/
¦     +- ingest_unit_volume_reports.py
¦     +- ingest_port_terminals_kpis.py
¦     +- smoke_test_port_terminals_kpis.py
¦     +- config_unit_volume.yml
¦     +- README.md
¦     +- README_port_terminals_kpis.md
+- data/
¦  +- benchmarks/port_efficiency_benchmarks.md
¦  +- processed/
¦     +- unit_volume/
¦     +- port_terminals_kpis/
+- outputs/web/
+- figures/
+- simulation/interactive_port_congestion_simulator/
+- docs/images/
```

Where the main simulation logic lives:
- `durban_port_simulation.ipynb` contains parameters, SimPy processes, baseline/improved runs, plotting, and sensitivity tests.
- `vessel_layer.py` and `vessel_params.py` contain optional vessel/berth dynamics.
- `truck_tas.py` implements the Truck Appointment System process used in the notebook.

How to run the project today (based on evidence):
1. Open `durban_port_simulation.ipynb` and run all cells top-to-bottom (baseline run is default; `USE_VESSEL_LAYER` toggles vessel-driven arrivals).
2. Optional web dashboard export: `python src/web_export/export_results_for_web.py` then `python -m http.server 8000`, open `http://localhost:8000/simulation/interactive_port_congestion_simulator/index.html`.
3. Optional data ingestion: `python scripts/ingest/ingest_unit_volume_reports.py` and `python scripts/ingest/ingest_port_terminals_kpis.py`.

Minimum viable entrypoint (proposed, not implemented):
- `scripts/run_simulation.py --scenario baseline|improved --seed 123 --out outputs/run_YYYYMMDD_HHMMSS/` to run without Jupyter and write results + metadata.

## 3) Runability and Reproducibility Audit
Environment setup:
- No `requirements.txt` or `environment.yml` present. Dependencies are listed in `README.md` as install commands.

Project shape:
- Notebook-first simulation with helper modules (`vessel_layer.py`, `truck_tas.py`) and separate ingestion scripts.

Hard-coded paths and missing data:

| Path | Issue |
| --- | --- |
| `data/processed/unit_volume/unit_volume_long.csv` | Required by `load_teu_arrival_profile`; file exists but is large (562MB) and read via CSV every run |
| `data/processed/unit_volume/unit_volume_wide.csv` | Fallback profile; exists |
| `data/reports/unit_volume_reports` | Expected by `scripts/ingest/config_unit_volume.yml` but not present; raw data sits under `$backup/data_reports/unit_volume_reports` |
| `data/reports/annual_results` | Expected by `scripts/ingest/ingest_port_terminals_kpis.py` but not present; raw PDFs under `$backup/data_reports/annual_results` |
| `/mnt/data/pasted.txt` | Referenced as source in `vessel_params.py` and `VESSEL_LAYER_NOTES.md` but not in repo |

Determinism:
- No random seed management in notebook. Both `random` and `numpy` RNGs are used, so runs are not reproducible.

Outputs:
- Plots saved per run under `figures/run_YYYYMMDD_HHMMSS/`.
- Web export JSON written to `outputs/web/` via `src/web_export/export_results_for_web.py`.
- Processed datasets written under `data/processed/` by ingestion scripts.

Concrete run commands that should exist in README:
```
python scripts/ingest/ingest_unit_volume_reports.py
python scripts/ingest/ingest_port_terminals_kpis.py
python src/web_export/export_results_for_web.py
python -m http.server 8000
```

## 4) System Thinking Signals (What Deloitte Will Look For)

| Signal | Score (0-5) | Evidence and justification |
| --- | --- | --- |
| Clear problem framing and constraints | 4 | Problem scope and limitations are stated in notebook intro; README describes baseline vs improved and disclaimers |
| Explicit system model (stages, queues, capacities) | 4 | SimPy resources and staged flow are defined in `durban_port_simulation.ipynb` (cranes, yard, scanners, loaders, gates) |
| State management and event loop clarity | 3 | SimPy processes are explicit, but core logic is spread across a large notebook and uses mutable globals |
| Instrumentation and KPI design | 3 | Rich KPI derivations in `_metrics_to_dataframe`, but several KPIs are defined without source timestamps |
| Scenario management (baseline vs interventions) | 2 | Baseline/improved runs exist but interventions like customs hold reduction are not actually applied |
| Failure modes and recovery strategies | 2 | Ingestion has some validation; simulation has limited error handling and no graceful fallback if data paths are missing |
| Extensibility and modularity | 3 | Vessel/TAS modules are separated, but main model remains notebook-bound |
| Governance awareness (assumptions, limitations, claims boundaries) | 3 | Assumptions are labeled, but referenced source file is missing and some claims do not map to code |
| Clarity of explanation (docs/README quality) | 3 | README is detailed, but lacks architecture diagrams, reproducibility steps, and reviewer path |

## 5) Architecture and Modeling Review (Evidence-Based)
Modeled pipeline stages:
- Import: crane discharge -> yard entry -> dwell -> yard to scan move -> scan -> ready store -> truck gate-in -> yard to truck move -> loading -> gate-out.
- Transshipment: crane discharge -> yard entry -> dwell -> yard to truck move -> loading -> exit (no gate-out).
- Export: truck gate-in -> yard entry -> dwell -> yard to truck move -> loading -> exit (no gate-out).
- Optional vessel layer: berth queue and crane assignment in `vessel_layer.py` with discharge releases into yard.

Entities, resources, and events:

| Category | Evidence |
| --- | --- |
| Entities | Containers (dict with timestamps, `container_id`, `teu_size`, `flow_type`), trucks (`truck_id` metrics), vessels (`vessel_id` metrics) |
| Resources | `simpy.Resource` for cranes, scanners, loaders, gates, yard equipment, customs (unused); `simpy.Container` for yard and crane pools; `simpy.FilterStore` for ready containers |
| Events/processes | `arrival_generator`, `export_arrival_generator`, `truck_arrival_generator`, `vessel_arrival_generator`, `shift_manager`, `truck_tas_arrival_generator` |

KPIs currently tracked (from `_metrics_to_dataframe` and TAS metrics):
- Container KPIs: `total_time`, `yard_dwell`, `dwell_terminal`, `scan_wait`, `yard_to_scan_wait`, `yard_to_truck_wait`, `loading_wait`, `gate_wait`, `ready_to_pickup_wait`, `pre_pickup_wait`, `yard_equipment_wait`, `dwell_terminal_days`, `pre_pickup_wait_hours`.
- Truck KPIs: `ttt_total`, `gate_in_wait`, `pickup_wait`, `loading_wait`, `gate_out_wait`; TAS adds `staging_wait`, `TTT_terminal`, `total_time`.
- Vessel KPIs (optional): anchorage wait, berth duration, cranes assigned, crane wait, effective SWH.

Intervention hooks currently implemented:
- Shift downtime alignment (`shift_manager` mode historical vs aligned).
- Yard equipment capacity stress test and availability sweep.
- Vessel layer toggles (`USE_VESSEL_LAYER`, `ENABLE_ANCHORAGE_QUEUE`, `INCLUDE_MARINE_DELAYS`).
- Truck Appointment System parameters and hourly arrival multipliers.
- Arrival profile calibration using processed unit volume data.

Key assumptions (explicit and implicit):
- Yard move times are triangular with congestion penalty (`YARD_OCC_THRESHOLD`, `REHANDLE_ALPHA`).
- Container mix via `PCT_40FT`, flow shares via `P_IMPORT`, `P_EXPORT`, `P_TRANSSHIP`.
- Import dwell bands and 24h post-discharge offset; export dwell is uniform placeholder.
- Vessel parameters marked SOURCE-ANCHORED vs ASSUMPTION in `vessel_params.py`.
- TEU-per-move conversion and berth/crane capacities are placeholders without source file in repo.

Modeling inconsistencies or unclear components:
- `dwell_params` are passed into container processes but not used; customs hold and rebook delays are not applied.
- `NUM_CUSTOMS_INSPECTION_BAYS` and `sample_customs_inspection_time` are defined but not invoked.
- `QUEUE_THRESHOLD_SCANNER/LOADER` are set but no rebooking logic uses them.
- `NIGHT_SHIFT_MULTIPLIER` is defined but not used.
- Notebook narrative mentions customs holds and rebooking improvements, but simulation flow does not implement them.

## 6) Experiments and Results Audit
Experiments present:
- Baseline vs improved dwell scenarios in the notebook.
- Yard equipment stress test (crisis capacity midpoint).
- Yard equipment availability sweep with scaled arrivals.
- TAS simulation for truck slotting and turnaround metrics.
- Optional vessel/berth layer runs.

Plots and tables:
- Per-run histograms and diagnostics are saved under `figures/run_YYYYMMDD_HHMMSS/`.
- Web dashboard consumes `outputs/web/baseline.json`, `outputs/web/improved.json`, and `outputs/web/metadata.json`.

Interpretability:
- Bottleneck ranking exists in the web UI; throughput capacity checks exist in the notebook.
- No consolidated results summary is committed for reviewers.

Missing experiments that would strengthen submission (feasible without major rewrites):
- Replicated runs with fixed seeds and confidence intervals.
- Calibration run that compares simulated KPI distributions to `data/processed/port_terminals_kpis`.
- Vessel layer on/off comparison with identical seed and arrival profile.
- Gate-lane and scanner capacity sensitivity sweeps with summarized trade-offs.
- Baseline vs improved scenario where the documented customs/rebook changes are actually applied.

## 7) Documentation Audit (Option 5 Reviewer Path)
README coverage:

| Topic | Status | Notes |
| --- | --- | --- |
| Problem statement | Present | Clear description in `README.md` |
| Architecture overview | Partial | Listed stages, but no diagram or module map |
| How to run | Partial | Notebook steps are present, but no CLI entrypoint |
| Outputs and KPIs | Present | Lists DataFrames and KPI columns |
| Trade-offs and failure modes | Partial | Some notes, but no explicit failure modes section |
| What next | Partial | Notebook has brief next steps; README lacks roadmap |

Missing README subsections (checklist):
- [ ] Architecture diagram (container flow and resources)
- [ ] CLI entrypoint and example command
- [ ] Data provenance and licensing notes
- [ ] Reproducibility (seeds, environment file)
- [ ] Validation criteria and acceptance thresholds
- [ ] Results summary (baseline vs improved headline metrics)
- [ ] Known failure modes and troubleshooting beyond dependencies
- [ ] Test instructions and CI status

Reviewer path (5-minute):
1. Read `README.md` for scope and run instructions.
2. Skim `durban_port_simulation.ipynb` sections: Introduction, Assumptions, Experiments, Results.
3. Open `outputs/web/metadata.json` and `simulation/interactive_port_congestion_simulator/index.html` to view the dashboard outputs.

Reviewer path (30-minute):
1. Run `python src/web_export/export_results_for_web.py` and open the web UI to confirm reproducible outputs.
2. Inspect `vessel_layer.py`, `truck_tas.py`, and `vessel_params.py` for model structure and assumptions.
3. Review `data/benchmarks/port_efficiency_benchmarks.md` and processed KPI data in `data/processed/port_terminals_kpis/`.
4. Review `figures/run_*/` to see distributions and bottlenecks.

Diagrams or screenshots that should exist for a strong submission:
- System flow diagram (import, export, transshipment paths).
- Resource/queue diagram (cranes, yard, scanners, loaders, gates).
- Vessel layer architecture (berth queue, crane pools, discharge rate).
- Data ingestion pipeline diagram (raw reports -> processed datasets).
- Baseline vs improved KPI comparison summary graphic.
- Web dashboard screenshot showing bottleneck ranking and tail behavior.

## 8) Quality, Testing, and Safety Checks
- Tests: only `scripts/ingest/smoke_test_port_terminals_kpis.py` exists; no simulation tests or CI.
- Error handling: ingestion scripts validate inputs; simulation raises errors on missing data but does not catch or recover; web export patches missing arrival profile paths.
- Security and privacy: no API keys detected; raw data in `$backup` should be checked for licensing and redistribution permissions.
- Performance: simulation reads a large CSV (`unit_volume_long.csv`) each run; results are stored in memory lists without chunking.

## 9) Small Agent Opportunities (Targeted)

| Agent task | Inputs required | Outputs produced | Guardrails |
| --- | --- | --- | --- |
| Generate a system flow diagram from the implemented stages | Stage list from notebook and README | `docs/diagrams/system_flow.svg` | Do not change model code or parameters |
| Create a scenario config template for baseline/improved | Global parameters from `durban_port_simulation.ipynb` | `docs/scenarios/template.yml` | Do not run long simulations |
| Build a results summary script for `outputs/web` | `outputs/web/baseline.json`, `outputs/web/improved.json` | `docs/results_summary.md` | Do not overwrite existing outputs |
| Produce a data provenance index | `data/benchmarks/port_efficiency_benchmarks.md`, `vessel_params.py` | `docs/data_sources.md` | Do not add new sources or claims |
| Add deterministic demo outputs | Seed value and short sim time | `outputs/demo/` JSON + plots | Do not modify notebook logic |
| Validate data path alignment | Repo tree and config files | `docs/data_path_audit.md` | Do not move or delete files |
| Generate KPI dictionary from dataframe columns | `outputs/web/metadata.json` | `docs/metrics_dictionary.md` | No changes to metric definitions |
| Draft a Reviewer Path section for README | Existing README content | `docs/reviewer_path.md` | Do not edit README automatically |

## 10) Action Plan to Reach Submission Level
Phase 1 (must-have for submission):

| Item | What to change | Where | Acceptance criteria |
| --- | --- | --- | --- |
| 1 | Implement customs hold and rebooking logic or remove those claims | `durban_port_simulation.ipynb`, `README.md` | Customs/rebook timestamps exist in metrics or claims are removed |
| 2 | Add pinned environment file and update install docs | `requirements.txt`, `README.md` | `pip install -r requirements.txt` succeeds |
| 3 | Add CLI runner for baseline/improved runs | `scripts/run_simulation.py` | `python scripts/run_simulation.py --scenario baseline` produces outputs |
| 4 | Add deterministic seeding and run metadata | `durban_port_simulation.ipynb` or runner script | Same seed yields identical KPIs; seed recorded in output metadata |
| 5 | Reconcile raw data paths and document data layout | `scripts/ingest/config_unit_volume.yml`, `scripts/ingest/ingest_port_terminals_kpis.py`, `data/README.md` | Ingestion runs without manual path edits |
| 6 | Add a results summary for baseline vs improved | `docs/results.md` | Summary includes key KPIs and plots from the latest run |
| 7 | Add simulation smoke tests and CI | `tests/`, `.github/workflows/ci.yml` | CI runs a short sim and ingestion smoke test |
| 8 | Add run output metadata and versioned outputs | `outputs/` structure and export script | Each run has `metadata.json` with config and run time |
| 9 | Add license and data usage note | `LICENSE`, `docs/data_usage.md` | Repo clarifies reuse rights for code and data |

Phase 2 (nice-to-have polish):

| Item | What to change | Where | Acceptance criteria |
| --- | --- | --- | --- |
| 1 | Extract core simulation into a package module | `src/` package + notebook import | Notebook runs using package functions |
| 2 | Add scenario config runner and sweep support | `scripts/run_simulation.py`, `docs/scenarios/` | Multiple scenarios run from config without manual edits |
| 3 | Add calibration report against KPI data | `docs/calibration.md` | Calibration uses `data/processed/port_terminals_kpis` |
| 4 | Add replication and confidence intervals | Notebook or runner | Results include mean and CI across seeds |
| 5 | Optimize arrival data loading | `load_teu_arrival_profile` | Uses parquet or cached subset to reduce load time |
| 6 | Expand web dashboard to compare runs | `simulation/interactive_port_congestion_simulator/app.js` | User can select run timestamps |
| 7 | Add architecture and data pipeline diagrams | `docs/diagrams/` | Diagrams referenced in README |
| 8 | Add governance and assumptions register | `docs/assumptions.md` | All SOURCE-ANCHORED values have citations |
| 9 | Add event trace export for auditability | Notebook or runner | Optional event log is saved per run |

## 11) Appendix
Key files inspected:

| File | Notes |
| --- | --- |
| `README.md` | Project overview, run steps, dependencies, outputs |
| `durban_port_simulation.ipynb` | Main simulation logic, experiments, plots |
| `vessel_layer.py` | Vessel/berth logic and crane pools |
| `vessel_params.py` | Vessel assumptions and parameter tags |
| `truck_tas.py` | Truck appointment system logic |
| `src/web_export/export_results_for_web.py` | Notebook execution for web export |
| `simulation/interactive_port_congestion_simulator/README.md` | Web dashboard instructions |
| `simulation/interactive_port_congestion_simulator/app.js` | Dashboard logic and KPI calculations |
| `scripts/ingest/ingest_unit_volume_reports.py` | Excel ingestion pipeline |
| `scripts/ingest/ingest_port_terminals_kpis.py` | KPI PDF extraction |
| `scripts/ingest/config_unit_volume.yml` | Ingestion configuration and paths |
| `data/benchmarks/port_efficiency_benchmarks.md` | Benchmark ranges and suggested sensitivity tests |
| `outputs/web/metadata.json` | Exported KPI metadata |

Commands executed:
```
Get-ChildItem -Force
rg --files
Get-Content -Path README.md
Get-Content -Path VESSEL_LAYER_NOTES.md
Get-Content -Path simulation\interactive_port_congestion_simulator\README.md
Get-Content -Path scripts\ingest\README.md
Get-Content -Path scripts\ingest\README_port_terminals_kpis.md
Get-Content -Path truck_tas.py
Get-Content -Path vessel_layer.py
Get-Content -Path vessel_params.py
Get-Content -Path src\web_export\export_results_for_web.py
Get-Content -Path data\benchmarks\port_efficiency_benchmarks.md
Get-Content -Path scripts\ingest\ingest_unit_volume_reports.py
Get-Content -Path scripts\ingest\ingest_port_terminals_kpis.py
Get-Content -Path scripts\ingest\smoke_test_port_terminals_kpis.py
Get-Content -Path simulation\interactive_port_congestion_simulator\app.js
python - <<'PY' (list notebook cell indices)
python - <<'PY' (scan cells for keywords)
python - <<'PY' (scan cells for function names)
python - <<'PY' (print selected functions)
rg -n "customs" durban_port_simulation.ipynb
python - <<'PY' (extract sample_pickup_request_delay cell)
rg -n "pickup_request" durban_port_simulation.ipynb
rg --files -g "requirements*"
rg --files -g "*.yml" -g "*.yaml"
Get-Content -Path scripts\ingest\config_unit_volume.yml
Get-ChildItem -Force -Path docs
Get-Content -Path outputs\web\metadata.json
python - <<'PY' (read outputs/web row counts)
python - <<'PY' (list baseline columns)
Get-ChildItem -Force -Path data\processed\unit_volume
Get-ChildItem -Force -Path data\processed\port_terminals_kpis
rg --files -g "*test*" -g "*Test*"
rg --files -g ".github/**"
python -c "import simpy, pandas, numpy, matplotlib, seaborn; print('imports ok')"
python -c "import sys; print(sys.version)"
python -c "import simpy; print('simpy ok')"
python -c "import pandas, numpy; print('pandas/numpy ok')"
python -c "import matplotlib, seaborn; print('mpl/seaborn ok')"
rg -n "seed" durban_port_simulation.ipynb
python - <<'PY' (list markdown headings)
python - <<'PY' (extract Model Scope and Limitations markdown)
python - <<'PY' (extract Phase 2 markdown)
python - <<'PY' (extract Experiment Design markdown)
rg -n "DWELL_PARAMS_BASE|DWELL_PARAMS_IMP" durban_port_simulation.ipynb
rg -n "NIGHT_SHIFT_MULTIPLIER" durban_port_simulation.ipynb
rg -n "env = simpy.Environment|env2 = simpy.Environment|env3 = simpy.Environment" durban_port_simulation.ipynb
python - <<'PY' (print baseline run cell)
python - <<'PY' (print _metrics_to_dataframe cell)
python - <<'PY' (print plot cell)
rg -n "customs_queue_enter|customs_inspection_start|customs_hold_start|rebook_start|rebook_end" durban_port_simulation.ipynb
rg -n "customs_queue|customs_hold|customs_inspection" durban_port_simulation.ipynb
rg -n "schedule_pickup_request|sample_pickup_request_time|maybe_customs_hold|maybe_rebook_pickup" durban_port_simulation.ipynb
```

Errors encountered:
- `python -c "import simpy, pandas, numpy, matplotlib, seaborn; print('imports ok')"` timed out after 13.6 seconds.
- PowerShell parser error when attempting to search for `t["customs` with an unterminated string in `rg`.
