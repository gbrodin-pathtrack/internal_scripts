"""Render supplied GPS observations and explicitly labelled registration estimates.

The POS loader and legacy nearest matcher retain their original behaviour.
The renderer also accepts time-interpolated/projected results from spatial.py;
it never solves positions or shifts timestamps a second time.
"""

from __future__ import annotations

from bisect import bisect_left
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import html
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


KML_NS = "http://www.opengis.net/kml/2.2"
ICON_URL = "https://maps.google.com/mapfiles/kml/paddle/wht-circle.png"
GPS_ICON_URL = "https://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"
POSITION_COLUMNS = [
    "time", "recorded_time", "source_row", "source_rows", "latitude", "longitude",
    "height", "num_sv", "seconds_of_day", "unknown1", "unknown2", "unknown3", "status",
]
_COLORS = {"success": "ff00aa00", "failure": "ff0000ff", "other": "ff888888"}
_GPS_COLOR = "ffff0000"  # KML colours are AABBGGRR: opaque blue.
_TRACK_COLOR = "ff800080"  # Opaque purple.
_MAX_TRACK_VERTEX_SPACING_M = 25000.0
ET.register_namespace("", KML_NS)


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    return number if np.isfinite(number) else np.nan


def _valid_coordinates(latitude, longitude):
    latitude, longitude = _finite(latitude), _finite(longitude)
    return bool(np.isfinite(latitude) and np.isfinite(longitude)
                and -90 <= latitude <= 90 and -180 <= longitude <= 180
                and not (latitude == 0 and longitude == 0))


def _times(frame, column):
    values = frame[column] if column in frame else pd.Series(pd.NaT, index=frame.index)
    return pd.to_datetime(values, format="mixed", utc=True, errors="coerce").astype("datetime64[ns, UTC]")


def registration_category(outcome):
    """Use explicit outcome labels only; unfamiliar outcomes stay neutral."""
    text = str(outcome).strip().lower()
    if text == "success":
        return "success"
    return "failure" if text in {"timeout", "failure", "failed"} else "other"


