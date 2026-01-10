# ====================================================================================================
# Fork Point: Policy Contract (Decide + Apply)
#
# This module is the "policy layer" that constrains the agent. It defines:
# - the ONLY scenario knobs the agent is allowed to touch (ALLOWED_PARAMETERS)
# - global guardrails (max actions and total delta caps)
# - the stage-to-action table used to map bottlenecks to safe interventions (ACTION_MAP)
#
# How it is referenced in the main loop (indirectly):
# - scripts/run_agentic_apply_demo.py calls recommend(...) in src/agent/recommend.py
# - recommend.py imports this module and reads ACTION_MAP + guardrail constants
#
# How it relates to Apply/validation:
# - scripts/run_agentic_apply_demo.py calls apply_actions(...) in src/agent/apply.py
# - apply_actions(...) enforces max_actions / max_total_delta and parameter existence/types
# - src/sim/overrides.py validates final overrides against the scenario schema and resource bounds
#
# Interview framing:
# - Treat this file as the shared "policy contract" for both DECIDE and APPLY.
# - It is intentionally small and conservative for safety and reviewer clarity.
# ====================================================================================================

from __future__ import annotations

# ALLOWED_PARAMETERS:
# - Supply-side "capacity knobs" that increase service capacity (resources), not demand.
# - These are deliberately discrete ints so overrides are easy to validate and reason about.
ALLOWED_PARAMETERS = [
    "num_scanners",
    "num_loaders",
    "yard_equipment_capacity",
    "num_gate_in",
    "num_gate_out",
    "num_cranes",
]

# FORBIDDEN_ACTIONS:
# - Things we intentionally do NOT let the agent change in the demo loop.
# - These are excluded to avoid "gaming" outcomes and to preserve fair baseline vs after comparability.
FORBIDDEN_ACTIONS = [
    "arrival rates",
    "flow mix",
    "dwell distributions",
    "vessel layer toggles",
    "data/profile rewrites",
]

# MAX_ACTIONS_DEFAULT:
# - Bound the decision to a small number of changes per iteration (readable + safer).
MAX_ACTIONS_DEFAULT = 2

# MAX_TOTAL_DELTA_DEFAULT:
# - Bound the total magnitude of changes across actions (prevents runaway capacity increases).
MAX_TOTAL_DELTA_DEFAULT = 2

# DEFAULT_ACTION_BOUNDS:
# - Min/max bounds exist for type safety and future extension (even if demo bounds are wide).
# - Apply/validation can reject actions that would push a parameter outside allowed ranges.
DEFAULT_ACTION_BOUNDS = {
    "min": 1,
    "max": 10,
}

# ACTION_MAP:
# - Keys are stage wait column names produced by Diagnose (see src/agent/diagnose.py).
# - Values are lists of safe actions we know how to justify and validate.
#
# How it is used:
# - recommend.py reads this map to propose actions for the top bottleneck stages.
# - apply.py selects from those recommended actions (bounded by max_actions/max_total_delta).
# - overrides.py validates the final overrides (schema keys, types, and resource >= 1 checks).
#
# Some stages intentionally map to an empty list (e.g., pre_pickup_wait):
# - This means "no safe intervention encoded yet" rather than guessing.
ACTION_MAP = {
    "scan_wait": [
        {
            "action": "INCREASE_SCANNERS",
            "param": "num_scanners",
            "delta": 1,
            "rationale": "Increase scanner capacity to reduce scan queue waits.",
            **DEFAULT_ACTION_BOUNDS,
        }
    ],
    "yard_to_scan_wait": [
        {
            "action": "INCREASE_YARD_EQUIPMENT",
            "param": "yard_equipment_capacity",
            "delta": 1,
            "rationale": "Increase yard equipment capacity to reduce yard-to-scan waits.",
            **DEFAULT_ACTION_BOUNDS,
        }
    ],
    "yard_to_truck_wait": [
        {
            "action": "INCREASE_YARD_EQUIPMENT",
            "param": "yard_equipment_capacity",
            "delta": 1,
            "rationale": "Increase yard equipment capacity to reduce yard-to-truck waits.",
            **DEFAULT_ACTION_BOUNDS,
        }
    ],
    "loading_wait": [
        {
            "action": "INCREASE_LOADERS",
            "param": "num_loaders",
            "delta": 1,
            "rationale": "Increase loader capacity to reduce loading queue waits.",
            **DEFAULT_ACTION_BOUNDS,
        }
    ],
    "gate_wait": [
        {
            "action": "INCREASE_GATE_OUT",
            "param": "num_gate_out",
            "delta": 1,
            "rationale": "Increase gate-out capacity to reduce exit queue waits.",
            **DEFAULT_ACTION_BOUNDS,
        }
    ],
    "pre_pickup_wait": [],
    "ready_to_pickup_wait": [
        {
            "action": "INCREASE_GATE_IN",
            "param": "num_gate_in",
            "delta": 1,
            "rationale": "Increase gate-in capacity to reduce pickup delays (proxy).",
            **DEFAULT_ACTION_BOUNDS,
        }
    ],
    "yard_equipment_wait": [
        {
            "action": "INCREASE_YARD_EQUIPMENT",
            "param": "yard_equipment_capacity",
            "delta": 1,
            "rationale": "Increase yard equipment capacity to reduce yard equipment waits.",
            **DEFAULT_ACTION_BOUNDS,
        }
    ],
}


# Return to orchestrator note:
# - Once recommend() produces decision.json using this policy, the orchestrator proceeds to APPLY,
#   where overrides are validated and then the simulation is re-run for comparison.
