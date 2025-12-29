"""
Vessel/Berth layer (V1) for the Durban Port DES.

This module is intentionally small and student-friendly:
- Vessel generator produces berth calls with a simple interarrival process.
- Each vessel holds a berth for a service time derived from moves-per-call and SWH.
- At berth start, the vessel spawns a batch of container processes via a callback.
"""

from __future__ import annotations

import random
from typing import Callable, Dict, Optional, Tuple

import pandas as pd
import simpy

import vessel_params as vp


def build_berth_resources(env: simpy.Environment) -> Tuple[simpy.Resource, simpy.Resource]:
    """
    Create berth resources for Pier 1 and Pier 2.
    """
    berth_pier1 = simpy.Resource(env, capacity=vp.PIER1_BERTHS)
    berth_pier2 = simpy.Resource(env, capacity=vp.PIER2_BERTHS)
    return berth_pier1, berth_pier2


def select_pier(
    berth_pier1: simpy.Resource,
    berth_pier2: simpy.Resource,
) -> Tuple[str, simpy.Resource]:
    """
    Simple routing: pick the pier with lower congestion (queue + utilization proxy).
    """
    def score(resource: simpy.Resource) -> float:
        if resource.capacity <= 0:
            return float("inf")
        return len(resource.queue) + (resource.count / resource.capacity)

    score1 = score(berth_pier1)
    score2 = score(berth_pier2)
    if score1 <= score2:
        return "Pier 1", berth_pier1
    return "Pier 2", berth_pier2


def estimate_berth_service_minutes(
    pier_name: str,
    moves_per_call: float,
    include_marine_delays: bool = True,
) -> float:
    """
    Estimate berth service time from moves-per-call and pier productivity.
    """
    if pier_name == "Pier 1":
        moves_per_hour = vp.SWH_PIER1_MOVES_PER_HOUR
    else:
        moves_per_hour = vp.SWH_PIER2_MOVES_PER_HOUR

    service = (moves_per_call / max(moves_per_hour, 1e-6)) * 60.0
    if include_marine_delays:
        service += vp.PILOTAGE_AND_BERTHING_TIME_MINS + vp.SAILING_CLEARANCE_WINDOW_MINS
    return max(0.0, service)


def vessel_metrics_to_dataframe(metrics_list) -> pd.DataFrame:
    """
    Convert vessel metrics to a dataframe and derive safe waits.
    """
    if not metrics_list:
        return pd.DataFrame()

    df = pd.DataFrame(metrics_list)

    if "berth_start_time" in df.columns and "vessel_arrival_time" in df.columns:
        df["anchorage_wait"] = (df["berth_start_time"] - df["vessel_arrival_time"]).clip(lower=0)

    if "berth_end_time" in df.columns and "berth_start_time" in df.columns:
        df["berth_duration"] = (df["berth_end_time"] - df["berth_start_time"]).clip(lower=0)

    return df


def vessel_call_process(
    env: simpy.Environment,
    vessel_id: int,
    berth_pier1: simpy.Resource,
    berth_pier2: simpy.Resource,
    record_vessel_metrics: Callable[[Dict], None],
    spawn_container_fn: Callable[[int, int, str], None],
    flow_type_sampler: Optional[Callable[[], str]] = None,
    enable_anchorage_queue: bool = True,
    include_marine_delays: bool = True,
    moves_per_call: float = vp.AVG_MOVES_PER_CALL,
    teu_per_move: float = vp.TEU_PER_MOVE,
    import_share: Optional[float] = None,
) -> simpy.events.Event:
    """
    Simulate a single vessel call: queue for berth, hold berth, and spawn containers.
    """
    t: Dict[str, object] = {}
    t["vessel_id"] = vessel_id
    t["vessel_arrival_time"] = env.now

    pier_name, berth = select_pier(berth_pier1, berth_pier2)
    t["pier"] = pier_name

    moves_total = float(moves_per_call)
    t["moves_per_call"] = moves_total

    if import_share is None:
        containers_generated = int(round(moves_total))
    else:
        containers_generated = int(round(moves_total * import_share))
    containers_generated = max(1, containers_generated)

    t["containers_generated"] = containers_generated
    t["teu_per_move"] = teu_per_move
    t["teu_total"] = containers_generated * teu_per_move

    def _spawn_batch():
        for idx in range(containers_generated):
            flow_type = flow_type_sampler() if flow_type_sampler else "IMPORT"
            spawn_container_fn(vessel_id, idx, flow_type)

    if enable_anchorage_queue:
        with berth.request() as req:
            yield req
            t["berth_start_time"] = env.now
            t["anchorage_wait"] = max(0.0, t["berth_start_time"] - t["vessel_arrival_time"])
            _spawn_batch()
            service_minutes = estimate_berth_service_minutes(
                pier_name,
                moves_total,
                include_marine_delays=include_marine_delays,
            )
            t["berth_service_minutes"] = service_minutes
            yield env.timeout(service_minutes)
            t["berth_end_time"] = env.now
    else:
        # When queue is disabled, berth capacity is not enforced (optimistic scenario).
        t["berth_start_time"] = env.now
        t["anchorage_wait"] = 0.0
        _spawn_batch()
        service_minutes = estimate_berth_service_minutes(
            pier_name,
            moves_total,
            include_marine_delays=include_marine_delays,
        )
        t["berth_service_minutes"] = service_minutes
        yield env.timeout(service_minutes)
        t["berth_end_time"] = env.now

    record_vessel_metrics(t)


def vessel_arrival_generator(
    env: simpy.Environment,
    berth_pier1: simpy.Resource,
    berth_pier2: simpy.Resource,
    stop_time: float,
    record_vessel_metrics: Callable[[Dict], None],
    spawn_container_fn: Callable[[int, int, str], None],
    flow_type_sampler: Optional[Callable[[], str]] = None,
    enable_anchorage_queue: bool = True,
    include_marine_delays: bool = True,
    moves_per_call: float = vp.AVG_MOVES_PER_CALL,
    teu_per_move: float = vp.TEU_PER_MOVE,
    interarrival_mean: float = vp.VESSEL_INTERARRIVAL_MEAN_MINS,
    import_share: Optional[float] = None,
) -> simpy.events.Event:
    """
    Generate vessel calls until stop_time, then allow the system to drain.
    """
    vessel_id = 0
    while True:
        interarrival = random.expovariate(1 / interarrival_mean)
        yield env.timeout(interarrival)
        if env.now >= stop_time:
            break
        env.process(
            vessel_call_process(
                env,
                vessel_id,
                berth_pier1,
                berth_pier2,
                record_vessel_metrics,
                spawn_container_fn,
                flow_type_sampler=flow_type_sampler,
                enable_anchorage_queue=enable_anchorage_queue,
                include_marine_delays=include_marine_delays,
                moves_per_call=moves_per_call,
                teu_per_move=teu_per_move,
                import_share=import_share,
            )
        )
        vessel_id += 1