def load_positions(path, clock_offset_seconds=18):
    """Read five POS header lines and the documented 15-field data rows.

    Date plus fractional secondsOfDay is authoritative. Integer HMS is a
    display field and may differ by one second; disagreement is counted, not
    used to reject an otherwise valid date/SOD and coordinate. Two-digit
    years use 2000+YY, matching these supplied exports.
    """
    if not np.isfinite(clock_offset_seconds):
        raise ValueError("POS clock offset must be finite")
    try:
        offset = pd.Timedelta(seconds=clock_offset_seconds)
    except (ValueError, OverflowError) as error:
        raise ValueError("POS clock offset is outside the supported range") from error
    path = Path(path)
    quality = {
        "source_file": str(path.resolve()), "clock_offset_seconds": float(clock_offset_seconds),
        "raw_rows": 0, "blank_rows": 0, "invalid_rows": 0, "invalid_coordinate_rows": 0,
        "valid_rows_before_duplicates": 0, "duplicate_timestamp_rows": 0,
        "conflicting_timestamp_groups": 0, "conflicting_timestamp_rows": 0,
        "hms_sod_display_difference_rows": 0, "hms_sod_max_difference_seconds": 0,
        "positions": 0, "audit": [],
        "time_method": "2000+YY date plus supplied fractional secondsOfDay; subtract configured POS clock offset for UTC",
        "quality_method": "Finite in-range latitude/longitude; 0,0 sentinel excluded. numSV, height, status and unknown fields are not position-quality filters.",
        "duplicate_method": "One position per timestamp; identical coordinates retain first row and source-row provenance; conflicting coordinates exclude the whole timestamp group",
    }
    records = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for _ in range(5):
            if not stream.readline():
                raise ValueError(f"{path}: POS file requires five text header lines")
        for source_row, line in enumerate(stream, 6):
            if not line.strip():
                quality["blank_rows"] += 1
                continue
            quality["raw_rows"] += 1
            try:
                values = next(csv.reader([line], strict=True))
                if len(values) != 15:
                    raise ValueError(f"Expected 15 comma fields, found {len(values)}")
                day, month, year, hour, minute, second = [int(value.strip()) for value in values[:6]]
                if not 0 <= year <= 99:
                    raise ValueError("POS year must be a two-digit year value from 0 to 99")
                if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                    raise ValueError("Integer POS HMS display fields are outside their ranges")
                midnight = pd.Timestamp(datetime(2000 + year, month, day, tzinfo=timezone.utc))
                seconds_of_day = Decimal(values[6].strip())
                if not seconds_of_day.is_finite() or not 0 <= seconds_of_day < Decimal(86400):
                    raise ValueError("Fractional secondsOfDay must be finite and in [0, 86400)")
                # Integer nanosecond arithmetic avoids floating errors at the
                # inclusive matching boundary; retain the supplied SOD text too.
                nanos = int(seconds_of_day * Decimal(1_000_000_000))
                recorded = midnight + pd.Timedelta(nanoseconds=nanos)
                latitude, longitude = _finite(values[8]), _finite(values[9])
                if not _valid_coordinates(latitude, longitude):
                    quality["invalid_coordinate_rows"] += 1
                    raise ValueError("Invalid latitude/longitude or excluded 0,0 sentinel")
                display_difference = abs((hour * 3600 + minute * 60 + second) - int(seconds_of_day))
                if display_difference:
                    quality["hms_sod_display_difference_rows"] += 1
                    quality["hms_sod_max_difference_seconds"] = max(quality["hms_sod_max_difference_seconds"], display_difference)
                records.append({
                    "time": recorded - offset, "recorded_time": recorded, "source_row": source_row,
                    "source_rows": [source_row], "latitude": latitude, "longitude": longitude,
                    "height": _finite(values[10]), "num_sv": _finite(values[7]),
                    "seconds_of_day": values[6].strip(), "unknown1": values[11].strip(),
                    "unknown2": values[12].strip(), "unknown3": values[13].strip(), "status": values[14].strip(),
                })
            except (ValueError, InvalidOperation, OverflowError, csv.Error) as error:
                quality["invalid_rows"] += 1
                quality["audit"].append({"source_row": source_row, "reason": str(error)})
    frame = pd.DataFrame(records, columns=POSITION_COLUMNS)
    quality["valid_rows_before_duplicates"] = len(frame)
    retained = []
    for _, group in frame.groupby("time", sort=True):
        coordinates = group[["latitude", "longitude"]].drop_duplicates()
        source_rows = [int(value) for value in group["source_row"]]
        if len(coordinates) > 1:
            quality["conflicting_timestamp_groups"] += 1
            quality["conflicting_timestamp_rows"] += len(group)
            quality["audit"].append({"source_rows": source_rows, "reason": "Conflicting coordinates at one POS timestamp; all excluded"})
        else:
            first = group.iloc[0].to_dict()
            first["source_rows"] = source_rows
            retained.append(first)
            if len(group) > 1:
                quality["duplicate_timestamp_rows"] += len(group) - 1
                quality["audit"].append({"source_rows": source_rows, "kept_source_row": source_rows[0],
                                         "reason": "Repeated POS timestamp with identical coordinates"})
    result = pd.DataFrame(retained, columns=POSITION_COLUMNS)
    for column in ("time", "recorded_time"):
        result[column] = _times(result, column)
    result = result.sort_values(["time", "source_row"], kind="stable").reset_index(drop=True)
    result.attrs["clock_offset_seconds"] = float(clock_offset_seconds)
    result.attrs["source_file"] = str(path.resolve())
    quality["positions"] = len(result)
    return result, quality


