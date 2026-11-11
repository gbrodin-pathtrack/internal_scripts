"""Conservative cleaning of exported stats, preserving receipt evidence.

Receipt time is server UTC. Device event and temperature clocks stay recorded
and unshifted in returned frames; the configured device-clock offset is used
only for receipt comparisons here. A missing receipt is not a delivery verdict.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd


EVENT_COLUMNS = ["time", "kind", "confidence", "source_row", "seq_before", "seq_after"]
STATS_FIELDS = [
    "post_ok", "psm_ok", "voltage_v", "modem_voltage_v", "temp_c", "temp_time",
    "temp_age_s", "stats_time", "rsrp_dbm", "tx_dbm", "connect_s", "send_s",
    "ttfb_s", "http_status", "os_rc",
]
REGISTRATION_MEASUREMENTS = ["rsrp_dbm", "tx_dbm", "voltage_v", "psm", "energy"]
_METADATA = {
    "record_hash", "stats_hash", "device_id", "counter_epoch", "stats_valid", "stats_rejected",
    "rejection_reason", "stats_counted", "receipt_match_status", "matched_receipt_time",
    "matched_receipt_source_row", "receipt_candidate_count", "merged_source_rows",
    "merged_record_hashes", "stats_ts_values", "conflict_fields", "raw_record", "raw_row",
}


def _known(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "-", "unknown", "nan", "nat", "none"}
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return False
    return not bool(pd.isna(value))


def _canonical(value):
    if not _known(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _json(value):
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return _canonical(value)


def _number(value) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if np.isfinite(result) else np.nan


def _integer(value):
    number = _number(value)
    return int(number) if np.isfinite(number) and number >= 0 and number.is_integer() else None


def _sequence(value):
    sequence = _integer(value)
    return sequence if sequence is not None and sequence > 0 else None


def _series(frame, column):
    return frame[column] if column in frame else pd.Series(np.nan, index=frame.index)


def _times(frame, column):
    return pd.to_datetime(_series(frame, column), format="mixed", utc=True, errors="coerce").astype("datetime64[ns, UTC]")


def _metadata(column):
    return column in _METADATA or column.startswith("source_") or column.startswith("_")


def _exact_duplicates(frame, source_kind, quality):
    """Use original-row hashes, or full normalized values excluding metadata."""
    frame = frame.copy().reset_index(drop=True)
    columns = [column for column in frame if not _metadata(column)]
    seen, keep = {}, []
    for position, row in frame.iterrows():
        record_hash = row.get("record_hash")
        key = ("hash", str(record_hash)) if _known(record_hash) else (
            "normalized", tuple((column, _canonical(row[column])) for column in columns)
        )
        if key in seen:
            quality["audit"].append(_json({
                "action": "exact_duplicate_removed", "source_kind": source_kind,
                "source_row": row.get("source_row", position + 2),
                "kept_source_row": frame.iloc[seen[key]].get("source_row", seen[key] + 2),
                "record_hash": record_hash,
            }))
        else:
            seen[key] = position
            keep.append(position)
    return frame.iloc[keep].copy().reset_index(drop=True)


def _registration_key(row):
    # A boot+ label is not an absolute event identity across boots.
    when = row.get("time")
    if not _known(when) or not _known(row.get("time_text")):
        return None
    counter = _integer(row.get("reg_count"))
    duration = _number(row.get("duration_s"))
    if counter is None or not np.isfinite(duration) or duration < 0:
        return None
    if not _known(row.get("tier")) or not _known(row.get("outcome")):
        return None
    return (str(row["time_text"]).strip(), counter, str(row["tier"]).strip(),
            str(row["outcome"]).strip().lower(), duration)


def _clean_registrations(frame, quality):
    exact = _exact_duplicates(frame, "registration", quality)
    quality["exact_registration_duplicates"] = len(frame) - len(exact)
    if exact.empty:
        return exact
    groups = defaultdict(list)
    for position, row in exact.iterrows():
        identity = _registration_key(row)
        groups[("event", identity) if identity is not None else ("separate", position)].append(position)

    records = []
    for positions in groups.values():
        group = exact.iloc[positions]
        result = group.iloc[0].to_dict()
        source_rows = [row.get("source_row", position + 2) for position, row in group.iterrows()]
        hashes = [value for value in group.get("record_hash", pd.Series(dtype=object)) if _known(value)]
        links = list(dict.fromkeys(str(value) for value in group.get("stats_ts", pd.Series(dtype=object)) if _known(value)))
        conflict_fields, conflict_values = [], {}
        if len(group) > 1:
            quality["semantic_registration_removed"] += len(group) - 1
            for field in REGISTRATION_MEASUREMENTS:
                if field not in group:
                    continue
                known = [value for value in group[field] if _known(value)]
                distinct = list(dict.fromkeys(_canonical(value) for value in known))
                if len(distinct) == 1:
                    result[field] = known[0]
                elif len(distinct) > 1:
                    result[field] = "unknown" if field == "psm" else np.nan
                    conflict_fields.append(field)
                    conflict_values[field] = distinct
            quality["audit"].append(_json({
                "action": "semantic_registration_merge", "source_rows": source_rows,
                "record_hashes": hashes, "identity": _registration_key(group.iloc[0]),
                "conflict_fields": conflict_fields, "conflicting_values": conflict_values,
                "stats_ts_values": links,
            }))
            if conflict_fields:
                quality["registration_conflicts"] += 1
        if links:
            result["stats_ts"] = links[0]
        result["merged_source_rows"] = source_rows
        result["merged_record_hashes"] = list(dict.fromkeys(hashes))
        result["stats_ts_values"] = links
        result["conflict_fields"] = conflict_fields
        records.append(result)
    result = pd.DataFrame(records)
    if "time" in result:
        result["time"] = _times(result, "time")
    return result


def _counter_epochs(uploads, quality):
    epochs = pd.Series(pd.NA, index=uploads.index, dtype="Int64")
    events = []
    ordered = uploads.loc[uploads["time"].notna()].sort_values("time", kind="stable")
    epoch, previous = 0, None
    for position, row in ordered.iterrows():
        sequence = _sequence(row.get("upload_seq"))
        if sequence is not None:
            if previous is not None and sequence < previous:
                epoch += 1
                kind = "counter_restart" if sequence == 1 else "sequence_regression"
                event = {"time": row["time"], "kind": kind,
                         "confidence": "counter_only" if sequence == 1 else "sequence_only",
                         "source_row": row.get("source_row", position + 2),
                         "seq_before": previous, "seq_after": sequence}
                events.append(event)
                quality["audit"].append(_json({"action": kind + "_candidate", **event}))
            previous = sequence
        epochs.loc[position] = epoch
    uploads["counter_epoch"] = epochs
    quality["counter_restarts"] = sum(event["kind"] == "counter_restart" for event in events)
    quality["sequence_regressions"] = sum(event["kind"] == "sequence_regression" for event in events)
    result = pd.DataFrame(events, columns=EVENT_COLUMNS)
    result["time"] = _times(result, "time")
    return result


def _receipt_stats(uploads, quality, future_lead_seconds, device_clock_offset_seconds):
    uploads["time"] = _times(uploads, "time")
    uploads["temp_time"] = _times(uploads, "temp_time")
    age = pd.to_numeric(_series(uploads, "temp_age_s"), errors="coerce")
    age = age.where(np.isfinite(age) & age.ge(0))
    uploads["temp_age_s"] = age
    uploads["stats_time"] = uploads["temp_time"] + pd.to_timedelta(age, unit="s", errors="coerce")
    offset = pd.Timedelta(seconds=device_clock_offset_seconds)
    temperature_lead = (uploads["temp_time"] - offset - uploads["time"]).dt.total_seconds()
    stats_lead = (uploads["stats_time"] - offset - uploads["time"]).dt.total_seconds()
    bad_temperature = temperature_lead.gt(future_lead_seconds)
    bad_stats = stats_lead.gt(future_lead_seconds)
    rejected = bad_temperature | bad_stats
    has_stats = pd.Series(False, index=uploads.index)
    for field in STATS_FIELDS:
        if field in uploads:
            has_stats |= pd.Series([_known(value) for value in uploads[field]], index=uploads.index, dtype=bool)
    uploads["stats_valid"] = has_stats & ~rejected
    uploads["stats_rejected"] = rejected
    uploads["rejection_reason"] = ""
    uploads["stats_counted"] = uploads["stats_valid"].copy()
    for position, row in uploads.loc[rejected].iterrows():
        reasons = []
        if bad_temperature.loc[position]:
            reasons.append("temperature_after_receipt")
        if bad_stats.loc[position]:
            reasons.append("inferred_stats_after_receipt")
        uploads.loc[position, "rejection_reason"] = ";".join(reasons)
        quality["audit"].append(_json({
            "action": "receipt_stats_rejected", "source_kind": "upload_receipt",
            "source_row": row.get("source_row", position + 2), "record_hash": row.get("record_hash"),
            "upload_seq": row.get("upload_seq"), "receipt_time": row["time"],
            "temperature_time_recorded": row["temp_time"], "stats_time_recorded": row["stats_time"],
            "temperature_lead_seconds": temperature_lead.loc[position],
            "stats_lead_seconds": stats_lead.loc[position], "reasons": reasons,
        }))
    for field in STATS_FIELDS:
        if field in uploads:
            uploads.loc[rejected, field] = pd.NaT if field in {"temp_time", "stats_time"} else np.nan
    quality["rejected_receipt_stats"] = int(rejected.sum())


def _count_receipt_stats_once(uploads, quality):
    fields = [field for field in STATS_FIELDS if field in uploads]
    seen = {}
    for position, row in uploads.iterrows():
        sequence = _sequence(row.get("upload_seq"))
        epoch = row["counter_epoch"]
        if not row["stats_valid"] or sequence is None or pd.isna(epoch):
            continue
        stats_hash = row.get("stats_hash")
        signature = (int(epoch), sequence, "hash", str(stats_hash)) if _known(stats_hash) else (
            int(epoch), sequence, "normalized", tuple((field, _canonical(row[field])) for field in fields)
        )
        if signature in seen:
            uploads.loc[position, "stats_counted"] = False
            quality["receipt_stats_deduplicated"] += 1
            quality["audit"].append(_json({
                "action": "repeated_receipt_stats_not_counted", "source_row": row.get("source_row", position + 2),
                "kept_source_row": uploads.iloc[seen[signature]].get("source_row", seen[signature] + 2),
                "counter_epoch": int(epoch), "upload_seq": sequence,
            }))
        else:
            seen[signature] = position


def _match_failed_receipts(uploads, failures, quality, receipt_window_seconds, device_clock_offset_seconds):
    failures["time"] = _times(failures, "time")
    failures["receipt_match_status"] = "no_matching_receipt"
    failures["matched_receipt_time"] = pd.Series(pd.NaT, index=failures.index, dtype="datetime64[ns, UTC]")
    failures["matched_receipt_source_row"] = np.nan
    failures["receipt_candidate_count"] = 0
    receipt_sequences = pd.to_numeric(_series(uploads, "upload_seq"), errors="coerce")
    for position, row in failures.iterrows():
        sequence = _sequence(row.get("upload_seq"))
        candidates = uploads.iloc[0:0]
        when = row["time"]
        if sequence is not None and pd.notna(when):
            event_utc = when - pd.Timedelta(seconds=device_clock_offset_seconds)
            delta = (uploads["time"] - event_utc).dt.total_seconds()
            candidates = uploads.loc[receipt_sequences.eq(sequence) & delta.abs().le(receipt_window_seconds)]
        count = len(candidates)
        failures.loc[position, "receipt_candidate_count"] = count
        if count == 1:
            receipt = candidates.iloc[0]
            failures.loc[position, "receipt_match_status"] = "received"
            failures.loc[position, "matched_receipt_time"] = receipt["time"]
            failures.loc[position, "matched_receipt_source_row"] = receipt.get("source_row", np.nan)
        elif count > 1:
            failures.loc[position, "receipt_match_status"] = "ambiguous"
        quality["audit"].append(_json({
            "action": "failed_attempt_receipt_evidence", "source_row": row.get("source_row", position + 2),
            "record_hash": row.get("record_hash"), "upload_seq": sequence,
            "status": failures.loc[position, "receipt_match_status"],
            "reason": "unknown_event_time_or_sequence" if sequence is None or pd.isna(when) else "same_sequence_time_window",
            "candidates": [{"source_row": item.get("source_row"), "time": item["time"]} for _, item in candidates.iterrows()],
        }))
    statuses = failures["receipt_match_status"]
    quality["failed_received"] = int(statuses.eq("received").sum())
    quality["failed_unmatched"] = int(statuses.eq("no_matching_receipt").sum())
    quality["failed_ambiguous"] = int(statuses.eq("ambiguous").sum())
    quality["failed_untimed"] = int(failures["time"].isna().sum())


def clean_stats_frames(device_id, uploads, failures, registrations, *, future_lead_seconds=600,
                       receipt_window_seconds=300, device_clock_offset_seconds=18):
    """Return cleaned copies, counter candidates and a JSON-safe quality audit.

    semantic_registration_removed counts additional removals AFTER exact
    duplicate removal. Counter decreases are candidates, not proven reboots.
    A "received" failure retains its original failed transport result.
    """
    for name, value in (("Future-stat lead", future_lead_seconds), ("Receipt window", receipt_window_seconds)):
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and nonnegative")
    if not np.isfinite(device_clock_offset_seconds):
        raise ValueError("Device clock offset must be finite")
    quality = {
        "device_id": str(device_id), "raw_uploads": len(uploads), "raw_failures": len(failures),
        "raw_registrations": len(registrations), "exact_failed_duplicates": 0,
        "exact_registration_duplicates": 0, "semantic_registration_removed": 0,
        "registration_conflicts": 0, "rejected_receipt_stats": 0,
        "receipt_stats_deduplicated": 0, "counter_restarts": 0, "sequence_regressions": 0,
        "failed_received": 0, "failed_unmatched": 0, "failed_ambiguous": 0, "failed_untimed": 0,
        "future_lead_seconds": float(future_lead_seconds),
        "receipt_window_seconds": float(receipt_window_seconds),
        "device_clock_offset_seconds": float(device_clock_offset_seconds), "audit": [],
    }
    uploads = uploads.copy().reset_index(drop=True)
    failures_clean = _exact_duplicates(failures, "failed_attempt", quality)
    quality["exact_failed_duplicates"] = len(failures) - len(failures_clean)
    registrations_clean = _clean_registrations(registrations, quality)
    uploads["time"] = _times(uploads, "time")
    events = _counter_epochs(uploads, quality)
    _receipt_stats(uploads, quality, future_lead_seconds, device_clock_offset_seconds)
    _count_receipt_stats_once(uploads, quality)
    _match_failed_receipts(uploads, failures_clean, quality, receipt_window_seconds, device_clock_offset_seconds)
    return uploads, failures_clean, registrations_clean, events, _json(quality)
