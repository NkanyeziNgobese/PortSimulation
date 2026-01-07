import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.diagnose import diagnose
from src.agent.recommend import recommend


def _default_input(root: Path) -> Path:
    baseline = root / "outputs" / "web" / "baseline.json"
    if baseline.exists():
        return baseline

    outputs_dir = root / "outputs"
    candidates = list(outputs_dir.rglob("kpis.csv")) if outputs_dir.exists() else []
    if not candidates:
        raise FileNotFoundError("No outputs/web/baseline.json or outputs/**/kpis.csv found.")
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def _default_out_dir(root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return root / "outputs" / "agentic_runs" / timestamp


def _format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _write_summary(out_dir: Path, diagnostics: dict, decision: dict) -> None:
    top = decision.get("top_bottlenecks", [])
    actions = decision.get("recommended_actions", [])
    confidence = decision.get("confidence")
    input_source = diagnostics.get("input_source")

    lines = [
        "# Agentic Summary",
        "",
        f"- Input: `{input_source}`",
        f"- Confidence: {confidence:.2f}" if isinstance(confidence, float) else "- Confidence: n/a",
    ]

    if top:
        best = top[0]
        stage = best.get("stage")
        contrib = _format_percent(best.get("contribution"))
        mean_wait = best.get("mean_wait")
        mean_wait_str = f"{mean_wait:.2f}" if isinstance(mean_wait, (int, float)) else "n/a"
        lines.append(f"- Top bottleneck: `{stage}` (mean={mean_wait_str}, contribution={contrib})")
    else:
        lines.append("- Top bottleneck: n/a")

    if actions:
        action = actions[0]
        lines.append(
            "- Recommendation: "
            f"`{action.get('param')}` {action.get('delta')} "
            f"(bounds {action.get('min')}..{action.get('max')})"
        )
    else:
        lines.append("- Recommendation: collect more metrics or run demo outputs.")

    summary_path = out_dir / "agentic_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Option A agentic diagnostics.")
    parser.add_argument(
        "--input",
        help="Path to outputs/web/baseline.json or a kpis.csv file.",
    )
    parser.add_argument(
        "--out",
        help="Output directory (default: outputs/agentic_runs/<timestamp>/).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input) if args.input else _default_input(ROOT)
    out_dir = Path(args.out) if args.out else _default_out_dir(ROOT)
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnostics = diagnose(input_path)
    decision = recommend(diagnostics)

    (out_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2), encoding="utf-8"
    )
    (out_dir / "decision.json").write_text(
        json.dumps(decision, indent=2), encoding="utf-8"
    )
    _write_summary(out_dir, diagnostics, decision)

    print(f"Wrote agentic artifacts to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