def match_registrations(registrations, positions, tolerance_seconds=None):
    """Retain every registration and associate only a nearest supplied point.

    A tie chooses the earlier POS timestamp. None means no cutoff, including
    registrations before the first or after the last supplied position. With
    a finite limit, outside-window rows retain nearest time/offset only.
    """
    if tolerance_seconds is not None and (not np.isfinite(tolerance_seconds) or tolerance_seconds < 0):
        raise ValueError("Registration/POS tolerance must be finite and nonnegative")
    result = registrations.copy().reset_index(drop=True)
    result["match_status"] = "no_positions"
    for column in ("position_time", "position_recorded_time"):
        result[column] = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns, UTC]")
    for column in ("position_source_row", "position_offset_s", "latitude", "longitude", "position_num_sv"):
        result[column] = np.nan
    result["position_source_rows"] = [[] for _ in range(len(result))]
    result["position_status"] = pd.Series("", index=result.index, dtype=object)
    eligible = positions.copy()
    eligible["time"] = _times(eligible, "time")
    if "latitude" not in eligible:
        eligible["latitude"] = np.nan
    if "longitude" not in eligible:
        eligible["longitude"] = np.nan
    valid = [_valid_coordinates(row.latitude, row.longitude) for row in eligible.itertuples()]
    eligible = eligible.loc[pd.Series(valid, index=eligible.index, dtype=bool) & eligible["time"].notna()]
    eligible = eligible.sort_values("time", kind="stable").reset_index(drop=True)
    times_ns = [int(value.value) for value in eligible["time"]]
    tolerance_ns = int(round(float(tolerance_seconds) * 1e9)) if tolerance_seconds is not None else None
    event_times = _times(result, "time")
    for position, event_time in event_times.items():
        if pd.isna(event_time):
            result.loc[position, "match_status"] = "untimed"
            continue
        if not times_ns:
            continue
        index = bisect_left(times_ns, int(event_time.value))
        choices = [candidate for candidate in (index - 1, index) if 0 <= candidate < len(eligible)]
        nearest = min(choices, key=lambda candidate: (abs(times_ns[candidate] - event_time.value), times_ns[candidate], candidate))
        point = eligible.iloc[nearest]
        offset_ns = times_ns[nearest] - int(event_time.value)
        result.loc[position, "position_time"] = point["time"]
        result.loc[position, "position_recorded_time"] = point.get("recorded_time", pd.NaT)
        result.loc[position, "position_source_row"] = point.get("source_row", np.nan)
        result.loc[position, "position_offset_s"] = offset_ns / 1e9
        if tolerance_ns is not None and abs(offset_ns) > tolerance_ns:
            result.loc[position, "match_status"] = "outside_window"
            continue
        result.loc[position, "match_status"] = "nearest" if tolerance_ns is None else "within_window"
        result.loc[position, ["latitude", "longitude"]] = [point["latitude"], point["longitude"]]
        result.loc[position, "position_num_sv"] = point.get("num_sv", np.nan)
        result.at[position, "position_source_rows"] = point.get("source_rows", [point.get("source_row")])
        result.at[position, "position_status"] = point.get("status", "")
    return result


def _element(parent, local_name, text=None, **attributes):
    element = ET.SubElement(parent, f"{{{KML_NS}}}{local_name}", attributes)
    if text is not None:
        element.text = str(text)
    return element


def _display(value):
    if isinstance(value, (tuple, list)):
        return ", ".join(_display(item) for item in value)
    if value is None or pd.isna(value):
        return "unknown"
    if isinstance(value, (bool, np.bool_)):
        return "true" if value else "false"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.15g}" if np.isfinite(float(value)) else "unknown"
    return str(value)


def _time_text(value, recorded=False):
    when = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(when):
        return "unknown"
    return when.tz_localize(None).isoformat() if recorded else when.isoformat().replace("+00:00", "Z")


def _signed_seconds(value):
    number = _finite(value)
    if not np.isfinite(number):
        return "unknown"
    return f"{number:+.9f}".rstrip("0").rstrip(".")


def _absolute_gap(value):
    number = _finite(value)
    if not np.isfinite(number):
        return "unknown"
    seconds = abs(number)
    for size, unit in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if seconds >= size:
            text = f"{seconds / size:.2f}".rstrip("0").rstrip(".")
            return text + " " + unit + ("" if text == "1" else "s")
    text = f"{seconds:.9f}".rstrip("0").rstrip(".")
    return text + " second" + ("" if text == "1" else "s")


def _gap_direction(value):
    number = _finite(value)
    if not np.isfinite(number):
        return "unknown"
    return "before registration" if number < 0 else "after registration" if number > 0 else "same timestamp"


def _description(rows, note=None):
    entries = "".join(f"<tr><th align='left'>{html.escape(str(label))}</th><td>{html.escape(_display(value))}</td></tr>"
                      for label, value in rows)
    return (f"<p>{html.escape(note)}</p>" if note else "") + "<table>" + entries + "</table>"


