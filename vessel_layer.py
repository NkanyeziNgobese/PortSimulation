"""
Vessel/Berth layer (Phase 2) for the Durban Port DES.

This module stays student-friendly but adds gang assignment and crane pools:
- Vessel generator produces berth calls with a simple interarrival process.
- Each vessel requests a berth and a variable number of cranes (gang intensity).
- Discharge releases containers to yard at a rate based on GCH * cranes * efficiency.
- Berth time includes pilotage/sailing delays and shift-change hook losses.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

import pandas as pd
import simpy

import vessel_params as vp


@dataclass
class CranePoolStats:
    """
    Track how long a crane pool sits empty (minutes).
    """
    name: str
    empty_minutes: float = 0.0
    last_time: float = 0.0
    last_empty: bool = False

    def update(self, env: simpy.Environment, crane_pool: simpy.Container) -> None:
        now = env.now
        elapsed = max(0.0, now - self.last_time)
        if self.last_empty:
            self.empty_minutes += elapsed
        self.last_time = now
        self.last_empty = crane_pool.level <= 0

    def empty_ratio(self, sim_time: float) -> float:
        if sim_time <= 0:
            return 0.0
        empty_minutes = self.empty_minutes
        if self.last_empty and sim_time > self.last_time:
            empty_minutes += sim_time - self.last_time
        return empty_minutes / sim_time


def build_berth_resources(env: simpy.Environment) -> Tuple[simpy.Resource, simpy.Resource]:
    """
    Create berth resources for Pier 1 and Pier 2.
    """
    berth_pier1 = simpy.Resource(env, capacity=vp.PIER1_BERTHS)
    berth_pier2 = simpy.Resource(env, capacity=vp.PIER2_BERTHS)
    return berth_pier1, berth_pier2


def build_quayside_resources(
    env: simpy.Environment,
) -> Tuple[simpy.Resource, simpy.Resource, simpy.Container, simpy.Container, CranePoolStats, CranePoolStats]:
    """
    Create berth resources and crane pools for Pier 1 and Pier 2.
    Crane pools use simpy.Container so a vessel can request multiple cranes at once.
    """
    berth_pier1, berth_pier2 = build_berth_resources(env)
    crane_pool_pier1 = simpy.Container(env, capacity=vp.PIER1_CRANE_POOL, init=vp.PIER1_CRANE_POOL)
    crane_pool_pier2 = simpy.Container(env, capacity=vp.PIER2_CRANE_POOL, init=vp.PIER2_CRANE_POOL)
    crane_stats_pier1 = CranePoolStats(name="Pier 1")
    crane_stats_pier2 = CranePoolStats(name="Pier 2")
    crane_stats_pier1.update(env, crane_pool_pier1)
    crane_stats_pier2.update(env, crane_pool_pier2)
    return (
        berth_pier1,
        berth_pier2,
        crane_pool_pier1,
        crane_pool_pier2,
        crane_stats_pier1,
        crane_stats_pier2,
    )


def _sample_from_distribution(dist: Dict[int, float]) -> int:
    r = random.random()
    cumulative = 0.0
    for cranes in sorted(dist.keys()):
        cumulative += dist[cranes]
        if r <= cumulative:
            return cranes
    return max(dist.keys())


def sample_pier1_gang() -> int:
    """
    Sample cranes for Pier 1 from a discrete distribution.
    """
    return _sample_from_distribution(vp.PIER1_GANG_DISTRIBUTION)


def sample_pier2_gang() -> int:
    """
    Sample cranes for Pier 2 from a triangular distribution.
    """
    min_c, mode_c, max_c = vp.PIER2_GANG_TRIANGULAR
    value = random.triangular(min_c, max_c, mode_c)
    return int(max(min(round(value), max_c), min_c))


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


def _effective_moves_per_hour(cranes_assigned: int, efficiency_factor: float) -> float:
    """
    Effective discharge rate (moves/hour) for the assigned gang.
    """
    base_rate = cranes_assigned * vp.GCH_MOVES_PER_HOUR
    work_factor = max(vp.NET_EFFECTIVE_WORK_FACTOR, 1e-6)
    return base_rate * max(efficiency_factor, 1e-6) * work_factor


def estimate_discharge_minutes(
    moves_per_call: float,
    cranes_assigned: int,
    efficiency_factor: float,
) -> float:
    """
    Estimate discharge time (minutes) using GCH rate * cranes * efficiency.
    """
    rate = _effective_moves_per_hour(cranes_assigned, efficiency_factor)
    if rate <= 0:
        return 0.0
    return (moves_per_call / rate) * 60.0


def estimate_shift_loss_minutes(
    discharge_minutes: float,
    cranes_assigned: int,
) -> float:
    """
    Approximate shift-change hook loss as an added downtime block.
    This is an MVP approximation to avoid per-container pause logic.
    """
    shifts_crossed = int(discharge_minutes // vp.SHIFT_LENGTH_MINS)
    if shifts_crossed <= 0:
        return 0.0
    total = 0.0
    for _ in range(shifts_crossed):
        hook = random.uniform(vp.SHIFT_CHANGE_HOOK_TIME_MIN, vp.SHIFT_CHANGE_HOOK_TIME_MAX)
        total += hook * cranes_assigned
    return total


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

    if "berth_duration" in df.columns and "moves_per_call" in df.columns:
        hours = (df["berth_duration"] / 60.0).replace(0, pd.NA)
        df["effective_swh"] = df["moves_per_call"] / hours

    return df


def _allocate_cranes(
    env: simpy.Environment,
    crane_pool: Optional[simpy.Container],
    crane_stats: Optional[CranePoolStats],
    cranes_requested: int,
    min_cranes: int,
) -> simpy.events.Event:
    """
    Allocate cranes from a shared pool with a minimum gang size guard.
    """
    if crane_pool is None:
        return cranes_requested, 0.0

    wait_start = env.now
    if crane_pool.level < min_cranes:
        yield crane_pool.get(min_cranes)
        cranes_assigned = min_cranes
    else:
        available = int(crane_pool.level)
        cranes_assigned = max(min(cranes_requested, available), min_cranes)
        yield crane_pool.get(cranes_assigned)

    if crane_stats is not None:
        crane_stats.update(env, crane_pool)
    crane_wait = max(0.0, env.now - wait_start)
    return cranes_assigned, crane_wait


def _release_cranes(
    env: simpy.Environment,
    crane_pool: Optional[simpy.Container],
    crane_stats: Optional[CranePoolStats],
    cranes_assigned: int,
) -> simpy.events.Event:
    """
    Return cranes to the shared pool.
    """
    if crane_pool is None:
        return
    yield crane_pool.put(cranes_assigned)
    if crane_stats is not None:
        crane_stats.update(env, crane_pool)


def vessel_call_process(
    env: simpy.Environment,
    vessel_id: int,
    berth_pier1: simpy.Resource,
    berth_pier2: simpy.Resource,
    record_vessel_metrics: Callable[[Dict], None],
    spawn_container_fn: Callable[[int, int, str], None],
    crane_pool_pier1: Optional[simpy.Container] = None,
    crane_pool_pier2: Optional[simpy.Container] = None,
    crane_stats_pier1: Optional[CranePoolStats] = None,
    crane_stats_pier2: Optional[CranePoolStats] = None,
    flow_type_sampler: Optional[Callable[[], str]] = None,
    enable_anchorage_queue: bool = True,
    include_marine_delays: bool = True,
    moves_per_call: float = vp.AVG_MOVES_PER_CALL,
    teu_per_move: float = vp.TEU_PER_MOVE,
    import_share: Optional[float] = None,
) -> simpy.events.Event:
    """
    Simulate a single vessel call: queue for berth, assign cranes, discharge, and spawn containers.
    Shift downtime is approximated via net-effective work factor + hook-loss minutes.
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
    t["teu_total"] = moves_total * teu_per_move
    t["teu_generated"] = containers_generated * teu_per_move
    t["notes"] = "shift loss aggregated as added downtime (MVP)"

    if pier_name == "Pier 1":
        crane_pool = crane_pool_pier1
        crane_stats = crane_stats_pier1
        efficiency_factor = vp.PIER1_EFFICIENCY_FACTOR
        cranes_requested = sample_pier1_gang()
    else:
        crane_pool = crane_pool_pier2
        crane_stats = crane_stats_pier2
        efficiency_factor = vp.PIER2_EFFICIENCY_FACTOR
        cranes_requested = sample_pier2_gang()

    cranes_requested = max(cranes_requested, vp.MIN_CRANES_PER_VESSEL)

    if enable_anchorage_queue:
        with berth.request() as req:
            yield req
            t["berth_start_time"] = env.now
            t["anchorage_wait"] = max(0.0, t["berth_start_time"] - t["vessel_arrival_time"])
            cranes_assigned, crane_wait = yield env.process(
                _allocate_cranes(
                    env,
                    crane_pool,
                    crane_stats,
                    cranes_requested,
                    vp.MIN_CRANES_PER_VESSEL,
                )
            )
            t["cranes_requested"] = cranes_requested
            t["cranes_assigned"] = cranes_assigned
            t["crane_wait"] = crane_wait
            t["efficiency_factor_used"] = efficiency_factor

            effective_rate = _effective_moves_per_hour(cranes_assigned, efficiency_factor)
            t["effective_rate_mph"] = effective_rate
            inter_release_minutes = 60.0 / max(effective_rate, 1e-6)
            t["inter_release_minutes"] = inter_release_minutes

            # Discharge minutes use GCH * cranes * efficiency and apply net-effective work factor.
            discharge_minutes = estimate_discharge_minutes(moves_total, cranes_assigned, efficiency_factor)
            # Shift-change hook loss is added as a single downtime block (MVP approximation).
            shift_loss = estimate_shift_loss_minutes(discharge_minutes, cranes_assigned)
            t["shift_loss_minutes_applied"] = shift_loss

            service_minutes = discharge_minutes + shift_loss
            if include_marine_delays:
                service_minutes += (
                    vp.PILOTAGE_AND_BERTHING_TIME_MINS + vp.SAILING_CLEARANCE_WINDOW_MINS
                )
            t["berth_service_minutes"] = max(0.0, service_minutes)

            release_minutes = containers_generated * inter_release_minutes
            for idx in range(containers_generated):
                yield env.timeout(inter_release_minutes)
                flow_type = flow_type_sampler() if flow_type_sampler else "IMPORT"
                spawn_container_fn(vessel_id, idx, flow_type)

            remaining = max(0.0, service_minutes - release_minutes)
            if remaining:
                yield env.timeout(remaining)
            yield env.process(_release_cranes(env, crane_pool, crane_stats, cranes_assigned))
            t["berth_end_time"] = env.now
    else:
        # When queue is disabled, berth capacity is not enforced (optimistic scenario).
        t["berth_start_time"] = env.now
        t["anchorage_wait"] = 0.0
        cranes_assigned, crane_wait = yield env.process(
            _allocate_cranes(
                env,
                crane_pool,
                crane_stats,
                cranes_requested,
                vp.MIN_CRANES_PER_VESSEL,
            )
        )
        t["cranes_requested"] = cranes_requested
        t["cranes_assigned"] = cranes_assigned
        t["crane_wait"] = crane_wait
        t["efficiency_factor_used"] = efficiency_factor

        effective_rate = _effective_moves_per_hour(cranes_assigned, efficiency_factor)
        t["effective_rate_mph"] = effective_rate
        inter_release_minutes = 60.0 / max(effective_rate, 1e-6)
        t["inter_release_minutes"] = inter_release_minutes

        # Discharge minutes use GCH * cranes * efficiency and apply net-effective work factor.
        discharge_minutes = estimate_discharge_minutes(moves_total, cranes_assigned, efficiency_factor)
        # Shift-change hook loss is added as a single downtime block (MVP approximation).
        shift_loss = estimate_shift_loss_minutes(discharge_minutes, cranes_assigned)
        t["shift_loss_minutes_applied"] = shift_loss

        service_minutes = discharge_minutes + shift_loss
        if include_marine_delays:
            service_minutes += vp.PILOTAGE_AND_BERTHING_TIME_MINS + vp.SAILING_CLEARANCE_WINDOW_MINS
        t["berth_service_minutes"] = max(0.0, service_minutes)

        release_minutes = containers_generated * inter_release_minutes
        for idx in range(containers_generated):
            yield env.timeout(inter_release_minutes)
            flow_type = flow_type_sampler() if flow_type_sampler else "IMPORT"
            spawn_container_fn(vessel_id, idx, flow_type)

        remaining = max(0.0, service_minutes - release_minutes)
        if remaining:
            yield env.timeout(remaining)
        yield env.process(_release_cranes(env, crane_pool, crane_stats, cranes_assigned))
        t["berth_end_time"] = env.now

    record_vessel_metrics(t)


def vessel_arrival_generator(
    env: simpy.Environment,
    berth_pier1: simpy.Resource,
    berth_pier2: simpy.Resource,
    stop_time: float,
    record_vessel_metrics: Callable[[Dict], None],
    spawn_container_fn: Callable[[int, int, str], None],
    crane_pool_pier1: Optional[simpy.Container] = None,
    crane_pool_pier2: Optional[simpy.Container] = None,
    crane_stats_pier1: Optional[CranePoolStats] = None,
    crane_stats_pier2: Optional[CranePoolStats] = None,
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
                crane_pool_pier1=crane_pool_pier1,
                crane_pool_pier2=crane_pool_pier2,
                crane_stats_pier1=crane_stats_pier1,
                crane_stats_pier2=crane_stats_pier2,
                flow_type_sampler=flow_type_sampler,
                enable_anchorage_queue=enable_anchorage_queue,
                include_marine_delays=include_marine_delays,
                moves_per_call=moves_per_call,
                teu_per_move=teu_per_move,
                import_share=import_share,
            )
        )
        vessel_id += 1
