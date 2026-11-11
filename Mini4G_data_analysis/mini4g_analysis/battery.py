"""Same-record ADC/modem battery agreement, without recalibrating inputs.

The exported ADC voltage is not a pre-compensation ADC measurement. A paired
row also does not establish simultaneous ADC and modem sampling. Temperature
ages below are the reported export values, never inferred from mixed clocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .loaders import DeviceData


PAIR_COLUMNS = [
    "time", "adc_v", "modem_v", "diff_mv", "temp_c", "temp_time",
    "temp_age_s", "source_kind", "source_row", "post_ok",
]


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame:
        return frame[name]
    return pd.Series(np.nan, index=frame.index, dtype=float)


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    values = pd.to_numeric(_column(frame, name), errors="coerce")
    values = pd.Series(values.to_numpy(dtype=float, na_value=np.nan), index=frame.index)
    return values.where(np.isfinite(values))


def _times(frame: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_datetime(_column(frame, name), errors="coerce", utc=True)


def battery_pairs(device: DeviceData) -> pd.DataFrame:
    """Retain each valid voltage pair from each source exactly once.

    Valid voltages are finite, positive and at most 6 V, matching the shared
    loader. Missing temperature, time or age never removes a voltage pair.
    Rows sharing timestamps or upload sequence numbers remain distinct.
    """
    parts = []
    for source_kind, source in (
        ("upload_receipt", device.uploads),
        ("failed_attempt", device.failures),
    ):
        if source_kind == "upload_receipt" and "stats_counted" in source:
            source = source.loc[source["stats_counted"].fillna(False).astype(bool)]
        frame = pd.DataFrame(index=source.index)
        frame["time"] = _times(source, "time")
        frame["adc_v"] = _numeric(source, "voltage_v")
        frame["modem_v"] = _numeric(source, "modem_voltage_v")
        valid = (frame["adc_v"].gt(0) & frame["adc_v"].le(6)
                 & frame["modem_v"].gt(0) & frame["modem_v"].le(6))
        # Preserve the ADC-minus-modem sign. Six decimal mV places prevent
        # floating noise making exactly 50/100 mV exceed those thresholds.
        frame["diff_mv"] = ((frame["adc_v"] - frame["modem_v"]) * 1000).round(6)
        frame["temp_c"] = _numeric(source, "temp_c")
        frame["temp_time"] = _times(source, "temp_time")
        frame["temp_age_s"] = _numeric(source, "temp_age_s").where(lambda values: values.ge(0))
        frame["source_kind"] = source_kind
        frame["source_row"] = source["source_row"].copy() if "source_row" in source else np.arange(2, len(source) + 2)
        frame["post_ok"] = _numeric(source, "post_ok")
        parts.append(frame.loc[valid, PAIR_COLUMNS].copy())

    result = pd.concat(parts, ignore_index=True)
    for column in ("time", "temp_time"):
        result[column] = pd.to_datetime(result[column], errors="coerce", utc=True)
    return result


def _finite_stat(values: pd.Series, statistic: str):
    values = values.dropna()
    if values.empty:
        return None
    value = float(getattr(values, statistic)())
    return value if np.isfinite(value) else None


def battery_summary(pairs: pd.DataFrame) -> dict:
    """Return strict JSON-safe agreement statistics and measurement counts.

    temperature_age_known and temp_age_median_s concern valid temperature
    samples only. reported_age_pairs separately counts any nonnegative age
    field, which is preserved even when its temperature is unavailable.
    """
    differences = _numeric(pairs, "diff_mv").dropna()
    absolute = differences.abs()
    temperature = _numeric(pairs, "temp_c")
    valid_temperature = temperature.notna()
    age = _numeric(pairs, "temp_age_s").where(lambda values: values.ge(0))
    temperature_age = age.loc[valid_temperature].dropna()
    temperature_time = _times(pairs, "temp_time")
    timed = _times(pairs, "time").notna()
    above_50 = int(absolute.gt(50).sum())
    above_100 = int(absolute.gt(100).sum())
    count = len(pairs)
    return {
        "pairs": count,
        "timed_pairs": int(timed.sum()),
        "untimed_pairs": int((~timed).sum()),
        "temperature_pairs": int(valid_temperature.sum()),
        "temperature_missing": int((~valid_temperature).sum()),
        "temperature_time_known": int((valid_temperature & temperature_time.notna()).sum()),
        "temperature_age_known": len(temperature_age),
        "temperature_age_missing": int(valid_temperature.sum()) - len(temperature_age),
        "reported_age_pairs": int(age.notna().sum()),
        "mean_diff_mv": _finite_stat(differences, "mean"),
        "median_diff_mv": _finite_stat(differences, "median"),
        "median_abs_diff_mv": _finite_stat(absolute, "median"),
        "p95_abs_diff_mv": float(absolute.quantile(0.95)) if not absolute.empty else None,
        "above_50mv_count": above_50,
        "above_100mv_count": above_100,
        "above_50mv_percent": 100.0 * above_50 / len(differences) if len(differences) else None,
        "above_100mv_percent": 100.0 * above_100 / len(differences) if len(differences) else None,
        "temp_age_median_s": _finite_stat(temperature_age, "median"),
        "receipt_pairs": int(_column(pairs, "source_kind").eq("upload_receipt").sum()),
        "failed_attempt_pairs": int(_column(pairs, "source_kind").eq("failed_attempt").sum()),
    }