def _extended(parent, values):
    data = _element(parent, "ExtendedData")
    for key, value in values.items():
        item = _element(data, "Data", name=key)
        _element(item, "value", _display(value))


def _coordinates(longitude, latitude):
    return f"{float(longitude):.10f},{float(latitude):.10f},0"


def _style(document, identifier, color, *, track=False, gps=False):
    style = _element(document, "Style", id=identifier)
    if not track:
        icon = _element(style, "IconStyle")
        _element(icon, "color", color)
        _element(icon, "scale", "0.35" if gps else "0.8")
        _element(_element(icon, "Icon"), "href", GPS_ICON_URL if gps else ICON_URL)
    _element(_element(style, "LabelStyle"), "scale", "0")
    if track:
        line = _element(style, "LineStyle")
        _element(line, "color", color)
        _element(line, "width", "2.5")


_ESTIMATE_METHODS = frozenset({"exact", "interpolated", "projected_before", "projected_after"})
_METHOD_NAMES = {
    "exact": "At supplied GPS timestamp",
    "interpolated": "Time-interpolated between supplied GPS anchors",
    "projected_before": "Time-projected before the first supplied GPS position",
    "projected_after": "Time-projected after the last supplied GPS position",
    "nearest": "Nearest supplied GPS position (legacy matching)",
}
_METHOD_SHORT_NAMES = {
    "exact": "Exact GPS timestamp", "interpolated": "Time-interpolated",
    "projected_before": "Projected before track", "projected_after": "Projected after track",
    "nearest": "Nearest GPS",
}


def _folder(parent, name):
    folder = _element(parent, "Folder")
    _element(folder, "name", name)
    _element(folder, "visibility", "1")
    _element(folder, "open", "0")
    return folder


def _estimated_coordinates(latitude, longitude):
    # An interpolated/projected (0,0) is legitimate. The raw POS loader owns
    # sentinel filtering; do not apply its 0,0 sentinel rule to an estimate.
    latitude, longitude = _finite(latitude), _finite(longitude)
    return bool(np.isfinite(latitude) and np.isfinite(longitude)
                and -90 <= latitude <= 90 and -180 <= longitude <= 180)


def _location_method(event):
    status = str(event.get("match_status", ""))
    method = str(event.get("position_method", status))
    if method in _ESTIMATE_METHODS and status in _ESTIMATE_METHODS:
        return method
    return "nearest" if status in {"nearest", "within_window"} else None


def _supplied_positions(positions):
    ordered = positions.copy()
    ordered["time"] = _times(ordered, "time")
    valid = pd.Series(
        [_valid_coordinates(point.get("latitude"), point.get("longitude")) for _, point in ordered.iterrows()],
        index=ordered.index, dtype=bool,
    )
    return ordered.loc[valid & ordered["time"].notna()].sort_values("time", kind="stable")


def _track_segments(ordered, track_gap_seconds):
    """Densify only actual observation legs using the estimator's geometry."""
    from .spatial import great_circle_distance_m, great_circle_position

    segments, current, previous = [], None, None
    ambiguous = 0
    for _, point in ordered.iterrows():
        coordinate = (float(point["latitude"]), float(point["longitude"]))
        split = previous is not None and track_gap_seconds is not None and (
            point["time"] - previous["time"]
        ).total_seconds() > track_gap_seconds
        if current is None or split:
            if current is not None:
                segments.append(current)
            current = {"vertices": [coordinate], "first_time": point["time"],
                       "last_time": point["time"], "observations": 1}
        else:
            start = (float(previous["latitude"]), float(previous["longitude"]))
            try:
                distance = great_circle_distance_m(*start, *coordinate)
                steps = max(1, int(np.ceil(distance / _MAX_TRACK_VERTEX_SPACING_M)))
                interior = [great_circle_position(*start, *coordinate, step / steps)
                            for step in range(1, steps)]
            except ValueError:
                # Antipodal endpoints do not define a unique connecting arc.
                # Keep the observations, but do not fabricate a direction.
                ambiguous += 1
                segments.append(current)
                current = {"vertices": [coordinate], "first_time": point["time"],
                           "last_time": point["time"], "observations": 1}
            else:
                current["vertices"].extend(interior)
                current["vertices"].append(coordinate)
                current["last_time"] = point["time"]
                current["observations"] += 1
        previous = point
    if current is not None:
        segments.append(current)
    return [segment for segment in segments if len(segment["vertices"]) > 1], ambiguous


