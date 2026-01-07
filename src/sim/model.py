from __future__ import annotations

import random
from typing import Callable, List, Optional, Tuple

import numpy as np
import pandas as pd
import simpy

from .metrics import metrics_to_dataframe
from .scenarios import ScenarioConfig


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _sample_banded_dwell(bands: List[Tuple[float, float, float]]) -> float:
    r = random.random()
    cumulative = 0.0
    for start_mins, end_mins, prob in bands:
        cumulative += prob
        if r <= cumulative:
            return random.uniform(start_mins, end_mins)
    start_mins, end_mins, _ = bands[-1]
    return random.uniform(start_mins, end_mins)


def sample_import_dwell_minutes(config: ScenarioConfig) -> float:
    return config.offset_after_discharge_mins + _sample_banded_dwell(config.import_dwell_bands)


def sample_transship_dwell_minutes(config: ScenarioConfig) -> float:
    return _sample_banded_dwell(config.transship_dwell_bands)


def sample_export_dwell_minutes(config: ScenarioConfig) -> float:
    return random.uniform(config.export_dwell_min, config.export_dwell_max)


def sample_teu_size(config: ScenarioConfig) -> int:
    return 2 if random.random() < config.pct_40ft else 1


def sample_yard_move_time(config: ScenarioConfig, yard: simpy.Container) -> float:
    base = random.triangular(config.yard_move_min, config.yard_move_mode, config.yard_move_max)
    if config.yard_capacity <= 0:
        return max(0.0, base)
    occ = yard.level / config.yard_capacity
    occ = max(0.0, min(1.0, occ))
    if occ <= config.yard_occ_threshold:
        return max(0.0, base)
    denom = max(1e-6, (1.0 - config.yard_occ_threshold))
    penalty = 1.0 + config.rehandle_alpha * (occ - config.yard_occ_threshold) / denom
    return max(0.0, base * penalty)


def sample_loading_time(config: ScenarioConfig) -> float:
    return random.triangular(
        config.loading_time_min,
        config.loading_time_mode,
        config.loading_time_max,
    )


def sample_gate_in_time(config: ScenarioConfig) -> float:
    return random.triangular(
        config.gate_in_time_min,
        config.gate_in_time_mode,
        config.gate_in_time_max,
    )


def sample_gate_out_time(config: ScenarioConfig) -> float:
    return random.triangular(
        config.gate_out_time_min,
        config.gate_out_time_mode,
        config.gate_out_time_max,
    )


def sample_ship_flow_type(config: ScenarioConfig) -> str:
    total = config.p_import + config.p_transship
    if total <= 0:
        return "IMPORT"
    r = random.random() * total
    return "IMPORT" if r < config.p_import else "TRANSSHIP"


def select_containers_for_truck(env, ready_store, truck_capacity_teu: int):
    if not ready_store.items:
        first = yield ready_store.get()
        selected = [first]
        if truck_capacity_teu >= 2 and first.get("teu_size") == 1:
            if any(item.get("teu_size") == 1 for item in ready_store.items):
                second = yield ready_store.get(lambda x: x.get("teu_size") == 1)
                selected.append(second)
        return selected

    if truck_capacity_teu >= 2 and any(item.get("teu_size") == 2 for item in ready_store.items):
        c = yield ready_store.get(lambda x: x.get("teu_size") == 2)
        return [c]

    one_teu_count = sum(1 for item in ready_store.items if item.get("teu_size") == 1)
    if truck_capacity_teu >= 2 and one_teu_count >= 2:
        c1 = yield ready_store.get(lambda x: x.get("teu_size") == 1)
        c2 = yield ready_store.get(lambda x: x.get("teu_size") == 1)
        return [c1, c2]

    if one_teu_count == 1:
        c1 = yield ready_store.get(lambda x: x.get("teu_size") == 1)
        return [c1]

    c = yield ready_store.get()
    return [c]


