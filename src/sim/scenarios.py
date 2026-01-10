# ====================================================================================================
# Fork Point — Demo Scenarios used by the Option B "Bounded Agentic Bottleneck Loop"
#
# Where this module sits in the loop:
# - Supports OBSERVE and RE-RUN by providing a `ScenarioConfig` for baseline (and a small "improved"
#   variant for quick comparisons).
#
# Why demo scenarios exist:
# - Reviewer-friendly: runs locally with no external data or notebooks required.
# - Fast: uses scaled timings + synthetic arrivals so a full run completes quickly.
# - Deterministic when seeded: the orchestrator/runner controls randomness via a fixed `seed`.
#
# How the agent interacts with this module:
# - The agent does NOT edit this file.
# - The Option B loop converts a scenario to a plain dict (`scenario_to_dict(...)`), then applies bounded
#   overrides later via `src/sim/overrides.py` (wired by `scripts/run_agentic_apply_demo.py`).
#
# What to emphasize in an interview:
# - `ScenarioConfig` is the simulation's "knob panel" (resources, service times, arrivals, dwell rules).
# - `get_scenario(...)` is the controlled entrypoint: it returns a known-good baseline/improved config
#   and keeps CLI demo runs scoped to these curated settings.
# ====================================================================================================

from dataclasses import asdict, dataclass, replace
from typing import List, Tuple


# ----------------------------------------------------------------------------------------------------
# ScenarioConfig
# Purpose (simple): Single, immutable configuration object for one simulation run.
# Loop stage(s): Observe / Re-run (shared config)
# Inputs: Field values (times, probabilities, capacities, arrival rates)
# Outputs: A frozen dataclass instance used by the simulation core
# Why it matters in the interview:
# - These fields directly shape queues/resources, so they drive wait times and KPIs (e.g., `total_time`).
# - `frozen=True` prevents accidental mutation, making baseline vs after comparisons reproducible.
# - Agent actions typically map to a small subset (resource counts and small timing tweaks), but the
#   action/override logic lives elsewhere (not in this config definition).
# ----------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ScenarioConfig:
    # Identity + flags (useful for metadata/logs; `demo` gates CLI behavior).
    name: str
    description: str
    demo: bool

    # Time horizon + dwell controls (how long we simulate and how long containers can stay in-system).
    sim_time_mins: int
    max_dwell_mins: int
    post_process_buffer_mins: int

    # Flow mix + container mix (shares of import/export/transship, and the 40ft split).
    p_import: float
    p_export: float
    p_transship: float
    pct_40ft: float

    # Capacities / resources (often the safest "knobs" for bounded agentic overrides).
    num_cranes: int
    yard_capacity: int
    yard_equipment_capacity: int
    num_scanners: int
    num_loaders: int
    num_gate_in: int
    num_gate_out: int

    # Service rates / processing times (drive queue service speed).
    crane_moves_per_hour: float
    scan_time_mins: float

    # Yard move time distribution + congestion sensitivity (rehandles increase with yard occupancy).
    yard_move_min: float
    yard_move_mode: float
    yard_move_max: float
    yard_occ_threshold: float
    rehandle_alpha: float

    # Loading time distribution (triangular parameters: min/mode/max).
    loading_time_min: float
    loading_time_mode: float
    loading_time_max: float

    # Gate in/out time distributions (triangular parameters: min/mode/max).
    gate_in_time_min: float
    gate_in_time_mode: float
    gate_in_time_max: float
    gate_out_time_min: float
    gate_out_time_mode: float
    gate_out_time_max: float

    # Dwell rules and offsets (how long different container types remain before they can move on).
    offset_after_discharge_mins: float
    import_dwell_bands: List[Tuple[float, float, float]]
    transship_dwell_bands: List[Tuple[float, float, float]]
    export_dwell_min: float
    export_dwell_max: float

    # Arrivals / demand drivers (typically treated as "fixed" in the Option B demo guardrails).
    ship_interarrival_mean_mins: float
    export_interarrival_mean_mins: float
    hourly_truck_teu_rate: List[float]
    truck_capacity_teu: int

    # ------------------------------------------------------------------------------------------------
    # ScenarioConfig.crane_time_mins
    # Purpose (simple): Convert a crane service rate (moves/hour) into minutes per move.
    # Loop stage(s): Observe / Re-run (used during simulation)
    # Inputs: `self.crane_moves_per_hour`
    # Outputs: Minutes per crane move (float)
    # Why it matters in the interview: Small rate changes here can have large downstream effects on
    # berth/vessel discharge pace, which then cascades into yard and gate congestion.
    # ------------------------------------------------------------------------------------------------
    @property
    def crane_time_mins(self) -> float:
        return 60.0 / max(self.crane_moves_per_hour, 1e-6)


# Stable list of scenario keys (kept in dataclass order) used for schema checks, metadata, and overrides.
SCENARIO_KEYS = tuple(ScenarioConfig.__dataclass_fields__.keys())  # pylint: disable=no-member


