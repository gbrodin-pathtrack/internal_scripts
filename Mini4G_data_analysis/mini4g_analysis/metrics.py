"""Metrics on audited observations, outcomes and explicit coverage populations."""
from __future__ import annotations

import numpy as np
import pandas as pd


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    return value


def _numbers(frame, column):
    if column not in frame:
        return pd.Series(dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce").astype(float)
    return values.where(np.isfinite(values)).dropna()


def _stat(values, method="median"):
    values = values.dropna()
    return None if values.empty else json_safe(getattr(values, method)())


def _percent(numerator, denominator):
    return 100.0 * numerator / denominator if denominator else None


def gps_intervals(gps):
    from .diagnostics import gps_intervals as calculate
    return calculate(gps)


def _normal(gps):
    from .diagnostics import normal_gps
    return normal_gps(gps)


def _counted_uploads(device):
    frame = device.uploads
    if "stats_counted" in frame:
        return frame.loc[frame["stats_counted"].fillna(False).astype(bool)]
    return frame


def device_metrics(device, matches, gap_seconds=3020, min_satellites=5, *, export_reference=None, gps_timeout_seconds=20):
    if not np.isfinite(gap_seconds) or gap_seconds < 0:
        raise ValueError("GPS gap threshold must be finite and nonnegative")
    if min_satellites < 1 or not np.isfinite(gps_timeout_seconds) or gps_timeout_seconds <= 0:
        raise ValueError("Satellite and timeout thresholds must be positive")
    gps = _normal(device.gps)
    interval_frame = gps_intervals(device.gps)
    intervals = _numbers(interval_frame, "interval_s")
    intervals = intervals[intervals >= 0]
    if intervals.empty:
        trimmed = None
    else:
        low, high = intervals.quantile([0.01, 0.99])
        middle = intervals[(intervals > low) & (intervals < high)]
        trimmed = float(intervals.mean()) if middle.empty else float(middle.mean())
    ttf = pd.to_numeric(gps.get("ttf_s", pd.Series(index=gps.index, dtype=float)), errors="coerce")
    ttf = ttf.where(np.isfinite(ttf) & ttf.ge(0))
    sv = pd.to_numeric(gps.get("num_sv", pd.Series(index=gps.index, dtype=float)), errors="coerce")
    sv = sv.where(np.isfinite(sv) & sv.ge(0))
    qualifies = sv.ge(min_satellites)
    known_on_time = ttf.notna() & sv.notna()
    on_time_denominator = int((qualifies & known_on_time).sum())
    on_time = float(ttf.loc[known_on_time].sum() / on_time_denominator) if on_time_denominator else None
    dates = device.gps["time"].dropna()
    first, last = (dates.min(), dates.max()) if len(dates) else (None, None)
    span_days = (last-first).total_seconds()/86400 if first is not None and last > first else 0
    cnr_obs = _numbers(gps, "cnr_mean")
    eligible_ids = set(gps.get("obs_id", []))
    sat_frame = device.satellites
    if "obs_id" in sat_frame:
        sat_frame = sat_frame.loc[sat_frame["obs_id"].isin(eligible_ids)]
    cnr = _numbers(sat_frame, "CNR")
    peaks = cnr if len(cnr) else _numbers(gps, "cnr_peak")
    if cnr.empty:
        cnr = cnr_obs

    attempts = pd.concat([_counted_uploads(device), device.failures], ignore_index=True)
    post = _numbers(attempts, "post_ok"); post = post[post.isin([0, 1])]
    successes, failures = int(post.eq(1).sum()), int(post.eq(0).sum())
    receipt_post = _numbers(device.uploads, "post_ok")
    receipts_with_stats = int(receipt_post.isin([0, 1]).sum())
    psm = _numbers(attempts, "psm_ok"); psm = psm[psm.isin([0, 1])]
    regs = device.registrations
    outcomes = regs["outcome"].fillna("unknown").astype(str).str.lower()
    known_reg = outcomes.isin(["success", "timeout", "shutdown"])
    reg_psm = regs["psm"].fillna("unknown").astype(str).str.lower()
    reg_psm_known = reg_psm.isin(["yes", "no"])
    durations = _numbers(regs, "duration_s")
    successful_regs = regs.loc[outcomes.eq("success")]
    successful_durations = _numbers(successful_regs, "duration_s")
    timeout_durations = _numbers(regs.loc[outcomes.eq("timeout")], "duration_s")
    from .battery import battery_pairs, battery_summary
    pairs = battery_pairs(device)
    agreement = battery_summary(pairs)
    difference = pairs["diff_mv"] / 1000
    pair_times = pairs["time"].dropna()
    latest_pair = pairs.loc[pairs["time"].notna()].sort_values("time", kind="stable").tail(1)
    receipt_times = device.uploads["time"].dropna()
    last_receipt = receipt_times.max() if len(receipt_times) else None
    ref = pd.Timestamp(export_reference) if export_reference is not None else last_receipt
    silence = (ref-last_receipt).total_seconds()/86400 if ref is not None and last_receipt is not None else None
    pair_time = latest_pair.iloc[0]["time"] if not latest_pair.empty else None
    pair_age = (ref-pair_time).total_seconds()/86400 if ref is not None and pair_time is not None else None

    prepared = getattr(device, "gaps", pd.DataFrame())
    if len(prepared) and "absolute_long" in prepared:
        parsed_gaps = prepared.loc[prepared["absolute_long"].fillna(False)]
        affected = prepared.get("unparsed_page_overlap", pd.Series(False, index=prepared.index)).fillna(False).astype(bool)
        supported = prepared.loc[~affected]
        gaps = supported.loc[supported["absolute_long"].fillna(False)]
        durations_s = _numbers(gaps, "duration_s")
        all_supported_intervals = _numbers(supported, "duration_s")
        parsed_durations = _numbers(parsed_gaps, "duration_s")
        affected_gaps = prepared.loc[affected & prepared["absolute_long"].fillna(False)]
        cadence_count = int(supported["cadence_gap"].fillna(False).sum())
    else:
        gaps = parsed_gaps = affected_gaps = pd.DataFrame()
        durations_s = intervals[intervals > gap_seconds]
        all_supported_intervals = intervals
        parsed_durations = durations_s
        cadence_count = 0
    gap_count = len(durations_s)
    diag = device.quality.get("diagnostics", {})
    timed_events = int(matches["event_time"].notna().sum())
    matched = matches["within_window"].fillna(False).astype(bool)
    offsets = _numbers(matches, "offset_s").abs()
    matched_offsets = _numbers(matches.loc[matched], "offset_s").abs()
    issues = list(device.issues)
    if len(ttf.dropna()) < len(gps):
        issues.append("GPS on-time proxy uses only attempts with known TTF and satellite count; coverage is reported.")
    reg_status = device.failures.get("receipt_match_status", pd.Series("unknown", index=device.failures.index))
    longest_outage = _stat(_numbers(device.outages, "duration_s"), "max")
    outage_with_gps = device.outages.loc[device.outages.get("gps_count", pd.Series(index=device.outages.index,dtype=float)).gt(0)] if len(device.outages) else pd.DataFrame()
    quality = {section: {key: value for key,value in content.items() if key not in ("audit",)}
               for section,content in device.quality.items() if isinstance(content, dict)}
    summary = {
        "device_id": str(device.device_id), "gps_records": len(device.gps), "gps_observations": len(gps),
        "gps_clock_records": len(device.gps)-len(gps), "satellite_rows": len(device.satellites),
        "first_gps": first, "last_gps": last, "gps_span_days": span_days,
        "gps_5plus_count": int(qualifies.sum()), "gps_satellite_count_known": int(sv.notna().sum()),
        "gps_5plus_percent": _percent(int(qualifies.sum()), int(sv.notna().sum())),
        "ttf_known_count": int(ttf.notna().sum()), "ttf_mean_s": _stat(ttf,"mean"),
        "ttf_median_s": _stat(ttf), "ttf_p95_s": float(ttf.quantile(.95)) if ttf.notna().any() else None,
        "gps_success_ttf_median_s": _stat(ttf.loc[qualifies]),
        "gps_timeout_count": int(ttf.ge(gps_timeout_seconds).sum()),
        "gps_timeout_percent": _percent(int(ttf.ge(gps_timeout_seconds).sum()),int(ttf.notna().sum())),
        "on_time_per_5plus_s": on_time, "on_time_known_attempts": int(known_on_time.sum()),
        "on_time_qualifying_denominator": on_time_denominator,
        "on_time_coverage_percent": _percent(int(known_on_time.sum()),len(gps)),
        "cnr_mean": _stat(cnr,"mean"), "cnr_peak": _stat(peaks,"max"),
        "cnr_observation_mean": _stat(cnr_obs,"mean"), "gps_gap_count": gap_count,
        "gps_gap_hours": float(durations_s.sum()/3600) if len(durations_s) else 0,
        "gps_gaps_per30d": gap_count*30/span_days if span_days else None,
        "gps_longest_gap_s": _stat(all_supported_intervals,"max"),
        "gps_parsed_gap_count": len(parsed_durations), "gps_parsed_gap_hours": float(parsed_durations.sum()/3600),
        "gps_parsed_longest_gap_s": _stat(parsed_durations,"max"),
        "parser_affected_gap_count": len(affected_gaps),
        "parser_affected_gap_hours": float(_numbers(affected_gaps,"duration_s").sum()/3600), "gps_interval_trimmed_mean_s": trimmed,
        "gps_interval_known_count": len(intervals), "gps_cadence_gap_count": cadence_count,
        "gps_clock_anomalies": int(device.gps["clock_anomaly"].fillna(False).sum()),
        "gps_duplicate_rows": int(device.quality.get("gps",{}).get("replayed_obs",0)),
        "upload_receipts": len(device.uploads), "upload_known_outcomes":len(post),
        "upload_successes":successes,"upload_failures":failures,
        "upload_success_percent":_percent(successes,len(post)),
        "upload_stats_missing":len(device.uploads)-receipts_with_stats,"upload_stats_present":receipts_with_stats,
        "post_stats_unknown_outcomes":len(attempts)-len(post),"psm_known":len(psm),"psm_yes":int(psm.eq(1).sum()),
        "psm_yes_percent":_percent(int(psm.eq(1).sum()),len(psm)),
        "registration_attempts":len(regs),"registration_known_outcomes":int(known_reg.sum()),
        "registration_unknown_outcomes":int((~known_reg).sum()),"registration_successes":int(outcomes.eq("success").sum()),
        "registration_timeouts":int(outcomes.eq("timeout").sum()),"registration_shutdowns":int(outcomes.eq("shutdown").sum()),
        "registration_success_percent":_percent(int(outcomes.eq("success").sum()),int(known_reg.sum())),
        "registration_duration_median_s":_stat(durations),"registration_duration_known":len(durations),
        "registration_success_duration_median_s":_stat(successful_durations),
        "registration_timeout_duration_median_s":_stat(timeout_durations),
        "registration_psm_known":int(reg_psm_known.sum()),"registration_psm_yes":int(reg_psm.eq("yes").sum()),
        "registration_psm_yes_percent":_percent(int(reg_psm.eq("yes").sum()),int(reg_psm_known.sum())),
        "battery_pairs":agreement["pairs"],"battery_diff_mean_v":_stat(difference,"mean"),
        "battery_diff_min_v":_stat(difference,"min"),"battery_diff_max_v":_stat(difference,"max"),
        "battery_agreement":agreement,"last_voltage_time":pair_time,"last_voltage_age_days":pair_age,
        "last_adc_v":float(latest_pair.iloc[0]["adc_v"]) if len(latest_pair) else None,
        "last_modem_v":float(latest_pair.iloc[0]["modem_v"]) if len(latest_pair) else None,
        "last_receipt":last_receipt,"receipt_silence_days":silence,"export_reference":ref,
        "post_failed_received":int(reg_status.eq("received").sum()),
        "post_failed_no_receipt":int(reg_status.eq("no_matching_receipt").sum()),
        "post_failed_ambiguous":int(reg_status.eq("ambiguous").sum()),
        "receipt_outage_count":len(device.outages),"longest_receipt_outage_s":longest_outage,
        "longest_receipt_outage_with_gps_s":_stat(_numbers(outage_with_gps,"duration_s"),"max"),
        "counter_restart_candidates":int(device.events.get("kind",pd.Series(dtype=str)).eq("counter_restart").sum()),
        "clock_recovery_candidates":int(device.events.get("kind",pd.Series(dtype=str)).eq("clock_recovery").sum()),
        "timed_events":timed_events,"untimed_events":len(matches)-timed_events,
        "gps_matched_events":int(matched.sum()),"gps_match_percent":_percent(int(matched.sum()),timed_events),
        "median_abs_gps_offset_s":_stat(offsets),"matched_median_abs_gps_offset_s":_stat(matched_offsets),
        "gps_overlap_events":int(matches["gps_overlap"].fillna(False).sum()),
        "clock_ambiguous_events":int(matches["match_status"].eq("clock_ambiguous").sum()),
        "quality":quality,"issues":list(dict.fromkeys(issues))}
    summary.update({key:diag.get(key) for key in ("gap_timeout_eligible","gap_timeout_hits","gap_timeout_expected_hits",
                    "observed_gap_timeout_percent","expected_gap_timeout_percent")})
    return json_safe(summary)