def container_process(
    env,
    container_id: str,
    flow_type: str,
    config: ScenarioConfig,
    cranes,
    yard,
    yard_equipment,
    scanners,
    ready_store,
    loaders,
    record_container_metrics: Callable[[str, dict], None],
):
    t = {"arrival_time": env.now, "flow_type": flow_type}
    teu_size = sample_teu_size(config)
    t["teu_size"] = teu_size

    with cranes.request() as req:
        yield req
        t["crane_start"] = env.now
        yield env.timeout(config.crane_time_mins)
        t["crane_end"] = env.now

    yield yard.put(teu_size)
    t["yard_entry_time"] = env.now

    if flow_type == "IMPORT":
        dwell_delay = sample_import_dwell_minutes(config)
    elif flow_type == "TRANSSHIP":
        dwell_delay = sample_transship_dwell_minutes(config)
    else:
        dwell_delay = 0.0

    yield env.timeout(dwell_delay)
    t["pickup_request_time"] = env.now
    t["scanner_queue_len_at_pickup"] = len(scanners.queue)
    t["loader_queue_len_at_pickup"] = len(loaders.queue)
    t["yard_exit_time"] = env.now

    if flow_type == "IMPORT":
        t["yard_to_scan_queue_enter"] = env.now
        with yard_equipment.request() as req:
            yield req
            t["yard_to_scan_start"] = env.now
            t["occupancy_at_yard_to_scan"] = (
                yard.level / config.yard_capacity if config.yard_capacity > 0 else 0.0
            )
            yield env.timeout(sample_yard_move_time(config, yard))
            t["yard_to_scan_end"] = env.now

        t["scan_queue_enter"] = env.now
        with scanners.request() as req:
            yield req
            t["scan_start"] = env.now
            yield env.timeout(config.scan_time_mins)
            t["scan_end"] = env.now

        t["ready_time"] = env.now
        ready_item = {
            "container_id": container_id,
            "teu_size": teu_size,
            "flow_type": flow_type,
            "timestamps": t,
        }
        yield ready_store.put(ready_item)
        return

    t["yard_to_truck_queue_enter"] = env.now
    with yard_equipment.request() as req:
        yield req
        t["yard_to_truck_start"] = env.now
        t["occupancy_at_yard_to_truck"] = (
            yard.level / config.yard_capacity if config.yard_capacity > 0 else 0.0
        )
        yield env.timeout(sample_yard_move_time(config, yard))
        t["yard_to_truck_end"] = env.now

    if teu_size > 0:
        yield yard.get(teu_size)

    t["loading_queue_enter"] = env.now
    with loaders.request() as req:
        yield req
        t["loading_start"] = env.now
        yield env.timeout(sample_loading_time(config))
        t["loading_end"] = env.now

    t["exit_time"] = t["loading_end"]
    record_container_metrics(container_id, t)


def export_container_process(
    env,
    container_id: str,
    config: ScenarioConfig,
    yard,
    yard_equipment,
    loaders,
    gate_in,
    record_container_metrics: Callable[[str, dict], None],
):
    t = {"arrival_time": env.now, "flow_type": "EXPORT"}
    teu_size = sample_teu_size(config)
    t["teu_size"] = teu_size

    t["gate_in_queue_enter"] = env.now
    with gate_in.request() as req:
        yield req
        t["gate_in_start"] = env.now
        yield env.timeout(sample_gate_in_time(config))
        t["gate_in_end"] = env.now

    yield yard.put(teu_size)
    t["yard_entry_time"] = env.now

    dwell_delay = sample_export_dwell_minutes(config)
    yield env.timeout(dwell_delay)
    t["pickup_request_time"] = env.now
    t["yard_exit_time"] = env.now

    t["yard_to_truck_queue_enter"] = env.now
    with yard_equipment.request() as req:
        yield req
        t["yard_to_truck_start"] = env.now
        t["occupancy_at_yard_to_truck"] = (
            yard.level / config.yard_capacity if config.yard_capacity > 0 else 0.0
        )
        yield env.timeout(sample_yard_move_time(config, yard))
        t["yard_to_truck_end"] = env.now

    if teu_size > 0:
        yield yard.get(teu_size)

    t["loading_queue_enter"] = env.now
    with loaders.request() as req:
        yield req
        t["loading_start"] = env.now
        yield env.timeout(sample_loading_time(config))
        t["loading_end"] = env.now

    t["exit_time"] = t["loading_end"]
    record_container_metrics(container_id, t)


