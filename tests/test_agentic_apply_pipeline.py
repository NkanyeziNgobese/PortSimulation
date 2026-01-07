import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim import get_scenario, scenario_to_dict


def _load_run_agentic_demo():
    scripts_dir = ROOT / "scripts"
    sys.path.insert(0, str(scripts_dir))
    import run_agentic_apply_demo

    return run_agentic_apply_demo.run_agentic_demo


def test_agentic_apply_pipeline(tmp_path):
    run_agentic_demo = _load_run_agentic_demo()
    base = scenario_to_dict(get_scenario("baseline", demo=True))
    base.update(
        {
            "sim_time_mins": 30,
            "max_dwell_mins": 30,
            "post_process_buffer_mins": 15,
            "ship_interarrival_mean_mins": 20.0,
            "export_interarrival_mean_mins": 25.0,
            "hourly_truck_teu_rate": [1] * 24,
        }
    )

    result = run_agentic_demo(out_dir=tmp_path, seed=123, max_actions=2, base_config=base)

    assert (tmp_path / "baseline" / "metadata.json").exists()
    assert (tmp_path / "baseline" / "kpis.csv").exists()
    assert (tmp_path / "decision.json").exists()

    if result.get("applied"):
        assert (tmp_path / "after" / "metadata.json").exists()
        assert (tmp_path / "after" / "kpis.csv").exists()
        assert (tmp_path / "comparison.json").exists()
