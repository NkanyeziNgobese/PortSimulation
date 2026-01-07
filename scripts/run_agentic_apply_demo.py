import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_simulation
from src.agent.apply import apply_actions
from src.agent.compare import compare_kpis
from src.agent.diagnose import diagnose_kpis_path
from src.agent.recommend import recommend
from src.sim import get_scenario, scenario_to_dict


def _default_out_dir(root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return root / "outputs" / f"agentic_demo_{timestamp}"


def _load_kpis(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _format_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _build_summary(
    out_dir: Path,
    diagnostics: dict,
    decision: dict,
    applied_actions: list,
    comparison: dict | None,
) -> None:
    confidence = diagnostics.get("confidence")
    top_bottleneck = (decision.get("top_bottlenecks") or [None])[0] or {}
    bottleneck_stage = top_bottleneck.get("stage", "n/a")
    bottleneck_contrib = top_bottleneck.get("contribution")
    bottleneck_contrib_str = (
        f"{bottleneck_contrib * 100:.1f}%" if isinstance(bottleneck_contrib, (int, float)) else "n/a"
    )

    lines = [
        "# Agentic Summary (Option B Demo)",
        "",
        f"- Confidence: {confidence:.2f}" if isinstance(confidence, float) else "- Confidence: n/a",
        f"- Top bottleneck: `{bottleneck_stage}` ({bottleneck_contrib_str} of total_time)",
    ]

    guardrails = decision.get("guardrails", {})
    if guardrails:
        lines.append(
            "- Guardrails: "
            f"max_actions={guardrails.get('max_actions')}, "
            f"max_total_delta={guardrails.get('max_total_delta')}, "
            "forbidden=arrival rates/flow mix/dwell/vessel toggles/data rewrites"
        )

    if applied_actions:
        lines.append("- Applied actions:")
        for action in applied_actions:
            lines.append(
                f"  - {action.get('action')} -> {action.get('param')} "
                f"{action.get('baseline')} -> {action.get('applied')}"
            )
    else:
        lines.append("- Applied actions: none")

    if comparison:
        metrics = comparison.get("metrics", [])
        total_row = next((row for row in metrics if row.get("metric") == "total_time"), {})
        lines.append(
            "- Baseline total_time mean/p95: "
            f"{_format_value(total_row.get('baseline_mean'))} / {_format_value(total_row.get('baseline_p95'))}"
        )
        lines.append(
            "- After total_time mean/p95: "
            f"{_format_value(total_row.get('after_mean'))} / {_format_value(total_row.get('after_p95'))}"
        )
        lines.append(
            "- Delta total_time mean/p95: "
            f"{_format_value(total_row.get('delta_mean'))} / {_format_value(total_row.get('delta_p95'))}"
        )

    summary_path = out_dir / "agentic_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_agentic_demo(
    out_dir: Path,
    seed: int,
    max_actions: int,
    base_config: dict | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir = out_dir / "baseline"
    after_dir = out_dir / "after"

    if base_config is None:
        base_config = scenario_to_dict(get_scenario("baseline", demo=True))

    run_simulation.run_demo(base_config, seed=seed, out_dir=baseline_dir)

    kpis_path = baseline_dir / "kpis.csv"
    diagnostics = diagnose_kpis_path(kpis_path)
    decision = recommend(diagnostics, max_actions=max_actions)
    _write_json(out_dir / "decision.json", decision)

    summary_path = out_dir / "agentic_summary.md"
    if float(diagnostics.get("confidence", 0.0)) < 0.5:
        _build_summary(out_dir, diagnostics, decision, [], None)
        return {
            "decision": decision,
            "applied": False,
            "applied_actions": [],
            "summary_path": summary_path,
        }

    baseline_metadata = json.loads((baseline_dir / "metadata.json").read_text(encoding="utf-8"))
    baseline_config = baseline_metadata.get("config_used") or base_config

    overrides, applied_actions = apply_actions(
        baseline_config,
        decision.get("recommended_actions", []),
        max_actions=max_actions,
    )

    if not overrides:
        _build_summary(out_dir, diagnostics, decision, applied_actions, None)
        return {
            "decision": decision,
            "applied": False,
            "applied_actions": applied_actions,
            "summary_path": summary_path,
        }

    _write_json(out_dir / "overrides.json", overrides)

    config_after = dict(baseline_config)
    config_after.update(overrides)
    run_simulation.run_demo(config_after, seed=seed, out_dir=after_dir)

    baseline_df = _load_kpis(baseline_dir / "kpis.csv")
    after_df = _load_kpis(after_dir / "kpis.csv")
    comparison, comparison_df = compare_kpis(baseline_df, after_df)
    _write_json(out_dir / "comparison.json", comparison)
    comparison_df.to_csv(out_dir / "comparison.csv", index=False)

    _build_summary(out_dir, diagnostics, decision, applied_actions, comparison)
    return {
        "decision": decision,
        "applied": True,
        "comparison": comparison,
        "applied_actions": applied_actions,
        "summary_path": summary_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Option B agentic demo with auto-apply.")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--max-actions", type=int, default=2)
    parser.add_argument("--out", help="Output directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out) if args.out else _default_out_dir(ROOT)
    result = run_agentic_demo(out_dir=out_dir, seed=args.seed, max_actions=args.max_actions)
    applied_actions = result.get("applied_actions") or []
    summary_path = result.get("summary_path")
    print(f"Wrote agentic demo outputs to {out_dir}")
    if applied_actions:
        actions_text = "; ".join(
            f"{item.get('param')} {item.get('baseline')}->{item.get('applied')}"
            for item in applied_actions
        )
        print(f"Applied actions: {actions_text}")
    else:
        print("Applied actions: none")
    if summary_path:
        print(f"Agentic summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