# ----------------------------------------------------------------------------------------------------
# scenario_to_dict
# Purpose (simple): Convert an immutable `ScenarioConfig` into a plain dict for storage and overrides.
# Loop stage(s): Observe / Re-run (shared config)
# Inputs: `config` (ScenarioConfig)
# Outputs: `dict` with keys matching `SCENARIO_KEYS`
# Why it matters in the interview: The orchestrator serializes this dict into `metadata.json`, and the
# agent loop later applies bounded overrides by updating this dict (not by mutating the dataclass).
# ----------------------------------------------------------------------------------------------------
def scenario_to_dict(config: ScenarioConfig) -> dict:
    return asdict(config)


# ----------------------------------------------------------------------------------------------------
# scenario_from_dict
# Purpose (simple): Re-hydrate a `ScenarioConfig` from a dict (the inverse of `scenario_to_dict`).
# Loop stage(s): Observe / Re-run (shared config)
# Inputs: `data` dict (expected to match the dataclass schema)
# Outputs: ScenarioConfig instance
# Why it matters in the interview: Makes configs portable between runs (e.g., load a config used in a
# prior run from `metadata.json`).
# ----------------------------------------------------------------------------------------------------
def scenario_from_dict(data: dict) -> ScenarioConfig:
    return ScenarioConfig(**data)


# ----------------------------------------------------------------------------------------------------
# _demo_base
# Purpose (simple): Define the baseline demo scenario (scaled timings + synthetic arrivals).
# Loop stage(s): Observe / Re-run (shared config)
# Inputs: None
# Outputs: ScenarioConfig named "baseline"
# Why it matters in the interview: This is the "known starting point" for the Option B demo loop — a
# small, deterministic, no-external-data scenario that still produces meaningful bottlenecks.
# ----------------------------------------------------------------------------------------------------
def _demo_base() -> ScenarioConfig:
    # Baseline demo scenario ("source of truth" for CLI demo runs).
    #
    # Agent-adjustable knobs in the Option B loop (safe, bounded overrides):
    # - num_cranes, num_scanners, num_loaders, yard_equipment_capacity, num_gate_in, num_gate_out
    #
    # Guardrails (kept fixed in this demo config):
    # - demand/arrivals (truck/ship interarrival rates), flow mix (import/export/transship), dwell rules,
    #   and data generation details. Those are intentionally not "agent knobs" in the interview demo.
    return ScenarioConfig(
        # Identity + demo flag (primarily for metadata/logging).
        name="baseline",
        description=(
            "Demo baseline scenario with scaled timings and synthetic arrivals. "
            "This does not use external datasets."
        ),
        demo=True,

        # Time horizon + dwell controls (how long we simulate + max time a container can stay in-system).
        sim_time_mins=8 * 60,
        max_dwell_mins=4 * 60,
        post_process_buffer_mins=2 * 60,

        # Flow mix + container mix (guardrailed: not changed by the Option B agent).
        p_import=0.6,
        p_export=0.2,
        p_transship=0.2,
        pct_40ft=0.3,

        # Capacities/resources (the Option B agent can adjust the marked integer "resource knobs").
        num_cranes=2,  # agent-adjustable
        yard_capacity=250,
        yard_equipment_capacity=5,  # agent-adjustable
        num_scanners=1,  # agent-adjustable
        num_loaders=2,  # agent-adjustable
        num_gate_in=1,  # agent-adjustable
        num_gate_out=1,  # agent-adjustable

        # Service rates / processing times (kept fixed for this bounded demo; influence queue service speed).
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

        # Dwell rules (guardrailed: treated as fixed distributions in the Option B demo).
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

        # Arrivals / demand drivers (guardrailed: the Option B agent does not change arrival rates).
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


# ----------------------------------------------------------------------------------------------------
# get_scenario
# Purpose (simple): Controlled entrypoint for selecting a curated demo scenario by name.
# Loop stage(s): Observe / Re-run (shared config)
# Inputs: `name` ("baseline" or "improved"), `demo` flag (CLI guard)
# Outputs: ScenarioConfig (baseline or a lightly modified "improved" variant)
# Why it matters in the interview: Keeps CLI demos bounded and repeatable; the "improved" variant is a
# small capacity bump used for quick comparisons.
# ----------------------------------------------------------------------------------------------------
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
            "Demo improved scenario with small capacity increases for comparison."
        ),
        num_scanners=base.num_scanners + 1,
        num_loaders=base.num_loaders + 1,
        yard_equipment_capacity=base.yard_equipment_capacity + 1,
        num_gate_out=base.num_gate_out + 1,
    )


# Interview "return to orchestrator" note:
# - After this module returns a ScenarioConfig (or dict), the Option B orchestrator passes it into
#   `run_simulation.run_demo(...)` and continues the loop with Diagnose → Decide → Apply → Compare.