def _observed_gps_features(group, ordered):
    folder = _folder(group, f"Actual GPS positions ({len(ordered):,} blue observed points)")
    for _, point in ordered.iterrows():
        placemark = _element(folder, "Placemark")
        _element(placemark, "name", f"Actual GPS — {_time_text(point['time'])} — POS row {_display(point.get('source_row'))}")
        fields = {
            "position_type": "Supplied solved GPS observation",
            "position_utc": _time_text(point["time"]),
            "position_recorded_clock": _time_text(point.get("recorded_time"), recorded=True),
            "source_rows": point.get("source_rows", [point.get("source_row")]),
            "latitude": point["latitude"], "longitude": point["longitude"],
            "supplied_height_uninterpreted": point.get("height"),
            "satellites": point.get("num_sv"), "supplied_status_uninterpreted": point.get("status"),
        }
        _element(placemark, "description", _description([
            ("Position type", fields["position_type"]), ("GPS observation UTC", fields["position_utc"]),
            ("Recorded GPS clock", fields["position_recorded_clock"]), ("Original POS rows", fields["source_rows"]),
            ("Latitude", point["latitude"]), ("Longitude", point["longitude"]),
            ("Supplied height (not used for map altitude)", fields["supplied_height_uninterpreted"]),
            ("Supplied satellites", fields["satellites"]), ("Status (not interpreted)", fields["supplied_status_uninterpreted"]),
        ], "Blue points are actual supplied POS records. Densified purple-line vertices are not observations. "
           "A supplied solution is not an independent accuracy guarantee."))
        _element(placemark, "styleUrl", "#observed_gps")
        _extended(placemark, fields)
        geometry = _element(placemark, "Point")
        _element(geometry, "altitudeMode", "clampToGround")
        _element(geometry, "coordinates", _coordinates(point["longitude"], point["latitude"]))


def _purple_track_features(group, segments):
    folder = _folder(group, f"Purple connecting track ({len(segments):,} chronological segments)")
    for number, segment in enumerate(segments, 1):
        placemark = _element(folder, "Placemark")
        _element(placemark, "name", f"Actual-position track segment {number} ({segment['observations']:,} observations)")
        _element(placemark, "description", _description([
            ("First actual GPS UTC", _time_text(segment["first_time"])),
            ("Last actual GPS UTC", _time_text(segment["last_time"])),
            ("Actual supplied observations", segment["observations"]),
            ("Displayed curve vertices", len(segment["vertices"])),
        ], "Purple connects consecutive actual GPS observations using the shortest spherical great-circle arc. "
           "Additional vertices only draw the curve at no more than 25 km spacing; they are not measured GPS points. "
           "The line does not reconstruct the path travelled between observations and never extends to projected registrations."))
        _element(placemark, "styleUrl", "#position_track")
        _extended(placemark, {"actual_observations": segment["observations"],
                              "display_vertices": len(segment["vertices"]),
                              "first_actual_gps_utc": _time_text(segment["first_time"]),
                              "last_actual_gps_utc": _time_text(segment["last_time"])})
        geometry = _element(placemark, "LineString")
        _element(geometry, "tessellate", "1")
        _element(geometry, "altitudeMode", "clampToGround")
        _element(geometry, "coordinates", " ".join(_coordinates(longitude, latitude)
                 for latitude, longitude in segment["vertices"]))


