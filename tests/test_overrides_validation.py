import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim import apply_overrides, get_scenario, scenario_to_dict


def test_apply_overrides_rejects_unknown_key():
    base = scenario_to_dict(get_scenario("baseline", demo=True))
    with pytest.raises(ValueError):
        apply_overrides(base, {"unknown_key": 1})


def test_apply_overrides_enforces_bounds():
    base = scenario_to_dict(get_scenario("baseline", demo=True))
    with pytest.raises(ValueError):
        apply_overrides(base, {"num_scanners": 0})


def test_apply_overrides_type_check():
    base = scenario_to_dict(get_scenario("baseline", demo=True))
    with pytest.raises(ValueError):
        apply_overrides(base, {"num_cranes": "2"})
