"""Descriptive GPS, communications and fleet diagnostics on cleaned frames.

Cadence is inferred from recorded intervals, not decoded device policy. Gap
context is temporal evidence, not a cause. Registration coverage is its outer
record span, not a guarantee of complete logging. The analytic timeout
baseline assumes uniform possible start times inside that recorded overlap;
it does not remove voltage/cadence confounding or produce a significance test.
All input times must already be normalized to UTC by the loader. This module
never applies a second device-clock offset; recorded values remain provenance.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
import math

import numpy as np
import pandas as pd


GAP_COLUMNS = [
    "time", "source_row", "obs_id", "previous_obs_id", "start", "end", "duration_s",
    "start_basis", "end_basis", "availability_basis",
    "voltage_before_v", "voltage_after_v", "boundary_voltage_v", "expected_interval_s",
    "cadence_multiple", "cadence_source", "absolute_long", "cadence_gap",
    "timeout_count", "failure_count", "receipt_count", "restart_count", "clock_marker_count",
    "low_voltage_boundary", "registration_coverage", "gap_class",
    "unparsed_page_overlap", "unparsed_page_count", "unparsed_source_lines",
    "timeout_baseline_eligible", "timeout_baseline_probability",
]
OUTAGE_COLUMNS = ["start", "end", "duration_s", "gps_count", "ongoing_at_export", "kind"]
MONTHLY_COLUMNS = [
    "month", "reg_attempts", "successes", "timeouts", "reg_successes", "reg_timeouts", "hot_attempts", "hot_timeouts",
    "cold_attempts", "cold_timeouts", "hot_good_v_attempts", "hot_good_v_timeouts",
    "gps_count", "median_cadence_s", "cadence_samples", "median_voltage_v", "voltage_samples",
    "receipts", "post_failures",
]
FLEET_COLUMNS = [
    "date", "timeout_device_count", "registration_device_count", "receipt_device_count",
    "gps_device_count", "gap_device_count", "counter_restart_device_count", "clock_marker_device_count",
]


def _series(frame, column):
    return frame[column] if column in frame else pd.Series(np.nan, index=frame.index)


def _numbers(frame, column):
    values = pd.to_numeric(_series(frame, column), errors="coerce")
    return values.where(np.isfinite(values))


def _times(frame, column="time"):
    return pd.to_datetime(_series(frame, column), format="mixed", utc=True, errors="coerce").astype("datetime64[ns, UTC]")


def _timestamp(value):
    return pd.to_datetime(value, utc=True, errors="coerce")


def _safe(value):
    return float(value) if value is not None and pd.notna(value) and np.isfinite(value) else None


def _iso(value):
    return value.isoformat() if value is not None and pd.notna(value) else None


def _ns(values):
    return sorted(int(pd.Timestamp(value).value) for value in values if pd.notna(value))


def _count(times_ns, start, end):
    """Events in (start, end], to avoid counting one boundary twice."""
    return bisect_right(times_ns, int(end.value)) - bisect_right(times_ns, int(start.value))


def normal_gps(gps):
    """Return an independent view without clock-recovery telemetry records."""
    marker = gps["clock_record"].fillna(False).astype(bool) if "clock_record" in gps else pd.Series(False, index=gps.index)
    return gps.loc[~marker].copy()


def gps_intervals(gps):
    """Normal GPS attempt-start intervals in source order, within clock segments.

    Negative/unknown intervals stay unavailable. A prior anomaly flag does not
    erase the following interval: quality cleaning already identifies markers
    and retained clock segments. No chronological sorting hides backwards steps.
    """
    result = normal_gps(gps)
    result["time"] = _times(result, "time")
    result["start_time"] = _times(result, "start_time")
    if "clock_segment" not in result:
        result["clock_segment"] = 0
    result["clock_segment"] = result["clock_segment"].fillna(0)
    result["interval_s"] = result.groupby("clock_segment", sort=False)["start_time"].diff().dt.total_seconds()
    result["interval_s"] = result["interval_s"].where(result["interval_s"].ge(0) & np.isfinite(result["interval_s"]))
    return result


def gps_availability(gps):
    """Canonical GPS/TIME availability points, distinct from normal cadence.

    Normal observations use their attempt start. Clock-recovery records still
    establish a GPS TIME point, but their TTF/start encoding is uncertain, so
    their measurement timestamp is used instead. No points are reconstructed.
    """
    result = gps.copy()
    marker = result["clock_record"].fillna(False).astype(bool) if "clock_record" in result else pd.Series(False, index=result.index)
    result["time"] = _times(result, "time")
    result["availability_time"] = _times(result, "start_time")
    result.loc[marker, "availability_time"] = result.loc[marker, "time"]
    if "voltage_v" in result:
        result.loc[marker, "voltage_v"] = np.nan
    result["availability_basis"] = np.where(marker, "clock_record_time", "attempt_start")
    if "clock_segment" not in result:
        result["clock_segment"] = 0
    result["clock_segment"] = result["clock_segment"].fillna(0)
    result["interval_s"] = result.groupby("clock_segment", sort=False)["availability_time"].diff().dt.total_seconds()
    result["interval_s"] = result["interval_s"].where(result["interval_s"].ge(0) & np.isfinite(result["interval_s"]))
    return result


def infer_service_start(devices):
    """Infer only a supported fleet-common small initial fragment / long gap.

    A candidate requires a >=3-day gap, a preceding fragment spanning <=2
    days and at most max(50, ceil(1% of observations)) records, and same-day
    resumption on at least max(2, ceil(half of GPS-bearing devices)).
    """
    candidates, gps_devices = [], 0
    for device in devices:
        frame = normal_gps(device.gps)
        timed = _times(frame).dropna().sort_values(kind="stable")
        if timed.empty:
            continue
        gps_devices += 1
        limit = max(50, math.ceil(len(timed) * 0.01))
        values = timed.tolist()
        for index in range(1, min(len(values), limit + 1)):
            length = (values[index] - values[index - 1]).total_seconds()
            fragment_span = (values[index - 1] - values[0]).total_seconds()
            if length >= 3 * 86400 and fragment_span <= 2 * 86400:
                candidates.append({
                    "device_id": str(device.device_id), "resumption_day": values[index].floor("D"),
                    "resumption_time": values[index], "fragment_rows": index,
                    "fragment_limit": limit, "fragment_span_s": fragment_span, "gap_s": length,
                })
                break
    support_required = max(2, math.ceil(gps_devices / 2))
    support = Counter(item["resumption_day"] for item in candidates)
    qualifying = sorted(((count, day) for day, count in support.items() if count >= support_required),
                        key=lambda item: (-item[0], item[1]))
    metadata = {
        "method": "fleet-common initial small-fragment/long-gap inference",
        "gps_devices": gps_devices, "support_required": support_required,
        "candidates": [{**item, "resumption_day": _iso(item["resumption_day"]),
                        "resumption_time": _iso(item["resumption_time"])} for item in candidates],
    }
    if not qualifying:
        return None, {**metadata, "reason": "No resumption day meets fleet support; no automatic service boundary"}
    if len(qualifying) > 1 and qualifying[0][0] == qualifying[1][0]:
        return None, {**metadata, "reason": "Equally supported resumption days are ambiguous; no automatic service boundary"}
    count, day = qualifying[0]
    return day, {**metadata, "service_start": _iso(day), "support": count,
                 "reason": "Supported common resumption day; its midnight is an inferred boundary, not a proven deployment time"}


def _mode_interval(frame):
    if frame.empty:
        return np.nan
    counts = frame["_rounded"].value_counts()
    if counts.empty or counts.max() < 3:
        return np.nan
    centre = min(counts[counts.eq(counts.max())].index)
    return float(frame.loc[frame["_rounded"].eq(centre), "interval_s"].median())


def _cadence(intervals, gap_seconds):
    """Supported local cadence first, with voltage/history fallback only.

    The current interval never supplies its own estimate. A sustained cadence
    change can be supported by its neighbors even at the same voltage, while
    an isolated double interval amid regular intervals remains diagnostic.
    """
    result = intervals.copy()
    result["_raw_before"] = _numbers(result, "vbatt_raw").groupby(result["clock_segment"], sort=False).shift()
    result["_rounded"] = (result["interval_s"] / 20.0).round() * 20.0
    positive = result.loc[result["interval_s"].gt(0) & result["_rounded"].gt(0)]
    counts = positive["_rounded"].value_counts()
    regular_centres = counts[counts.ge(max(3, math.ceil(len(positive) * 0.01)))].index
    base_centres = counts[counts.ge(max(3, math.ceil(len(positive) * 0.05)))].index
    base = float(min(base_centres)) if len(base_centres) else (
        float(min(regular_centres)) if len(regular_centres) else np.nan
    )
    pool = positive.loc[positive["_rounded"].isin(regular_centres)].copy()
    if np.isfinite(base):
        pool = pool.loc[pool["interval_s"].ge(base * 0.75)]
    # Retrospective local evidence takes precedence over a full-history
    # voltage-bin mode. Discard the candidate being evaluated, catchups and
    # absolute-long intervals from its surrounding evidence.
    local_models = {}
    candidate = result["interval_s"].gt(0) & result["interval_s"].le(gap_seconds) & result["_rounded"].gt(0)
    if np.isfinite(base):
        candidate &= result["interval_s"].ge(base * 0.75)
    rounded_values = result["_rounded"].to_numpy(dtype=float)
    interval_values = result["interval_s"].to_numpy(dtype=float)
    candidate_values = candidate.to_numpy(dtype=bool)
    for positions in result.groupby("clock_segment", sort=False).indices.values():
        for local_index, position in enumerate(positions):
            neighbors = [int(positions[index]) for index in range(max(0, local_index - 6), min(len(positions), local_index + 7))
                         if index != local_index and candidate_values[positions[index]]]
            if len(neighbors) < 2:
                continue
            centers = Counter(rounded_values[index] for index in neighbors)
            current_center = rounded_values[position]
            if candidate_values[position] and centers.get(current_center, 0) >= 2:
                chosen, method = current_center, "local_supported_tier"
            elif centers and max(centers.values()) >= 2:
                largest_count = max(centers.values())
                chosen = max(center for center, count in centers.items() if count == largest_count)
                method = "local_mode"
            else:
                continue
            value = float(np.median([interval_values[index] for index in neighbors if rounded_values[index] == chosen]))
            local_models[int(position)] = (value, method)
    pool["_bin"] = np.floor(pool["_raw_before"] / 5.0) * 5.0
    models = {}
    for bucket, group in pool.dropna(subset=["_bin"]).groupby("_bin", sort=True):
        if len(group) >= 5:
            value = _mode_interval(group)
            if np.isfinite(value):
                models[bucket] = (value, "voltage_bin_mode")
    history = defaultdict(list)
    expected, sources = [], []
    for position, (_, row) in enumerate(result.iterrows()):
        value, source = local_models.get(position, (np.nan, "unknown"))
        raw = row["_raw_before"]
        bucket = math.floor(raw / 5.0) * 5.0 if pd.notna(raw) else np.nan
        if not np.isfinite(value) and bucket in models:
            value, source = models[bucket]
        elif not np.isfinite(value) and pd.notna(bucket):
            nearby = pool.loc[pool["_bin"].sub(bucket).abs().le(5)]
            if len(nearby) >= 8:
                value = _mode_interval(nearby)
                if np.isfinite(value):
                    source = "nearby_voltage_mode"
        previous = history[row["clock_segment"]]
        if not np.isfinite(value) and len(previous) >= 3:
            value, source = float(np.median(previous[-12:])), "trailing_median"
        if not np.isfinite(value) and np.isfinite(base):
            value, source = base, "dominant_interval"
        expected.append(value)
        sources.append(source)
        interval = row["interval_s"]
        regular = row["_rounded"] in regular_centres if len(regular_centres) else pd.notna(interval) and 0 < interval <= gap_seconds
        if pd.notna(interval) and interval > 0 and regular:
            previous.append(float(interval))
    result["expected_interval_s"] = expected
    result["cadence_source"] = sources
    return result


def uniform_start_timeout_probability(timeout_times, duration_s, start_min, start_max):
    """Analytic probability of a timeout in a uniformly placed [s, s+L].

    Possible starts are [start_min, start_max]. The union of each timeout's
    [timeout-L, timeout] interval is clipped to that domain. None means no
    supported start domain, not zero expected events.
    """
    if not np.isfinite(duration_s) or duration_s < 0:
        raise ValueError("Window duration must be finite and nonnegative")
    first, last = _timestamp(start_min), _timestamp(start_max)
    if pd.isna(first) or pd.isna(last) or last <= first:
        return None
    duration_ns = int(round(float(duration_s) * 1e9))
    low, high = int(first.value), int(last.value)
    windows = []
    for timeout in timeout_times:
        when = _timestamp(timeout)
        if pd.isna(when):
            continue
        end = int(when.value)
        start, end = max(low, end - duration_ns), min(high, end)
        if end > start:
            windows.append((start, end))
    covered, current_start, current_end = 0, None, None
    for start, end in sorted(windows):
        if current_start is None:
            current_start, current_end = start, end
        elif start <= current_end:
            current_end = max(current_end, end)
        else:
            covered += current_end - current_start
            current_start, current_end = start, end
    if current_start is not None:
        covered += current_end - current_start
    return float(covered / (high - low))


def _unparsed_hints(device):
    hints = []
    quality = getattr(device, "quality", {})
    for entry in quality.get("gps", {}).get("unparsed_dat_pages", []):
        first = _timestamp(entry.get("first_time_utc"))
        last = _timestamp(entry.get("last_time_utc"))
        if pd.isna(first) and pd.isna(last):
            continue
        first = last if pd.isna(first) else first
        last = first if pd.isna(last) else last
        if last < first:
            first, last = last, first
        hints.append((first, last, entry.get("line", entry.get("source_line", entry.get("physical_line")))))
    return hints


def _build_gaps(device, gap_seconds, low_voltage):
    cadence = _cadence(gps_intervals(device.gps), gap_seconds)
    intervals = gps_availability(device.gps)
    # Cadence is estimated exclusively from normal observations. Canonical
    # TIME points can bound availability gaps without entering performance.
    for column in ("expected_interval_s", "cadence_source"):
        intervals[column] = cadence[column].reindex(intervals.index)
        carried = intervals.groupby("clock_segment", sort=False)[column].ffill()
        marker = intervals["availability_basis"].eq("clock_record_time")
        intervals.loc[marker, column] = carried.loc[marker]
    intervals["cadence_source"] = intervals["cadence_source"].fillna("unknown")
    intervals["_previous_obs"] = _series(intervals, "obs_id").groupby(intervals["clock_segment"], sort=False).shift()
    intervals["_previous_basis"] = intervals.groupby("clock_segment", sort=False)["availability_basis"].shift()
    intervals["_voltage_before"] = _numbers(intervals, "voltage_v").groupby(intervals["clock_segment"], sort=False).shift()
    unparsed_hints = _unparsed_hints(device)
    reg_time = _times(device.registrations)
    outcomes = _series(device.registrations, "outcome").fillna("").astype(str).str.lower()
    timeout_ns = _ns(reg_time.loc[outcomes.eq("timeout")])
    failed = _numbers(device.failures, "post_ok").eq(0)
    failure_ns = _ns(_times(device.failures).loc[failed])
    receipt_ns = _ns(_times(device.uploads))
    kinds = _series(device.events, "kind").fillna("").astype(str)
    restart_ns = _ns(_times(device.events).loc[kinds.eq("counter_restart")])
    marker_ns = _ns(_times(device.events).loc[kinds.eq("clock_recovery")])
    first_reg, last_reg = reg_time.min(), reg_time.max()
    rows = []
    for _, record in intervals.loc[intervals["interval_s"].notna()].iterrows():
        length, end = float(record["interval_s"]), record["availability_time"]
        start = end - pd.Timedelta(seconds=length)
        before, after = record["_voltage_before"], record.get("voltage_v", np.nan)
        low = bool((pd.notna(before) and before <= low_voltage) or (pd.notna(after) and after <= low_voltage))
        expected = record["expected_interval_s"]
        absolute = length > gap_seconds
        relative = bool(pd.notna(expected) and expected > 0 and length > 1.5 * expected + 20.0)
        timeouts = _count(timeout_ns, start, end)
        failures = _count(failure_ns, start, end)
        receipts = _count(receipt_ns, start, end)
        restarts = _count(restart_ns, start, end)
        markers = _count(marker_ns, start, end)
        coverage = bool(pd.notna(first_reg) and pd.notna(last_reg) and start >= first_reg and end <= last_reg)
        overlapping = [(first, last, line) for first, last, line in unparsed_hints if last > start and first < end]
        unparsed = bool(overlapping)
        source_lines = list(dict.fromkeys(line for _, _, line in overlapping if line is not None and pd.notna(line)))
        if unparsed:
            category = "unparsed_source"
        elif not absolute and not relative:
            category = "regular"
        elif restarts or markers:
            category = "restart_or_clock"
        elif timeouts and low:
            category = "timeout_and_low"
        elif timeouts:
            category = "timeout"
        elif low:
            category = "low_voltage"
        elif not coverage:
            category = "outside_reg_span"
        else:
            category = "unexplained"
        rows.append({
            "time": record["time"], "source_row": record.get("source_row"), "obs_id": record.get("obs_id"),
            "previous_obs_id": record["_previous_obs"], "start": start, "end": end, "duration_s": length,
            "start_basis": record["_previous_basis"], "end_basis": record["availability_basis"],
            "availability_basis": record["availability_basis"],
            "voltage_before_v": before, "voltage_after_v": after, "boundary_voltage_v": before,
            "expected_interval_s": expected, "cadence_multiple": length / expected if pd.notna(expected) and expected > 0 else np.nan,
            "cadence_source": record["cadence_source"], "absolute_long": absolute, "cadence_gap": relative,
            "timeout_count": timeouts, "failure_count": failures, "receipt_count": receipts,
            "restart_count": restarts, "clock_marker_count": markers,
            "low_voltage_boundary": low, "registration_coverage": coverage, "gap_class": category,
            "unparsed_page_overlap": unparsed, "unparsed_page_count": len(overlapping),
            "unparsed_source_lines": source_lines,
            "timeout_baseline_eligible": False, "timeout_baseline_probability": np.nan,
        })
    result = pd.DataFrame(rows, columns=GAP_COLUMNS)
    for column in ("time", "start", "end"):
        result[column] = _times(result, column)
    return result


def _timeout_baseline(device):
    gps_times = gps_availability(device.gps)["availability_time"].dropna()
    reg_times = _times(device.registrations).dropna()
    eligible, hits, expected_hits = 0, 0, 0.0
    if len(gps_times) and len(reg_times):
        overlap_start = max(gps_times.min(), reg_times.min())
        overlap_end = min(gps_times.max(), reg_times.max())
        outcomes = _series(device.registrations, "outcome").fillna("").astype(str).str.lower()
        timeouts = _times(device.registrations).loc[outcomes.eq("timeout")].dropna().tolist()
        supported = device.gaps["absolute_long"].astype(bool) & ~device.gaps["unparsed_page_overlap"].astype(bool)
        for index, gap in device.gaps.loc[supported].iterrows():
            if gap["start"] < overlap_start or gap["end"] > overlap_end:
                continue
            month_start = gap["start"].normalize().replace(day=1)
            month_end = month_start + pd.offsets.MonthBegin(1)
            first = max(month_start, overlap_start)
            last = min(month_end, overlap_end - pd.Timedelta(seconds=float(gap["duration_s"])))
            probability = uniform_start_timeout_probability(timeouts, gap["duration_s"], first, last)
            if probability is None:
                continue
            eligible += 1
            hits += int(gap["timeout_count"] > 0)
            expected_hits += probability
            device.gaps.loc[index, "timeout_baseline_eligible"] = True
            device.gaps.loc[index, "timeout_baseline_probability"] = probability
    return {
        "gap_timeout_eligible": eligible, "gap_timeout_hits": hits,
        "gap_timeout_expected_hits": expected_hits if eligible else None,
        "observed_gap_timeout_percent": 100.0 * hits / eligible if eligible else None,
        "expected_gap_timeout_percent": 100.0 * expected_hits / eligible if eligible else None,
        "timeout_baseline_method": "Analytic union of timeout-hit start intervals; uniform starts in the gap-start month within recorded GPS/registration overlap, conditioned on each observed absolute-gap duration",
        "timeout_baseline_limits": "Outer spans do not prove complete logs; uneven coverage, voltage and cadence can confound the comparison. No random simulation, p-value or causal claim.",
    }


def _export_time(devices, supplied):
    if supplied is not None:
        result = _timestamp(supplied)
        if pd.isna(result):
            raise ValueError("Export reference must be a valid UTC timestamp")
        return result
    receipts = [value for device in devices for value in _times(device.uploads).dropna()]
    if receipts:
        return max(receipts)
    observed = []
    for device in devices:
        for frame in (normal_gps(device.gps), device.registrations, device.failures):
            observed.extend(_times(frame).dropna())
    return max(observed) if observed else None


def _receipt_outages(device, reference, threshold):
    rows = []
    if reference is None:
        return pd.DataFrame(columns=OUTAGE_COLUMNS)
    gps_times = _times(normal_gps(device.gps))
    gps_ns = _ns(gps_times)
    observed = [value for frame in (normal_gps(device.gps), device.registrations, device.failures)
                for value in _times(frame).dropna() if value <= reference]
    receipts = sorted(_times(device.uploads).loc[lambda values: values.notna() & values.le(reference)].tolist())
    if receipts:
        observed.append(receipts[0])
    if not observed:
        return pd.DataFrame(columns=OUTAGE_COLUMNS)
    beginning = min(observed)
    spans = []
    if not receipts:
        spans.append((beginning, reference, "no_receipts", True))
    else:
        spans.append((beginning, receipts[0], "leading", False))
        spans.extend((left, right, "internal", False) for left, right in zip(receipts, receipts[1:]))
        spans.append((receipts[-1], reference, "trailing", True))
    for start, end, kind, ongoing in spans:
        duration = (end - start).total_seconds()
        if duration > threshold:
            rows.append({"start": start, "end": end, "duration_s": duration,
                         "gps_count": _count(gps_ns, start, end),
                         "ongoing_at_export": ongoing, "kind": kind})
    return pd.DataFrame(rows, columns=OUTAGE_COLUMNS)


def _months(times):
    return times.dt.tz_localize(None).dt.to_period("M").dt.to_timestamp().dt.tz_localize("UTC")


def _monthly(device):
    gps = normal_gps(device.gps)
    intervals = gps_intervals(device.gps)
    gps_month, reg_month = _months(_times(gps)), _months(_times(device.registrations))
    receipt_month, failure_month = _months(_times(device.uploads)), _months(_times(device.failures))
    observed_months = pd.concat([gps_month, reg_month, receipt_month, failure_month], ignore_index=True).dropna()
    if observed_months.empty:
        return pd.DataFrame(columns=MONTHLY_COLUMNS)
    outcomes = _series(device.registrations, "outcome").fillna("").astype(str).str.lower()
    tier = _series(device.registrations, "tier").fillna("").astype(str).str.upper()
    voltage = _numbers(device.registrations, "voltage_v")
    hot, cold = tier.str.endswith("HOT"), tier.str.endswith("COLD")
    good_v = voltage.between(4.0, 4.15, inclusive="both")
    rows = []
    for month in pd.date_range(observed_months.min(), observed_months.max(), freq="MS"):
        reg = reg_month.eq(month)
        gp = gps_month.eq(month)
        cadence = _numbers(intervals.loc[gp], "interval_s").loc[lambda values: values.gt(0)].dropna()
        volts = _numbers(gps.loc[gp], "voltage_v").dropna()
        rows.append({
            "month": month, "reg_attempts": int(reg.sum()), "successes": int((reg & outcomes.eq("success")).sum()),
            "timeouts": int((reg & outcomes.eq("timeout")).sum()),
            "reg_successes": int((reg & outcomes.eq("success")).sum()),
            "reg_timeouts": int((reg & outcomes.eq("timeout")).sum()),
            "hot_attempts": int((reg & hot).sum()), "hot_timeouts": int((reg & hot & outcomes.eq("timeout")).sum()),
            "cold_attempts": int((reg & cold).sum()), "cold_timeouts": int((reg & cold & outcomes.eq("timeout")).sum()),
            "hot_good_v_attempts": int((reg & hot & good_v).sum()),
            "hot_good_v_timeouts": int((reg & hot & good_v & outcomes.eq("timeout")).sum()),
            "gps_count": int(gp.sum()), "median_cadence_s": float(cadence.median()) if len(cadence) >= 3 else np.nan,
            "cadence_samples": len(cadence), "median_voltage_v": float(volts.median()) if len(volts) >= 3 else np.nan,
            "voltage_samples": len(volts), "receipts": int(receipt_month.eq(month).sum()),
            "post_failures": int((failure_month.eq(month) & _numbers(device.failures, "post_ok").eq(0)).sum()),
        })
    return pd.DataFrame(rows, columns=MONTHLY_COLUMNS)


def prepare_diagnostics(devices, export_reference=None, gap_seconds=3020,
                        receipt_gap_seconds=86400, low_voltage=3.64):
    """Populate derived diagnostics only; return the export snapshot reference.

    All frames use UTC-aligned time columns prepared by the loader. Original
    recorded clock values are retained separately; no second offset is applied.
    """
    for name, value in (("Gap threshold", gap_seconds), ("Receipt-gap threshold", receipt_gap_seconds), ("Low-voltage boundary", low_voltage)):
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and nonnegative")
    reference = _export_time(devices, export_reference)
    for device in devices:
        existing = getattr(device, "events", pd.DataFrame()).copy()
        kinds = _series(existing, "kind").fillna("").astype(str)
        existing = existing.loc[~kinds.eq("clock_recovery")].copy()
        marker = device.gps["clock_record"].fillna(False).astype(bool) if "clock_record" in device.gps else pd.Series(False, index=device.gps.index)
        records = []
        for _, row in device.gps.loc[marker].iterrows():
            records.append({"time": row.get("time"), "kind": "clock_recovery", "confidence": "marker_candidate",
                            "source_row": row.get("source_row"), "seq_before": np.nan, "seq_after": np.nan,
                            "voltage_v": row.get("decoded_marker_voltage_v", np.nan), "clock_basis": "device"})
        device.events = pd.concat([existing, pd.DataFrame(records)], ignore_index=True, sort=False)
        if "kind" not in device.events:
            device.events["kind"] = pd.Series(dtype=str)
        device.events["time"] = _times(device.events)
        if "clock_basis" not in device.events:
            device.events["clock_basis"] = "server_receipt"
        device.events.loc[device.events["kind"].isin(["counter_restart", "sequence_regression"]), "clock_basis"] = "server_receipt"
        device.events = device.events.sort_values(["time", "kind"], kind="stable", na_position="last").reset_index(drop=True)
        device.gaps = _build_gaps(device, gap_seconds, low_voltage)
        device.outages = _receipt_outages(device, reference, receipt_gap_seconds)
        device.monthly = _monthly(device)
        if not isinstance(getattr(device, "quality", None), dict):
            device.quality = {}
        affected = device.gaps["unparsed_page_overlap"].astype(bool)
        flagged = device.gaps["absolute_long"].astype(bool) | device.gaps["cadence_gap"].astype(bool)
        device.quality["diagnostics"] = {
            "export_reference": _iso(reference), "export_reference_source": "explicit" if export_reference is not None else "latest receipt in selected exports, falling back to latest recorded event",
            "absolute_gap_seconds": float(gap_seconds), "receipt_gap_seconds": float(receipt_gap_seconds),
            "low_voltage_boundary_v": float(low_voltage), "clock_offset_seconds_for_receipt_comparisons": 0.0,
            "input_time_basis": "Loader-prepared UTC; original recorded times are separate provenance",
            "cadence_method": "INFERRED: centered local evidence excludes the current interval, absolute-long gaps and catchups; a tier needs two neighboring supports, otherwise supported local mode wins (ties prefer longer cadence). Historical 5-code voltage-bin modes, trailing median and dominant interval are fallbacks only.",
            "cadence_local_half_window_records": 6, "cadence_neighbor_support": 2,
            "cadence_gap_rule": "duration > 1.5 * inferred interval + 20 seconds; not a proven missed configured slot",
            "gap_class_priority": ["unparsed_source", "restart_or_clock", "timeout_and_low", "timeout", "low_voltage", "outside_reg_span", "unexplained"],
            "availability_method": "Canonical GPS availability includes clock-recovery TIME records at their measurement time; normal records use attempt starts. Cadence/performance use normal observations only.",
            "parser_affected_method": "Intervals overlapping timestamp hints from unparsed DAT pages are parsed-export coverage uncertainty, excluded from device-gap causes, fleet gap counts and timeout baseline; no source records are repaired or fabricated.",
            "context_definition": "Events in (canonical availability boundary, next availability boundary]; registration coverage is outer first/last logged registration span only",
            "voltage_definition": "Boundary voltage is the preceding recorded ADC-derived value; low flag can use either boundary. It is not calibrated true-cell voltage.",
            "outage_definition": "Receipt silences, including leading/trailing to export reference; GPS counts inside do not establish continuous acquisition or undelivered requests",
            "clock_marker_count": int(marker.sum()), "counter_restart_candidates": int(device.events["kind"].eq("counter_restart").sum()),
            "absolute_gap_count": int((device.gaps["absolute_long"].astype(bool) & ~affected).sum()),
            "cadence_gap_count": int((device.gaps["cadence_gap"].astype(bool) & ~affected).sum()),
            "parsed_absolute_gap_count": int(device.gaps["absolute_long"].sum()),
            "parsed_cadence_gap_count": int(device.gaps["cadence_gap"].sum()),
            "parser_affected_interval_count": int(affected.sum()),
            "parser_affected_gap_count": int((affected & flagged).sum()),
            "parser_affected_gap_hours": float(device.gaps.loc[affected & flagged, "duration_s"].sum() / 3600),
            "parser_affected_source_lines": list(dict.fromkeys(line for lines in device.gaps.loc[affected, "unparsed_source_lines"] for line in lines)),
            "receipt_outage_count": len(device.outages), **_timeout_baseline(device),
        }
    return reference


def fleet_event_table(devices):
    """Daily distinct-device evidence counts, aligned to UTC for comparison."""
    counts = defaultdict(lambda: defaultdict(set))
    bounds = []

    def add(device_id, values, column):
        for value in values:
            if pd.isna(value):
                continue
            day = value.floor("D")
            counts[day][column].add(str(device_id))
            bounds.append(day)

    for device in devices:
        registrations = _times(device.registrations)
        outcomes = _series(device.registrations, "outcome").fillna("").astype(str).str.lower()
        add(device.device_id, registrations, "registration_device_count")
        add(device.device_id, registrations.loc[outcomes.eq("timeout")], "timeout_device_count")
        add(device.device_id, _times(device.uploads), "receipt_device_count")
        add(device.device_id, _times(normal_gps(device.gps)), "gps_device_count")
        events = getattr(device, "events", pd.DataFrame())
        kinds = _series(events, "kind").fillna("").astype(str)
        add(device.device_id, _times(events).loc[kinds.eq("counter_restart")], "counter_restart_device_count")
        add(device.device_id, _times(events).loc[kinds.eq("clock_recovery")], "clock_marker_device_count")
        gaps = getattr(device, "gaps", pd.DataFrame())
        if not gaps.empty:
            selected = gaps.loc[(gaps["absolute_long"].astype(bool) | gaps["cadence_gap"].astype(bool))
                                & ~gaps["unparsed_page_overlap"].astype(bool)]
            for _, gap in selected.iterrows():
                first = gap["start"].floor("D")
                last = (gap["end"] - pd.Timedelta(nanoseconds=1)).floor("D")
                if last >= first:
                    for day in pd.date_range(first, last, freq="D"):
                        counts[day]["gap_device_count"].add(str(device.device_id))
                        bounds.append(day)
        outages = getattr(device, "outages", pd.DataFrame())
        if not outages.empty:
            bounds.extend(_times(outages, "end").dropna().dt.floor("D").tolist())
    if not bounds:
        return pd.DataFrame(columns=FLEET_COLUMNS)
    rows = []
    for day in pd.date_range(min(bounds), max(bounds), freq="D"):
        rows.append({"date": day, **{column: len(counts[day][column]) for column in FLEET_COLUMNS[1:]}})
    return pd.DataFrame(rows, columns=FLEET_COLUMNS)
