from __future__ import annotations

from typing import Dict, List, Tuple

from .actions import MAX_ACTIONS_DEFAULT, MAX_TOTAL_DELTA_DEFAULT


def apply_actions(
    baseline_config: Dict[str, object],
    recommended_actions: List[dict],
    max_actions: int = MAX_ACTIONS_DEFAULT,
    max_total_delta: int = MAX_TOTAL_DELTA_DEFAULT,
) -> Tuple[Dict[str, object], List[dict]]:
    if not recommended_actions:
        return {}, []

    overrides: Dict[str, object] = {}
    applied: List[dict] = []
    total_delta = 0

    for action in recommended_actions:
        if len(applied) >= max_actions:
            break

        delta = int(action.get("delta", 0))
        if delta < 0:
            raise ValueError("Action delta must be non-negative.")
        if delta > 1:
            raise ValueError("Action delta must be +1 per guardrails.")
        if total_delta + delta > max_total_delta:
            break

        param = action.get("param")
        if not param or param not in baseline_config:
            raise ValueError(f"Action parameter not found in baseline config: {param}")

        base_value = baseline_config[param]
        if not isinstance(base_value, int):
            raise ValueError(f"Baseline value for {param} must be int.")

        new_value = base_value + delta
        min_allowed = action.get("min")
        max_allowed = action.get("max")
        if min_allowed is not None and new_value < min_allowed:
            raise ValueError(f"Action for {param} below min bound.")
        if max_allowed is not None and new_value > max_allowed:
            raise ValueError(f"Action for {param} above max bound.")

        overrides[param] = new_value
        applied.append(
            {
                "action": action.get("action"),
                "param": param,
                "delta": delta,
                "baseline": base_value,
                "applied": new_value,
            }
        )
        total_delta += delta

    return overrides, applied
