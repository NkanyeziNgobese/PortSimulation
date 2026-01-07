from __future__ import annotations

from typing import Dict, List, Optional

from .actions import (
    ACTION_MAP,
    ALLOWED_PARAMETERS,
    FORBIDDEN_ACTIONS,
    MAX_ACTIONS_DEFAULT,
    MAX_TOTAL_DELTA_DEFAULT,
)


DEFAULT_CONFIDENCE_THRESHOLD = 0.5


def _sorted_bottlenecks(stage_rankings: List[dict]) -> List[dict]:
    return sorted(
        [row for row in stage_rankings if row.get("contribution") is not None],
        key=lambda row: row["contribution"],
        reverse=True,
    )


def recommend(
    diagnostics: Dict[str, object],
    action_map: Optional[Dict[str, List[dict]]] = None,
    max_actions: int = MAX_ACTIONS_DEFAULT,
    max_total_delta: int = MAX_TOTAL_DELTA_DEFAULT,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Dict[str, object]:
    if action_map is None:
        action_map = ACTION_MAP

    stage_rankings = diagnostics.get("stage_rankings", [])
    confidence = float(diagnostics.get("confidence", 0.0))

    top_bottlenecks = _sorted_bottlenecks(stage_rankings)[:3]
    recommended_actions: List[dict] = []
    notes: List[str] = []

    if confidence < confidence_threshold:
        notes.append("Confidence below threshold; collect more metrics or run demo outputs.")
    else:
        seen_params = set()
        total_delta = 0
        for bottleneck in top_bottlenecks:
            stage = bottleneck.get("stage")
            actions = action_map.get(stage, [])
            if not actions:
                notes.append(f"No safe action mapped for stage: {stage}.")
                continue
            for action in actions:
                param = action.get("param")
                delta = int(action.get("delta", 0))
                if not param or param in seen_params:
                    continue
                if total_delta + delta > max_total_delta:
                    continue
                recommended_actions.append(
                    {
                        "stage": stage,
                        "action": action.get("action"),
                        "param": param,
                        "delta": delta,
                        "min": action.get("min"),
                        "max": action.get("max"),
                        "rationale": action.get("rationale", ""),
                    }
                )
                seen_params.add(param)
                total_delta += delta
                if len(recommended_actions) >= max_actions:
                    break
            if len(recommended_actions) >= max_actions:
                break

    decision = {
        "top_bottlenecks": top_bottlenecks,
        "recommended_actions": recommended_actions,
        "guardrails": {
            "max_actions": max_actions,
            "max_total_delta": max_total_delta,
            "allowed_parameters": ALLOWED_PARAMETERS,
            "forbidden_actions": FORBIDDEN_ACTIONS,
            "claims_boundary": "simulation suggests; not operational advice",
        },
        "confidence": confidence,
    }

    if notes:
        decision["notes"] = notes

    return decision
