# Results Summary

Source of this summary:
- `outputs/web/baseline.json`
- `outputs/web/improved.json`
- Exported at `2026-01-06T10:00:49+00:00` (from `outputs/web/metadata.json`)

All values below are in minutes.

| Metric | Baseline mean | Baseline p90 | Improved mean | Improved p90 |
| --- | --- | --- | --- | --- |
| total_time | 3599.7 | 5359.5 | 3554.2 | 5296.7 |
| yard_dwell | 3544.4 | 5284.1 | 3509.9 | 5236.6 |
| scan_wait | 3.3 | 9.9 | 0.6 | 2.7 |
| loading_wait | 0.0 | 0.0 | 0.0 | 0.0 |
| gate_wait | 0.1 | 0.0 | 0.0 | 0.0 |

Notes:
- `scan_wait` and `gate_wait` are only present for import flows, so their sample sizes are smaller than total containers.
- This summary is based on existing exported outputs; it does not imply a reproducible run unless you re-export from the notebook.

Suggested plots to view:
- `simulation/interactive_port_congestion_simulator/index.html` (dashboard)
- `figures/run_YYYYMMDD_HHMMSS/total_time.png`
- `figures/run_YYYYMMDD_HHMMSS/scan_wait.png`
