from dataclasses import dataclass, replace
from typing import List, Tuple


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    description: str
    demo: bool
    sim_time_mins: int
    max_dwell_mins: int
    post_process_buffer_mins: int
    p_import: float
    p_export: float
    p_transship: float
    pct_40ft: float
    num_cranes: int
    yard_capacity: int
    yard_equipment_capacity: int
    num_scanners: int
    num_loaders: int
    num_gate_in: int
    num_gate_out: int
    crane_moves_per_hour: float
    scan_time_mins: float
    yard_move_min: float
    yard_move_mode: float
    yard_move_max: float
    yard_occ_threshold: float
    rehandle_alpha: float
    loading_time_min: float
    loading_time_mode: float
    loading_time_max: float
    gate_in_time_min: float
    gate_in_time_mode: float
    gate_in_time_max: float
    gate_out_time_min: float
    gate_out_time_mode: float
    gate_out_time_max: float
    offset_after_discharge_mins: float
    import_dwell_bands: List[Tuple[float, float, float]]
    transship_dwell_bands: List[Tuple[float, float, float]]
    export_dwell_min: float
    export_dwell_max: float
    ship_interarrival_mean_mins: float
    export_interarrival_mean_mins: float
    hourly_truck_teu_rate: List[float]
    truck_capacity_teu: int

    @property
    def crane_time_mins(self) -> float:
        return 60.0 / max(self.crane_moves_per_hour, 1e-6)


def _demo_base() -> ScenarioConfig:
    return ScenarioConfig(
        name="baseline",
        description=(
            "Demo baseline scenario with scaled timings and synthetic arrivals. "
            "This does not use external datasets."
        ),
        demo=True,
        sim_time_mins=8 * 60,
        max_dwell_mins=4 * 60,
        post_process_buffer_mins=2 * 60,
        p_import=0.6,
        p_export=0.2,
        p_transship=0.2,
        pct_40ft=0.3,
        num_cranes=2,
        yard_capacity=250,
        yard_equipment_capacity=5,
        num_scanners=1,
        num_loaders=2,
        num_gate_in=1,
        num_gate_out=1,
        crane_moves_per_hour=30.0,
        scan_time_mins=5.0,
        yard_move_min=2.0,
        yard_move_mode=3.0,
        yard_move_max=6.0,
        yard_occ_threshold=0.8,
        rehandle_alpha=1.25,
        loading_time_min=6.0,
        loading_time_mode=10.0,
        loading_time_max=18.0,
        gate_in_time_min=0.5,
        gate_in_time_mode=1.0,
        gate_in_time_max=2.0,
        gate_out_time_min=0.5,
        gate_out_time_mode=1.0,
        gate_out_time_max=2.0,
        offset_after_discharge_mins=10.0,
        import_dwell_bands=[
            (10, 30, 0.35),
            (30, 60, 0.35),
            (60, 120, 0.25),
            (120, 180, 0.05),
        ],
        transship_dwell_bands=[
            (5, 20, 0.5),
            (20, 40, 0.3),
            (40, 90, 0.2),
        ],
        export_dwell_min=20.0,
        export_dwell_max=120.0,
        ship_interarrival_mean_mins=6.0,
        export_interarrival_mean_mins=12.0,
        hourly_truck_teu_rate=[
            2, 2, 2, 2, 3, 4,
            5, 6, 7, 7, 7, 6,
            6, 6, 6, 6, 6, 5,
            4, 3, 3, 3, 2, 2,
        ],
        truck_capacity_teu=2,
    )


def get_scenario(name: str, demo: bool) -> ScenarioConfig:
    if not demo:
        raise ValueError("Non-demo CLI runs are not implemented; use the notebook for full runs.")
    name = name.lower().strip()
    if name not in {"baseline", "improved"}:
        raise ValueError(f"Unknown scenario: {name}")
    base = _demo_base()
    if name == "baseline":
        return base
    return replace(
        base,
        name="improved",
        description=(
            "Demo improved scenario (currently identical to baseline; improvements are planned "
            "but not wired in the CLI demo)."
        ),
    )
