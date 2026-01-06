# Interactive Port Congestion Simulator

This browser dashboard reads the latest Python simulation exports and compares baseline vs improved performance.
It does not run the simulation in the browser; instead it loads the JSON outputs produced by the Python model.

## What it shows
- Side-by-side KPI cards (mean, median, p90, p95) for the two scenarios.
- Distribution charts for total time and key waits.
- Long-tail diagnostics (p95, p99, and highest-delay outliers).
- Bottleneck ranking by percent contribution to mean total time.
- Sources & assumptions pulled directly from the export metadata.

## 1) Export results for the web
From the repo root:

```powershell
python src\web_export\export_results_for_web.py
```

This writes JSON outputs to:

```
outputs\web\baseline.json
outputs\web\improved.json
outputs\web\metadata.json
```

## 2) Open the web app
Because the app loads JSON via `fetch`, use a local server so the browser can read the files.

From the repo root:

```powershell
python -m http.server 8000
```

Then open:

```
http://localhost:8000/simulation/interactive_port_congestion_simulator/index.html
```

## Interface tour (visual walkthrough)

![Header and data status](images/interactive_head.png)
The header shows data load status and the run timestamp from the export. Use the Baseline/Improved/Reload buttons to switch scenarios or refresh outputs.

![Scenario KPI summary](images/interactive_scenario_kpi.png)
KPI cards compare the two scenarios using mean, median, p90, and p95 so you can see both central tendency and tail behavior.

![Distribution charts](images/interactive_distribution.png)
Distributions reveal how each wait time shifts between baseline and improved runs, highlighting congestion spikes and long tails.

![Long-tail diagnostics](images/interactive_long_tail_diagnostics.png)
The long-tail panel isolates p95 and p99 for total time, plus the top outliers to make extreme delays easy to inspect.

![Bottleneck ranking](images/interactive_bottleneck_ranking.png)
The bottleneck panel ranks stages by percent contribution to mean total time, making it clear where the system spends most of its time.

![Sources and assumptions](images/interactive_sources.png)
Sources and assumptions are read from `outputs/web/metadata.json`, keeping metric units and references traceable back to the model.

## Notes
- Use the Baseline/Improved buttons to toggle the active scenario.
- The Sources & Assumptions panel pulls from `outputs/web/metadata.json`.
- If you re-run the export script, click "Reload Data" in the UI.