def truck_process(
    env,
    truck_id: int,
    config: ScenarioConfig,
    gate_in,
    ready_store,
    loaders,
    gate_out,
    yard,
    yard_equipment,
    record_container_metrics: Callable[[str, dict], None],
):
    tm = {"truck_id": truck_id}
    tm["gate_in_queue_enter"] = env.now

    with gate_in.request() as req:
        yield req
        tm["gate_in_start"] = env.now
        yield env.timeout(sample_gate_in_time(config))
        tm["gate_in_end"] = env.now

    tm["pickup_start"] = env.now
    containers = yield env.process(select_containers_for_truck(env, ready_store, config.truck_capacity_teu))
    tm["pickup_end"] = env.now

    picked_teu = sum(c.get("teu_size", 0) for c in containers)
    tm["picked_teu"] = picked_teu
    tm["picked_containers"] = len(containers)

    tm["yard_to_truck_queue_enter"] = env.now
    with yard_equipment.request() as req:
        yield req
        tm["yard_to_truck_start"] = env.now
        tm["occupancy_at_yard_to_truck"] = (
            yard.level / config.yard_capacity if config.yard_capacity > 0 else 0.0
        )
        yield env.timeout(sample_yard_move_time(config, yard))
        tm["yard_to_truck_end"] = env.now

    if picked_teu > 0:
        yield yard.get(picked_teu)

    tm["loading_queue_enter"] = env.now
    with loaders.request() as req:
        yield req
        tm["loading_start"] = env.now
        yield env.timeout(sample_loading_time(config))
        tm["loading_end"] = env.now

    tm["gate_out_queue_enter"] = env.now
    with gate_out.request() as req:
        yield req
        tm["gate_out_start"] = env.now
        yield env.timeout(sample_gate_out_time(config))
        tm["gate_out_end"] = env.now

    for c in containers:
        t = c.get("timestamps", {})
        t["gate_in_queue_enter"] = tm["gate_in_queue_enter"]
        t["gate_in_start"] = tm["gate_in_start"]
        t["gate_in_end"] = tm["gate_in_end"]
        t["pickup_time"] = tm["pickup_end"]
        t["yard_to_truck_queue_enter"] = tm["yard_to_truck_queue_enter"]
        t["yard_to_truck_start"] = tm["yard_to_truck_start"]
        t["yard_to_truck_end"] = tm["yard_to_truck_end"]
        t["occupancy_at_yard_to_truck"] = tm["occupancy_at_yard_to_truck"]
        t["loading_queue_enter"] = tm["loading_queue_enter"]
        t["loading_start"] = tm["loading_start"]
        t["loading_end"] = tm["loading_end"]
        t["gate_queue_enter"] = tm["gate_out_queue_enter"]
        t["gate_start"] = tm["gate_out_start"]
        t["gate_out_exit_time"] = tm["gate_out_end"]
        t["exit_time"] = tm["gate_out_end"]
        container_id = c.get("container_id")
        if container_id is not None:
            record_container_metrics(container_id, t)


def arrival_generator(
    env,
    config: ScenarioConfig,
    cranes,
    yard,
    yard_equipment,
    scanners,
    ready_store,
    loaders,
    stop_time: float,
    record_container_metrics: Callable[[str, dict], None],
):
    ship_total = config.p_import + config.p_transship
    if ship_total <= 0:
        return
    container_id = 0
    while True:
        interarrival = random.expovariate(1 / config.ship_interarrival_mean_mins)
        yield env.timeout(interarrival)
        if env.now >= stop_time:
            break
        flow_type = sample_ship_flow_type(config)
        label = f"S{container_id}"
        env.process(
            container_process(
                env,
                label,
                flow_type,
                config,
                cranes,
                yard,
                yard_equipment,
                scanners,
                ready_store,
                loaders,
                record_container_metrics,
            )
        )
        container_id += 1


