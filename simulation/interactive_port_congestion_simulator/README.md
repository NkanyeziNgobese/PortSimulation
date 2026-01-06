# Interactive Port Congestion Simulator

This browser dashboard reads the latest Python simulation exports and compares baseline vs improved performance.

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

## Notes
- Use the Baseline/Improved buttons to toggle the active scenario.
- The Sources & Assumptions panel pulls from `outputs/web/metadata.json`.
- If you re-run the export script, click "Reload Data" in the UI.
