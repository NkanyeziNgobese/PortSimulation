# Failure Modes and Recovery

This document lists known failure scenarios and how the current system responds.

## Missing data files
Scenario:
- `data/processed/unit_volume/unit_volume_long.csv` is missing and the notebook tries to load it.

Current behavior:
- The notebook raises a `ValueError` when the file or required columns are missing.
- The web export script logs a warning and falls back to a synthetic arrival profile.

Recovery:
- Run `python scripts/ingest/ingest_unit_volume_reports.py` with valid input files.
- Or set the arrival profile path to `None` to use the synthetic fallback.

## Invalid parameters (negative capacities or rates)
Scenario:
- A resource capacity (cranes, scanners, loaders) is set to 0 or negative.

Current behavior:
- SimPy resource creation may fail or lead to no progress.

Recovery:
- Validate inputs before running; ensure all capacities are positive.
- Use the CLI demo defaults for a known-good baseline.

## Output directory not writable
Scenario:
- The output path passed to `scripts/run_simulation.py` is not writable.

Current behavior:
- The CLI demo will raise an exception when trying to create directories or write files.

Recovery:
- Choose a writable path (e.g., under `outputs/`) or fix permissions.

## Missing optional dependencies
Scenario:
- Optional ingestion dependencies (PyYAML, pdfplumber, pyarrow) are not installed.

Current behavior:
- Ingestion scripts raise import errors with install instructions.

Recovery:
- Install the missing packages from `requirements.txt` (and optional extras as needed).
