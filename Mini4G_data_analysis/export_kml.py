"""Export observed GPS positions and time-estimated registration positions for Google Earth."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd

from mini4g_analysis.kml import load_positions, build_kml, registration_category
from mini4g_analysis.spatial import estimate_registration_positions, MAPPED_METHODS
from mini4g_analysis.loaders import discover_sources, load_registration_export
from mini4g_analysis.metrics import json_safe
from mini4g_analysis.study import DEFAULT_START_UTC


def _timestamp(text):
    try:
        result = pd.Timestamp(text)
        if pd.isna(result):
            raise ValueError("Missing date")
        return result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError(f"Invalid ISO UTC date/time: {text}") from error


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="Directory containing Tag<ID> folders")
    parser.add_argument("--output", type=Path, required=True, help="External output root; writes registration_kml beneath it")
    parser.add_argument("--device", action="append", dest="devices", help="Select a numeric tag ID; repeat for more")
    parser.add_argument("--start", type=_timestamp, default=_timestamp(DEFAULT_START_UTC),
                        help="Inclusive UTC start; default 1 July 2026")
    parser.add_argument("--end", type=_timestamp, help="Exclusive UTC end; default through the supplied export")
    parser.add_argument("--track-gap-seconds", type=float, default=None,
                        help="Optional display-only track split threshold; default connects all consecutive positions")
    parser.add_argument("--device-clock-offset-seconds", type=float, default=18,
                        help="Recorded device time minus UTC")
    parser.add_argument("--pos-time-basis", choices=["gps", "utc"], default="gps",
                        help="Supplied POS time basis; these files use GPS time, confirmed by the user")
    return parser


def _validate_paths(data, output):
    if data == output or data in output.parents or output in data.parents:
        raise ValueError("Input and output directories must be disjoint")
    here = Path(__file__).resolve().parent
    repo = next((p for p in [here, *here.parents] if (p / ".git").exists()), here)
    if output == repo or repo in output.parents:
        raise ValueError("Generated KML files must stay outside the Git repository")


def _hashes(root, paths):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def _write_text(path, content):
    path.write_bytes(content.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def _date(value):
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S UTC") if pd.notna(value) else "n/a"


def _select_period(positions, registrations, start, end):
    def mask(frame):
        keep = frame["time"].ge(start)
        if end is not None:
            keep &= frame["time"].lt(end)
        return keep.fillna(False)
    position_keep, registration_keep = mask(positions), mask(registrations)
    # Clockless records stay in the registration audit but never acquire a map location.
    registration_keep |= registrations["time"].isna()
    audit = {"start_inclusive": start, "end_exclusive": end,
             "positions_before_selection": len(positions), "positions_excluded": int((~position_keep).sum()),
             "registrations_before_selection": len(registrations), "dated_registrations_excluded": int((~registration_keep).sum()),
             "untimed_registrations_retained_for_audit": int(registrations["time"].isna().sum())}
    return positions.loc[position_keep].copy(), registrations.loc[registration_keep].copy(), audit


def _summary(device_id, positions, matches, pos_quality, reg_quality, period_quality):
    located = matches["position_method"].isin(MAPPED_METHODS)
    category = matches["outcome"].map(registration_category)
    counts = {kind: {"mapped": int((located & category.eq(kind)).sum()),
                     "total": int(category.eq(kind).sum())}
              for kind in ["success", "failure", "other"]}
    return {"device_id": device_id, "file": f"{device_id}.kml", "positions": len(positions),
            "first_position_utc": positions["time"].min(), "last_position_utc": positions["time"].max(),
            "registrations": len(matches), "dated_registrations": int(matches["time"].notna().sum()),
            "mapped": int(located.sum()), "unmapped": int((~located).sum()), "outcomes": counts,
            "position_method_counts": {str(k): int(v) for k,v in matches["position_method"].value_counts().items()},
            "position_quality": pos_quality, "registration_quality": reg_quality, "period_selection": period_quality}


def _index(summaries, settings):
    lines = ["# Estimated registration maps for Google Earth", "",
             f"Study period: {_date(settings['start_inclusive'])} inclusive to "
             f"{_date(settings['end_exclusive']) if settings['end_exclusive'] else 'the end of supplied data'}" +
             (" (exclusive end)." if settings['end_exclusive'] else "."), "",
             "Open a device KML in Google Earth. The folders distinguish measured GPS positions from estimated registration positions:", "",
             "- Blue dots: actual valid supplied GPS positions, with clickable GPS timestamps.",
             "- Purple line: connections between consecutive actual positions, following the shortest great-circle arc.",
             "- Green registration markers: reported success.",
             "- Red registration markers: reported timeout/failure.",
             "- Grey registration markers: another or unknown outcome, if present.", "",
             "Within GPS coverage, the registration is placed along the arc between its surrounding GPS points in proportion to elapsed time. "
             "This assumes constant speed on that arc. Exact timestamp matches use the supplied GPS coordinate. "
             "Before/after GPS coverage, the first/last two positions define a constant speed and direction projection. "
             "There is no time cutoff; long-gap interpolations and long-horizon projections remain visible and labelled as estimates.", "",
             "Click a registration for its positioning method, registration time, both GPS anchor times/source rows, "
             "anchor interval, time from/to each anchor, interpolation fraction, nearest-point time difference, "
             "and (for projections) the prediction horizon and last-leg speed. "
             "Projected markers are explicitly labelled; purple observed-track lines end at the final actual GPS point.", "",
             "All markers are visible by default without a time-slider filter. Dense map labels are hidden; names remain in the Places sidebar. "
             "Folders can be toggled independently. Multiple genuine or stationary estimated coordinates may still overlap; no artificial displacement is applied.", "",
             f"Times are UTC aligned. Registrations subtract {settings['device_clock_offset_seconds']:g} seconds; "
             f"POS times ({settings['pos_time_basis']}) subtract {settings['pos_clock_offset_seconds']:g} seconds. "
             "The user confirmed these POS exports use GPS time.", "",
             "| Device KML | Actual GPS points | Dated registrations | Exact | Interpolated | Projected | Green / red mapped | Clockless |",
             "|---|---:|---:|---:|---:|---:|---|---:|"]
    for row in summaries:
        methods = row["position_method_counts"]
        projected = methods.get("projected_before",0) + methods.get("projected_after",0)
        lines.append(f"| [Tag {row['device_id']}]({row['file']}) | {row['positions']:,} | {row['dated_registrations']} | "
                     f"{methods.get('exact',0)} | {methods.get('interpolated',0)} | {projected} | "
                     f"{row['outcomes']['success']['mapped']} / {row['outcomes']['failure']['mapped']} | {methods.get('untimed',0)} |")
    if settings["track_gap_seconds"] is None:
        lines += ["", "Purple lines connect all consecutive selected GPS points, including long gaps. Extra arc vertices used for drawing are not measured GPS points."]
    else:
        lines += ["", f"Purple lines use an optional display split for gaps over {settings['track_gap_seconds']:g} seconds; registration estimation still uses both anchors without a time cutoff."]
    lines += ["", "Clockless records, missing positions, insufficient distinct-time anchors and ambiguous antipodal geometry cannot supply an estimated location and remain in the JSON audit. "
              "Position quality and registration cleaning counts describe full-source cleaning; date exclusions are recorded separately. "
              "No raw GPS decoding is run. Original data and saved firmware reviews are preserved.", "",
              "The script reads and hashes only each selected tag's POS and registration CSV. "
              "Google Earth may fetch marker artwork from Google's public KML icon service; the script uploads no tracking data.", "",
              "[KML format reference](https://developers.google.com/kml/documentation/kmlreference).", ""]
    return "\n".join(lines)


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        invalid_gap = args.track_gap_seconds is not None and (not np.isfinite(args.track_gap_seconds) or args.track_gap_seconds <= 0)
        if not np.isfinite(args.device_clock_offset_seconds) or invalid_gap:
            raise ValueError("Clock offset must be finite; an optional track gap must be finite and positive")
        if args.end is not None and args.start >= args.end:
            raise ValueError("Inclusive --start must precede exclusive --end")
        data, output = args.data.resolve(), args.output.resolve()
        _validate_paths(data, output)
        selected = []
        for source in discover_sources(data, args.devices):
            registration = source.paths["registrations"]
            position = registration.parent / f"{source.device_id}.pos"
            for path in (position, registration):
                if not path.is_file():
                    raise ValueError(f"Required source file missing: {path}")
            selected.append((source.device_id, position, registration))
        files = [path for _, position, registration in selected for path in (position, registration)]
        before = _hashes(data, files)
        pos_offset = args.device_clock_offset_seconds if args.pos_time_basis == "gps" else 0
        settings = {"position_match_policy": "time_interpolation_and_endpoint_projection",
                    "track_gap_seconds": args.track_gap_seconds, "start_inclusive": args.start,
                    "end_exclusive": args.end, "device_clock_offset_seconds": args.device_clock_offset_seconds,
                    "pos_time_basis": args.pos_time_basis, "pos_clock_offset_seconds": pos_offset,
                    "motion_model": "Constant speed on the shortest great-circle arc; endpoint leg continued for projection"}
        results, summaries = [], []
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".kml-stage-", dir=output) as temporary:
            stage = Path(temporary).resolve()
            if stage.parent != output:
                raise ValueError("Unsafe KML staging directory")
            for device_id, position, registration in selected:
                positions, pos_quality = load_positions(position, clock_offset_seconds=pos_offset)
                registrations, reg_quality = load_registration_export(registration, device_id=device_id,
                    device_clock_offset_seconds=args.device_clock_offset_seconds)
                positions, registrations, period_quality = _select_period(positions,registrations,args.start,args.end)
                matches = estimate_registration_positions(registrations, positions)
                content = build_kml(device_id, positions, matches, track_gap_seconds=args.track_gap_seconds,
                                    clock_offset_seconds=args.device_clock_offset_seconds)
                (stage / f"{device_id}.kml").write_bytes(content)
                summaries.append(_summary(device_id,positions,matches,pos_quality,reg_quality,period_quality))
                results.append({"device_id": device_id, "registrations": matches.to_dict("records")})
            if _hashes(data, files) != before:
                raise ValueError("Selected source files changed during export; existing KML results were not replaced")
            code = Path(__file__).resolve().parent
            scripts = [code/name for name in ["export_kml.py", "mini4g_analysis/kml.py", "mini4g_analysis/spatial.py",
                       "mini4g_analysis/study.py", "mini4g_analysis/loaders.py", "mini4g_analysis/stats_quality.py",
                       "mini4g_analysis/metrics.py", "mini4g_analysis/__init__.py"]]
            manifest = {"format_version": 2, "analysis": "time_estimated_registration_kml", "settings": settings,
                        "input_sha256": before, "script_sha256": _hashes(code,scripts), "source_count": len(files),
                        "raw_files_unchanged": True, "devices": summaries, "events": results}
            _write_text(stage/"run.json",json.dumps(json_safe(manifest),indent=2,allow_nan=False)+"\n")
            _write_text(stage/"index.md",_index(summaries,settings))
            target = (output/"registration_kml").resolve()
            if target.parent != output:
                raise ValueError("Unsafe KML output directory")
            target.mkdir(exist_ok=True)
            for source in sorted(stage.iterdir()):
                destination = (target/source.name).resolve()
                if destination.parent != target:
                    raise ValueError("Unsafe KML publication target")
                os.replace(source,destination)
        print(f"Exported {len(summaries)} device KML files; {sum(r['mapped'] for r in summaries)} mapped registrations, {sum(r['unmapped'] for r in summaries)} unmapped.")
        print(f"Open {output/'registration_kml'/'index.md'}")
        print(f"Verified {len(files)} selected POS/registration source files unchanged.")
        return 0
    except (ValueError,OSError,pd.errors.ParserError) as error:
        print(f"KML export failed: {error}",file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
