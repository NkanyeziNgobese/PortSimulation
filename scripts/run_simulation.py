import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CalledProcessError, check_output

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim import apply_overrides, get_scenario, run_simulation, scenario_from_dict, scenario_to_dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic demo simulation.")
    parser.add_argument("--scenario", choices=["baseline", "improved"], required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--demo", action="store_true", help="Run the lightweight demo simulation.")
    parser.add_argument("--out", required=True, help="Output directory path.")
    parser.add_argument("--config", help="Optional JSON base config path.")
    parser.add_argument("--override", help="Optional JSON overrides path.")
    return parser.parse_args()


def get_git_commit(root: Path) -> str | None:
    try:
        return check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    except (CalledProcessError, FileNotFoundError):
        return None


def plot_histogram(df: pd.DataFrame, column: str, title: str, xlabel: str, out_path: Path) -> bool:
    if df.empty or column not in df.columns:
        return False
    series = df[column].dropna()
    if series.empty:
        return False
    plt.figure(figsize=(10, 5))
    plt.hist(series, bins=30, edgecolor="black", alpha=0.8)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    return True


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_config_dict(args: argparse.Namespace) -> dict:
    if args.config:
        base_config = _load_json(Path(args.config))
    else:
        base_config = scenario_to_dict(get_scenario(args.scenario, demo=True))

    if args.override:
        overrides = _load_json(Path(args.override))
        base_config = apply_overrides(base_config, overrides)

    return base_config


def run_demo(config_dict: dict, seed: int, out_dir: Path) -> dict:
    config = scenario_from_dict(config_dict)

    plots_dir = out_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / "run.log"
    logger = logging.getLogger(f"demo_run_{out_dir.name}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    logger.info("Starting demo run: scenario=%s seed=%s", config.name, seed)
    logger.info("Demo description: %s", config.description)

    df = run_simulation(config, seed=seed)
    logger.info("Completed simulation with %s container rows.", len(df))

    kpis_path = out_dir / "kpis.csv"
    df.to_csv(kpis_path, index=False)
    logger.info("Wrote KPIs to %s", kpis_path)

    total_plot = plots_dir / "total_time_hist.png"
    ok_total = plot_histogram(
        df,
        "total_time",
        "Total Time Distribution (Demo)",
        "Minutes in system",
        total_plot,
    )
    if ok_total:
        logger.info("Saved plot %s", total_plot)
    else:
        logger.warning("Skipped total_time plot (missing data).")

    queue_plot = plots_dir / "scanner_queue_len_hist.png"
    ok_queue = plot_histogram(
        df,
        "scanner_queue_len_at_pickup",
        "Scanner Queue Length at Pickup Request (Demo)",
        "Queue length (count)",
        queue_plot,
    )
    if ok_queue:
        logger.info("Saved plot %s", queue_plot)
    else:
        logger.warning("Skipped scanner queue plot (missing data).")
        fallback_plot = plots_dir / "yard_equipment_wait_hist.png"
        ok_queue = plot_histogram(
            df,
            "yard_equipment_wait",
            "Yard Equipment Wait Distribution (Demo)",
            "Minutes waiting for yard equipment",
            fallback_plot,
        )
        if ok_queue:
            logger.info("Saved plot %s", fallback_plot)
        else:
            logger.warning("Skipped yard equipment wait plot (missing data).")

    metadata = {
        "scenario_name": config.name,
        "scenario_description": config.description,
        "seed": seed,
        "demo": True,
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_commit": get_git_commit(ROOT),
        "row_count": int(len(df)),
        "outputs": {
            "kpis_csv": str(kpis_path.as_posix()),
            "plots_dir": str(plots_dir.as_posix()),
            "run_log": str(log_path.as_posix()),
        },
        "config_summary": {
            "sim_time_mins": config.sim_time_mins,
            "max_dwell_mins": config.max_dwell_mins,
            "post_process_buffer_mins": config.post_process_buffer_mins,
            "flow_mix": {
                "import": config.p_import,
                "export": config.p_export,
                "transship": config.p_transship,
            },
            "resources": {
                "cranes": config.num_cranes,
                "yard_capacity": config.yard_capacity,
                "yard_equipment": config.yard_equipment_capacity,
                "scanners": config.num_scanners,
                "loaders": config.num_loaders,
                "gate_in": config.num_gate_in,
                "gate_out": config.num_gate_out,
            },
        },
        "config_used": config_dict,
    }

    metadata_path = out_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info("Wrote metadata to %s", metadata_path)

    logger.info("Demo run complete.")
    return metadata


def main() -> int:
    args = parse_args()
    if not args.demo:
        print("Non-demo CLI runs are not implemented. Use --demo or the notebook.")
        return 2

    config_dict = _build_config_dict(args)
    run_demo(config_dict, seed=args.seed, out_dir=Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
