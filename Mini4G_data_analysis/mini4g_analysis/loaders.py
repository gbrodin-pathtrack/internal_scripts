"""Read exports and construct audited, cleaned views without editing inputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import re

import numpy as np
import pandas as pd

GPS_COLUMNS = ["obs_id", "time", "start_time", "ttf_s", "num_sv", "vbatt_raw", "voltage_v",
               "source_line", "source_row", "clock_segment", "clock_anomaly", "duplicate", "cnr_mean", "cnr_peak",
               "clock_record", "marker_kind", "decoded_marker_voltage_v", "raw_ttf_s"]
STAT_COLUMNS = ["time", "time_text", "upload_seq", "post_ok", "psm_ok", "voltage_v", "modem_voltage_v",
                "temp_c", "rsrp_dbm", "tx_dbm", "connect_s", "send_s", "ttfb_s", "source_row", "http_status",
                "os_rc", "temp_time", "temp_age_s", "stats_time", "record_hash", "stats_hash", "data_summary"]
REG_COLUMNS = ["time", "time_text", "outcome", "tier", "duration_s", "rsrp_dbm", "tx_dbm", "voltage_v",
               "psm", "energy", "reg_count", "stats_ts", "source_row", "record_hash"]


def _empty(columns):
    frame = pd.DataFrame({name: pd.Series(dtype="float64") for name in columns})
    for name in ("time", "start_time", "temp_time", "stats_time"):
        if name in frame:
            frame[name] = pd.Series(dtype="datetime64[ns, UTC]")
    return frame


@dataclass
class DeviceData:
    device_id: str
    gps: pd.DataFrame = field(default_factory=lambda: _empty(GPS_COLUMNS))
    satellites: pd.DataFrame = field(default_factory=lambda: _empty(["obs_id", "CNR", "ID", "codePhase"]))
    uploads: pd.DataFrame = field(default_factory=lambda: _empty(STAT_COLUMNS))
    failures: pd.DataFrame = field(default_factory=lambda: _empty(STAT_COLUMNS))
    registrations: pd.DataFrame = field(default_factory=lambda: _empty(REG_COLUMNS))
    issues: list[str] = field(default_factory=list)
    source_files: list[Path] = field(default_factory=list)
    quality: dict = field(default_factory=dict)
    events: pd.DataFrame = field(default_factory=pd.DataFrame)
    gaps: pd.DataFrame = field(default_factory=pd.DataFrame)
    outages: pd.DataFrame = field(default_factory=pd.DataFrame)
    monthly: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass(frozen=True)
class DeviceSources:
    device_id: str
    paths: dict[str, Path]

    @property
    def files(self):
        return tuple(sorted({path for path in self.paths.values() if path.is_file()}))


def discover_sources(data_dir: Path, device_ids: list[str] | None = None) -> list[DeviceSources]:
    """Select the documented Tag<ID>/<ID>_* exports; ignore unrelated trees."""
    data_dir = Path(data_dir).resolve()
    if not data_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {data_dir}")
    folders = {}
    for folder in sorted(data_dir.iterdir()):
        match = re.fullmatch(r"Tag(\d+)", folder.name)
        if folder.is_dir() and match:
            folders[match.group(1)] = folder
    wanted = set(device_ids or folders)
    unknown = wanted.difference(folders)
    if unknown:
        raise ValueError("Device IDs not found: " + ", ".join(sorted(unknown)))
    if not wanted:
        raise ValueError("No Tag<ID> device folders found")
    result = []
    for device_id in sorted(wanted, key=int):
        folder = folders[device_id]
        paths = {"gps_obs": folder / f"{device_id}_ublox_GPS_Obs.csv",
                 "gps_sv": folder / f"{device_id}_ublox_GPS_SVs.csv",
                 "gps_dat": folder / f"{device_id}_ublox.dat",
                 "uploads": folder / f"{device_id}_uploads.csv",
                 "failures": folder / f"{device_id}_failed_stats.csv",
                 "registrations": folder / f"{device_id}_registrations.csv"}
        result.append(DeviceSources(device_id, paths))
    return result


def selected_input_files(sources):
    return sorted({path for source in sources for path in source.files})


def _text(frame, column):
    return frame[column].astype("string").fillna("") if column in frame else pd.Series("", index=frame.index, dtype="string")


def _number(frame, column, *, units=False):
    values = _text(frame, column)
    if units:
        values = values.str.extract(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))", expand=False)
    result = pd.to_numeric(values, errors="coerce").astype(float)
    return result.where(np.isfinite(result))


def _times(values):
    cleaned = values.astype("string").str.replace(r"\s+UTC$", "+00:00", regex=True)
    # Exports are ISO calendar strings. Do not guess ambiguous day/month order.
    cleaned = cleaned.where(cleaned.str.match(r"^\d{4}-\d{2}-\d{2}(?:[ T]|$)", na=False))
    return pd.to_datetime(cleaned, format="ISO8601", errors="coerce", utc=True).astype("datetime64[ns, UTC]")


def _voltage(values):
    return values.where(values.gt(0) & values.le(6))


def _hash_rows(frame, excluded=()):
    columns = sorted(name for name in frame.columns if name not in set(excluded) | {"source_row"})
    return pd.Series([hashlib.sha256(json.dumps(list(zip(columns, row)), ensure_ascii=False,
                      separators=(",", ":")).encode()).hexdigest()
                      for row in frame[columns].itertuples(index=False, name=None)], index=frame.index, dtype="string")


def _read(path, device, required):
    if not path.is_file():
        device.issues.append(f"Missing input: {path.name}")
        return pd.DataFrame(columns=required)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig", on_bad_lines="error")
    missing = [name for name in required if name not in frame]
    if missing:
        raise ValueError(f"{path}: missing required columns: {', '.join(missing)}")
    frame["source_row"] = np.arange(2, len(frame) + 2)
    return frame


def _read_stats(path, device, receipt):
    timestamp = "upload_time_utc" if receipt else "attempt_time_utc"
    raw = _read(path, device, [timestamp, "upload_seq", "post_ok"])
    frame = pd.DataFrame(index=raw.index)
    frame["time_text"] = _text(raw, timestamp)
    frame["time"] = _times(frame["time_text"])
    frame["source_row"] = raw.get("source_row", pd.Series(dtype=float))
    frame["record_hash"] = _hash_rows(raw)
    frame["stats_hash"] = _hash_rows(raw, [timestamp, "upload_seq", "data_summary"])
    frame["data_summary"] = _text(raw, "data_summary")
    direct = {"upload_seq": "upload_seq", "post_ok": "post_ok", "psm_ok": "psm_ok", "temp_c": "temp (C)",
              "rsrp_dbm": "rsrp (dBm)", "tx_dbm": "tx_power (dBm)", "http_status": "http_status", "os_rc": "os_rc"}
    for dest, source in direct.items():
        frame[dest] = _number(raw, source)
    frame["post_ok"] = frame["post_ok"].where(frame["post_ok"].isin([0, 1]))
    frame["psm_ok"] = frame["psm_ok"].where(frame["psm_ok"].isin([0, 1]))
    frame["temp_c"] = frame["temp_c"].where(_number(raw, "temp_valid").eq(1))
    frame["temp_time"] = _times(_text(raw, "temp_time_utc"))
    frame["temp_age_s"] = _number(raw, "temp_to_upload_age_s").where(lambda values: values.ge(0))
    frame["stats_time"] = frame["temp_time"] + pd.to_timedelta(frame["temp_age_s"], unit="s")
    frame["voltage_v"] = _voltage(_number(raw, "vbatt (V)"))
    frame["modem_voltage_v"] = _voltage(_number(raw, "modem_vbatt_mv") / 1000)
    frame["rsrp_dbm"] = frame["rsrp_dbm"].where(frame["rsrp_dbm"].between(-160, -20))
    frame["tx_dbm"] = frame["tx_dbm"].where(frame["tx_dbm"].between(-50, 40))
    for dest, source in (("connect_s", "connect (ms)"), ("send_s", "send (ms)"), ("ttfb_s", "ttfb (ms)")):
        frame[dest] = (_number(raw, source) / 1000).where(lambda values: values.ge(0))
    failed = frame["post_ok"].eq(0)
    for name in ("send_s", "ttfb_s"):
        frame.loc[failed & frame[name].eq(0), name] = np.nan
    return frame[STAT_COLUMNS]


def _read_registrations(path, device):
    raw = _read(path, device, ["time", "tier", "outcome", "reg_time", "psm"])
    frame = pd.DataFrame(index=raw.index)
    frame["time_text"] = _text(raw, "time")
    frame["time"] = _times(frame["time_text"])
    for name in ("tier", "outcome", "stats_ts"):
        frame[name] = _text(raw, name)
    frame["outcome"] = frame["outcome"].str.lower().replace({"": "unknown"})
    frame["psm"] = _text(raw, "psm").str.lower().where(lambda values: values.isin(["yes", "no"]), "unknown")
    for dest, source in (("duration_s", "reg_time"), ("rsrp_dbm", "rsrp"), ("tx_dbm", "tx_power"),
                         ("voltage_v", "vbatt"), ("energy", "energy"), ("reg_count", "reg_count")):
        frame[dest] = _number(raw, source, units=True)
    frame["duration_s"] = frame["duration_s"].where(frame["duration_s"].ge(0))
    frame["voltage_v"] = _voltage(frame["voltage_v"])
    frame["rsrp_dbm"] = frame["rsrp_dbm"].where(frame["rsrp_dbm"].between(-160, -20))
    frame["tx_dbm"] = frame["tx_dbm"].where(frame["tx_dbm"].between(-50, 40))
    frame["source_row"] = raw.get("source_row", pd.Series(dtype=float))
    frame["record_hash"] = _hash_rows(raw)
    return frame[REG_COLUMNS]


def _boundary(value):
    if value is None:
        return None
    result = pd.Timestamp(value)
    return result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")


def select_period(devices, start=None, end=None):
    """Filter cleaned views; removal audits retain full-source provenance."""
    start, end = _boundary(start), _boundary(end)
    if start is not None and end is not None and start >= end:
        raise ValueError("Period start must precede end")
    for device in devices:
        excluded = {}
        for name in ("gps", "uploads", "failures", "registrations", "events"):
            frame = getattr(device, name)
            if frame.empty or "time" not in frame:
                continue
            if start is None and end is None:
                continue
            keep = frame["time"].notna()
            if start is not None:
                keep &= frame["time"].ge(start)
            if end is not None:
                keep &= frame["time"].lt(end)
            excluded[name] = {"rows": int((~keep).sum()), "untimed": int(frame["time"].isna().sum())}
            setattr(device, name, frame.loc[keep].copy())
        if start is not None or end is not None:
            device.satellites = device.satellites[device.satellites["obs_id"].isin(device.gps["obs_id"])].copy()
        device.quality["period_excluded"] = excluded
        device.quality["selected_counts"] = {name: len(getattr(device, name))
            for name in ("gps", "satellites", "uploads", "failures", "registrations")}
    return devices


def _align_device_clocks(device, offset_seconds):
    if not np.isfinite(offset_seconds):
        raise ValueError("Device clock offset must be finite")
    shift = pd.Timedelta(seconds=float(offset_seconds))
    for name in ("gps", "failures", "registrations"):
        frame = getattr(device, name)
        frame["recorded_time"] = frame["time"].copy()
        frame["time"] = frame["time"] - shift
    device.gps["recorded_start_time"] = device.gps["start_time"].copy()
    device.gps["start_time"] = device.gps["start_time"] - shift
    for name in ("uploads", "failures"):
        frame = getattr(device, name)
        if name == "uploads":
            frame["recorded_time"] = frame["time"].copy()
        for field_name in ("temp_time", "stats_time"):
            frame["recorded_" + field_name] = frame[field_name].copy()
            frame[field_name] = frame[field_name] - shift
    # Raw-page header hints are metadata only; keep recorded values and add
    # UTC bounds for overlap diagnostics without creating observations.
    for page in device.quality.get("gps", {}).get("unparsed_dat_pages", []):
        for source_name, target_name in (("recorded_first_time", "first_time_utc"),
                                         ("recorded_last_time", "last_time_utc")):
            value = page.get(source_name)
            candidate = pd.to_datetime(value, utc=True, errors="coerce") if value else pd.NaT
            page[target_name] = (candidate-shift).isoformat() if pd.notna(candidate) else None
    device.quality["clock"] = {"device_offset_seconds": float(offset_seconds),
                                "analysis_time": "UTC aligned", "recorded_values_retained": True}


def load_registration_export(path: Path, *, device_id: str,
                             device_clock_offset_seconds=18):
    """Load only the explicitly supplied registration CSV using shared rules.

    Returns ``(registrations, quality)``. Quality has ``stats`` (the existing
    deduplication/enrichment audit), ``clock`` (the applied offset policy),
    ``source_file`` (the resolved CSV path) and ``issues``. Calendar timestamps
    are aligned by the configured offset while ``recorded_time`` and merged
    source provenance remain available. Exact-duplicate provenance remains in
    the shared stats audit. Boot-relative values stay untimed.

    No source discovery or GPS/DAT/upload/failure-file read is performed.
    Missing files, malformed CSVs and missing required headers fail explicitly;
    a header-only valid export returns an empty registration frame.
    """
    from .stats_quality import clean_stats_frames

    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("Registration export device_id must be a nonempty string")
    try:
        offset = float(device_clock_offset_seconds)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Device clock offset must be finite") from error
    if not np.isfinite(offset):
        raise ValueError("Device clock offset must be finite")
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError(f"Registration export does not exist or is not a file: {path}")
    device = DeviceData(device_id.strip())
    device.source_files = [path]
    try:
        registrations = _read_registrations(path, device)
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise ValueError(f"Cannot read registration export {path}: {error}") from error
    device.uploads, device.failures, device.registrations, device.events, stats_quality = clean_stats_frames(
        device.device_id, device.uploads, device.failures, registrations,
        device_clock_offset_seconds=offset)
    device.quality["stats"] = stats_quality
    _align_device_clocks(device, offset)
    return device.registrations, {"stats": stats_quality, "clock": device.quality["clock"],
                                  "source_file": str(path), "issues": list(device.issues)}


def load_devices(data_dir: Path, *, device_ids=None, gps_voltage_mode="legacy", start=None, end=None,
                 sources=None, future_lead_seconds=600, receipt_window_seconds=300,
                 device_clock_offset_seconds=18):
    """Discover and clean raw exports once, preserving originals and an audit."""
    from .gps_quality import clean_gps_frames
    from .stats_quality import clean_stats_frames
    if gps_voltage_mode not in ("legacy", "raw"):
        raise ValueError("GPS voltage mode must be legacy or raw")
    sources = sources if sources is not None else discover_sources(data_dir, device_ids)
    devices = []
    for source in sources:
        device = DeviceData(source.device_id)
        device.source_files = list(source.files)
        paths = source.paths
        if "gps_obs" in paths:
            raw_obs = _read(paths["gps_obs"], device, ["line", "datetime", "date", "time", "numSV", "vbatt", "TTF", "startDatetime"])
            raw_sv = _read(paths["gps_sv"], device, ["line", "datetime", "date", "time", "numSV", "vbatt", "TTF", "startDatetime", "ID", "CNR", "codePhase"])
            device.gps, device.satellites, gps_quality = clean_gps_frames(
                device.device_id, raw_obs, raw_sv, paths.get("gps_dat"), gps_voltage_mode)
        else:
            gps_quality = {"raw_obs": 0, "raw_sv": 0, "audit": []}
            device.issues.append("No GPS export folder.")
        if "uploads" in paths:
            uploads = _read_stats(paths["uploads"], device, True)
            failures = _read_stats(paths["failures"], device, False)
            registrations = _read_registrations(paths["registrations"], device)
            device.uploads, device.failures, device.registrations, device.events, stats_quality = clean_stats_frames(
                device.device_id, uploads, failures, registrations,
                future_lead_seconds=future_lead_seconds, receipt_window_seconds=receipt_window_seconds,
                device_clock_offset_seconds=device_clock_offset_seconds)
        else:
            stats_quality = {"raw_uploads": 0, "raw_failures": 0, "raw_registrations": 0, "audit": []}
            device.issues.append("No stats export folder.")
        device.quality.update(gps=gps_quality, stats=stats_quality)
        _align_device_clocks(device, device_clock_offset_seconds)
        devices.append(device)
    return select_period(devices, start, end)
