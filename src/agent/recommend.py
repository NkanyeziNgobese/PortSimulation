# ====================================================================================================
# Fork Point: Decide stage (Option B agent loop)
#
# This module corresponds to DECIDE:
# - Input: a diagnostics dict from `src/agent/diagnose.py` (stage_rankings + confidence).
# - Output: a decision dict that says "here are the top bottlenecks, and here are bounded actions we
#   recommend trying next".
#
# What the decision includes (key artifacts for the interview):
# - top_bottlenecks: highest-contribution stages (based on Diagnose output)
# - recommended_actions: bounded, allowlisted actions (may be empty)
# - guardrails: what we allow and what we refuse to change
# - notes: optional explanations when we cannot recommend anything
#
# Governance idea:
# - This module does NOT apply changes. It only recommends safe actions.
# - Apply happens later (overrides built/applied by the orchestrator + `src/sim/overrides.py`).
# ====================================================================================================

from __future__ import annotations

from typing import Dict, List, Optional

# Action policy lives in `src/agent/actions.py` (the allowlist + guardrails table):
# - ACTION_MAP: stage -> list of safe actions (param, delta, bounds, rationale)
# - ALLOWED_PARAMETERS / FORBIDDEN_ACTIONS: explicit "can change" vs "do not change"
# - MAX_ACTIONS_DEFAULT / MAX_TOTAL_DELTA_DEFAULT: built-in caps when the caller doesn't override them
from .actions import (
    ACTION_MAP,
    ALLOWED_PARAMETERS,
    FORBIDDEN_ACTIONS,
    MAX_ACTIONS_DEFAULT,
    MAX_TOTAL_DELTA_DEFAULT,
)


DEFAULT_CONFIDENCE_THRESHOLD = 0.5

# ----------------------------------------------------------------------------------------------------
# _sorted_bottlenecks
# Purpose (simple): Sort bottlenecks by contribution (largest share of total_time first).
# Loop stage: Decide
# Inputs: `stage_rankings` list from Diagnose (each item may have contribution=None)
# Outputs: filtered + sorted list (drops rows with missing contribution)
# Interview explanation: "We focus on stages we can quantify, and rank by biggest share of delay."
# ----------------------------------------------------------------------------------------------------
def _sorted_bottlenecks(stage_rankings: List[dict]) -> List[dict]:
    return sorted(
        [row for row in stage_rankings if row.get("contribution") is not None],
        key=lambda row: row["contribution"],
        reverse=True,
    )


# ----------------------------------------------------------------------------------------------------
# recommend
# Purpose (simple): Convert diagnostics into a bounded set of recommended actions and guardrails.
# Loop stage: Decide
# Inputs: diagnostics dict (stage_rankings + confidence), plus optional policy/limits
# Outputs: decision dict (top_bottlenecks, recommended_actions, guardrails, confidence, optional notes)
# Interview explanation: "This is constrained decision-making: only allowlisted knobs, capped actions,
# and a confidence gate that can return 'no recommendation'."
# ----------------------------------------------------------------------------------------------------
def recommend(
    diagnostics: Dict[str, object],
    action_map: Optional[Dict[str, List[dict]]] = None,
    max_actions: int = MAX_ACTIONS_DEFAULT,
    max_total_delta: int = MAX_TOTAL_DELTA_DEFAULT,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Dict[str, object]:
    # Policy default: use the built-in stage->action mapping unless the caller injects a custom policy.
    if action_map is None:
        action_map = ACTION_MAP

    # Read Diagnose outputs (these are produced from baseline KPIs).
    stage_rankings = diagnostics.get("stage_rankings", [])
    confidence = float(diagnostics.get("confidence", 0.0))

    # Consider only the top few bottlenecks for a short, interview-friendly decision (cap at 3 stages).
    top_bottlenecks = _sorted_bottlenecks(stage_rankings)[:3]
    recommended_actions: List[dict] = []
    notes: List[str] = []

    # Confidence gate: below threshold => do not recommend changes (upstream will typically "no-apply").
    if confidence < confidence_threshold:
        notes.append("Confidence below threshold; collect more metrics or run demo outputs.")
    else:
        # Guardrail enforcement inside the recommendation step:
        # - seen_params: avoid changing the same parameter twice
        # - total_delta: cap total changes across all actions
        # - max_actions: cap the number of actions returned
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
                # Build a recommendation record (the Apply step will later translate this into overrides).
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

    # Decision payload includes guardrails explicitly so downstream steps (and reviewers) can verify bounds.
    # The "claims_boundary" reminds that this is a simulation suggestion, not operational advice.
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


# ----------------------------------------------------------------------------------------------------
# Closing notes (for interviews / demos)
#
# What this module proves:
# - You can turn diagnostics into a bounded, auditable decision under uncertainty (confidence gate).
#
# Limitation (intentional):
# - The stage->action mapping is small and conservative. It is an allowlist, not a full optimizer.
#
# Where the loop goes next:
# - The orchestrator uses `recommended_actions` to build concrete config overrides in Apply, then re-runs
#   the simulation and compares KPIs.
# ----------------------------------------------------------------------------------------------------
