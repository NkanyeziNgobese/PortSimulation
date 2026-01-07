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

DEFAULT_BOUNDS = {
    "min_delta": 0,
    "max_delta": 2,
    "unit": "count",
}

ACTION_MAP = {
    "scan_wait": [
        {
            "parameter": "num_scanners",
            "delta": 1,
            "rationale": "Increase scanner capacity to reduce scan queue waits.",
            **DEFAULT_BOUNDS,
        }
    ],
    "yard_to_scan_wait": [
        {
            "parameter": "yard_equipment_capacity",
            "delta": 1,
            "rationale": "Increase yard equipment capacity to reduce yard-to-scan waits.",
            **DEFAULT_BOUNDS,
        }
    ],
    "yard_to_truck_wait": [
        {
            "parameter": "yard_equipment_capacity",
            "delta": 1,
            "rationale": "Increase yard equipment capacity to reduce yard-to-truck waits.",
            **DEFAULT_BOUNDS,
        }
    ],
    "loading_wait": [
        {
            "parameter": "num_loaders",
            "delta": 1,
            "rationale": "Increase loader capacity to reduce loading queue waits.",
            **DEFAULT_BOUNDS,
        }
    ],
    "gate_wait": [
        {
            "parameter": "num_gate_out",
            "delta": 1,
            "rationale": "Increase gate-out capacity to reduce exit queue waits.",
            **DEFAULT_BOUNDS,
        }
    ],
    "pre_pickup_wait": [],
    "ready_to_pickup_wait": [
        {
            "parameter": "num_gate_in",
            "delta": 1,
            "rationale": "Increase gate-in capacity to reduce pickup delays (proxy).",
            **DEFAULT_BOUNDS,
        }
    ],
    "yard_equipment_wait": [
        {
            "parameter": "yard_equipment_capacity",
            "delta": 1,
            "rationale": "Increase yard equipment capacity to reduce yard equipment waits.",
            **DEFAULT_BOUNDS,
        }
    ],
}
