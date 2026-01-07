# Submission Checklist (Option 5)

## Clean clone test
- Clone the repo into a fresh folder.
- Ensure no existing outputs/ or virtual environments exist.
- Verify Python 3.11+ is available.

## Commands to run
- `python -m pip install -r requirements.txt`
- `python scripts/run_agentic_apply_demo.py --seed 123 --max-actions 2 --out outputs/agentic_demo`
- `pytest -q`

## Outputs to verify
- `outputs/agentic_demo/baseline/metadata.json`
- `outputs/agentic_demo/baseline/kpis.csv`
- `outputs/agentic_demo/baseline/plots/`
- `outputs/agentic_demo/decision.json`
- `outputs/agentic_demo/after/metadata.json`
- `outputs/agentic_demo/after/kpis.csv`
- `outputs/agentic_demo/after/plots/`
- `outputs/agentic_demo/comparison.json`
- `outputs/agentic_demo/comparison.csv`
- `outputs/agentic_demo/agentic_summary.md`

## Screenshots to capture (placeholders)
- Agentic summary (`outputs/agentic_demo/agentic_summary.md`)
- Baseline total_time histogram (`outputs/agentic_demo/baseline/plots/total_time_hist.png`)
- After total_time histogram (`outputs/agentic_demo/after/plots/total_time_hist.png`)
- Decision JSON (`outputs/agentic_demo/decision.json`)
