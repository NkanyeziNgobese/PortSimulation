from __future__ import annotations

ALLOWED_PARAMETERS = [
    "num_scanners",
    "num_loaders",
    "yard_equipment_capacity",
    "num_gate_in",
    "num_gate_out",
    "num_cranes",
]

FORBIDDEN_ACTIONS = [
    "arrival rates",
    "flow mix",
    "dwell distributions",
    "vessel layer toggles",
    "data/profile rewrites",
]

MAX_ACTIONS_DEFAULT = 2
MAX_TOTAL_DELTA_DEFAULT = 2

DEFAULT_ACTION_BOUNDS = {
    "min": 1,
    "max": 10,
}

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