def export_arrival_generator(
    env,
    config: ScenarioConfig,
    yard,
    yard_equipment,
    loaders,
    gate_in,
    stop_time: float,
    record_container_metrics: Callable[[str, dict], None],
):
    if config.p_export <= 0:
        return
    export_id = 0
    while True:
        interarrival = random.expovariate(1 / config.export_interarrival_mean_mins)
        yield env.timeout(interarrival)
        if env.now >= stop_time:
            break
        label = f"E{export_id}"
        env.process(
            export_container_process(
                env,
                label,
                config,
                yard,
                yard_equipment,
                loaders,
                gate_in,
                record_container_metrics,
            )
        )
        export_id += 1


def build_truck_teu_rate_fn(hourly_teu_rate: List[float]) -> Callable[[float], float]:
    if len(hourly_teu_rate) != 24:
        raise ValueError("hourly_truck_teu_rate must have 24 values.")

    def rate_fn(t_min: float) -> float:
        hour = int((t_min // 60) % 24)
        return float(hourly_teu_rate[hour])

    return rate_fn


def truck_arrival_generator(
    env,
    config: ScenarioConfig,
    gate_in,
    ready_store,
    loaders,
    gate_out,
    yard,
    yard_equipment,
    stop_time: float,
    record_container_metrics: Callable[[str, dict], None],
):
    truck_id = 0
    rate_fn = build_truck_teu_rate_fn(config.hourly_truck_teu_rate)
    while True:
        if env.now >= stop_time:
            break

        current_teu_rate = float(rate_fn(env.now))
        truck_rate_per_min = (current_teu_rate / config.truck_capacity_teu) / 60.0
        if truck_rate_per_min <= 0:
            wait_to_next_hour = 60 - (env.now % 60)
            yield env.timeout(wait_to_next_hour)
            continue

        interarrival = random.expovariate(truck_rate_per_min)
        yield env.timeout(interarrival)
        if env.now >= stop_time:
            break

        env.process(
            truck_process(
                env,
                truck_id,
                config,
                gate_in,
                ready_store,
                loaders,
                gate_out,
                yard,
                yard_equipment,
                record_container_metrics,
            )
        )
        truck_id += 1


def run_simulation(config: ScenarioConfig, seed: int) -> pd.DataFrame:
    set_seed(seed)

    metrics: List[dict] = []

    def record_container_metrics(container_id: str, timestamps: dict) -> None:
        metrics.append({"container_id": container_id, **timestamps})

    env = simpy.Environment()

    cranes = simpy.Resource(env, capacity=config.num_cranes)
    yard = simpy.Container(env, capacity=config.yard_capacity, init=0)
    yard_equipment = simpy.Resource(env, capacity=config.yard_equipment_capacity)
    scanners = simpy.Resource(env, capacity=config.num_scanners)
    loaders = simpy.Resource(env, capacity=config.num_loaders)
    gate_in = simpy.Resource(env, capacity=config.num_gate_in)
    gate_out = simpy.Resource(env, capacity=config.num_gate_out)
    ready_store = simpy.FilterStore(env)

    env.process(
        arrival_generator(
            env,
            config,
            cranes,
            yard,
            yard_equipment,
            scanners,
            ready_store,
            loaders,
            config.sim_time_mins,
            record_container_metrics,
        )
    )
    env.process(
        export_arrival_generator(
            env,
            config,
            yard,
            yard_equipment,
            loaders,
            gate_in,
            config.sim_time_mins,
            record_container_metrics,
        )
    )
    env.process(
        truck_arrival_generator(
            env,
            config,
            gate_in,
            ready_store,
            loaders,
            gate_out,
            yard,
            yard_equipment,
            config.sim_time_mins,
            record_container_metrics,
        )
    )

    run_until = config.sim_time_mins + config.max_dwell_mins + config.post_process_buffer_mins
    env.run(until=run_until)

    return metrics_to_dataframe(metrics)
