from __future__ import annotations

from typing import List

import pandas as pd


def _safe_diff(df: pd.DataFrame, new_col: str, end_col: str, start_col: str) -> None:
    if end_col in df.columns and start_col in df.columns:
        df[new_col] = (df[end_col] - df[start_col]).clip(lower=0)


def metrics_to_dataframe(metrics_list: List[dict]) -> pd.DataFrame:
    if not metrics_list:
        return pd.DataFrame()

    completed = [m for m in metrics_list if "exit_time" in m]
    if not completed:
        return pd.DataFrame()

    df = pd.DataFrame(completed)

    _safe_diff(df, "total_time", "exit_time", "arrival_time")
    _safe_diff(df, "yard_dwell", "yard_exit_time", "yard_entry_time")
    _safe_diff(df, "dwell_terminal", "exit_time", "yard_entry_time")

    _safe_diff(df, "scan_wait", "scan_start", "scan_queue_enter")
    _safe_diff(df, "yard_to_scan_wait", "yard_to_scan_start", "yard_to_scan_queue_enter")
    _safe_diff(df, "yard_to_truck_wait", "yard_to_truck_start", "yard_to_truck_queue_enter")
    _safe_diff(df, "ready_to_pickup_wait", "pickup_time", "ready_time")
    _safe_diff(df, "loading_wait", "loading_start", "loading_queue_enter")
    _safe_diff(df, "gate_wait", "gate_start", "gate_queue_enter")

    _safe_diff(df, "pre_pickup_wait", "pickup_request_time", "yard_entry_time")

    if "yard_to_scan_wait" in df.columns or "yard_to_truck_wait" in df.columns:
        df["yard_equipment_wait"] = 0.0
        if "yard_to_scan_wait" in df.columns:
            df["yard_equipment_wait"] += df["yard_to_scan_wait"].fillna(0)
        if "yard_to_truck_wait" in df.columns:
            df["yard_equipment_wait"] += df["yard_to_truck_wait"].fillna(0)

    if "dwell_terminal" in df.columns:
        df["dwell_terminal_days"] = df["dwell_terminal"] / 1440.0
    if "pre_pickup_wait" in df.columns:
        df["pre_pickup_wait_hours"] = df["pre_pickup_wait"] / 60.0

    return df
