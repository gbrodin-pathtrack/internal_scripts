"""Registration-time positions from supplied, UTC-aligned POS coordinates.

Interior times use shortest-path spherical great-circle interpolation. Times
outside the supplied track continue the first/last leg's angular velocity in
the same direction, without a time cutoff. These are modelled estimates, not
observations. No second clock shift, smoothing or outlier filter is applied.
"""

from __future__ import annotations

from bisect import bisect_left
import math

import numpy as np
import pandas as pd


EARTH_RADIUS_M = 6371008.8
MAPPED_METHODS = frozenset({"exact", "interpolated", "projected_before", "projected_after"})
_GEOMETRY_EPSILON = 1e-12
_TIME_COLUMNS = [
    "anchor_start_time", "anchor_end_time", "anchor_start_recorded_time", "anchor_end_recorded_time",
    "position_time", "position_recorded_time",
]
_NUMBER_COLUMNS = [
    "latitude", "longitude", "anchor_start_latitude", "anchor_start_longitude",
    "anchor_end_latitude", "anchor_end_longitude", "anchor_span_s", "time_fraction",
    "seconds_from_anchor_start", "seconds_to_anchor_end", "projection_horizon_s",
    "segment_distance_m", "segment_speed_m_s", "position_source_row", "position_offset_s",
]


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    return number if np.isfinite(number) else np.nan


def _valid_coordinate(latitude, longitude):
    latitude, longitude = _number(latitude), _number(longitude)
    # Raw POS sentinel filtering is the loader's job. A computed (0,0) is a
    # legitimate geographic coordinate and must not be discarded here.
    return bool(np.isfinite(latitude) and np.isfinite(longitude)
                and -90 <= latitude <= 90 and -180 <= longitude <= 180)


def _longitude(value):
    result = (float(value) + 180.0) % 360.0 - 180.0
    return 0.0 if result == 0 else result


def _unit(latitude, longitude):
    if not _valid_coordinate(latitude, longitude):
        raise ValueError("Great-circle coordinates must be finite and in range")
    latitude, longitude = math.radians(float(latitude)), math.radians(float(longitude))
    cosine = math.cos(latitude)
    return (cosine * math.cos(longitude), cosine * math.sin(longitude), math.sin(latitude))


def _arc(latitude1, longitude1, latitude2, longitude2):
    first, last = _unit(latitude1, longitude1), _unit(latitude2, longitude2)
    dot = min(1.0, max(-1.0, sum(a * b for a, b in zip(first, last))))
    cross = (first[1]*last[2] - first[2]*last[1], first[2]*last[0] - first[0]*last[2], first[0]*last[1] - first[1]*last[0])
    sine = math.sqrt(sum(value * value for value in cross))
    angle = 0.0 if sine <= _GEOMETRY_EPSILON and dot >= 0 else math.atan2(sine, dot)
    return first, last, dot, sine, angle


def great_circle_distance_m(lat1, lon1, lat2, lon2):
    """Spherical shortest-arc distance; even antipodal distance is defined."""
    return float(_arc(lat1, lon1, lat2, lon2)[4] * EARTH_RADIUS_M)


