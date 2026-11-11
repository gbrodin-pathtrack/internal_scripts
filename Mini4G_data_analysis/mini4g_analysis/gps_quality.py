"""Audited GPS cleaning over immutable CSV frames and optional raw DAT pages.

Page identity is evidence of replay, not proof of its network/firmware cause.
Clock-record labels are telemetry-format candidates, not MCU reboot verdicts.
Recorded device clocks remain unshifted in UTC-aware timestamp containers.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


_OBS_FIELDS = ["line", "datetime", "date", "time", "numSV", "vbatt", "TTF", "startDatetime"]
_REQUIRED = ["line", "datetime", "numSV", "vbatt", "TTF", "startDatetime"]
GPS_COLUMNS = ["obs_id", "time", "start_time", "ttf_s", "num_sv", "vbatt_raw",
               "voltage_v", "source_line", "source_row", "clock_segment",
               "clock_anomaly", "duplicate", "cnr_mean", "cnr_peak",
               "clock_record", "marker_kind", "decoded_marker_voltage_v", "raw_ttf_s",
               "recorded_time", "recorded_start_time"]


def _text(value):
    return "" if pd.isna(value) else str(value)


def _frame(raw, required):
    frame = raw.copy(deep=True).reset_index(drop=True)
    missing = [name for name in required if name not in frame]
    if missing and not frame.empty:
        raise ValueError("Missing GPS quality columns: " + ", ".join(missing))
    for name in missing:
        frame[name] = pd.Series(dtype="string")
    if "source_row" not in frame:
        frame["source_row"] = np.arange(2, len(frame) + 2)
    source = pd.to_numeric(frame["source_row"], errors="coerce")
    if (source.isna().any() or source.lt(2).any() or source.mod(1).ne(0).any()
            or source.duplicated().any()):
        raise ValueError("GPS source_row values must be distinct CSV row numbers starting at 2")
    frame["source_row"] = source.astype(int)
    return frame


def _number(frame, name):
    values = pd.to_numeric(frame[name], errors="coerce").astype(float)
    return values.where(np.isfinite(values))


def _times(values):
    # The exports use ISO calendar fields. Reject ambiguous day/month text.
    cleaned = values.astype("string").str.strip().str.replace(r"\s+UTC$", "+00:00", regex=True)
    cleaned = cleaned.where(cleaned.str.match(r"^\d{4}-\d{2}-\d{2}(?:[ T]|$)", na=False))
    return pd.to_datetime(cleaned, format="ISO8601", errors="coerce",
                          utc=True).astype("datetime64[ns, UTC]")


def _key(row, columns):
    return tuple(_text(row[name]) for name in columns)


def _source(row):
    try:
        value = float(_text(row["line"]))
        if np.isfinite(value) and value.is_integer():
            return int(value)
    except (TypeError, ValueError):
        pass
    return _text(row["line"])


def _dat_pages(path):
    """Return physical-line page identities; malformed numeric pages fail closed."""
    pages = {}
    first = {}
    replay = {}
    groups = set()
    with path.open("r", encoding="utf-8-sig") as stream:
        for line, text in enumerate(stream, 1):
            if not text[:1].isdigit():
                continue
            try:
                data = bytes(int(token) for token in text.split())
            except ValueError as error:
                raise ValueError(f"{path}:{line}: invalid DAT byte row") from error
            if len(data) != 512:
                raise ValueError(f"{path}:{line}: expected 512 DAT bytes, got {len(data)}")
            pages[line] = data
            if data in first:
                replay[line] = first[data]
                groups.add(first[data])
            else:
                first[data] = line
    return pages, replay, len(groups)


def _packed_calendar_hint(packed):
    """Decode a calendar header only; UTC tzinfo represents its recorded scale."""
    if len(packed) != 5 or not any(packed):
        return None
    bits = int.from_bytes(packed, "little")
    year = bits & 0x7F
    subsecond = (bits >> 33) & 0x7F
    if year > 99 or subsecond > 63:
        return None
    try:
        return datetime(2000 + year, (bits >> 7) & 0x0F,
                        (bits >> 11) & 0x1F, (bits >> 16) & 0x1F,
                        (bits >> 21) & 0x3F, (bits >> 27) & 0x3F,
                        subsecond * 15625, tzinfo=timezone.utc)
    except ValueError:
        return None


def _header_time_hints(data, declared_length, header_length):
    """Walk record boundaries for time hints without decoding measurements.

    complete_record_count is a structural byte-count check, including records
    whose calendar is unavailable. complete_valid_time_records reports its
    valid-calendar subset. A partial final payload can still supply a valid
    calendar hint. Neither count creates or repairs an observation.
    """
    hints = {"recorded_first_time": None, "recorded_last_time": None,
             "valid_time_headers": 0, "complete_record_count": 0,
             "complete_valid_time_records": 0, "invalid_time_headers": 0,
             "partial_record_payload": False, "partial_record_header": False,
             "recorded_time_headers": [], "header_walk_stop": "declared_end",
             "time_hint_basis": "Recorded device calendar headers only; not decoded GPS measurements or continuous coverage."}
    if not (header_length < declared_length <= len(data)):
        hints["header_walk_stop"] = "invalid_declared_length"
        return hints
    times = []
    offset = header_length
    while offset < declared_length:
        if offset + 8 > declared_length:
            hints["partial_record_header"] = True
            hints["header_walk_stop"] = "partial_record_header"
            break
        header = data[offset:offset + 8]
        when = _packed_calendar_hint(header[:5])
        if when is None:
            hints["invalid_time_headers"] += 1
        else:
            times.append(when)
        record_length = 8 + int(header[5]) * 5
        if offset + record_length > declared_length:
            hints["partial_record_payload"] = True
            hints["header_walk_stop"] = "partial_record_payload"
            break
        hints["complete_record_count"] += 1
        if when is not None:
            hints["complete_valid_time_records"] += 1
        offset += record_length
    hints["valid_time_headers"] = len(times)
    hints["recorded_time_headers"] = [when.isoformat() for when in times]
    if times:
        hints["recorded_first_time"] = min(times).isoformat()
        hints["recorded_last_time"] = max(times).isoformat()
    return hints


def clean_gps_frames(device_id: str, raw_obs: pd.DataFrame, raw_sv: pd.DataFrame,
                     dat_path: Path | None, voltage_mode="legacy"):
    """Return cleaned observations, their satellite rows and JSON-safe audit.

    DAT replay removal uses whole-page byte equality at physical source lines.
    Without DAT, exact observation semantics excluding line/source_row provide
    a weaker fallback. Identical CSV rows are accounted for separately.
    Payload-duplicate evidence requires nonempty, complete satellite payloads;
    timestamps alone never identify duplicates.
    """
    if voltage_mode not in ("legacy", "raw"):
        raise ValueError("GPS voltage mode must be legacy or raw")
    obs = _frame(raw_obs, _REQUIRED)
    sv = _frame(raw_sv, _REQUIRED + ["ID", "CNR", "codePhase"])
    obs_records = obs.to_dict("records")
    sv_records = sv.to_dict("records")
    audit = []
    quality = {
        "raw_gps_rows": len(obs), "retained_gps_rows": 0,
        "raw_sv_rows": len(sv), "retained_sv_rows": 0,
        "page_identity_available": False, "replay_page_groups": 0, "extra_page_copies": 0,
        "unparsed_dat_pages": [], "unparsed_dat_page_count": 0,
        "replayed_obs": 0, "replayed_sv": 0,
        "identical_csv_obs": 0, "identical_csv_sv": 0,
        "semantic_duplicate_obs": 0, "semantic_duplicate_sv": 0,
        "payload_duplicate_obs": 0, "payload_duplicate_sv": 0,
        "raw_wrapped_markers": 0, "wrapped_markers": 0,
        "raw_contextual_markers": 0, "contextual_markers": 0,
        "raw_clock_records": 0, "clock_records": 0, "unavailable_255": 0,
        "remaining_backwards": 0, "invalid_time_rows": 0,
        "unmatched_sv": 0, "issues": [], "audit": audit,
    }
    obs_fields = [name for name in obs if name != "source_row"]
    semantic_fields = [name for name in obs_fields if name != "line"]
    parent_fields = [name for name in _OBS_FIELDS if name in obs and name in sv]
    sv_fields = [name for name in sv if name != "source_row"]
    payload_fields = [name for name in sv_fields if name not in _OBS_FIELDS]
    obs_keys = [_key(row, parent_fields) for row in obs_records]
    semantic_keys = [_key(row, semantic_fields) for row in obs_records]
    obs_lines = [_source(row) for row in obs_records]
    sv_lines = [_source(row) for row in sv_records]
    times = _times(obs["datetime"])
    raw_ttf = _number(obs, "TTF")
    raw_num_sv = _number(obs, "numSV")
    raw_battery = _number(obs, "vbatt").where(lambda value: value.between(0, 255))

    pages, replay = {}, {}
    if dat_path is not None and Path(dat_path).is_file():
        pages, replay, quality["replay_page_groups"] = _dat_pages(Path(dat_path))
        quality["page_identity_available"] = True
        quality["extra_page_copies"] = len(replay)
    else:
        quality["issues"].append(
            "DAT unavailable: semantic observation deduplication is weaker than raw page identity.")
    # Layout/calendar hints only; never decode or recreate GPS/SV measurements.
    parsed_lines = set(obs_lines)
    for line, data in pages.items():
        if (data[0] & 0xFE) not in (0x90, 0x94):
            continue
        declared_length = data[1] | ((data[2] & 0x0F) << 8)
        header_length = 5 if data[0] & 1 else 3
        if declared_length <= header_length or line in parsed_lines:
            continue
        entry = {"line": line, "data_type": int(data[0]),
                 "declared_length": declared_length, "header_length": header_length,
                 "page_sha256": hashlib.sha256(data).hexdigest()}
        entry.update(_header_time_hints(data, declared_length, header_length))
        quality["unparsed_dat_pages"].append(entry)
        audit.append({"reason": "dat_page_without_parsed_observation", "source_row": None, **entry})
    quality["unparsed_dat_page_count"] = len(quality["unparsed_dat_pages"])
    if quality["unparsed_dat_page_count"]:
        quality["issues"].append(
            f"{quality['unparsed_dat_page_count']} nonempty legacy GPS DAT pages have no parsed observation; raw pages are preserved.")
    replay_obs = {i for i, line in enumerate(obs_lines) if line in replay}
    replay_sv = {i for i, line in enumerate(sv_lines) if line in replay}
    quality["replayed_obs"] = len(replay_obs)
    quality["replayed_sv"] = len(replay_sv)

    # Record every removed physical page, including CSV provenance and first copy.
    by_line_semantic = defaultdict(list)
    for i, line in enumerate(obs_lines):
        if i not in replay_obs:
            by_line_semantic[(line, semantic_keys[i])].append(i)
    aliases = {}
    for line, retained_line in replay.items():
        removed = [i for i, value in enumerate(obs_lines) if value == line]
        counterparts = []
        for i in removed:
            original = by_line_semantic.get((retained_line, semantic_keys[i]), [])
            if original:
                aliases[i] = original[0]
                counterparts.append(int(obs.iloc[original[0]]["source_row"]))
            else:
                counterparts.append(None)
        audit.append({
            "reason": "dat_page_replay", "line": line, "retained_line": retained_line,
            "source_rows": [int(obs.iloc[i]["source_row"]) for i in removed],
            "retained_source_rows": counterparts,
            "sv_source_rows": [int(sv.iloc[i]["source_row"]) for i, value in enumerate(sv_lines) if value == line],
            "page_sha256": hashlib.sha256(pages[line]).hexdigest(),
        })

    dropped_obs = set(replay_obs)
    exact_seen = {}
    for i, row in enumerate(obs_records):
        if i in dropped_obs:
            continue
        key = _key(row, obs_fields)
        if key in exact_seen:
            original = exact_seen[key]
            dropped_obs.add(i)
            aliases[i] = original
            quality["identical_csv_obs"] += 1
            audit.append({"reason": "identical_csv_observation", "source_row": int(row["source_row"]),
                          "line": obs_lines[i], "retained_source_row": int(obs.iloc[original]["source_row"])})
        else:
            exact_seen[key] = i

    # Parent keys refer to original raw rows before canonical cleaning.
    original_parents = defaultdict(list)
    for i, key in enumerate(obs_keys):
        if i not in replay_obs:
            original_parents[key].append(aliases.get(i, i))
    parent_lookup = {key: values[0] for key, values in original_parents.items()
                     if len(set(values)) == 1}
    parents = [parent_lookup.get(_key(row, parent_fields)) for row in sv_records]

    fallback_obs = set()
    if not quality["page_identity_available"]:
        seen_semantic = {}
        for i in obs.index:
            if i in dropped_obs:
                continue
            key = semantic_keys[i]
            if key in seen_semantic:
                original = seen_semantic[key]
                fallback_obs.add(i)
                aliases[i] = original
                audit.append({"reason": "semantic_duplicate_without_dat",
                              "source_row": int(obs.iloc[i]["source_row"]), "line": obs_lines[i],
                              "retained_source_row": int(obs.iloc[original]["source_row"])})
            else:
                seen_semantic[key] = i
        dropped_obs.update(fallback_obs)
    quality["semantic_duplicate_obs"] = len(fallback_obs)
    fallback_sv = {i for i, parent in enumerate(parents) if parent in fallback_obs and i not in replay_sv}
    quality["semantic_duplicate_sv"] = len(fallback_sv)
    dropped_sv = replay_sv | fallback_sv
    exact_sv_seen = {}
    for i, row in enumerate(sv_records):
        if i in dropped_sv:
            continue
        key = _key(row, sv_fields)
        if key in exact_sv_seen:
            original = exact_sv_seen[key]
            dropped_sv.add(i)
            quality["identical_csv_sv"] += 1
            audit.append({"reason": "identical_csv_satellite", "source_row": int(row["source_row"]),
                          "line": sv_lines[i], "retained_source_row": int(sv.iloc[original]["source_row"])})
        else:
            exact_sv_seen[key] = i

    payloads = defaultdict(list)
    for i, row in enumerate(sv_records):
        parent = parents[i]
        if i not in dropped_sv and parent is not None and parent not in dropped_obs:
            payloads[parent].append(_key(row, payload_fields))
    groups = defaultdict(list)
    for i, row in enumerate(obs_records):
        if i in dropped_obs or pd.isna(times.iloc[i]) or not payloads[i]:
            continue
        # Satellite count must agree with the available payload before it can
        # prove a duplicate. Partial/orphan data cannot establish identity.
        count = raw_num_sv.iloc[i]
        if pd.isna(count) or count != len(payloads[i]):
            continue
        key = (int(times.iloc[i].value), _text(row["vbatt"]), _text(row["numSV"]),
               tuple(sorted(payloads[i])))
        groups[key].append(i)
    payload_clock = set()
    payload_removed = set()
    for values in groups.values():
        known_ttf = {float(raw_ttf.iloc[i]) for i in values if pd.notna(raw_ttf.iloc[i])}
        if len(values) < 2 or len(known_ttf) < 2:
            continue
        original = values[0]
        payload_clock.update(values)
        for i in values[1:]:
            payload_removed.add(i)
            aliases[i] = original
            audit.append({"reason": "same_payload_different_ttf", "source_row": int(obs.iloc[i]["source_row"]),
                          "line": obs_lines[i], "retained_source_row": int(obs.iloc[original]["source_row"])})
    dropped_obs.update(payload_removed)
    quality["payload_duplicate_obs"] = len(payload_removed)
    payload_sv = {i for i, parent in enumerate(parents) if parent in payload_removed and i not in dropped_sv}
    quality["payload_duplicate_sv"] = len(payload_sv)
    dropped_sv.update(payload_sv)

    def canonical(index):
        seen = set()
        while index in aliases and index not in seen:
            seen.add(index)
            index = aliases[index]
        return index

    payload_clock = {canonical(i) for i in payload_clock}
    marker_kinds, decoded, clock_records = [], [], []
    for i, code in enumerate(raw_battery):
        strong_payload = canonical(i) in payload_clock
        data = pages.get(obs_lines[i])
        legacy_page = data is not None and (data[0] & 0xFE) == 0x90
        assumed_legacy = legacy_page or not quality["page_identity_available"]
        kind, voltage, clock = "", np.nan, False
        if pd.notna(code) and 156 <= code <= 254:
            kind, clock = "legacy_wrapped_candidate", True
            voltage = (code - 156) * 0.005263 + 3.5
        elif code == 255:
            kind = "unavailable_255"
            if legacy_page or strong_payload:
                kind, clock = "legacy_wrapped_255_candidate", True
                voltage = 99 * 0.005263 + 3.5
        elif strong_payload:
            kind, clock = "clock_payload_duplicate", True
            if pd.notna(code) and 0 <= code <= 52 and assumed_legacy:
                kind = "contextual_unwrapped_clock_candidate"
                voltage = (code + 100) * 0.005263 + 3.5
        marker_kinds.append(kind)
        decoded.append(voltage)
        clock_records.append(clock)
    wrapped = [kind in ("legacy_wrapped_candidate", "legacy_wrapped_255_candidate") for kind in marker_kinds]
    contextual = [kind == "contextual_unwrapped_clock_candidate" for kind in marker_kinds]
    quality["raw_wrapped_markers"] = sum(wrapped)
    quality["raw_contextual_markers"] = sum(contextual)
    quality["raw_clock_records"] = sum(clock_records)

    retained = [i for i in obs.index if i not in dropped_obs]
    gps = pd.DataFrame(index=retained)
    gps["source_row"] = obs.loc[retained, "source_row"]
    gps["obs_id"] = [f"{device_id}:gps:{int(row)}" for row in gps["source_row"]]
    gps["time"] = times.loc[retained]
    gps["start_time"] = _times(obs["startDatetime"]).loc[retained]
    gps["recorded_time"] = gps["time"]
    gps["recorded_start_time"] = gps["start_time"]
    gps["source_line"] = _number(obs, "line").loc[retained]
    gps["raw_ttf_s"] = raw_ttf.loc[retained]
    gps["ttf_s"] = gps["raw_ttf_s"].where(gps["raw_ttf_s"].ge(0))
    gps["num_sv"] = _number(obs, "numSV").loc[retained].where(lambda value: value.between(0, 255))
    gps["vbatt_raw"] = raw_battery.loc[retained]
    gps["clock_record"] = pd.Series([clock_records[i] for i in retained], index=retained, dtype=bool)
    gps["marker_kind"] = [marker_kinds[i] for i in retained]
    gps["decoded_marker_voltage_v"] = [decoded[i] for i in retained]
    valid_voltage = gps["vbatt_raw"].between(0, 152) & ~gps["clock_record"]
    gps["voltage_v"] = ((gps["vbatt_raw"] * 0.005263 + 3.5).where(valid_voltage)
                        if voltage_mode == "legacy" else np.nan)
    # A marker's derived start uses uncertain historical TTF units. Only
    # normal observations can introduce a normal-clock ordering boundary.
    normal = gps.loc[~gps["clock_record"]]
    normal_backwards = (normal["time"].diff().dt.total_seconds().lt(0)
                        | normal["start_time"].diff().dt.total_seconds().lt(0))
    backwards = pd.Series(False, index=gps.index, dtype=bool)
    backwards.loc[normal.index] = normal_backwards
    invalid = gps["time"].isna() | gps["start_time"].isna() | gps["start_time"].gt(gps["time"])
    gps["clock_anomaly"] = backwards | invalid
    segments = pd.Series(np.nan, index=gps.index, dtype=float)
    segments.loc[normal.index] = normal_backwards.cumsum()
    gps["clock_segment"] = segments.ffill().bfill().fillna(0).astype(int)
    gps["duplicate"] = False
    gps["cnr_mean"] = np.nan
    gps["cnr_peak"] = np.nan
    for i in gps.index[gps["clock_anomaly"]]:
        audit.append({"reason": "backward_ordering" if bool(backwards.loc[i]) else "invalid_calendar_time",
                      "source_row": int(gps.loc[i, "source_row"]), "line": obs_lines[i]})
    quality["remaining_backwards"] = int(backwards.sum())
    quality["invalid_time_rows"] = int(invalid.sum())
    quality["wrapped_markers"] = sum(wrapped[i] for i in retained)
    quality["contextual_markers"] = sum(contextual[i] for i in retained)
    quality["clock_records"] = int(gps["clock_record"].sum())
    quality["unavailable_255"] = int(gps["marker_kind"].eq("unavailable_255").sum())
    for i in retained:
        if marker_kinds[i]:
            audit.append({"reason": marker_kinds[i], "source_row": int(obs.iloc[i]["source_row"]),
                          "line": obs_lines[i], "raw_battery_code": None if pd.isna(raw_battery.iloc[i]) else int(raw_battery.iloc[i]),
                          "decoded_marker_voltage_v": None if pd.isna(decoded[i]) else float(decoded[i])})

    kept_sv = [i for i in sv.index if i not in dropped_sv]
    sats = pd.DataFrame(index=kept_sv)
    ids = gps["obs_id"].to_dict()
    sats["obs_id"] = [ids.get(parents[i]) for i in kept_sv]
    for name in ("ID", "CNR", "codePhase"):
        sats[name] = _number(sv, name).loc[kept_sv]
    sats["CNR"] = sats["CNR"].where(sats["CNR"].between(0, 255))
    sats["source_row"] = sv.loc[kept_sv, "source_row"]
    sats["source_line"] = _number(sv, "line").loc[kept_sv]
    sats["clock_record"] = pd.Series([bool(clock_records[parents[i]]) if parents[i] in ids else False for i in kept_sv], index=kept_sv, dtype=bool)
    sats["parent_status"] = np.where(sats["obs_id"].notna(), "matched", "unmatched")
    quality["unmatched_sv"] = int(sats["obs_id"].isna().sum())
    if not sats.empty:
        cnr = sats.dropna(subset=["obs_id"]).groupby("obs_id")["CNR"].agg(["mean", "max"])
        gps["cnr_mean"] = gps["obs_id"].map(cnr["mean"])
        gps["cnr_peak"] = gps["obs_id"].map(cnr["max"])
    quality["retained_gps_rows"] = len(gps)
    quality["retained_sv_rows"] = len(sats)
    if quality["remaining_backwards"]:
        quality["issues"].append("Remaining backward GPS ordering is not proof of a physical clock reset.")
    if quality["clock_records"]:
        quality["issues"].append("Clock-record candidates retain recorded timestamps/TTF; decoded marker voltage is diagnostic only.")
    if quality["unmatched_sv"]:
        quality["issues"].append("Unmatched satellite rows are retained outside per-observation CNR.")
    return gps[GPS_COLUMNS].reset_index(drop=True), sats.reset_index(drop=True), quality
