from __future__ import annotations

from typing import Any, Dict

from .scenarios import SCENARIO_KEYS


ALLOWED_OVERRIDE_KEYS = set(SCENARIO_KEYS)
RESOURCE_KEYS = {
    "num_scanners",
    "num_loaders",
    "yard_equipment_capacity",
    "num_gate_in",
    "num_gate_out",
    "num_cranes",
}


def _validate_type(key: str, value: Any, expected: Any) -> None:
    if isinstance(expected, bool):
        if not isinstance(value, bool):
            raise ValueError(f"Override '{key}' must be bool.")
        return
    if isinstance(expected, int) and not isinstance(expected, bool):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Override '{key}' must be int.")
        return
    if isinstance(expected, float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Override '{key}' must be float.")
        return
    if isinstance(expected, str):
        if not isinstance(value, str):
            raise ValueError(f"Override '{key}' must be str.")
        return
    if isinstance(expected, list):
        if not isinstance(value, list):
            raise ValueError(f"Override '{key}' must be list.")
        return


def apply_overrides(config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(config, dict) or not config:
        raise ValueError("Config must be a non-empty dict.")
    if not overrides:
        return dict(config)

    unknown = [key for key in overrides if key not in ALLOWED_OVERRIDE_KEYS]
    if unknown:
        raise ValueError(f"Unknown override keys: {', '.join(sorted(unknown))}")

    merged = dict(config)
    for key, value in overrides.items():
        if key not in merged:
            raise ValueError(f"Override key not in base config: {key}")
        _validate_type(key, value, merged[key])
        merged[key] = value

    for key in RESOURCE_KEYS:
        if key in merged:
            value = merged[key]
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"{key} must be an int >= 1.")

    return merged