def great_circle_position(lat1, lon1, lat2, lon2, fraction):
    """Return a shortest-circle position or constant-angular-speed continuation.

    fraction may be below zero or above one. Coincident anchors are stationary.
    Antipodal interior/extrapolated geometry is ambiguous and raises ValueError;
    the exact supplied endpoints remain usable. Longitudes normalize to [-180,180).
    """
    fraction = _number(fraction)
    if not np.isfinite(fraction):
        raise ValueError("Great-circle fraction must be finite")
    first, last, dot, sine, angle = _arc(lat1, lon1, lat2, lon2)
    if fraction == 0:
        return float(lat1), _longitude(lon1)
    if fraction == 1:
        return float(lat2), _longitude(lon2)
    if sine <= _GEOMETRY_EPSILON:
        if dot < 0:
            raise ValueError("Antipodal anchors have no unique great-circle direction")
        return float(lat1), _longitude(lon1)
    tangent = tuple((end - dot * start) / sine for start, end in zip(first, last))
    tangent_norm = math.sqrt(sum(value * value for value in tangent))
    tangent = tuple(value / tangent_norm for value in tangent)
    phase = angle * fraction
    if not math.isfinite(phase):
        raise ValueError("Great-circle continuation exceeds the supported numeric range")
    phase = math.remainder(phase, 2 * math.pi)
    point = tuple(math.cos(phase) * start + math.sin(phase) * direction for start, direction in zip(first, tangent))
    horizontal = math.hypot(point[0], point[1])
    latitude = math.degrees(math.atan2(point[2], horizontal))
    longitude = _longitude(lon1) if horizontal < 1e-14 else _longitude(math.degrees(math.atan2(point[1], point[0])))
    return latitude, longitude


def _times(frame, column):
    values = frame[column] if column in frame else pd.Series(pd.NaT, index=frame.index)
    return pd.to_datetime(values, format="mixed", utc=True, errors="coerce").astype("datetime64[ns, UTC]")


def _source_rows(row):
    supplied = row.get("source_rows")
    if isinstance(supplied, (list, tuple)):
        return list(supplied)
    value = row.get("source_row")
    return [value] if value is not None and pd.notna(value) else []


def _positions(positions):
    """Defend against invalid/duplicate inputs without guessing a conflicting point."""
    result = positions.copy()
    result["time"] = _times(result, "time")
    result["recorded_time"] = _times(result, "recorded_time")
    for name in ("latitude", "longitude"):
        if name not in result:
            result[name] = np.nan
        result[name] = pd.to_numeric(result[name], errors="coerce")
    valid = pd.Series([_valid_coordinate(row.latitude, row.longitude) for row in result.itertuples()],
                      index=result.index, dtype=bool)
    result = result.loc[valid & result["time"].notna()].sort_values("time", kind="stable").copy()
    conflicts = set()
    duplicated = result["time"].duplicated(keep=False)
    if duplicated.any():
        keep = pd.Series(True, index=result.index)
        for when, group in result.loc[duplicated].groupby("time", sort=False):
            if len(group[["latitude", "longitude"]].drop_duplicates()) > 1:
                keep.loc[group.index] = False
                conflicts.add(int(when.value))
            else:
                keep.loc[group.index[1:]] = False
        result = result.loc[keep]
    return result.reset_index(drop=True), sorted(conflicts)


def _fill_anchor(result, index, start, end):
    for prefix, anchor in (("anchor_start", start), ("anchor_end", end)):
        result.loc[index, prefix + "_time"] = anchor["time"]
        result.loc[index, prefix + "_recorded_time"] = anchor["recorded_time"]
        result.at[index, prefix + "_source_rows"] = _source_rows(anchor)
        result.loc[index, prefix + "_latitude"] = anchor["latitude"]
        result.loc[index, prefix + "_longitude"] = anchor["longitude"]