def _registration_fields(device_id, event, method):
    fields = {
        "device_id": device_id,
        "position_method": method,
        "position_method_description": _METHOD_NAMES[method],
        "registration_location_measured": False,
        "registration_utc": _time_text(event.get("time")),
        "registration_recorded_clock": _time_text(event.get("recorded_time"), recorded=True),
        "registration_source_rows": event.get("merged_source_rows", event.get("source_row")),
        "estimated_latitude": event.get("latitude"), "estimated_longitude": event.get("longitude"),
        # These existing keys are retained as nearest-observation audit fields.
        "position_utc": _time_text(event.get("position_time")),
        "position_recorded_clock": _time_text(event.get("position_recorded_time"), recorded=True),
        "position_source_rows": event.get("position_source_rows", event.get("position_source_row")),
        "position_offset_seconds": _signed_seconds(event.get("position_offset_s")),
        "absolute_time_gap": _absolute_gap(event.get("position_offset_s")),
        "position_time_direction": _gap_direction(event.get("position_offset_s")),
        "tier": event.get("tier"), "outcome": event.get("outcome"),
        "registration_duration_seconds": event.get("duration_s"),
        "rsrp_dbm": event.get("rsrp_dbm"), "tx_power_dbm": event.get("tx_dbm"),
        "reported_battery_v": event.get("voltage_v"),
        "position_num_sv": event.get("position_num_sv"),
        "position_status_uninterpreted": event.get("position_status"),
    }
    if method in _ESTIMATE_METHODS:
        fields.update({
            "estimate_utc": _time_text(event.get("time")),
            "anchor_start_utc": _time_text(event.get("anchor_start_time")),
            "anchor_end_utc": _time_text(event.get("anchor_end_time")),
            "anchor_start_recorded_clock": _time_text(event.get("anchor_start_recorded_time"), recorded=True),
            "anchor_end_recorded_clock": _time_text(event.get("anchor_end_recorded_time"), recorded=True),
            "anchor_start_source_rows": event.get("anchor_start_source_rows"),
            "anchor_end_source_rows": event.get("anchor_end_source_rows"),
            "anchor_start_latitude": event.get("anchor_start_latitude"),
            "anchor_start_longitude": event.get("anchor_start_longitude"),
            "anchor_end_latitude": event.get("anchor_end_latitude"),
            "anchor_end_longitude": event.get("anchor_end_longitude"),
            "anchor_span_s": _signed_seconds(event.get("anchor_span_s")).lstrip("+"),
            "anchor_interval": _absolute_gap(event.get("anchor_span_s")),
            "time_fraction": event.get("time_fraction"),
            "seconds_from_anchor_start": _signed_seconds(event.get("seconds_from_anchor_start")),
            "seconds_to_anchor_end": _signed_seconds(event.get("seconds_to_anchor_end")),
            "projection_horizon_s": _signed_seconds(event.get("projection_horizon_s")).lstrip("+"),
            "projection_horizon": _absolute_gap(event.get("projection_horizon_s")),
            "segment_distance_m": event.get("segment_distance_m"),
            "segment_speed_m_s": event.get("segment_speed_m_s"),
        })
    return fields


_FIELD_LABELS = {
    "device_id": "Tag",
    "position_method_description": "Location method",
    "position_method": "Method code",
    "registration_location_measured": "Independently measured registration location",
    "registration_utc": "Registration UTC",
    "registration_recorded_clock": "Registration recorded clock",
    "registration_source_rows": "Original registration CSV rows",
    "estimated_latitude": "Registration estimated latitude",
    "estimated_longitude": "Registration estimated longitude",
    "position_utc": "Nearest actual GPS UTC (audit only)",
    "position_recorded_clock": "Nearest GPS recorded clock",
    "position_source_rows": "Nearest original POS rows",
    "position_offset_seconds": "Nearest GPS minus registration time (seconds)",
    "absolute_time_gap": "Absolute nearest-GPS time gap",
    "position_time_direction": "Nearest GPS direction in time",
    "estimate_utc": "Time of estimated location",
    "anchor_start_utc": "Earlier anchor GPS UTC",
    "anchor_end_utc": "Later anchor GPS UTC",
    "anchor_start_recorded_clock": "Earlier anchor recorded clock",
    "anchor_end_recorded_clock": "Later anchor recorded clock",
    "anchor_start_source_rows": "Earlier anchor original POS rows",
    "anchor_end_source_rows": "Later anchor original POS rows",
    "anchor_span_s": "Interval between anchor GPS records (seconds)",
    "anchor_interval": "Interval between anchors",
    "time_fraction": "Fraction of anchor interval at registration",
    "seconds_from_anchor_start": "Registration minus earlier anchor time (seconds)",
    "seconds_to_anchor_end": "Later anchor time minus registration (seconds)",
    "projection_horizon_s": "Projection beyond actual track (seconds)",
    "projection_horizon": "Projection horizon",
    "segment_distance_m": "Anchor great-circle distance (metres)",
    "segment_speed_m_s": "Anchor-derived model speed (metres/second)",
}


