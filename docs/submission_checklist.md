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

## Screenshots (evidence)
- `docs/screenshots/terminal_success_run_screenshot.png` - terminal success run for the demo command
- `docs/screenshots/output_artifacts_proof_screenshot.png` - proof of generated outputs folder
- `docs/screenshots/before_and_after_plot_screenshot.png` - before vs after plots
- `docs/screenshots/agentic_summary_screenshot.png` - agentic summary excerpt

## Before submitting
- Run: `python scripts/run_agentic_apply_demo.py --seed 123 --max-actions 2 --out outputs/agentic_demo`
- Confirm all artifacts in the outputs list exist.
- Confirm all screenshots in `docs/screenshots/` exist and render in README.
