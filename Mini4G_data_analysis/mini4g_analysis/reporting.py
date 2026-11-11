"""Pure Markdown renderers for audited Mini4G analysis results.

The CLI owns file writes. Links are relative to the published Outputs directory;
the battery index is intended for battery_adc_modem/index.md. No renderer reads
input files, performs cleaning, or changes a measurement or DataFrame.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import math


def _number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _text(value, default="n/a"):
    if value is None or str(value) in ("nan", "NaN", "NaT", "<NA>", "None"):
        return default
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _fmt(value, digits=1, suffix=""):
    number = _number(value)
    return "n/a" if number is None else f"{number:,.{digits}f}{suffix}"


def _count(value):
    number = _number(value)
    return "n/a" if number is None else f"{int(number):,}"


def _datetime(value):
    if value is None or _text(value) == "n/a":
        return None
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _date(value, *, short=False):
    date = _datetime(value)
    return "n/a" if date is None else date.strftime("%Y-%m-%d" if short else "%Y-%m-%d %H:%M")


def _days(reference, time):
    reference, time = _datetime(reference), _datetime(time)
    return (reference - time).total_seconds() / 86400 if reference and time else None


def _ordered(devices):
    return sorted(devices, key=lambda item: int(item.device_id))


def _rows(value):
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        return value.to_dict("records")
    return list(value) if not isinstance(value, Mapping) else [value]


def _summaries(value):
    if isinstance(value, Mapping):
        if "device_id" in value:
            return {str(value["device_id"]): value}
        return {str(key): row for key, row in value.items() if isinstance(row, Mapping)}
    return {str(row["device_id"]): row for row in (value or []) if isinstance(row, Mapping) and "device_id" in row}


def _quality(device, section):
    quality = getattr(device, "quality", {}) or {}
    value = quality.get(section, {})
    return value if isinstance(value, Mapping) else {}


def _dat_omissions(device):
    quality = _quality(device, "gps")
    entries = _rows(quality.get("unparsed_dat_pages"))
    count = _number(quality.get("unparsed_dat_page_count"))
    if count is None and "unparsed_dat_pages" in quality:
        count = len(entries)
    if not quality.get("page_identity_available", bool(entries)) and not entries:
        count = None
    lines = sorted({int(line) for row in entries if (line := _number(row.get("line"))) is not None})
    line_text = ", ".join(str(line) for line in lines) if lines else ("none identified" if count == 0 else "n/a")
    return count, line_text


def _length(device, field):
    value = getattr(device, field, None)
    return len(value) if value is not None else 0


def _sum(rows, key):
    values = [_number(row.get(key)) for row in rows]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _rate(numerator, denominator):
    numerator, denominator = _number(numerator), _number(denominator)
    if numerator is None or denominator is None or denominator <= 0:
        return "n/a (no known denominator)"
    return f"{_count(numerator)}/{_count(denominator)} ({100 * numerator / denominator:.1f}%)"


def _table(headers, rows):
    result = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    result.extend("| " + " | ".join(_text(cell) for cell in row) + " |" for row in rows)
    return "\n".join(result)


def clock_description(devices, config=None):
    """Shared factual clock-policy caption for plots and Markdown reports."""
    offsets = sorted({number for device in devices
                      if (number := _number(_quality(device, "clock").get("device_offset_seconds"))) is not None})
    if not offsets and config:
        policy = config.get("clockpolicy")
        if isinstance(policy, Mapping):
            number = _number(policy.get("device_offset_seconds", policy.get("device_clock_offset_seconds")))
            if number is not None:
                offsets = [number]
        elif policy:
            return _text(policy) + "; recorded timestamps are preserved."
    if len(offsets) == 1 and offsets[0] == 0:
        return "Device GPS clocks are uncorrected (0 s offset); receipt clocks are UTC; recorded timestamps are preserved."
    if len(offsets) == 1:
        return f"UTC aligned; device GPS clock offset {offsets[0]:g} s corrected; recorded timestamps are preserved."
    if offsets:
        return "Configured per-tag device clock offsets: " + ", ".join(f"{value:g} s" for value in offsets) + "; recorded timestamps are preserved."
    return "Clock basis not provided; no clock-alignment inference is made."


def clock_axis_label(devices):
    offsets = [_number(_quality(device, "clock").get("device_offset_seconds")) for device in devices]
    if offsets and all(value is not None and value != 0 for value in offsets):
        return "Analysis date / time (UTC aligned)"
    if offsets and all(value == 0 for value in offsets):
        return "Recorded device time / receipt UTC (0 s correction)"
    return "Analysis date / time (clock basis not provided)" if not offsets or all(value is None for value in offsets) else "Analysis date / time (per-tag clock policies)"


def gap_class_description(value):
    return {
        "regular": "Regular interval",
        "restart_or_clock": "Counter / clock evidence",
        "timeout_and_low": "Timeout overlap and low boundary reading",
        "timeout": "Recorded timeout overlap",
        "low_voltage": "Low reading at a boundary",
        "outside_reg_span": "Outside recorded registration span",
        "unparsed_source": "Parsed source page omitted",
        "unexplained": "No classified context",
    }.get(str(value), _text(value).replace("_", " "))


def _period(config):
    start = config.get("effective_start", config.get("service_start"))
    end = config.get("effective_end", config.get("service_end"))
    reason = config.get("period_selection", {})
    reason = reason.get("reason", "not specified") if isinstance(reason, Mapping) else reason
    start_label = _date(start) + " inclusive" if _datetime(start) else "open start (all supplied history)"
    end_label = _date(end) + " exclusive" if _datetime(end) else "open end (through supplied export)"
    return (f"Selected period: **{start_label} to {end_label}**. "
            f"Selection reason: {_text(reason)}. Export reference: **{_date(config.get('export_reference'))} UTC**.")


def _path(paths, suffix):
    return next((str(path).replace("\\", "/") for path in (paths or [])
                 if str(path).replace("\\", "/").endswith(suffix)), suffix)


def _tag_link(device_id, paths=None):
    path = _path(paths, f"devices/{device_id}.svg")
    return f"[Tag {device_id}]({path})"


def _unparsed_interval(row):
    return row.get("gap_class") == "unparsed_source" or str(row.get("unparsed_page_overlap", False)) == "True"


def _longest(device, name, *, gps_required=False, absolute=False, exclude_unparsed=False):
    rows = _rows(getattr(device, name, None))
    if gps_required:
        rows = [row for row in rows if (_number(row.get("gps_count")) or 0) > 0]
    if absolute:
        rows = [row for row in rows if row.get("absolute_long") is True or str(row.get("absolute_long")) == "True"]
    if exclude_unparsed:
        rows = [row for row in rows if not _unparsed_interval(row)]
    rows = [row for row in rows if _number(row.get("duration_s")) is not None]
    return max(rows, key=lambda row: float(row["duration_s"])) if rows else None


def _episode(row, *, unit="h"):
    if not row:
        return "n/a"
    divisor = 86400 if unit == "d" else 3600
    return f"{_date(row.get('start'))} to {_date(row.get('end'))} ({_fmt(row.get('duration_s') / divisor, 1, ' ' + unit)})"


def _voltage_summary(summary, reference=None):
    age = summary.get("last_voltage_age_days")
    if _number(age) is None:
        age = _days(reference or summary.get("export_reference"), summary.get("last_voltage_time"))
    return (f"{_fmt(summary.get('last_adc_v'), 3)} / {_fmt(summary.get('last_modem_v'), 3)}",
            _date(summary.get("last_voltage_time")), _fmt(age, 1, " d"))


def _fleet_coincidences(fleet_events):
    rows = _rows(fleet_events)
    messages = []
    for column, denominator, label in (
        ("timeout_device_count", "registration_device_count", "tags with recorded registration timeouts"),
        ("counter_restart_device_count", None, "tags with counter-restart evidence"),
    ):
        eligible = [row for row in rows if (_number(row.get(column)) or 0) >= 2]
        if not eligible:
            continue
        peak = max(eligible, key=lambda row: (float(row[column]), str(row.get("date", ""))))
        count = _count(peak[column])
        if denominator:
            count += "/" + _count(peak.get(denominator))
        messages.append(f"{_date(peak.get('date'), short=True)}: {count} {label}")
    return messages


def _short_verdict(device, summary, reference):
    parts = []
    if _datetime(summary.get("last_receipt")):
        parts.append(f"Last receipt {_date(summary.get('last_receipt'))}, {_fmt(summary.get('receipt_silence_days'), 1, ' d')} before the export reference")
    else:
        parts.append("No receipt in the selected records")
    outage = _longest(device, "outages", gps_required=True)
    if outage:
        parts.append(f"longest receipt interval containing GPS records {_fmt(outage['duration_s'] / 86400, 1, ' d')}")
    known = _number(summary.get("registration_known_outcomes"))
    if known:
        parts.append(f"registration timeouts {_count(summary.get('registration_timeouts'))}/{_count(known)}")
    return "; ".join(parts) + "."


def overview_markdown(devices, summaries, config, paths, fleet_events):
    devices = _ordered(devices)
    by_id = _summaries(summaries)
    rows = [by_id.get(str(device.device_id), {}) for device in devices]
    reference = config.get("export_reference")
    lines = ["# Mini4G analysis overview", "", _period(config), "", clock_description(devices, config), "",
             "## Key findings", "",
             f"- Selected cleaned records cover **{len(devices)} tags**, {_count(_sum(rows, 'gps_observations'))} normal GPS observations, "
             f"{_count(_sum(rows, 'upload_receipts'))} upload receipts and {_count(_sum(rows, 'registration_attempts'))} registration records."]
    ranked = sorted(((device, outage) for device in devices
                     if (outage := _longest(device, "outages", gps_required=True))),
                    key=lambda item: float(item[1]["duration_s"]), reverse=True)
    if ranked:
        examples = [f"Tag {device.device_id}: {_episode(outage, unit='d')}, {_count(outage.get('gps_count'))} GPS observations"
                    for device, outage in ranked[:3]]
        lines.append("- Largest receipt intervals containing GPS data: " + "; ".join(examples) +
                     ". This demonstrates recorded collection during some of the interval, not uninterrupted GPS or no transmission attempts.")
    received, unmatched, ambiguous = (_sum(rows, name) for name in
        ("post_failed_received", "post_failed_no_receipt", "post_failed_ambiguous"))
    if any(value is not None for value in (received, unmatched, ambiguous)):
        lines.append(f"- Reported failed-POST receipt evidence: {_count(received)} confirmed received, {_count(unmatched)} without a matching receipt, "
                     f"and {_count(ambiguous)} ambiguous. A device-reported transport failure is not proof that the server received nothing.")
    eligible, hits, expected = (_sum(rows, name) for name in
        ("gap_timeout_eligible", "gap_timeout_hits", "gap_timeout_expected_hits"))
    if eligible:
        lines.append(f"- Timeout overlap occurs in {_count(hits)}/{_count(eligible)} eligible gap intervals; "
                     f"the analytical monthly-uniform expectation is {_fmt(expected, 1)} intervals. This is descriptive association, not a firmware or network verdict. "
                     "It is [consistent with the documented legacy starvation mechanism](firmware_comparison.md), "
                     "not proof of the cause of each gap or that the issue persists in current BinaryHost firmware.")
    coincidences = _fleet_coincidences(fleet_events)
    if coincidences:
        lines.append("- Coincident recorded fleet events: " + "; ".join(coincidences) + ". A common cause is not established.")
    lines += ["", "## Fleet status at export", "",
              "Absence is measured against the exported dataset, not the current date or a live service. "
              "The last valid voltage measurement may be older than the last receipt.", ""]
    table_rows = []
    for device in devices:
        summary = by_id.get(str(device.device_id), {})
        voltage, voltage_time, voltage_age = _voltage_summary(summary, reference)
        table_rows.append([_tag_link(device.device_id, paths), _date(summary.get("last_gps")),
            _date(summary.get("last_receipt")), _fmt(summary.get("receipt_silence_days"), 1), voltage,
            voltage_time, voltage_age])
    lines.append(_table(["Tag timeline", "Last GPS", "Last receipt", "Receipt absence (d)",
                         "Last ADC / modem (V)", "Voltage measurement date", "Voltage age at export"], table_rows))
    lines += ["", "## Per-tag observations", ""]
    lines.extend(f"- **Tag {device.device_id}:** {_short_verdict(device, by_id.get(str(device.device_id), {}), reference)}"
                 for device in devices)
    lines += ["", "See [dated per-tag findings](device_findings.md) for the gap, receipt and battery episodes behind these observations.", "",
              "## Figure guide", ""]
    for filename, title, purpose in (
        ("gps.svg", "GPS acquisition and continuity", "5+ proxy and timeout-cap rates, qualifying-attempt TTF, per-observation CNR and absolute-long service intervals"),
        ("lte.svg", "LTE outcomes and successful timing", "known registration outcomes, success-only durations, transport versus receipt evidence and monthly tier timeout rates"),
        ("battery.svg", "Battery small multiples", "one trajectory per tag with the same voltage scale and a reported 3.6 V reference"),
        ("gps_lte.svg", "GPS-gap and LTE evidence", "descriptive gap classes, analytical baseline, pre-gap voltage and receipt intervals containing GPS records"),
        ("fleet_status.svg", "Fleet status timeline", "recorded coverage, receipt intervals and counter/clock evidence at export"),
        ("cadence.svg", "Inferred cadence heatmap", "device-month interval estimates and the observation count behind each cell"),
    ):
        lines.append(f"- [{title}]({_path(paths, 'comparisons/' + filename)}): {purpose}.")
    lines += ["", "The fleet table links each four-panel tag timeline: GPS spacing, communication events, battery, then LTE signal. "
              "Gap spans align vertically across all panels. Counter and clock markers describe evidence, not proven physical reboot counts.", "",
              "Additional [ADC–modem agreement figures](battery_adc_modem/index.md) compare the same exported stats records without recalibrating them.", "",
              "## Data quality", ""]
    gps_quality = [_quality(device, "gps") for device in devices]
    stats_quality = [_quality(device, "stats") for device in devices]
    lines.append(f"Source cleaning identifies {_count(_sum(gps_quality, 'replayed_obs'))} replayed GPS rows and "
                 f"{_count(_sum(gps_quality, 'replayed_sv'))} replayed satellite rows; "
                 f"{_count(_sum(gps_quality, 'clock_records'))} retained clock-marker records are excluded from normal GPS performance. "
                 f"{_count(_sum(stats_quality, 'rejected_receipt_stats'))} receipt-attached stats are withheld, while their receipt rows remain.")
    unparsed_count = _sum(gps_quality, "unparsed_dat_page_count")
    if unparsed_count is not None:
        lines.append(f"The header-only DAT coverage audit identifies {_count(unparsed_count)} nonempty pages without parsed observations. "
                     "See the physical DAT lines in the data-quality report; an observed interval in parsed exports need not mean GPS stopped collecting.")
    lines += ["", "The [data-quality report](data_quality.md) separates full-source cleaning, enrichment/conflicts, remaining ordering issues and selected-period exclusions. "
              "Inputs are preserved; cleaning decisions and source-row provenance are recorded by the CLI audits.", "",
              "## Definitions and interpretation", ""]
    lines += _definitions(config)
    return "\n".join(lines).rstrip() + "\n"


def _definitions(config):
    return [
        "- **Populations:** normal GPS performance excludes replay copies, identified clock records and invalid ordering boundaries. A 5+ satellite proxy is not a solved position.",
        "- **Durations:** qualifying GPS TTF and successful registration durations are separate from timeout durations. Counts accompany percentages; unavailable denominators remain n/a.",
        "- **POST outcomes:** known unique device-reported results use post_ok. Confirmed server receipt is independent evidence. Unknown outcomes and unmatched/ambiguous receipt evidence are not converted into success or failure.",
        "- **PSM:** percentages use known yes/no or 0/1 states, with unknown states excluded and counted separately.",
        f"- **Gaps:** the legacy absolute-long threshold is strictly greater than {_fmt(config.get('gap_seconds'), 0, ' s')}. "
        "Cadence-relative gaps are additional diagnostics; cadence is inferred from observed local/voltage patterns, not proof of configured scheduling. Elapsed interval hours are not proven lost logging hours.",
        "- **Parser coverage:** intervals overlapping known nonempty DAT pages without parsed observations remain visible as availability holes, but are excluded from supportable device-gap counts and the timeout baseline.",
        "- **Gap baseline:** analytical uniform starts within the same calendar month and recorded GPS/registration overlap, preserving each observed interval duration. It does not control voltage or missing logs and supplies no p-value or causal verdict.",
        f"- **Nearby GPS:** the lookup window is ±{_fmt(config.get('gps_window_seconds'), 0, ' s')}, inclusive, after the configured clock policy. "
        "It remains contextual for future position lookup; its percentage is not independent evidence of GPS/LTE interaction or payload ownership. Untimed events and ambiguous clocks are reported separately.",
        f"- **Receipt matching:** window {_fmt(config.get('receipt_window_seconds'), 0, ' s')}; tolerated future stats lead {_fmt(config.get('future_stats_lead_seconds'), 0, ' s')}. "
        "Matching is constrained by the cleaned source evidence, not sequence number alone.",
        "- **Battery:** ADC is the already temperature-corrected/per-boot-offset-calibrated exported value. No second correction is applied. Modem voltage is not an absolute-accuracy reference; sensor load, cache age and reported temperature age affect agreement.",
        "- **Date scope:** selected-period rates use only assignable rows in that period. Untimed boot-relative records cannot be placed into a bounded date window. Source cleaning counts cover the full supplied files, with period exclusions reported separately.",
        "- **Status:** receipt absence is relative to the export reference. Ending records do not establish device death, battery exhaustion or live availability.",
        "- **Evidence limits:** counter restarts, sequence regressions and clock recovery candidates are not physical reboot counts. Positions are not calculated here, and associations do not establish firmware or network causes.",
    ]


def data_quality_markdown(devices, config):
    devices = _ordered(devices)
    lines = ["# Mini4G data quality", "", _period(config), "", clock_description(devices, config), "",
             "Cleaning is an audited view of the supplied sources; inputs are unchanged. Raw and retained columns below refer to full-source cleaning before date selection. "
             "Selected columns refer to the analysis period, so they can be smaller for a separate reason.", "", "## GPS observations and satellites", ""]
    rows = []
    for device in devices:
        quality = _quality(device, "gps")
        rows.append([f"Tag {device.device_id}", _count(quality.get("raw_gps_rows")), _count(quality.get("retained_gps_rows")),
                     _count(_length(device, "gps")), _count(quality.get("replayed_obs")), _count(quality.get("raw_sv_rows")),
                     _count(quality.get("retained_sv_rows")), _count(_length(device, "satellites")), _count(quality.get("replayed_sv"))])
    lines.append(_table(["Tag", "GPS raw", "GPS retained", "GPS selected", "GPS replay rows", "SV raw", "SV retained", "SV selected", "SV replay rows"], rows))
    lines += ["", "Retained GPS rows include marker records kept for provenance. They are excluded from normal acquisition performance, voltage and cadence; "
              "clock TIME points may bound availability intervals at their recorded measurement time.", ""]
    rows = []
    for device in devices:
        quality = _quality(device, "gps")
        rows.append([f"Tag {device.device_id}", _count(quality.get("extra_page_copies")), _count(quality.get("clock_records")),
                     _count(quality.get("wrapped_markers")), _count(quality.get("contextual_markers")),
                     _count(quality.get("payload_duplicate_obs")), _count(quality.get("remaining_backwards")),
                     _count(quality.get("invalid_time_rows")), _count(quality.get("unmatched_sv"))])
    lines.append(_table(["Tag", "Extra DAT page copies", "Clock records", "Wrapped candidates", "Contextual candidates", "Payload-duplicate GPS rows", "Remaining backward rows", "Invalid times", "Unmatched SV parents"], rows))
    rows = []
    for device in devices:
        quality = _quality(device, "gps")
        rows.append([f"Tag {device.device_id}", *[_count(quality.get(key)) for key in (
            "identical_csv_obs", "semantic_duplicate_obs", "identical_csv_sv", "semantic_duplicate_sv", "payload_duplicate_sv")]])
    lines += ["", _table(["Tag", "Identical CSV GPS rows", "Semantic GPS fallback removals", "Identical CSV SV rows", "Semantic SV fallback removals", "Payload-duplicate SV rows"], rows)]
    lines += ["", "## Nonempty DAT pages without parsed observations", "",
              "This header-only coverage audit identifies nonempty legacy GPS pages with no corresponding observation in the supplied parsed export. "
              "Line numbers are physical lines in that tag's original DAT file. Raw pages remain preserved; the audit does not classify the payload or infer a cause. "
              "A long interval between parsed observations may therefore include unparsed raw data rather than continuous GPS shutdown.", ""]
    omission_rows = []
    for device in devices:
        count, physical_lines = _dat_omissions(device)
        omission_rows.append([f"Tag {device.device_id}", _count(count), physical_lines])
    lines.append(_table(["Tag", "Nonempty DAT pages without parsed observations", "Physical DAT line(s)"], omission_rows))
    lines += ["", "n/a means DAT-page coverage could not be established; zero means no such page was identified in the inspected DAT source."]
    lines += ["", "Replay identity uses DAT page evidence where available. Semantic or payload identities are audited separately; equal timestamps alone do not establish a duplicate. "
              "Clock markers are evidence of an encoded clock event, not an automatic physical reboot count. The original DAT parser is not rerun, so this is not a guarantee that every raw page originally parsed completely.", "",
              "## Upload, failure and registration records", ""]
    rows = []
    for device in devices:
        quality = _quality(device, "stats")
        raw_fail, exact_fail = _number(quality.get("raw_failures")), _number(quality.get("exact_failed_duplicates"))
        raw_reg, exact_reg = _number(quality.get("raw_registrations")), _number(quality.get("exact_registration_duplicates"))
        semantic = _number(quality.get("semantic_registration_removed"))
        fail_retained = raw_fail - exact_fail if raw_fail is not None and exact_fail is not None else None
        reg_retained = raw_reg - exact_reg - semantic if None not in (raw_reg, exact_reg, semantic) else None
        rows.append([f"Tag {device.device_id}", _count(quality.get("raw_uploads")), _count(_length(device, "uploads")),
                     _count(raw_fail), _count(fail_retained), _count(_length(device, "failures")),
                     _count(raw_reg), _count(reg_retained), _count(_length(device, "registrations"))])
    lines.append(_table(["Tag", "Receipt raw/retained", "Receipt selected", "Failure raw", "Failure retained", "Failure selected", "Registration raw", "Registration retained", "Registration selected"], rows))
    lines += ["", "Receipt rows are retained even when attached stats are rejected. Registration retained counts subtract exact duplicates and then additional semantic merges, without double-counting those removals.", ""]
    rows = []
    for device in devices:
        quality = _quality(device, "stats")
        rows.append([f"Tag {device.device_id}", *[_count(quality.get(key)) for key in (
            "exact_failed_duplicates", "exact_registration_duplicates", "semantic_registration_removed", "registration_conflicts",
            "rejected_receipt_stats", "receipt_stats_deduplicated", "failed_received", "failed_unmatched", "failed_ambiguous")]])
    lines.append(_table(["Tag", "Exact failure dupes", "Exact registration dupes", "Additional semantic merges", "Known-field conflict groups", "Rejected receipt stats", "Repeated stats counted once", "Failed POST received", "No receipt match", "Ambiguous"], rows))
    lines += ["", "Unknown-to-known enrichment is not classified as a contradictory known measurement. Known-field conflicts remain flagged. "
              "A no-matching-receipt classification is absence of corroboration, not proof of non-delivery.", "", "## Selected-period exclusions", ""]
    rows = []
    for device in devices:
        exclusions = _quality(device, "period_excluded")
        for source, value in exclusions.items():
            if isinstance(value, Mapping):
                rows.append([f"Tag {device.device_id}", source, _count(value.get("rows")), _count(value.get("untimed"))])
    lines.append(_table(["Tag", "Source view", "Rows excluded by date selection", "Untimed rows among excluded"], rows) if rows else
                 "No selected-period exclusions were recorded.")
    lines += ["", "Study-period selection is explicit: " + _period(config), "",
              "## Additional source notes", ""]
    notes = {}
    for device in devices:
        issues = list(getattr(device, "issues", []) or []) + list(_quality(device, "gps").get("issues", []) or [])
        for issue in dict.fromkeys(str(issue) for issue in issues):
            notes.setdefault(issue, []).append(str(device.device_id))
    lines.extend(f"- Tags {', '.join(tags)}: {_text(issue)}" for issue, tags in sorted(notes.items()))
    if not notes:
        lines.append("No additional source notes recorded.")
    lines += ["", "[Back to overview](overview.md)."]
    return "\n".join(lines).rstrip() + "\n"


def device_findings_markdown(devices, summaries, fleet_events):
    devices = _ordered(devices)
    by_id = _summaries(summaries)
    lines = ["# Mini4G per-tag findings", "", clock_description(devices), "",
             "These are descriptive investigation targets from cleaned selected records, not firmware verdicts. "
             "Receipt absence and voltage age use each summary's export reference.", "", "## Investigation order by receipt interval containing GPS records", ""]
    ranked = sorted(((device, outage) for device in devices if (outage := _longest(device, "outages", gps_required=True))),
                    key=lambda item: float(item[1]["duration_s"]), reverse=True)
    lines.extend(f"- Tag {device.device_id}: {_episode(outage, unit='d')}; {_count(outage.get('gps_count'))} GPS observations within the interval."
                 for device, outage in ranked)
    if not ranked:
        lines.append("No qualifying receipt interval with recorded GPS data.")
    for device in devices:
        summary = by_id.get(str(device.device_id), {})
        lines += ["", f"## Tag {device.device_id}", "",
                  f"[Aligned timeline](devices/{device.device_id}.svg) · [ADC–modem agreement](battery_adc_modem/{device.device_id}.svg)", "",
                  f"- Last GPS: {_date(summary.get('last_gps'))}; last receipt: {_date(summary.get('last_receipt'))}; "
                  f"receipt absence at export: {_fmt(summary.get('receipt_silence_days'), 1, ' d')}."]
        lines.append(f"- GPS acquisition: 5+ satellite proxy {_rate(summary.get('gps_5plus_count'), summary.get('gps_satellite_count_known'))}; "
                     f"qualifying-observation TTF median {_fmt(summary.get('gps_success_ttf_median_s'), 2, ' s')}. This is an acquisition proxy, not solved-position success.")
        lines.append(f"- Known acquisition on-time per qualifying observation: {_fmt(summary.get('on_time_per_5plus_s'), 2, ' s')}; "
                     f"known TTF/satellite attempts {_count(summary.get('on_time_known_attempts'))}/{_count(summary.get('gps_observations'))} "
                     f"({_fmt(summary.get('on_time_coverage_percent'), 1, '%')} availability); qualifying known denominator {_count(summary.get('on_time_qualifying_denominator'))}.")
        voltage, voltage_time, voltage_age = _voltage_summary(summary)
        if _number(summary.get("last_adc_v")) is None or _number(summary.get("last_modem_v")) is None:
            lines.append("- No dated valid ADC/modem voltage pair is available in the selected records.")
        else:
            lines.append(f"- Last valid ADC / modem pair: {voltage} V, measured {voltage_time}; age at export {voltage_age}. This may predate the last receipt.")
        parsed_gap = _longest(device, "gaps", absolute=True)
        if parsed_gap and _unparsed_interval(parsed_gap):
            source_lines = parsed_gap.get("unparsed_source_lines", [])
            line_text = ", ".join(str(value) for value in source_lines) if isinstance(source_lines, (list, tuple)) else _text(source_lines)
            lines.append(f"- Largest observed interval in parsed GPS availability: {_episode(parsed_gap)}; **Parsed source page omitted**, "
                         f"physical DAT line(s) {line_text or 'n/a'}. It is excluded from device-gap counts and the timeout baseline, not treated as continuous GPS shutdown.")
        gap = _longest(device, "gaps", absolute=True, exclude_unparsed=True)
        if gap:
            label = "Largest source-covered absolute-long GPS interval candidate" if parsed_gap and _unparsed_interval(parsed_gap) else "Largest parsed-availability / source-covered absolute-long GPS interval candidate"
            lines.append(f"- {label}: {_episode(gap)}; "
                         f"{_count(gap.get('timeout_count'))} registration timeouts, {_count(gap.get('failure_count'))} reported POST failures and "
                         f"{_count(gap.get('receipt_count'))} receipts inside. Boundary GPS voltages: "
                         f"{_fmt(gap.get('voltage_before_v'), 3)} / {_fmt(gap.get('voltage_after_v'), 3)} V; descriptive class {gap_class_description(gap.get('gap_class'))}.")
        else:
            lines.append("- No source-covered absolute-long GPS interval candidate is available in the selected period.")
        unparsed_count, physical_lines = _dat_omissions(device)
        if unparsed_count:
            lines.append(f"- DAT coverage caveat: {_count(unparsed_count)} nonempty pages have no parsed observation, at physical DAT line(s) {physical_lines}. "
                         f"Selected parser-affected absolute-long intervals: {_count(summary.get('parser_affected_gap_count'))}, "
                         f"{_fmt(summary.get('parser_affected_gap_hours'), 1, ' h')} elapsed. "
                         "These intervals are excluded from supported device-gap headlines and the timeout baseline; they do not establish continuous GPS shutdown. "
                         "See [data quality](data_quality.md#nonempty-dat-pages-without-parsed-observations).")
        outage = _longest(device, "outages", gps_required=True)
        if outage:
            ongoing = " It continues to the export reference." if outage.get("ongoing_at_export") else ""
            lines.append(f"- Largest receipt interval containing GPS data: {_episode(outage, unit='d')}; {_count(outage.get('gps_count'))} observations. "
                         "Some collection occurred inside; continuous operation and transmission attempts are not established." + ongoing)
        lines.append(f"- Registration successes: {_rate(summary.get('registration_successes'), summary.get('registration_known_outcomes'))}; "
                     f"success-only duration median {_fmt(summary.get('registration_success_duration_median_s'), 2, ' s')}. "
                     f"Known device POST successes: {_rate(summary.get('upload_successes'), summary.get('upload_known_outcomes'))}; "
                     f"receipts without outcome stats: {_count(summary.get('upload_stats_missing'))}.")
        lines.append(f"- Failed-POST evidence: {_count(summary.get('post_failed_received'))} received, {_count(summary.get('post_failed_no_receipt'))} unmatched, "
                     f"{_count(summary.get('post_failed_ambiguous'))} ambiguous. Counter restart candidates: {_count(summary.get('counter_restart_candidates'))}; "
                     f"clock recovery candidates: {_count(summary.get('clock_recovery_candidates'))}. These are not proven reboot counts.")
        if _number(summary.get("gap_timeout_eligible")):
            lines.append(f"- Eligible gap intervals with a registration timeout: {_rate(summary.get('gap_timeout_hits'), summary.get('gap_timeout_eligible'))}; "
                         f"monthly-uniform expected hits {_fmt(summary.get('gap_timeout_expected_hits'), 1)}. Voltage and missing logs remain uncontrolled. "
                         "[Documented legacy mechanism context](firmware_comparison.md): the overlap can be consistent with starvation, "
                         "but is not proof for each gap or for current BinaryHost firmware.")
    coincidences = _fleet_coincidences(fleet_events)
    lines += ["", "## Coincident fleet events", ""]
    lines.extend("- " + message + "." for message in coincidences)
    if not coincidences:
        lines.append("No multi-tag daily coincidence was classified.")
    lines += ["", "See [data quality](data_quality.md) and the [overview definitions](overview.md#definitions-and-interpretation) before assigning a cause."]
    return "\n".join(lines).rstrip() + "\n"


def battery_index_markdown(devices, battery_summaries):
    source_devices = list(devices)
    by_id = _summaries(battery_summaries)
    if not isinstance(battery_summaries, Mapping):
        positional = list(battery_summaries or [])
        unidentified = [row for row in positional if isinstance(row, Mapping) and "device_id" not in row]
        if unidentified:
            if len(positional) != len(source_devices) or len(unidentified) != len(positional):
                raise ValueError("Unidentified battery summaries require one positional summary per supplied tag")
            by_id = {str(device.device_id): row for device, row in zip(source_devices, positional)}
    devices = _ordered(source_devices)
    lines = ["# ADC–modem agreement by tag", "", clock_description(devices), "",
             "Each figure contains paired exported ADC/modem voltage, residual over time with a trailing 7-day median (minimum 3 pairs), "
             "residual versus valid temperature with reported-age context, and equal-scale sensor agreement.", ""]
    rows = []
    for device in devices:
        summary = by_id.get(str(device.device_id), {})
        rows.append([f"[Tag {device.device_id}]({device.device_id}.svg)", _count(summary.get("pairs")),
                     _count(summary.get("timed_pairs")), _count(summary.get("temperature_pairs")),
                     _fmt(summary.get("mean_diff_mv"), 1), _fmt(summary.get("median_abs_diff_mv"), 1),
                     _fmt(summary.get("p95_abs_diff_mv"), 1), _fmt(summary.get("temp_age_median_s"), 0)])
    lines.append(_table(["Tag figure", "Valid pairs", "Dated pairs", "Valid temperature", "Mean ADC−modem (mV)",
                         "Median absolute difference (mV)", "95th absolute difference (mV)", "Median reported temp age (s)"], rows))
    lines += ["", "- Voltage pairs come from the same cleaned export record; this does not imply simultaneous measurements or equal loads.",
              "- ADC values already include the firmware's temperature correction and per-boot modem-offset calibration. No additional voltage recalibration is applied.",
              "- Modem voltage is not an absolute-accuracy reference. Cache age, RF load, quantisation, clamping and temperature age can affect differences.",
              "- Missing temperature does not exclude a valid voltage pair from the other panels. Unknown reported age is grey; it is not inferred from mixed measurement times.",
              "- All eligible paired points contribute to summaries. Dense data layers may be rasterised inside SVGs, while labels and accessible descriptions remain available.",
              "- Counts above 50 or 100 mV, if present in the machine-readable summary, are descriptive counts rather than pass/fail limits. No calibration frequency or firmware change is inferred.",
              "", "[Back to overview](../overview.md) · [Data quality](../data_quality.md)."]
    return "\n".join(lines).rstrip() + "\n"