def _registration_feature(folder, device_id, event, method, match_rule):
    placemark = _element(folder, "Placemark")
    _element(placemark, "name",
             f"{_display(event.get('outcome'))} — {_METHOD_SHORT_NAMES[method]} — "
             f"{_time_text(event.get('time'))} — row {_display(event.get('source_row'))}")
    fields = _registration_fields(device_id, event, method)
    if method == "nearest":
        note = (f"Approximate location from nearest supplied POS record {match_rule}. "
                f"Position time: {_gap_direction(event.get('position_offset_s'))}; "
                f"absolute gap: {_absolute_gap(event.get('position_offset_s'))}. "
                "This is legacy nearest matching, not time interpolation.")
    elif method.startswith("projected_"):
        note = ("TIME-PROJECTED location outside the supplied GPS track. The first/last anchor leg's "
                "constant angular speed and great-circle direction are continued, possibly over a long horizon. "
                "This modelled location is not measured and uncertainty is not bounded. "
                "No projected motion line is added to the actual purple track.")
    elif method == "interpolated":
        note = ("TIME-INTERPOLATED location between two supplied GPS records, using elapsed time along their "
                "shortest spherical great-circle arc. Speed between anchors is assumed constant. "
                "This is not a measured registration location or a reconstruction of the travelled route.")
    else:
        note = ("The registration shares a supplied GPS timestamp, so that observation's coordinate is used. "
                "The registration location is still not independently measured.")
    note += " Recorded clocks have no UTC suffix; comparison times are already UTC. No second clock correction is applied."
    _element(placemark, "description", _description(
        [(_FIELD_LABELS.get(key, key.replace("_", " ")), value) for key, value in fields.items()], note))
    _element(placemark, "styleUrl", "#registration_" + registration_category(event.get("outcome")))
    _extended(placemark, fields)
    point = _element(placemark, "Point")
    _element(point, "altitudeMode", "clampToGround")
    _element(point, "coordinates", _coordinates(event["longitude"], event["latitude"]))


