"""Associate LTE events with nearby recorded GPS observations.

These are temporal associations, not payload ownership or solved positions.
Offset is GPS observation time minus LTE event time, in seconds. Upload
receipts retain their server clock basis; they are not renamed as attempts.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .loaders import DeviceData


MATCH_COLUMNS = [
    "event_id", "device_id", "event_type", "event_time", "event_outcome",
    "clock_basis", "gps_obs_id", "gps_time", "offset_s",
    "previous_gps_time", "next_gps_time", "bracket_gap_s", "within_window",
    "gps_overlap", "match_status", "gps_ttf_s", "gps_num_sv", "gps_cnr",
    "gps_voltage_v", "event_rsrp_dbm", "event_duration_s", "match_reason",
    "gps_clock_record", "gps_marker_kind", "receipt_evidence",
]

_TIME_COLUMNS = [
    "event_time", "gps_time", "previous_gps_time", "next_gps_time",
]
_NUMERIC_COLUMNS = [
    "offset_s", "bracket_gap_s", "gps_ttf_s", "gps_num_sv", "gps_cnr",
    "gps_voltage_v", "event_rsrp_dbm", "event_duration_s",
]


def _number(value) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if np.isfinite(result) else np.nan


def _time(value) -> pd.Timestamp:
    if value is None or pd.isna(value):
        return pd.NaT
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise ValueError("Event matching requires timezone-aware normalized times")
    return result.tz_convert("UTC")


def _post_outcome(value) -> str:
    number = _number(value)
    return {1: "success", 0: "failure"}.get(number, "unknown")


def _events(device: DeviceData) -> list[dict]:
    events = []
    for event_type, frame, clock_basis in (
        ("registration", device.registrations, "device"),
        ("upload_failure", device.failures, "device"),
        ("upload_receipt", device.uploads, "server_receipt"),
    ):
        for ordinal, (_, row) in enumerate(frame.iterrows(), 2):
            source_row = row.get("source_row", ordinal)
            if pd.isna(source_row):
                source_row = ordinal
            if isinstance(source_row, (float, np.floating)) and source_row.is_integer():
                source_row = int(source_row)
            if event_type == "registration":
                outcome = str(row.get("outcome", "unknown")).lower()
                duration = _number(row.get("duration_s"))
            else:
                outcome = "received" if event_type == "upload_receipt" else _post_outcome(row.get("post_ok"))
                phases = [_number(row.get(name)) for name in ("connect_s", "send_s", "ttfb_s")]
                # This is the sum of the three exported phases, not total modem on-time.
                duration = sum(phases) if all(np.isfinite(v) and v >= 0 for v in phases) else np.nan
            events.append({
                "event_id": f"{device.device_id}:{event_type}:{source_row}",
                "device_id": str(device.device_id),
                "event_type": event_type,
                "event_time": _time(row.get("time")),
                "event_outcome": outcome,
                "clock_basis": clock_basis,
                "receipt_evidence": "received" if event_type == "upload_receipt" else row.get("receipt_match_status", "not_applicable"),
                "event_rsrp_dbm": _number(row.get("rsrp_dbm")),
                "event_duration_s": duration,
            })
    return events


def build_event_matches(device: DeviceData, tolerance_seconds: float = 60) -> pd.DataFrame:
    """Return one association record for every LTE row, including untimed rows.

    Ties choose the earlier GPS observation. Before/after times are inclusive
    of an exact timestamp. GPS rows flagged as clock anomalies are excluded.
    If the event is near two overlapping clock segments, no observation is
    selected: the association is ambiguous. No records are deduplicated here.
    Acquisition overlap concerns any valid GPS start/end interval in the
    unambiguous eligible clock segment, independently of the nearest endpoint.
    """
    if not np.isfinite(tolerance_seconds) or tolerance_seconds < 0:
        raise ValueError("GPS matching tolerance must be finite and nonnegative")

    gps = device.gps.copy()
    if not gps.empty:
        valid = gps["time"].notna()
        if "clock_anomaly" in gps:
            valid &= ~gps["clock_anomaly"].fillna(False).astype(bool)
        gps = gps.loc[valid].copy()
    if "clock_segment" not in gps:
        gps["clock_segment"] = 0
    gps["clock_segment"] = gps["clock_segment"].fillna(0)
    gps = gps.sort_values("time", kind="stable").reset_index(drop=True)
    # Timestamp.value is explicitly nanoseconds; DatetimeIndex.asi8 can use
    # microseconds in pandas 3 depending on the input unit.
    gps_ns = [int(_time(value).value) for value in gps["time"]]
    tolerance_ns = int(round(float(tolerance_seconds) * 1_000_000_000))
    spans = []
    acquisitions = {}
    for segment, group in gps.groupby("clock_segment", sort=False):
        times = [_time(value).value for value in group["time"]]
        spans.append((segment, min(times), max(times)))
        intervals = []
        for start_value, end_value in zip(group["start_time"], group["time"]):
            start_time, end_time = _time(start_value), _time(end_value)
            if pd.notna(start_time) and start_time <= end_time:
                intervals.append((int(start_time.value), int(end_time.value)))
        intervals.sort()
        if intervals:
            starts = [start for start, _ in intervals]
            # Prefix maxima answer interval containment without scanning every
            # acquisition for every event, including overlapping acquisitions.
            latest_ends = np.maximum.accumulate([end for _, end in intervals]).tolist()
            acquisitions[segment] = (starts, latest_ends)

    records = []
    for event in _events(device):
        record = dict(event)
        record.update({
            "gps_obs_id": None, "gps_time": pd.NaT, "offset_s": np.nan,
            "previous_gps_time": pd.NaT, "next_gps_time": pd.NaT,
            "bracket_gap_s": np.nan, "within_window": False,
            "gps_overlap": False, "match_status": "no_gps",
            "gps_ttf_s": np.nan, "gps_num_sv": np.nan,
            "gps_cnr": np.nan, "gps_voltage_v": np.nan,
            "match_reason": "No usable GPS observation",
            "gps_clock_record": False, "gps_marker_kind": None,
        })
        when = event["event_time"]
        if pd.isna(when):
            record.update(match_status="untimed", match_reason="No absolute event timestamp")
        elif gps_ns:
            event_ns = int(when.value)
            plausible_segments = [
                segment for segment, first, last in spans
                if first - tolerance_ns <= event_ns <= last + tolerance_ns
            ]
            overlap_segments = []
            for segment, (starts, latest_ends) in acquisitions.items():
                previous_start = bisect_right(starts, event_ns) - 1
                if previous_start >= 0 and latest_ends[previous_start] >= event_ns:
                    overlap_segments.append(segment)
            plausible_segments = set(plausible_segments).union(overlap_segments)
            if len(plausible_segments) > 1:
                record.update(
                    match_status="clock_ambiguous",
                    match_reason="Overlapping recorded clock segments near event",
                )
            else:
                before = bisect_right(gps_ns, event_ns) - 1
                after = bisect_left(gps_ns, event_ns)
                if before >= 0:
                    record["previous_gps_time"] = _time(gps.iloc[before]["time"])
                if after < len(gps):
                    record["next_gps_time"] = _time(gps.iloc[after]["time"])
                if before >= 0 and after < len(gps):
                    # A bracket crossing a detected reset is not a valid local GPS gap.
                    if gps.iloc[before]["clock_segment"] == gps.iloc[after]["clock_segment"]:
                        record["bracket_gap_s"] = (gps_ns[after] - gps_ns[before]) / 1e9
                choices = [index for index in (before, after) if 0 <= index < len(gps)]
                nearest = min(choices, key=lambda index: (abs(gps_ns[index] - event_ns), gps_ns[index], index))
                observation = gps.iloc[nearest]
                gps_time = _time(observation["time"])
                offset = (gps_ns[nearest] - event_ns) / 1e9
                within = abs(gps_ns[nearest] - event_ns) <= tolerance_ns
                record.update({
                    "gps_obs_id": str(observation["obs_id"]),
                    "gps_time": gps_time,
                    "offset_s": offset,
                    "within_window": within,
                    "gps_overlap": bool(overlap_segments),
                    "match_status": "within_window" if within else "outside_window",
                    "match_reason": "GPS observation within tolerance" if within else "Nearest GPS observation exceeds tolerance",
                    "gps_ttf_s": _number(observation.get("ttf_s")),
                    "gps_num_sv": _number(observation.get("num_sv")),
                    "gps_cnr": _number(observation.get("cnr_mean")),
                    "gps_voltage_v": _number(observation.get("voltage_v")),
                    "gps_clock_record": bool(observation.get("clock_record", False)),
                    "gps_marker_kind": observation.get("marker_kind", ""),
                })
        records.append(record)

    result = pd.DataFrame(records, columns=MATCH_COLUMNS)
    for column in _TIME_COLUMNS:
        result[column] = pd.to_datetime(result[column], utc=True)
    for column in _NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    for column in ("within_window", "gps_overlap"):
        result[column] = result[column].astype(bool)
    return result.sort_values(["event_time", "event_id"], kind="stable", na_position="last").reset_index(drop=True)