def estimate_registration_positions(registrations, positions):
    """Keep every registration, adding a UTC-time great-circle estimate and audit.

    Exact points need no velocity assumption. Interior times use the bracketing
    pair; outside times continue the first/last two supplied points. A single
    point is sufficient only for an exact time. No extrapolation cutoff applies.
    """
    result = registrations.copy().reset_index(drop=True)
    for column in _TIME_COLUMNS:
        result[column] = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns, UTC]")
    for column in _NUMBER_COLUMNS:
        result[column] = np.nan
    for column in ("anchor_start_source_rows", "anchor_end_source_rows", "position_source_rows"):
        result[column] = [[] for _ in range(len(result))]
    result["position_method"] = "no_positions"
    result["match_status"] = "no_positions"
    eligible, conflict_times = _positions(positions)
    times_ns = [int(value.value) for value in eligible["time"]]
    event_times = _times(result, "time")
    for index, when in event_times.items():
        if pd.isna(when):
            result.loc[index, ["position_method", "match_status"]] = "untimed"
            continue
        event_ns = int(when.value)
        if event_ns in conflict_times:
            result.loc[index, ["position_method", "match_status"]] = "ambiguous_geometry"
            continue
        if not times_ns:
            if conflict_times:
                result.loc[index, ["position_method", "match_status"]] = "ambiguous_geometry"
            continue
        following = bisect_left(times_ns, event_ns)
        candidates = [value for value in (following - 1, following) if 0 <= value < len(times_ns)]
        nearest = min(candidates, key=lambda value: (abs(times_ns[value] - event_ns), times_ns[value], value))
        nearest_point = eligible.iloc[nearest]
        result.loc[index, "position_time"] = nearest_point["time"]
        result.loc[index, "position_recorded_time"] = nearest_point["recorded_time"]
        result.loc[index, "position_source_row"] = nearest_point.get("source_row", np.nan)
        result.at[index, "position_source_rows"] = _source_rows(nearest_point)
        result.loc[index, "position_offset_s"] = (times_ns[nearest] - event_ns) / 1e9
        if following < len(times_ns) and times_ns[following] == event_ns:
            point = eligible.iloc[following]
            _fill_anchor(result, index, point, point)
            result.loc[index, ["latitude", "longitude"]] = [point["latitude"], point["longitude"]]
            result.loc[index, ["anchor_span_s", "time_fraction", "seconds_from_anchor_start",
                               "seconds_to_anchor_end", "projection_horizon_s", "segment_distance_m"]] = 0.0
            # A single instantaneous point has no inferred speed, not zero speed.
            result.loc[index, ["position_method", "match_status"]] = "exact"
            continue
        if len(times_ns) < 2:
            result.loc[index, ["position_method", "match_status"]] = "insufficient_positions"
            continue
        if following == 0:
            first, last, method = 0, 1, "projected_before"
        elif following == len(times_ns):
            first, last, method = len(times_ns) - 2, len(times_ns) - 1, "projected_after"
        else:
            first, last, method = following - 1, following, "interpolated"
        start, end = eligible.iloc[first], eligible.iloc[last]
        _fill_anchor(result, index, start, end)
        span_ns = times_ns[last] - times_ns[first]
        if span_ns <= 0:
            result.loc[index, ["position_method", "match_status"]] = "ambiguous_geometry"
            continue
        elapsed_ns = event_ns - times_ns[first]
        fraction = elapsed_ns / span_ns
        distance = great_circle_distance_m(start["latitude"], start["longitude"], end["latitude"], end["longitude"])
        result.loc[index, "anchor_span_s"] = span_ns / 1e9
        result.loc[index, "time_fraction"] = fraction
        result.loc[index, "seconds_from_anchor_start"] = elapsed_ns / 1e9
        result.loc[index, "seconds_to_anchor_end"] = (times_ns[last] - event_ns) / 1e9
        result.loc[index, "projection_horizon_s"] = max(0, -elapsed_ns, event_ns - times_ns[last]) / 1e9
        result.loc[index, "segment_distance_m"] = distance
        result.loc[index, "segment_speed_m_s"] = distance / (span_ns / 1e9)
        if any(times_ns[first] <= conflict <= times_ns[last] for conflict in conflict_times):
            result.loc[index, ["position_method", "match_status"]] = "ambiguous_geometry"
            continue
        try:
            latitude, longitude = great_circle_position(start["latitude"], start["longitude"], end["latitude"], end["longitude"], fraction)
        except ValueError:
            result.loc[index, ["position_method", "match_status"]] = "ambiguous_geometry"
            continue
        result.loc[index, ["latitude", "longitude"]] = [latitude, longitude]
        result.loc[index, ["position_method", "match_status"]] = method
    result.attrs["position_model"] = "Shortest-path spherical great-circle interpolation; first/last-leg constant angular velocity outside track; no cutoff"
    result.attrs["earth_radius_m"] = EARTH_RADIUS_M
    return result
