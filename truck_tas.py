from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple, Any
import math
import random

import numpy as np


@dataclass(frozen=True)
class TruckTASParams:
    """
    Parameter bundle for the Truck Arrival + TAS layer.

    Values should be set in the notebook with SOURCE-ANCHORED vs ASSUMPTION
    notes. The fields here are intentionally explicit to keep the model
    auditable and easy to tune.
    """

    trucks_per_day: float
    hourly_arrival_multipliers: List[float]
    slot_minutes: int = 60
    late_tolerance_mins: int = 30
    no_show_prob: float = 0.22
    rebook_delay_mean_mins: float = 360.0
    rebook_delay_sigma_mins: float = 120.0
    arrival_std_mins: float = 15.0


def validate_hourly_multipliers(multipliers: Sequence[float]) -> None:
    """
    Ensure the hourly multipliers describe a 24-hour profile that sums to 24.

    This normalization lets us interpret the list as "mean 1.0" hourly weights,
    which keeps the daily total consistent.
    """
    if len(multipliers) != 24:
        raise ValueError("HOURLY_ARRIVAL_MULTIPLIERS must have 24 values.")

    total = float(sum(multipliers))
    if not math.isclose(total, 24.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("HOURLY_ARRIVAL_MULTIPLIERS must sum to 24.0.")


def _lognormal_mu_sigma(mean: float, sigma: float) -> Tuple[float, float]:
    """
    Convert lognormal mean/sigma into the underlying normal mu/sigma.
    This is needed for random.lognormvariate.
    """
    variance = sigma ** 2
    mu = math.log((mean ** 2) / math.sqrt(variance + mean ** 2))
    sigma_ln = math.sqrt(math.log(1 + variance / (mean ** 2)))
    return mu, sigma_ln


def sample_rebook_delay_minutes(params: TruckTASParams, rng: random.Random) -> float:
    """
    Sample a missed-slot rebook delay using a lognormal distribution.
    """
    mu, sigma = _lognormal_mu_sigma(params.rebook_delay_mean_mins, params.rebook_delay_sigma_mins)
    return rng.lognormvariate(mu, sigma)


def next_slot_start(t_min: float, slot_minutes: int) -> float:
    """
    Align a time (in minutes) to the next slot boundary.
    """
    return math.ceil(t_min / float(slot_minutes)) * float(slot_minutes)


def sample_nhpp_slot_times(
    sim_time_mins: float,
    params: TruckTASParams,
    np_rng: Optional[np.random.Generator] = None,
) -> List[float]:
    """
    Generate slot booking times using an NHPP with hourly piecewise rates.

    The NHPP is implemented by sampling a Poisson count within each hour and
    placing those bookings uniformly within the hour.
    """
    validate_hourly_multipliers(params.hourly_arrival_multipliers)
    np_rng = np_rng or np.random.default_rng()

    total_hours = int(math.ceil(sim_time_mins / 60.0))
    slot_times: List[float] = []

    for hour in range(total_hours):
        hourly_rate = (params.trucks_per_day / 24.0) * params.hourly_arrival_multipliers[hour % 24]
        count = int(np_rng.poisson(hourly_rate))
        if count <= 0:
            continue
        offsets = np_rng.random(count) * 60.0
        for offset in offsets:
            slot_times.append((hour * 60.0) + float(offset))

    slot_times.sort()
    return slot_times


def build_tas_arrival_schedule(
    sim_time_mins: float,
    params: TruckTASParams,
    rng: Optional[random.Random] = None,
    np_rng: Optional[np.random.Generator] = None,
    max_attempts: int = 10000,
) -> List[Tuple[float, float, int]]:
    """
    Resolve slot bookings into actual arrivals.

    Returns a list of tuples:
        (arrival_time, slot_start, missed_slot_count)
    """
    rng = rng or random.Random()
    slot_times = sample_nhpp_slot_times(sim_time_mins, params, np_rng=np_rng)
    schedule: List[Tuple[float, float, int]] = []

    for slot_start in slot_times:
        missed = 0
        attempts = 0

        while True:
            attempts += 1
            if attempts > max_attempts:
                break

            # No-show leads to rebook.
            if rng.random() < params.no_show_prob:
                missed += 1
                slot_start = next_slot_start(
                    slot_start + sample_rebook_delay_minutes(params, rng),
                    params.slot_minutes,
                )
                continue

            # Arrival deviation around the booked slot (ASSUMPTION TO TUNE).
            arrival = slot_start + rng.normalvariate(0.0, params.arrival_std_mins)
            arrival = max(arrival, 0.0)

            # Late arrivals beyond tolerance are treated as missed slots.
            if arrival > slot_start + params.slot_minutes + params.late_tolerance_mins:
                missed += 1
                slot_start = next_slot_start(
                    arrival + sample_rebook_delay_minutes(params, rng),
                    params.slot_minutes,
                )
                continue

            schedule.append((arrival, slot_start, missed))
            break

    schedule.sort(key=lambda x: x[0])
    return schedule


def _claim_ready_containers(
    env,
    ready_store,
    select_containers_fn: Optional[Callable[..., Any]],
):
    """
    Pull ready containers from the store using an optional selection policy.
    """
    if select_containers_fn is None:
        item = yield ready_store.get()
        return [item]

    return (yield env.process(select_containers_fn(env, ready_store)))


def _container_teu(item: Any) -> int:
    """
    Extract TEU size from a ready-store item, defaulting to 1 TEU.
    """
    if isinstance(item, dict) and "teu_size" in item:
        try:
            return int(item["teu_size"])
        except (TypeError, ValueError):
            return 1
    return 1


def truck_process_tas(
    env,
    truck_id: int,
    slot_start: float,
    missed_slot_count: int,
    gate_in,
    ready_store,
    loaders,
    gate_out,
    yard,
    record_truck_metrics: Callable[[int, dict], None],
    select_containers_fn: Optional[Callable[..., Any]] = None,
    gate_in_time_fn: Optional[Callable[[], float]] = None,
    gate_out_time_fn: Optional[Callable[[], float]] = None,
    pickup_service_time_fn: Optional[Callable[[], float]] = None,
    record_container_metrics: Optional[Callable[[int, dict], None]] = None,
):
    """
    Truck state machine with TAS validation and pickup flow.

    ARRIVE -> VALIDATE_SLOT -> (STAGING_WAIT) -> GATE_IN_QUEUE -> GATE_IN_SERVICE
    -> WAIT_FOR_READY_CONTAINER -> YARD_PICKUP_SERVICE -> GATE_OUT_SERVICE -> EXIT
    """
    tm = {
        "t_slot_start": slot_start,
        "missed_slot_count": missed_slot_count,
    }

    tm["t_precinct_arrival"] = env.now

    # Early arrivals wait in staging until their slot starts.
    if env.now < slot_start:
        yield env.timeout(slot_start - env.now)

    tm["t_gate_in_queue_enter"] = env.now

    with gate_in.request() as req:
        yield req
        tm["t_gate_in_start"] = env.now
        if gate_in_time_fn:
            yield env.timeout(gate_in_time_fn())
        tm["t_gate_in_end"] = env.now

    # Yard entry is the end of gate-in service.
    tm["t_yard_entry"] = tm["t_gate_in_end"]

    # Wait for ready containers to be claimed.
    containers = yield env.process(_claim_ready_containers(env, ready_store, select_containers_fn))
    tm["t_ready_claim_time"] = env.now

    # Pickup service (reuse loading resource).
    tm["t_pickup_queue_enter"] = env.now
    with loaders.request() as req:
        yield req
        tm["t_pickup_start"] = env.now
        if pickup_service_time_fn:
            yield env.timeout(pickup_service_time_fn())
        tm["t_pickup_end"] = env.now

    picked_teu = sum(_container_teu(c) for c in containers)
    tm["picked_teu"] = picked_teu
    tm["picked_containers"] = len(containers)

    # Release yard capacity when containers leave.
    if picked_teu > 0:
        yield yard.get(picked_teu)

    tm["t_gate_out_queue_enter"] = env.now
    with gate_out.request() as req:
        yield req
        tm["t_gate_out_start"] = env.now
        if gate_out_time_fn:
            yield env.timeout(gate_out_time_fn())
        tm["t_gate_out_end"] = env.now

    tm["t_exit"] = tm["t_gate_out_end"]
    record_truck_metrics(truck_id, tm)

    # Optional: update container-level metrics if timestamps are provided.
    if record_container_metrics:
        for c in containers:
            if not isinstance(c, dict):
                continue
            t = c.get("timestamps")
            if not isinstance(t, dict):
                continue
            container_id = c.get("container_id")
            t["pickup_time"] = tm["t_ready_claim_time"]
            t["loading_queue_enter"] = tm["t_ready_claim_time"]
            t["loading_start"] = tm["t_pickup_start"]
            t["loading_end"] = tm["t_pickup_end"]
            t["gate_queue_enter"] = tm["t_gate_out_queue_enter"]
            t["gate_start"] = tm["t_gate_out_start"]
            t["gate_out_exit_time"] = tm["t_exit"]
            t["exit_time"] = tm["t_exit"]
            if container_id is not None:
                record_container_metrics(container_id, t)


def truck_tas_arrival_generator(
    env,
    params: TruckTASParams,
    ready_store,
    gate_in,
    loaders,
    gate_out,
    yard,
    stop_time: float,
    record_truck_metrics: Callable[[int, dict], None],
    select_containers_fn: Optional[Callable[..., Any]] = None,
    gate_in_time_fn: Optional[Callable[[], float]] = None,
    gate_out_time_fn: Optional[Callable[[], float]] = None,
    pickup_service_time_fn: Optional[Callable[[], float]] = None,
    record_container_metrics: Optional[Callable[[int, dict], None]] = None,
    rng: Optional[random.Random] = None,
    np_rng: Optional[np.random.Generator] = None,
):
    """
    Generate trucks with TAS slots and independent NHPP arrivals.

    The arrival schedule is precomputed so rebooked trucks do not block
    later arrivals.
    """
    rng = rng or random.Random()
    schedule = build_tas_arrival_schedule(
        stop_time,
        params,
        rng=rng,
        np_rng=np_rng,
    )

    truck_id = 0
    for arrival_time, slot_start, missed in schedule:
        wait = max(0.0, arrival_time - env.now)
        if wait > 0:
            yield env.timeout(wait)
        env.process(
            truck_process_tas(
                env,
                truck_id,
                slot_start,
                missed,
                gate_in,
                ready_store,
                loaders,
                gate_out,
                yard,
                record_truck_metrics,
                select_containers_fn=select_containers_fn,
                gate_in_time_fn=gate_in_time_fn,
                gate_out_time_fn=gate_out_time_fn,
                pickup_service_time_fn=pickup_service_time_fn,
                record_container_metrics=record_container_metrics,
            )
        )
        truck_id += 1