def build_kml(device_id, positions, matches, *, track_gap_seconds=None,
              clock_offset_seconds=18, tolerance_seconds=None):
    """Create visible GPS observations, a purple track and labelled registrations.

    New spatial estimates are rendered as supplied; this function does not
    interpolate registration coordinates or shift any timestamp. A finite
    tolerance still bounds legacy nearest rows only. None joins actual track
    points across time gaps; a finite track gap retains the optional old split.
    """
    if track_gap_seconds is not None and (not np.isfinite(track_gap_seconds) or track_gap_seconds <= 0):
        raise ValueError("KML track gap must be None or finite and positive")
    if not np.isfinite(clock_offset_seconds) or (
        tolerance_seconds is not None and (not np.isfinite(tolerance_seconds) or tolerance_seconds < 0)
    ):
        raise ValueError("KML clock/tolerance settings must be finite; tolerance cannot be negative")
    ordered = _supplied_positions(positions)
    segments, ambiguous_legs = _track_segments(ordered, track_gap_seconds)
    methods, mapped_values = [], []
    for _, event in matches.iterrows():
        method = _location_method(event)
        spatial = method in _ESTIMATE_METHODS
        valid = method is not None and _estimated_coordinates(event.get("latitude"), event.get("longitude"))
        if valid and not spatial:
            valid = _valid_coordinates(event.get("latitude"), event.get("longitude"))
            if tolerance_seconds is not None:
                offset = _finite(event.get("position_offset_s"))
                valid = np.isfinite(offset) and abs(offset) <= tolerance_seconds
        valid = valid and pd.notna(pd.to_datetime(event.get("time"), utc=True, errors="coerce"))
        methods.append(method)
        mapped_values.append(bool(valid))
    mapped = pd.Series(mapped_values, index=matches.index, dtype=bool)
    method_series = pd.Series(methods, index=matches.index, dtype=object)
    spatial_mode = "position_method" in matches or any(method in _ESTIMATE_METHODS for method in methods)
    pos_offset = positions.attrs.get("clock_offset_seconds", clock_offset_seconds)
    match_rule = "with no time cutoff" if tolerance_seconds is None else f"within {tolerance_seconds:g} seconds"
    track_rule = "None — consecutive actual positions joined across time gaps" if track_gap_seconds is None else f"{track_gap_seconds:g} seconds"
    if spatial_mode:
        location_note = ("Registrations use time interpolation inside the actual GPS span and first/last-leg projection outside it. "
                         "Each marker states its method and both anchor timestamps. Projected markers keep the same green/red outcome colour. "
                         "These locations are modelled estimates, not independently measured registration locations. ")
    else:
        location_note = (f"Legacy registration markers use the nearest supplied POS point {match_rule}. "
                         "No registration coordinates are interpolated; the nearest point may be hours or days away when no cutoff is selected. ")
    note = (location_note + "Blue circles are actual supplied GPS observations. Purple connects chronological actual observations "
            "with great-circle display vertices at no more than 25 km spacing; those extra vertices are not observations. "
            "The purple line ends at actual GPS endpoints and does not extend to projected registrations. "
            "No extra status/numSV filter, smoothing or outlier rejection is applied. "
            "All features are visible without a time-slider selection. "
            f"Ambiguous antipodal legs left unjoined: {ambiguous_legs}.")
    root = ET.Element(f"{{{KML_NS}}}kml")
    document = _element(root, "Document")
    _element(document, "name", f"Device {device_id} registrations and GPS positions")
    _element(document, "open", "1")
    _element(document, "description", _description([
        ("Tag", device_id), ("Actual supplied GPS observations", len(ordered)),
        ("Registrations", len(matches)), ("Mapped registrations", int(mapped.sum())),
        ("Unmapped registrations", int((~mapped).sum())),
        ("Nearest-only compatibility cutoff", "None (no time limit)" if tolerance_seconds is None else f"{tolerance_seconds:g} seconds"),
        ("Track split gap", track_rule),
        ("Maximum purple display-vertex spacing (m)", _MAX_TRACK_VERTEX_SPACING_M),
        ("POS clock seconds subtracted for UTC", pos_offset),
        ("Registration device clock seconds subtracted for UTC", clock_offset_seconds),
        ("Nearest audit offset sign", "POS UTC time minus registration UTC time"),
    ], note))
    for category, color in _COLORS.items():
        _style(document, "registration_" + category, color)
    _style(document, "observed_gps", _GPS_COLOR, gps=True)
    _style(document, "position_track", _TRACK_COLOR, track=True)
    _extended(document, {"actual_gps_observations": len(ordered),
                         "purple_track_segments": len(segments),
                         "ambiguous_geodesic_legs_not_joined": ambiguous_legs,
                         "max_track_vertex_spacing_m": _MAX_TRACK_VERTEX_SPACING_M})
    gps_group = _folder(document, f"GPS observations and track ({len(ordered):,} supplied positions)")
    _observed_gps_features(gps_group, ordered)
    _purple_track_features(gps_group, segments)

    categories = matches["outcome"].map(registration_category) if "outcome" in matches else pd.Series("other", index=matches.index)
    names = {"success": "Successful registrations", "failure": "Timeout / failure registrations", "other": "Other registration outcomes"}
    for category in ("success", "failure", "other"):
        selection = categories.eq(category)
        folder = _folder(document, f"{names[category]} ({int((selection & mapped).sum())} mapped / {int(selection.sum())} records)")
        selected = matches.loc[selection & mapped]
        if spatial_mode:
            for method in ("exact", "interpolated", "projected_before", "projected_after", "nearest"):
                subset = selected.loc[method_series.loc[selected.index].eq(method)]
                if subset.empty:
                    continue
                method_folder = _folder(folder, f"{_METHOD_SHORT_NAMES[method]} ({len(subset):,} markers)")
                for _, event in subset.iterrows():
                    _registration_feature(method_folder, device_id, event, method, match_rule)
        else:
            for index, event in selected.iterrows():
                _registration_feature(folder, device_id, event, method_series.loc[index], match_rule)
    ET.indent(root, space="  ")
    output = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return output.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n") + b"\r\n"
