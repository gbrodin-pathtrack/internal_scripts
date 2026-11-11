"""Reproducible Mini4G analysis using audited views of immutable exports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import matplotlib
import numpy as np
import pandas as pd

from mini4g_analysis.study import DEFAULT_START_UTC
from mini4g_analysis.battery import battery_pairs, battery_summary
from mini4g_analysis.diagnostics import infer_service_start, prepare_diagnostics, fleet_event_table
from mini4g_analysis.loaders import discover_sources, selected_input_files, load_devices, select_period
from mini4g_analysis.matching import build_event_matches
from mini4g_analysis.metrics import device_metrics, json_safe
from mini4g_analysis.plots import write_all_plots, write_adc_modem_plots
from mini4g_analysis.reporting import (overview_markdown, data_quality_markdown,
                                      device_findings_markdown, battery_index_markdown)


def _timestamp(text):
    try:
        result = pd.Timestamp(text)
        return result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError(f"Invalid ISO UTC date/time: {text}") from error


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="External directory containing Tag<ID> folders")
    parser.add_argument("--output", type=Path, required=True, help="External analysis output directory")
    parser.add_argument("--device", action="append", dest="devices", help="Select a numeric tag ID; repeat for more")
    parser.add_argument("--period", choices=["study", "service", "all"], default="study",
                        help="study starts 1 July 2026; service infers the initial bench break; all includes full history")
    parser.add_argument("--start", type=_timestamp, help="Explicit inclusive UTC start, overriding service inference")
    parser.add_argument("--end", type=_timestamp, help="Exclusive UTC end; a date denotes midnight at its start")
    parser.add_argument("--gps-window-seconds", type=float, default=60, help="Nearby-GPS coverage tolerance, inclusive")
    parser.add_argument("--gap-seconds", type=float, default=3020, help="Historical absolute long-gap threshold, strict >")
    parser.add_argument("--receipt-gap-hours", type=float, default=24, help="Threshold for exported receipt-outage diagnostics")
    parser.add_argument("--gps-timeout-seconds", type=float, default=20, help="Configured GPS acquisition timeout for this export")
    parser.add_argument("--min-satellites", type=int, default=5, help="GPS acquisition-quality proxy threshold, not position-fix success")
    parser.add_argument("--gps-battery", choices=["legacy", "raw"], default="legacy")
    parser.add_argument("--device-clock-offset-seconds", type=float, default=18,
                        help="Recorded device time minus UTC; 18 for these GPS-scale exports, 0 reproduces unshifted clocks")
    parser.add_argument("--future-stats-lead-seconds", type=float, default=600,
                        help="Maximum future joined-stats lead after clock alignment; larger leads are rejected")
    parser.add_argument("--receipt-window-seconds", type=float, default=300,
                        help="Failed-result/receipt association window, with device/server clock alignment")
    parser.add_argument("--event-details", action="store_true", help="Also save temporal associations as JSON Lines")
    parser.add_argument("--plot-set", choices=["all", "adc-modem"], default="all")
    return parser


def _validate_paths(data, output):
    if data == output or data in output.parents or output in data.parents:
        raise ValueError("Input/output directories must be disjoint")
    here = Path(__file__).resolve().parent
    repo = next((parent for parent in [here, *here.parents] if (parent/".git").exists()), here)
    if output == repo or repo in output.parents:
        raise ValueError("Generated results must stay outside the Git repository")


def _input_state(data, files):
    """Hash exactly the selected CSV and raw-DAT sources, not unrelated trees."""
    return {path.relative_to(data).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)}


def _code_state():
    root = Path(__file__).resolve().parent
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*.py"))}


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def _write_json(path, content):
    _write_text(path, json.dumps(json_safe(content), indent=2, allow_nan=False, ensure_ascii=False) + "\n")


def _records(frame):
    return json_safe(frame.to_dict("records"))


def _group_metric(row):
    groups = {
        "coverage": ["first_gps", "last_gps", "gps_span_days", "last_receipt", "receipt_silence_days", "export_reference",
                     "last_adc_v", "last_modem_v", "last_voltage_time", "last_voltage_age_days", "receipt_outage_count",
                     "longest_receipt_outage_s", "longest_receipt_outage_with_gps_s"],
        "gps": [key for key in row if key.startswith(("gps_", "ttf_", "on_time_", "cnr_")) and key not in ("gps_matched_events", "gps_match_percent", "gps_overlap_events")] + ["satellite_rows"],
        "lte": [key for key in row if key.startswith(("upload_", "registration_", "psm_", "post_"))],
        "source_coverage_uncertainty": [key for key in row if key.startswith("parser_affected_")],
        "battery": [key for key in row if key.startswith("battery_")],
        "temporal_coverage_appendix": ["timed_events", "untimed_events", "gps_matched_events", "gps_match_percent", "gps_overlap_events", "median_abs_gps_offset_s", "matched_median_abs_gps_offset_s", "clock_ambiguous_events"],
        "descriptive_gap_baseline": ["gap_timeout_eligible", "gap_timeout_hits", "gap_timeout_expected_hits", "observed_gap_timeout_percent", "expected_gap_timeout_percent"],
        "restart_evidence": ["counter_restart_candidates", "clock_recovery_candidates"],
    }
    return {"device_id": row["device_id"], **{name:{key:row.get(key) for key in keys} for name,keys in groups.items()},
            "data_quality": row.get("quality", {}), "issues": row.get("issues", [])}


def _definitions(config):
    return {
        "time": "All analysis times are UTC aligned; recorded columns preserve original export values. Only device clocks are shifted by the configured offset.",
        "period": "Default study period starts 1 July 2026 UTC. Explicit --start/--end override it; --period service retains optional initial-bench inference. End is exclusive. No live wall clock defines export status.",
        "gps_population": "Canonical observations after page/payload replay cleaning; identified clock records remain evidence but are excluded from normal acquisition metrics.",
        "gps_quality": "Known normal observations reaching the configured satellite threshold / known normal satellite-count observations; not solved-position success.",
        "gps_timeout": f"Reported normal TTF >= {config['gps_timeout_seconds']:g} seconds / normal attempts with known TTF.",
        "on_time_proxy": "Sum of reported TTF on normal attempts with known TTF and satellite count / qualifying observations in that same available-case population; coverage is reported.",
        "absolute_gap": f"Canonical GPS availability interval strictly greater than {config['gap_seconds']:g} seconds; normal observations use attempt starts and clock TIME records use measurement times. Parser-affected intervals remain separate; count rate uses recorded GPS span, not assumed continuous operation.",
        "relative_gap": "Diagnostic excess over supported neighboring normal cadence, excluding the current interval from inference; voltage/history is fallback only, with documented jitter allowance. It is not proof of missed configured slots.",
        "gap_classes": "Descriptive evidence priority: unparsed-source uncertainty, restart/clock, timeout+low boundary, timeout, low boundary, outside registration span, unexplained; all context flags retained. Parser-affected intervals are excluded from supported gap causes and the timeout baseline.",
        "gap_null": "Analytic uniform-start windows within the observed gap's start-month and GPS/registration outer-span overlap, conditioned on each gap duration. Incomplete logs and voltage are not controlled; no p-values or causal attribution.",
        "post_outcome": "Known unique device-reported post_ok=1 / known unique post_ok in 0,1; invalid receipt associations are masked, not turned into failures.",
        "receipt_evidence": f"A unique same-sequence receipt within {config['receipt_window_seconds']:g} seconds after clock alignment confirms receipt despite a reported failure. No match does not establish non-delivery.",
        "registration": "Exact and supported calendar-event identity duplicates are consolidated, preserving known enrichment and exposing known-value conflicts. Successful and timeout durations are separate.",
        "restart_evidence": "Counter restarts, sequence regressions and clock-record markers are separate evidence categories, not definitive MCU reboot counts.",
        "battery": "Reported ADC values already include firmware compensation/calibration. No additional correction is fitted. Pair agreement is not absolute ADC accuracy; same-row readings can differ in sample time/load.",
        "parser_coverage": "Header-only timestamp hints identify intervals overlapping raw DAT pages absent from the decoded CSV. They do not reconstruct measurements or prove continuous GPS logging.",
        "provenance": "Only selected source CSVs and raw DATs are consumed/hashed. Raw inputs are immutable; exclusion reasons and original row/page references are saved separately.",
    }


def main(argv=None):
    args = _parser().parse_args(argv)
    started = time.perf_counter()
    try:
        nonnegative = [args.gps_window_seconds,args.gap_seconds,args.future_stats_lead_seconds,args.receipt_window_seconds]
        if any(not np.isfinite(value) or value < 0 for value in nonnegative):
            raise ValueError("Comparison windows must be finite and nonnegative")
        if args.min_satellites < 1 or not np.isfinite(args.gps_timeout_seconds) or args.gps_timeout_seconds <= 0 or args.receipt_gap_hours <= 0:
            raise ValueError("Satellite, timeout and receipt-gap settings must be positive")
        if args.start is not None and args.end is not None and args.start >= args.end:
            raise ValueError("--start must precede exclusive --end")
        if args.event_details and args.plot_set != "all":
            raise ValueError("--event-details requires --plot-set all")
        data, output = args.data.resolve(), args.output.resolve()
        _validate_paths(data, output)
        sources = discover_sources(data, args.devices)
        files = selected_input_files(sources)
        before = _input_state(data, files)
        devices = load_devices(data, sources=sources, gps_voltage_mode=args.gps_battery,
                               future_lead_seconds=args.future_stats_lead_seconds,
                               receipt_window_seconds=args.receipt_window_seconds,
                               device_clock_offset_seconds=args.device_clock_offset_seconds)
        if args.start is not None:
            effective_start = args.start
            selection = {"mode":"explicit", "reason":"User supplied inclusive UTC start"}
        elif args.period == "study":
            effective_start = _timestamp(DEFAULT_START_UTC)
            selection = {"mode":"study", "reason":"User-selected field-study start: exclude June; begin 1 July 2026 UTC"}
        elif args.period == "service":
            effective_start, selection = infer_service_start(devices)
        else:
            effective_start, selection = None, {"mode":"all", "reason":"Full supplied history requested"}
        # Export status uses the latest selected receipt before period filtering,
        # capped at an explicitly requested end rather than today's clock.
        receipt_dates = [value for device in devices for value in device.uploads["time"].dropna()]
        reference = max(receipt_dates) if receipt_dates else None
        if args.end is not None and reference is not None:
            reference = min(reference,args.end)
        select_period(devices,effective_start,args.end)
        reference = prepare_diagnostics(devices,export_reference=reference,gap_seconds=args.gap_seconds,
                                         receipt_gap_seconds=args.receipt_gap_hours*3600,low_voltage=3.64)
        fleet = fleet_event_table(devices)
        matches = {device.device_id:build_event_matches(device,args.gps_window_seconds) for device in devices}
        summaries = [device_metrics(device,matches[device.device_id],args.gap_seconds,args.min_satellites,
                                    export_reference=reference,gps_timeout_seconds=args.gps_timeout_seconds) for device in devices]
        battery_summaries = [battery_summary(battery_pairs(device)) for device in devices]
        config = {"period":args.period,"period_selection":selection,"service_start":effective_start,
                  "effective_start":effective_start,"effective_end":args.end,"export_reference":reference,
                  "start_inclusive":effective_start,"end_exclusive":args.end,
                  "devices":[device.device_id for device in devices],"plot_set":args.plot_set,
                  "gps_window_seconds":args.gps_window_seconds,"gap_seconds":args.gap_seconds,
                  "gps_timeout_seconds":args.gps_timeout_seconds,"min_satellites":args.min_satellites,
                  "gps_battery":args.gps_battery,"receipt_gap_hours":args.receipt_gap_hours,
                  "receipt_window_seconds":args.receipt_window_seconds,"future_stats_lead_seconds":args.future_stats_lead_seconds,
                  "device_clock_offset_seconds":args.device_clock_offset_seconds,
                  "clockpolicy":"UTC aligned with recorded values preserved; offset configurable"}
        versions = {"python":sys.version.split()[0],"pandas":pd.__version__,"numpy":np.__version__,"matplotlib":matplotlib.__version__}
        output.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".analysis-stage-",dir=output) as temporary:
            stage = Path(temporary).resolve()
            if stage.parent != output:
                raise ValueError("Unsafe staging directory")
            paths = []
            if args.plot_set == "all":
                paths.extend(write_all_plots(devices,matches,summaries,stage,tolerance_seconds=args.gps_window_seconds,
                                             gap_seconds=args.gap_seconds,gps_battery_mode=args.gps_battery))
            battery_paths = write_adc_modem_plots(devices,stage)
            paths.extend(battery_paths)
            if any(stage not in path.resolve().parents for path in paths):
                raise ValueError("Plot writer returned a path outside its staging directory")
            relative_paths = [path.relative_to(stage).as_posix() for path in paths]
            if _input_state(data,files) != before:
                raise ValueError("Selected source files changed during analysis; existing results were not replaced")
            hashes = _code_state()
            common = {"settings":config,"versions":versions,"definitions":_definitions(config),
                      "input_sha256":before,"script_sha256":hashes}
            battery_manifest = {"format_version":2,"analysis":"adc_modem_agreement",
                                "metrics":[dict(device_id=device.device_id,**row) for device,row in zip(devices,battery_summaries)],
                                "plots":[path.relative_to(stage).as_posix() for path in battery_paths],**common}
            _write_json(stage/"battery_adc_modem/run.json",battery_manifest)
            _write_text(stage/"battery_adc_modem/index.md",battery_index_markdown(devices,battery_manifest["metrics"]))
            if args.plot_set == "all":
                quality = {"period_selection":selection,"settings":config,
                           "devices":[{"device_id":device.device_id,**device.quality} for device in devices]}
                diagnostics = {"settings":config,"fleet_events":_records(fleet),"devices":[]}
                for device in devices:
                    flags = device.gaps
                    if len(flags):
                        flags = flags.loc[flags["absolute_long"]|flags["cadence_gap"]]
                    diagnostics["devices"].append({"device_id":device.device_id,"gaps":_records(flags),
                        "outages":_records(device.outages),"events":_records(device.events),"monthly":_records(device.monthly)})
                manifest = {"format_version":3,"analysis":"cleaned_mini4g_service_review",
                            "settings":config,"metrics":[_group_metric(row) for row in summaries],
                            "battery_agreement":battery_manifest["metrics"],"plots":relative_paths,
                            "definitions":_definitions(config),"versions":versions,
                            "provenance":{"input_layout":"Data/Tag<ID>/<ID>_*", "source_count":len(files),
                                          "raw_files_unchanged":True,"data_quality":"data_quality.json","diagnostics":"diagnostics.json"},
                            "input_sha256":before,"script_sha256":hashes}
                _write_json(stage/"run.json",manifest)
                _write_json(stage/"data_quality.json",quality)
                _write_json(stage/"diagnostics.json",diagnostics)
                _write_text(stage/"overview.md",overview_markdown(devices,summaries,config,relative_paths,fleet))
                _write_text(stage/"data_quality.md",data_quality_markdown(devices,config))
                _write_text(stage/"device_findings.md",device_findings_markdown(devices,summaries,fleet))
                if args.event_details:
                    detail=pd.concat(matches.values(),ignore_index=True).sort_values(["device_id","event_time","event_id"],kind="stable",na_position="last")
                    _write_text(stage/"event_matches.jsonl",detail.to_json(orient="records",lines=True,date_format="iso",date_unit="ns"))
            # Publish only files created in the verified staging tree. No input,
            # firmware, saved firmware review, or unrelated output is removed.
            protected = {"firmware_comparison.md","firmware_comparison.html"}
            for source in sorted(stage.rglob("*")):
                if not source.is_file():
                    continue
                relative=source.relative_to(stage)
                if relative.as_posix() in protected:
                    raise ValueError("Unexpected protected report in analysis output")
                destination=(output/relative).resolve()
                if output not in destination.parents:
                    raise ValueError("Unsafe output publication target")
                destination.parent.mkdir(parents=True,exist_ok=True)
                os.replace(source,destination)
        entry=output/"overview.md" if args.plot_set=="all" else output/"battery_adc_modem/index.md"
        print(f"Analysed {len(devices)} tags; published {len(relative_paths)} figures in {time.perf_counter()-started:.1f}s.")
        print(f"Open {entry}")
        print(f"Verified {len(files)} selected source files unchanged; unrelated input trees were not consumed.")
        return 0
    except (ValueError,OSError,pd.errors.ParserError,KeyError) as error:
        print(f"Analysis error: {error}",file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
