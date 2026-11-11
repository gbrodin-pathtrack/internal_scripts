"""Deterministic, evidence-labelled SVG figures for cleaned Mini4G exports."""

from __future__ import annotations

from datetime import timezone
from io import StringIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import SymLogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


_SUCCESS = "#238636"
_FAILURE = "#c43c39"
_UNKNOWN = "#808080"
_GPS = "#17a0b6"
_ADC = "#2673b8"
_MODEM = "#8b55a5"
_TX = "#cc7314"
_SCATTER_LIMIT = 1500  # Kept for compatibility; redesigned figures do not sample.
_DEVICE_PALETTE = (
    "#2668a8", "#8b55a5", "#d87c18", "#138ba1", "#8c5a35",
    "#c064a7", "#414a87", "#a38b12", "#633a84",
)
_PLOT_RC = {
    "svg.fonttype": "path",
    "svg.hashsalt": "mini4g-data-analysis-v2",
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 11,
    "legend.fontsize": 7,
}


def _col(frame, name):
    return frame[name] if name in frame else pd.Series(np.nan, index=frame.index)


def _numeric(frame, name):
    values = pd.to_numeric(_col(frame, name), errors="coerce")
    return values.where(np.isfinite(values))


def _values(frame, name):
    return _numeric(frame, name).dropna().to_numpy(dtype=float)


def _flag(frame, name):
    return _col(frame, name).eq(True).fillna(False).astype(bool)


def _time(values):
    return pd.to_datetime(values, utc=True, errors="coerce", format="mixed")


def _frame(device, name):
    value = getattr(device, name, None)
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _ordered(devices):
    return sorted(devices, key=lambda device: int(device.device_id))


def _colors(devices):
    return {str(device.device_id): _DEVICE_PALETTE[index % len(_DEVICE_PALETTE)]
            for index, device in enumerate(_ordered(devices))}


def _concat(device, names):
    frames = [getattr(device, name) for name in names]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _normal_gps(device):
    gps = device.gps
    exclude = _flag(gps, "clock_record") | _flag(gps, "clock_anomaly")
    return gps.loc[~exclude]


def _note_empty(ax, text="No eligible measurements"):
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes,
            fontsize=10, color="#666666", wrap=True)


def _style(ax, title, ylabel=None):
    ax.set_title(title, loc="left", fontsize=10.5, pad=9)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.2, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.set_axisbelow(True)


def _date_axis(ax):
    locator = mdates.AutoDateLocator(minticks=3, maxticks=7, tz=timezone.utc)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=timezone.utc))


def _ids_axis(ax, devices, labels=None):
    ax.set_xticks(np.arange(len(devices)))
    ax.set_xticklabels(labels or [str(device.device_id) for device in devices],
                       rotation=35, ha="right", fontsize=7.5)
    ax.set_xlim(-0.65, max(len(devices) - 0.35, 0.65))


def _rate_label(ax, x, rate, text, *, fontsize=6):
    """Keep long, rotated count labels inside a 0–100% plotting area."""
    if not np.isfinite(rate):
        return None
    low_bar = rate < 25
    y = max(2.0, float(rate) + 1.0) if low_bar else min(98.0, float(rate) - 1.0)
    return ax.text(x, y, text, ha="center", va="bottom" if low_bar else "top",
                   rotation=90, fontsize=fontsize,
                   bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})


def _cadence_cell(value, count):
    if not np.isfinite(value):
        return "n/a"
    interval = f"{float(value):.1f}".removesuffix(".0")
    return f"{interval} min\nn={int(count):,}"


def _metric(metrics, device, key, default=None):
    value = metrics.get(str(device.device_id), {}).get(key, default)
    return default if value is None or pd.isna(value) else value


def _all_times(devices):
    parts = []
    for device in devices:
        # Clock records remain availability evidence even though they are not
        # normal performance or battery measurements.
        for frame in (device.gps, device.uploads, device.failures, device.registrations):
            times = _time(_col(frame, "time")).dropna()
            if len(times):
                parts.extend([times.min(), times.max()])
    return parts


def _period_text(devices):
    times = _all_times(devices)
    if not times:
        return "Selected period: no usable calendar times"
    return f"Selected analysis span: {min(times):%d %b %Y} to {max(times):%d %b %Y}"


def _clock_caption(devices):
    from .reporting import clock_description
    return clock_description(devices)


def _clock_axis(devices):
    from .reporting import clock_axis_label
    return clock_axis_label(devices)


def _time_limits(devices, metrics=None):
    parts = _all_times(devices)
    if metrics:
        for row in metrics.values():
            value = pd.to_datetime(row.get("export_reference"), utc=True, errors="coerce")
            if not pd.isna(value):
                parts.append(value)
    if not parts:
        return None
    first, last = min(parts), max(parts)
    padding = max((last - first) * 0.012, pd.Timedelta(hours=1))
    return first - padding, last + padding


def _comparison_figure(title, devices):
    fig, axes = plt.subplots(2, 2, figsize=(17, 12), layout="constrained")
    fig.suptitle(f"{title}\n{_period_text(devices)}", fontsize=13)
    return fig, axes.flat


def _save(fig, path):
    """Write an accessible SVG; rasterise dense data, never labels or metrics."""
    for ax in fig.axes:
        for collection in ax.collections:
            try:
                if len(collection.get_offsets()) >= 750:
                    collection.set_rasterized(True)
            except (AttributeError, TypeError):
                pass
        for line in ax.lines:
            if len(line.get_xdata()) >= 750:
                line.set_rasterized(True)
    title_parts = [text.get_text() for text in fig.texts if text.get_text()]
    panel_parts = []
    for ax in fig.axes:
        labels = [ax.get_title(loc="left") or ax.get_title(), ax.get_xlabel(), ax.get_ylabel()]
        panel_parts.extend(label for label in labels if label)
        panel_parts.extend(text.get_text() for text in ax.texts if text.get_text())
        legend = ax.get_legend()
        if legend is not None:
            panel_parts.extend(text.get_text() for text in legend.get_texts())
    title = title_parts[0] if title_parts else "Mini4G data analysis"
    description = "\n".join(title_parts + panel_parts)
    buffer = StringIO()
    fig.savefig(buffer, format="svg", dpi=150,
                metadata={"Date": None, "Creator": "Mini4G data analysis"})
    svg = buffer.getvalue()
    accessible = (
        '\n <title id="figure-title">' + escape(title) + "</title>\n"
        ' <desc id="figure-description">' + escape(description) + "</desc>\n"
    )
    svg = re.sub(r"(<svg\b[^>]*)(>)",
                 lambda match: match.group(1) +
                 ' role="img" aria-labelledby="figure-title figure-description"' +
                 match.group(2) + accessible, svg, count=1, flags=re.DOTALL)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(svg.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    plt.close(fig)
    return path


def _boxplot(ax, arrays, devices, colors, *, ylabel, title, full_range=False):
    total = 0
    labels = []
    for index, (device, values) in enumerate(zip(devices, arrays)):
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        labels.append(f"{device.device_id}\nn={len(values):,}")
        if len(values):
            artists = ax.boxplot(
                [values], positions=[index], widths=0.55, patch_artist=True,
                showfliers=True, whis=(0, 100) if full_range else 1.5,
                medianprops={"color": "#202020", "linewidth": 1.2},
                flierprops={"marker": ".", "markersize": 2, "alpha": 0.35},
            )
            artists["boxes"][0].set(facecolor=colors[str(device.device_id)], alpha=0.55)
            total += len(values)
    _style(ax, title, ylabel)
    _ids_axis(ax, devices, labels)
    if not total:
        _note_empty(ax)


def _timed_scatter(ax, frame, value, *, color, label, marker="o", size=7):
    data = pd.DataFrame({"time": _time(_col(frame, "time")),
                         "value": _numeric(frame, value)}).dropna()
    if len(data):
        ax.scatter(data["time"], data["value"], s=size, c=color, alpha=0.55,
                   marker=marker, label=f"{label} (n={len(data):,})", linewidths=0.35)
    return len(data)


def _intervals(device):
    from .metrics import gps_intervals
    return gps_intervals(device.gps)


def _gps_voltage_note(mode):
    if mode == "legacy":
        return "GPS voltage uses the assumed legacy decoding of an already processed battery code."
    return "GPS voltage omitted: raw battery codes retained without conversion."


def _selected_gaps(device):
    gaps = _frame(device, "gaps")
    return gaps.loc[_flag(gaps, "cadence_gap") | _flag(gaps, "absolute_long") | _flag(gaps, "unparsed_page_overlap")]


def _shade_context(axes, device, limits):
    gaps = _selected_gaps(device)
    for _, row in gaps.iterrows():
        start, end = _time(row.get("start")), _time(row.get("end"))
        if not pd.isna(start) and not pd.isna(end) and start < end:
            omitted = str(row.get("unparsed_page_overlap", False)) == "True" or row.get("gap_class") == "unparsed_source"
            for ax in axes:
                if omitted:
                    ax.axvspan(start, end, facecolor="#b8b8b8", edgecolor="#777777", hatch="////",
                               alpha=0.3, linewidth=0.35, zorder=0)
                else:
                    ax.axvspan(start, end, color="#e4b455", alpha=0.16, linewidth=0, zorder=0)
    known = _all_times([device])
    if limits and known:
        for start, end in ((limits[0], min(known)), (max(known), limits[1])):
            if start < end:
                for ax in axes:
                    ax.axvspan(start, end, color="#bdbdbd", alpha=0.2, linewidth=0, zorder=0)
    styles = {"counter_restart": ("#8053a2", "--"),
              "clock_recovery": ("#3d6a9e", "-."),
              "clock_ordering": ("#777777", ":"),
              "sequence_regression": ("#8c5a35", (0, (4, 2)))}
    events = _frame(device, "events")
    for _, row in events.iterrows():
        time = _time(row.get("time"))
        if not pd.isna(time):
            color, linestyle = styles.get(str(row.get("kind")), ("#777777", ":"))
            for ax in axes:
                ax.axvline(time, color=color, linestyle=linestyle, linewidth=0.7, alpha=0.75)


def _draw_radio(ax, device, limits):
    radio = _concat(device, ("uploads", "failures", "registrations"))
    count = _timed_scatter(ax, radio, "rsrp_dbm", color=_ADC, label="RSRP", size=7)
    right = ax.twinx()
    count += _timed_scatter(right, radio, "tx_dbm", color=_TX, label="TX power", marker="^", size=7)
    _style(ax, "4. LTE radio measurements", "RSRP (dBm)")
    right.set_ylabel("TX power (dBm)", color=_TX)
    right.tick_params(axis="y", labelcolor=_TX, labelsize=8)
    right.spines["top"].set_visible(False)
    ax.set_ylim(limits[0]); right.set_ylim(limits[1])
    handles, labels = ax.get_legend_handles_labels()
    other, other_labels = right.get_legend_handles_labels()
    if count:
        ax.legend(handles + other, labels + other_labels, loc="lower left", fontsize=7)
    else:
        _note_empty(ax)


def _radio_limits(devices, column, fallback):
    parts = [_values(getattr(device, name), column)
             for device in devices for name in ("uploads", "failures", "registrations")]
    values = np.concatenate(parts) if parts else np.array([])
    if not len(values):
        return fallback
    low, high = min(float(values.min()), fallback[0]), max(float(values.max()), fallback[1])
    margin = max(2, (high - low) * 0.04)
    return low - margin, high + margin


def _draw_voltage(ax, device, gps_battery_mode, *, title, small=False):
    gps = _normal_gps(device)
    stats = _concat(device, ("uploads", "failures"))
    n = 0
    if gps_battery_mode == "legacy":
        n += _timed_scatter(ax, gps, "voltage_v", color=_GPS, label="GPS decoded code",
                            marker=".", size=2 if small else 3)
    n += _timed_scatter(ax, stats, "voltage_v", color=_ADC, label="Corrected ADC",
                        marker="s", size=5 if small else 9)
    n += _timed_scatter(ax, stats, "modem_voltage_v", color=_MODEM, label="Modem",
                        marker="x", size=7 if small else 11)
    ax.axhline(3.6, color="#333333", linestyle=":", linewidth=0.8)
    _style(ax, title, "Reported voltage (V)")
    ax.set_ylim(3.5, 4.3)
    voltage_arrays = [_values(stats, "voltage_v"), _values(stats, "modem_voltage_v")]
    if gps_battery_mode == "legacy":
        voltage_arrays.append(_values(gps, "voltage_v"))
    values = np.concatenate(voltage_arrays) if voltage_arrays else np.array([])
    outside = int(((values < 3.5) | (values > 4.3)).sum())
    if outside:
        ax.text(0.99, 0.02, f"Outside fixed display range: {outside}", transform=ax.transAxes,
                ha="right", fontsize=6.5, color="#666666")
    if not n:
        _note_empty(ax)
    return n


def _communication_lanes(ax, matches, color):
    dated = matches.loc[_col(matches, "event_time").notna()]
    outcomes = {"success": (_SUCCESS, "|"), "timeout": (_FAILURE, "x"),
                "failure": (_FAILURE, "x"), "shutdown": (_TX, "v")}
    lanes = {"registration": 2, "upload_failure": 1, "upload_receipt": 0}
    for kind, lane in lanes.items():
        part = dated.loc[_col(dated, "event_type").eq(kind)]
        if kind == "upload_receipt":
            ax.scatter(part["event_time"], np.full(len(part), lane), c=color,
                       marker="|", s=28, alpha=0.7, linewidths=0.7)
            continue
        for outcome, (outcome_color, marker) in outcomes.items():
            selected = part.loc[_col(part, "event_outcome").eq(outcome)]
            if len(selected):
                ax.scatter(selected["event_time"], np.full(len(selected), lane),
                           c=outcome_color, marker=marker, s=17, alpha=0.7, linewidths=0.65)
        other = part.loc[~_col(part, "event_outcome").isin(outcomes)]
        if len(other):
            ax.scatter(other["event_time"], np.full(len(other), lane), c=_UNKNOWN,
                       marker="o", s=7, alpha=0.65)
    _style(ax, "2. Communication outcomes directly beneath the GPS gaps")
    ax.set_yticks([0, 1, 2], ["Receipts\n(server UTC)", "Reported POST\nfailure records", "Registrations"])
    ax.set_ylim(-0.5, 2.8)
    ax.legend(handles=[
        Line2D([], [], color=_SUCCESS, marker="|", linestyle="none", label="Reported success"),
        Line2D([], [], color=_FAILURE, marker="x", linestyle="none", label="Reported failure / timeout"),
        Line2D([], [], color=color, marker="|", linestyle="none", label="Confirmed receipt"),
        Line2D([], [], color=_TX, marker="v", linestyle="none", label="Shutdown"),
    ], fontsize=7, loc="upper left", ncols=2)
    ax.text(0.99, 0.03, f"Untimed events omitted: {len(matches) - len(dated)}",
            transform=ax.transAxes, ha="right", fontsize=7, color="#666666")
    if dated.empty:
        _note_empty(ax, "No dated communication events")


def _device_plot(device, matches, output, *, gap_seconds, time_limits, signal_limits,
                 gps_battery_mode, color):
    fig, axes = plt.subplots(4, 1, figsize=(16, 13), sharex=True, layout="constrained")
    fig.suptitle(f"Device {device.device_id} — GPS gaps, communication and battery\n"
                 f"{_period_text([device])}", fontsize=13, color=color)
    _shade_context(axes, device, time_limits)
    all_intervals = _frame(device, "gaps")
    if len(all_intervals) and "duration_s" in all_intervals and "end" in all_intervals:
        intervals = all_intervals.copy()
        intervals["time"] = _time(intervals["end"])
        intervals["interval_s"] = _numeric(intervals, "duration_s")
    else:
        intervals = _intervals(device)
    valid = intervals.loc[_numeric(intervals, "interval_s").ge(0) & _col(intervals, "time").notna()]
    if len(valid):
        groups = valid.groupby("clock_segment", sort=False) if "clock_segment" in valid else [(0, valid)]
        for _, group in groups:
            axes[0].plot(group["time"], group["interval_s"] / 60, c=color, linewidth=0.7,
                         marker=".", markersize=1.5)
    else:
        _note_empty(axes[0], "No valid consecutive normal GPS observations")
    expected = pd.DataFrame({"time": _time(_col(all_intervals, "end")),
                             "cadence": _numeric(all_intervals, "expected_interval_s") / 60}).dropna()
    if len(expected):
        expected = expected.sort_values("time", kind="stable")
        axes[0].plot(expected["time"], expected["cadence"], c="#555555", linestyle="--",
                     linewidth=0.8, drawstyle="steps-post", label="Inferred cadence (observed local/voltage patterns)")
    axes[0].axhline(gap_seconds / 60, c="#ba7610", linestyle=":", linewidth=0.8,
                    label=f"Legacy absolute-long threshold: {gap_seconds / 60:.1f} min")
    axes[0].set_yscale("symlog", linthresh=5)
    maximum = max(float(_numeric(valid, "interval_s").max() / 60) if len(valid) else 0, gap_seconds / 60)
    ticks = [value for value in (0, 5, 10, 20, 40, 60, 180, 720, 1440, 10080) if value <= maximum * 1.15]
    axes[0].set_yticks(ticks)
    axes[0].set_yticklabels([f"{value:g}" for value in ticks])
    axes[0].set_ylim(bottom=0)
    _style(axes[0], "1. Parsed GPS record spacing and inferred cadence; shaded spans are availability intervals",
           "Interval (min; nonlinear scale)")
    handles, labels = axes[0].get_legend_handles_labels()
    if _flag(all_intervals, "unparsed_page_overlap").any():
        handles.append(Patch(facecolor="#b8b8b8", edgecolor="#777777", hatch="////", alpha=0.3))
        labels.append("Parsed source page omitted")
    axes[0].legend(handles, labels, fontsize=7, loc="upper left")
    _communication_lanes(axes[1], matches, color)
    if _draw_voltage(axes[2], device, gps_battery_mode, title="3. Battery trajectories — identical 3.5–4.3 V scale"):
        axes[2].legend(fontsize=7, loc="lower left", ncols=3)
    _draw_radio(axes[3], device, signal_limits)
    if time_limits:
        axes[3].set_xlim(time_limits)
    _date_axis(axes[3])
    axes[3].set_xlabel(_clock_axis([device]))
    fig.supxlabel(
        "Amber: source-covered flagged intervals. Grey hatching: parsed source page omitted, excluded from device-gap metrics. Grey ends: outside recorded span.\n"
        "Purple: counter restart; blue: clock recovery; grey: clock ordering; brown: sequence regression — evidence, not proven reboots.\n"
        + _clock_caption([device]) + "\n" + _gps_voltage_note(gps_battery_mode) +
        " Dotted battery line: 3.6 V reference. Reported POST failure does not prove no server receipt. Association is not cause.",
        fontsize=7.5,
    )
    return _save(fig, output / "devices" / f"{device.device_id}.svg")


def _gps_comparison(devices, metrics, colors, output, gap_seconds):
    fig, axes = _comparison_figure("GPS acquisition quality and service continuity", devices)
    a, b, c, d = axes
    x = np.arange(len(devices))
    proxy_rates, cap_rates = [], []
    for device in devices:
        gps = _normal_gps(device)
        satellites = _values(gps, "num_sv")
        ttf = _values(gps, "ttf_s")
        proxy_n = int((satellites >= 5).sum())
        cap_n = int((ttf >= 20).sum())
        proxy_rates.append(100 * proxy_n / len(satellites) if len(satellites) else np.nan)
        cap_rates.append(100 * cap_n / len(ttf) if len(ttf) else np.nan)
        for offset, numerator, denominator, rate in ((-0.18, proxy_n, len(satellites), proxy_rates[-1]),
                                                     (0.18, cap_n, len(ttf), cap_rates[-1])):
            if denominator:
                _rate_label(a, x[len(proxy_rates) - 1] + offset, rate, f"{numerator}/{denominator}")
    a.bar(x - 0.18, proxy_rates, width=0.34, color=_ADC, label="5+ satellite proxy")
    a.bar(x + 0.18, cap_rates, width=0.34, color=_TX, label="TTF at / above 20 s cap")
    _style(a, "1. Acquisition proxy and timeout-cap rates — strongly related measures", "Known-observation rate (%)")
    a.set_ylim(0, 100); _ids_axis(a, devices)
    a.legend(fontsize=7, loc="lower left")
    if not np.isfinite(proxy_rates + cap_rates).any():
        _note_empty(a, "No eligible normal GPS acquisition records")
    _boxplot(b, [_values(_normal_gps(device).loc[_numeric(_normal_gps(device), "num_sv").ge(5)], "ttf_s")
                 for device in devices], devices, colors, ylabel="TTF (s)",
             title="2. Acquisition duration for the 5+ satellite proxy only")
    _boxplot(c, [_values(_normal_gps(device), "cnr_mean") for device in devices], devices, colors,
             ylabel="Mean CNR per observation", title="3. Per-observation GPS signal quality (known values)")
    rates = [_metric(metrics, device, "gps_gaps_per30d", np.nan) for device in devices]
    hours = [_metric(metrics, device, "gps_gap_hours", np.nan) for device in devices]
    bars = d.bar(x, rates, color=[colors[str(device.device_id)] for device in devices], alpha=0.75)
    for bar, value in zip(bars, rates):
        if np.isfinite(value):
            d.annotate(f"{value:.1f}", (bar.get_x() + bar.get_width() / 2, value),
                       xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)
    right = d.twinx()
    right.plot(x, hours, "D", color="#333333", markersize=4)
    right.set_ylabel("Total absolute-long interval hours")
    right.spines["top"].set_visible(False); right.tick_params(labelsize=8)
    _style(d, f"4. Legacy >{gap_seconds / 60:.1f} min interval rate and elapsed hours", "Intervals per 30 recorded days")
    _ids_axis(d, devices)
    d.legend(handles=[Patch(facecolor="#8b55a5", alpha=0.7, label="Long intervals / 30 days"),
                      Line2D([], [], color="#333333", marker="D", linestyle="none", label="Elapsed interval hours")],
             fontsize=7)
    if not np.isfinite(rates + hours).any():
        _note_empty(d, "No eligible service interval-rate or duration estimate")
    fig.supxlabel("Clock-marker records and replay pages are excluded from normal performance. CNR requires satellite data.\n"
                  "A 5+ satellite observation is not a solved position. Long-interval hours are elapsed interval duration, not proven lost logging time.\n"
                  "Absolute-long and cadence-relative gaps answer different questions; rates depend on the selected recording period.\n"
                  + _clock_caption(devices), fontsize=8)
    return _save(fig, output / "comparisons" / "gps.svg")


def _lte_comparison(devices, metrics, colors, output):
    fig, axes = _comparison_figure("LTE outcome rates, successful registration timing and monthly trends", devices)
    a, b, c, d = axes
    x = np.arange(len(devices))
    totals = np.array([int(_col(device.registrations, "outcome").isin(["success", "timeout", "shutdown"]).sum())
                       for device in devices])
    bottom = np.zeros(len(devices))
    for outcome, color in (("success", _SUCCESS), ("timeout", _FAILURE), ("shutdown", _TX)):
        counts = np.array([int(_col(device.registrations, "outcome").eq(outcome).sum()) for device in devices])
        values = np.divide(counts * 100.0, totals, out=np.full(len(devices), np.nan), where=totals > 0)
        a.bar(x, values, bottom=bottom, color=color, label=outcome.capitalize(), alpha=0.8)
        bottom += np.nan_to_num(values)
    for i, device in enumerate(devices):
        successes = int(_col(device.registrations, "outcome").eq("success").sum())
        unknown = len(device.registrations) - totals[i]
        label = f"{successes}/{totals[i]}\nunknown={unknown}" if totals[i] else f"n/a\nknown=0; unknown={unknown}"
        a.text(i, 97, label, ha="center", va="top", fontsize=6,
               rotation=90, bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85})
    _style(a, "1. Registration outcomes — rates among known outcomes", "Known-outcome rate (%)")
    a.set_ylim(0, 100); _ids_axis(a, devices); a.legend(fontsize=7, loc="lower left")
    duration_count = 0
    for i, device in enumerate(devices):
        success = device.registrations.loc[_col(device.registrations, "outcome").eq("success")]
        tier = _col(success, "tier").fillna("").astype(str).str.upper()
        for offset, label, color in ((-0.17, "HOT", _TX), (0.17, "COLD", _MODEM)):
            values = _values(success.loc[tier.str.contains(r"(?:^|\s)" + label + "$", regex=True)], "duration_s")
            if len(values):
                duration_count += len(values)
                artists = b.boxplot([values], positions=[i + offset], widths=0.27, patch_artist=True,
                                    showfliers=True, flierprops={"marker": ".", "markersize": 2, "alpha": 0.4},
                                    medianprops={"color": "#222222"})
                artists["boxes"][0].set(facecolor=color, alpha=0.55)
                b.text(i + offset, 0.97, str(len(values)), transform=b.get_xaxis_transform(),
                       ha="center", va="top", fontsize=6, color=color)
    _style(b, "2. Successful registration duration by HOT / COLD tier (n shown)", "Duration (s)")
    _ids_axis(b, devices)
    b.legend(handles=[Patch(facecolor=_TX, alpha=0.55, label="HOT successes"),
                      Patch(facecolor=_MODEM, alpha=0.55, label="COLD successes")], fontsize=7)
    if not duration_count:
        _note_empty(b, "No known HOT/COLD success durations")
    known = np.array([_metric(metrics, device, "upload_known_outcomes", 0) for device in devices], dtype=float)
    success = np.array([_metric(metrics, device, "upload_successes", 0) for device in devices], dtype=float)
    failed = np.array([_metric(metrics, device, "upload_failures", 0) for device in devices], dtype=float)
    for counts, bottom_counts, label, color in ((success, np.zeros(len(devices)), "Transport success", _SUCCESS),
                                               (failed, success, "Transport failure", _FAILURE)):
        height = np.divide(counts * 100, known, out=np.full(len(devices), np.nan), where=known > 0)
        base = np.divide(bottom_counts * 100, known, out=np.zeros(len(devices)), where=known > 0)
        c.bar(x - 0.17, height, bottom=base, width=0.28, color=color, label=label, alpha=0.8)
    evidence = [(key, label, color) for key, label, color in (
        ("post_failed_received", "Failed POST: receipt confirmed", _ADC),
        ("post_failed_no_receipt", "Failed POST: no matching receipt", _MODEM),
        ("post_failed_ambiguous", "Failed POST: ambiguous evidence", _UNKNOWN))]
    evidence_total = np.array([sum(_metric(metrics, device, key, 0) for key, _, _ in evidence)
                               for device in devices], dtype=float)
    base = np.zeros(len(devices))
    for key, label, color in evidence:
        counts = np.array([_metric(metrics, device, key, 0) for device in devices], dtype=float)
        height = np.divide(counts * 100, evidence_total, out=np.full(len(devices), np.nan), where=evidence_total > 0)
        c.bar(x + 0.17, height, bottom=base, width=0.28, color=color, label=label, alpha=0.8)
        base += np.nan_to_num(height)
    for i in range(len(devices)):
        if known[i]:
            c.text(i - 0.17, 97, f"{int(success[i])}/{int(known[i])}", rotation=90, ha="center", va="top", fontsize=6,
                   bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})
        if evidence_total[i]:
            c.text(i + 0.17, 97, f"n={int(evidence_total[i])}", rotation=90, ha="center", va="top", fontsize=6,
                   bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})
    _style(c, "3. Known POST results (left) / failed-POST receipt evidence (right)", "Within-population rate (%)")
    c.set_ylim(0, 100)
    _ids_axis(c, devices, [f"{device.device_id}\nno stats={int(_metric(metrics, device, 'upload_stats_missing', 0))}"
                          for device in devices])
    c.legend(fontsize=6.3, loc="lower left", ncols=2)
    if not known.sum() and not evidence_total.sum():
        _note_empty(c, "No known POST outcomes or failed-POST receipt evidence")
    monthly_parts = [_frame(device, "monthly") for device in devices]
    monthly = pd.concat(monthly_parts, ignore_index=True, sort=False) if monthly_parts else pd.DataFrame()
    plotted = False
    if not monthly.empty and "month" in monthly:
        for tier, color in (("hot", _TX), ("cold", _MODEM)):
            attempts, timeouts = tier + "_attempts", tier + "_timeouts"
            if attempts not in monthly or timeouts not in monthly:
                continue
            grouped = monthly.groupby("month", sort=True)[[attempts, timeouts]].sum()
            dates = pd.to_datetime(grouped.index.astype(str).str[:7] + "-01", utc=True, errors="coerce")
            values = (100 * grouped[timeouts] / grouped[attempts].where(grouped[attempts] > 0)).to_numpy()
            d.plot(dates, values, "-o", color=color, linewidth=1, markersize=4, label=tier.upper())
            for date, rate, numerator, denominator in zip(dates, values, grouped[timeouts], grouped[attempts]):
                if np.isfinite(rate):
                    d.annotate(f"{int(numerator)}/{int(denominator)}", (date, rate),
                               xytext=(0, 7 if tier == "hot" else -12), textcoords="offset points",
                               ha="center", fontsize=6.5, color=color)
            plotted = True
    _style(d, "4. Fleet monthly timeout rates — weighted attempt counts", "Timeouts / known tier attempts (%)")
    d.set_ylim(0, 100); _date_axis(d); d.set_xlabel("Month of recorded registration event")
    if plotted:
        d.legend(fontsize=7)
    else:
        _note_empty(d, "No monthly tier data")
    fig.supxlabel("Successful duration excludes timeouts; other success tiers are not included in the HOT/COLD timing panel.\n"
                  "Transport failure and server receipt are different evidence. No matching receipt does not prove non-receipt.\n"
                  "Monthly rates depend on recorded exposure and missing logs; no network/firmware cause is established.\n"
                  + _clock_caption(devices), fontsize=8)
    return _save(fig, output / "comparisons" / "lte.svg")


def _battery_comparison(devices, colors, output, gps_battery_mode):
    columns = 3
    rows = max(1, int(np.ceil(len(devices) / columns)))
    fig, axes = plt.subplots(rows, columns, figsize=(17, max(5, rows * 3.4)), sharex=True, sharey=True,
                              squeeze=False, layout="constrained")
    fig.suptitle("Battery trajectories by device — identical voltage scale\n" + _period_text(devices), fontsize=13)
    limits = _time_limits(devices)
    for index, ax in enumerate(axes.flat):
        if index >= len(devices):
            ax.set_visible(False)
            continue
        device = devices[index]
        _draw_voltage(ax, device, gps_battery_mode, title=str(device.device_id), small=True)
        ax.title.set_color(colors[str(device.device_id)])
        ax.set_title(str(device.device_id), loc="left", color=colors[str(device.device_id)], fontsize=10)
        if limits:
            ax.set_xlim(limits)
        _date_axis(ax)
        if index == 0:
            ax.legend(handles=[Line2D([], [], color=_GPS, marker=".", linestyle="none", label="GPS decoded code"),
                               Line2D([], [], color=_ADC, marker="s", linestyle="none", markersize=3, label="Corrected ADC"),
                               Line2D([], [], color=_MODEM, marker="x", linestyle="none", label="Modem"),
                               Line2D([], [], color="#333333", linestyle=":", label="3.6 V reference")],
                      fontsize=6.5, loc="lower left", ncols=2)
    fig.supxlabel(_gps_voltage_note(gps_battery_mode) + "\n"
                  "Clock-marker values are excluded. The 3.6 V line is a reported-voltage reference, not an absolute cell-voltage threshold.\n"
                  + _clock_caption(devices) + " Gaps in recorded values are not interpolated. Agreement is not absolute accuracy.",
                  fontsize=8)
    return _save(fig, output / "comparisons" / "battery.svg")


def _gap_label(value):
    from .reporting import gap_class_description
    return gap_class_description(value)


def _links_comparison(devices, matches_by_device, metrics, colors, output, tolerance_seconds):
    fig, axes = _comparison_figure("GPS gaps and LTE evidence — descriptive associations", devices)
    a, b, c, d = axes
    x = np.arange(len(devices))
    parts = [(_frame(device, "gaps").loc[_flag(_frame(device, "gaps"), "cadence_gap")
                                       & ~_flag(_frame(device, "gaps"), "unparsed_page_overlap")
                                       & ~_col(_frame(device, "gaps"), "gap_class").eq("unparsed_source")])
             for device in devices]
    classes = sorted({str(value) for frame in parts for value in _col(frame, "gap_class").dropna()
                      if str(value) != "regular"})
    bottom = np.zeros(len(devices))
    for index, gap_class in enumerate(classes):
        hours = [float(_numeric(frame.loc[_col(frame, "gap_class").eq(gap_class)], "duration_s").sum()) / 3600
                 for frame in parts]
        a.bar(x, hours, bottom=bottom, color=_DEVICE_PALETTE[index % len(_DEVICE_PALETTE)],
              label=_gap_label(gap_class), alpha=0.75)
        bottom += hours
    _style(a, "1. Cadence-relative gap interval hours by descriptive label", "Elapsed interval hours")
    _ids_axis(a, devices)
    if classes:
        a.legend(fontsize=6.5)
    else:
        _note_empty(a, "No cadence-relative gaps in the selected period")
    observed = [_metric(metrics, device, "observed_gap_timeout_percent", np.nan) for device in devices]
    expected = [_metric(metrics, device, "expected_gap_timeout_percent", np.nan) for device in devices]
    b.bar(x - 0.18, observed, width=0.34, color=_TX, label="Observed timeout overlap")
    b.bar(x + 0.18, expected, width=0.34, color=_MODEM, label="Monthly uniform-start baseline")
    for i, device in enumerate(devices):
        eligible = _metric(metrics, device, "gap_timeout_eligible", 0)
        hits = _metric(metrics, device, "gap_timeout_hits", 0)
        if eligible and np.isfinite(observed[i]):
            _rate_label(b, i - 0.18, float(observed[i]), f"{hits}/{eligible}")
    _style(b, "2. Timeout overlap versus analytical descriptive baseline", "Eligible intervals with a timeout (%)")
    b.set_ylim(0, 100); _ids_axis(b, devices); b.legend(fontsize=7, loc="lower left")
    if not np.isfinite(observed + expected).any():
        _note_empty(b, "No eligible interval / registration overlap estimate")
    plotted = False
    for device, gaps in zip(devices, parts):
        data = pd.DataFrame({"voltage": _numeric(gaps, "boundary_voltage_v"),
                             "hours": _numeric(gaps, "duration_s") / 3600}).dropna()
        if len(data):
            c.scatter(data["voltage"], data["hours"], c=colors[str(device.device_id)], s=16, alpha=0.65,
                      label=f"{device.device_id} (n={len(data)})")
            plotted = True
    _style(c, "3. Cadence-relative interval duration and pre-gap voltage", "Elapsed interval duration (hours)")
    c.set_xlabel("Pre-gap reported GPS voltage (V)")
    c.set_yscale("symlog", linthresh=1)
    if plotted:
        c.legend(fontsize=6.5, ncols=2)
    else:
        _note_empty(c, "No valid pre-gap voltage paired with a cadence-relative gap")
    lengths, labels = [], []
    for device in devices:
        outages = _frame(device, "outages")
        eligible = outages.loc[_numeric(outages, "gps_count").gt(0)]
        valid = eligible.loc[_numeric(eligible, "duration_s").notna()]
        if len(valid):
            row = valid.loc[_numeric(valid, "duration_s").idxmax()]
            lengths.append(float(row["duration_s"]) / 86400)
            labels.append(f"{int(row['gps_count']):,} GPS rows")
        else:
            lengths.append(np.nan); labels.append("n/a")
    bars = d.bar(x, lengths, color=[colors[str(device.device_id)] for device in devices], alpha=0.75)
    for bar, length, label in zip(bars, lengths, labels):
        if np.isfinite(length):
            d.annotate(label, (bar.get_x() + bar.get_width() / 2, length), xytext=(0, 3),
                       textcoords="offset points", ha="center", fontsize=6.7)
    _style(d, "4. Longest receipt interval containing recorded GPS data", "Time between receipts (days)")
    _ids_axis(d, devices)
    if not np.isfinite(lengths).any():
        _note_empty(d)
    fig.supxlabel("Baseline: same calendar month, recorded GPS/registration overlap, and each observed interval duration; uniform start times only.\n"
                  "Voltage and missing logs are not controlled. No p-values or causal verdict. A boundary low reading is not proof of battery causation.\n"
                  f"GPS nearest-time lookup (±{tolerance_seconds:g} s) remains contextual; GPS records within a receipt interval do not prove continuous logging or payload ownership.\n"
                  + _clock_caption(devices),
                  fontsize=8)
    return _save(fig, output / "comparisons" / "gps_lte.svg")


def _fleet_status(devices, metrics, colors, output):
    fig, axes = plt.subplots(3, 1, figsize=(17, 11), sharex=True, layout="constrained")
    references = [_time(row.get("export_reference")) for row in metrics.values()]
    references = [time for time in references if not pd.isna(time)]
    reference = max(references) if references else None
    reference_label = f"{reference:%d %b %Y %H:%M} UTC" if reference is not None else "unavailable"
    fig.suptitle(f"Fleet coverage and evidence at export — not live status\n"
                 f"Export reference: {reference_label}; {_period_text(devices)}", fontsize=13)
    y = np.arange(len(devices))
    for i, device in enumerate(devices):
        color = colors[str(device.device_id)]
        for frame, offset, marker, width in ((_normal_gps(device), 0.13, "o", 3.5),
                                             (device.uploads, -0.13, "|", 1.5)):
            times = _time(_col(frame, "time")).dropna()
            if len(times):
                axes[0].plot([times.min(), times.max()], [i + offset, i + offset], c=color, linewidth=width, alpha=0.8)
                axes[0].plot([times.max()], [i + offset], marker=marker, c=color, markersize=4)
        silence = _metric(metrics, device, "receipt_silence_days", np.nan)
        if np.isfinite(silence):
            axes[0].text(0.995, i, f"Receipt absence: {silence:.1f} d",
                         transform=axes[0].get_yaxis_transform(), ha="right", va="center", fontsize=7)
        for _, row in _frame(device, "outages").iterrows():
            start, end = _time(row.get("start")), _time(row.get("end"))
            if pd.isna(start) or pd.isna(end) or start >= end:
                continue
            ongoing = bool(row.get("ongoing_at_export", False))
            axes[1].plot([start, end], [i, i], color=color, linewidth=7 if ongoing else 4,
                         alpha=0.65, linestyle="--" if ongoing else "-")
        events = _frame(device, "events")
        for kind, marker in (("counter_restart", "v"), ("clock_recovery", "o"),
                             ("clock_ordering", "x"), ("sequence_regression", "^")):
            selected = events.loc[_col(events, "kind").eq(kind)]
            times = _time(_col(selected, "time")).dropna()
            if len(times):
                axes[2].scatter(times, np.full(len(times), i), c=color, marker=marker, s=28, alpha=0.8)
    titles = ("1. Recorded GPS span (thick) and receipt span (thin); not continuous-uptime proof",
              "2. Receipt intervals / outages; dashed portions continue to the export reference",
              "3. Counter and clock evidence — not proven physical reboot counts")
    for ax, title in zip(axes, titles):
        _style(ax, title)
        ax.set_yticks(y, [str(device.device_id) for device in devices])
        ax.set_ylim(-0.6, max(len(devices) - 0.4, 0.6))
        ax.invert_yaxis()
        if reference is not None:
            ax.axvline(reference, color="#333333", linestyle=":", linewidth=0.7)
    axes[2].legend(handles=[Line2D([], [], color="#555555", marker="v", linestyle="none", label="Counter restart evidence"),
                            Line2D([], [], color="#555555", marker="o", linestyle="none", label="Clock recovery evidence"),
                            Line2D([], [], color="#555555", marker="x", linestyle="none", label="Clock ordering evidence"),
                            Line2D([], [], color="#555555", marker="^", linestyle="none", label="Sequence regression evidence")],
                   fontsize=7, loc="upper left", ncols=2)
    limits = _time_limits(devices, metrics)
    if limits:
        axes[2].set_xlim(limits)
    _date_axis(axes[2]); axes[2].set_xlabel(_clock_axis(devices))
    fig.supxlabel("Receipt absence is relative to this exported dataset, not a live device verdict. Last valid voltage may predate the last receipt.\n"
                  "A span between first and last records does not demonstrate uninterrupted collection. Event labels describe evidence only.\n"
                  + _clock_caption(devices), fontsize=8)
    return _save(fig, output / "comparisons" / "fleet_status.svg")


def _cadence_comparison(devices, colors, output):
    months = sorted({str(value)[:7] for device in devices for value in _col(_frame(device, "monthly"), "month").dropna()})
    fig, ax = plt.subplots(figsize=(16, max(5, 0.7 * len(devices) + 2)), layout="constrained")
    fig.suptitle("Inferred GPS cadence by device and month\n" + _period_text(devices), fontsize=13)
    values = np.full((len(devices), len(months)), np.nan)
    counts = np.zeros((len(devices), len(months)), dtype=int)
    for i, device in enumerate(devices):
        monthly = _frame(device, "monthly")
        for _, row in monthly.iterrows():
            month = str(row.get("month"))[:7]
            if month in months:
                j = months.index(month)
                cadence = row.get("median_cadence_s")
                if cadence is not None and not pd.isna(cadence):
                    values[i, j] = float(cadence) / 60
                count = row.get("gps_count", 0)
                counts[i, j] = 0 if pd.isna(count) else int(count)
    if months and np.isfinite(values).any():
        image = ax.imshow(np.ma.masked_invalid(values), cmap="Purples", aspect="auto", vmin=0,
                          vmax=max(50, float(np.nanmax(values))), interpolation="nearest")
        fig.colorbar(image, ax=ax, pad=0.02, label="Median inferred interval (minutes)")
        maximum = max(50, float(np.nanmax(values)))
        for i in range(len(devices)):
            for j in range(len(months)):
                text = _cadence_cell(values[i, j], counts[i, j])
                ax.text(j, i, text, ha="center", va="center", fontsize=8,
                        color="white" if np.isfinite(values[i, j]) and values[i, j] > maximum * 0.58 else "#333333")
        ax.set_xticks(np.arange(len(months)), months)
        ax.set_yticks(np.arange(len(devices)), [str(device.device_id) for device in devices])
        for label, device in zip(ax.get_yticklabels(), devices):
            label.set_color(colors[str(device.device_id)])
        ax.set_xlabel("Month of recorded GPS observation"); ax.set_ylabel("Device")
    else:
        _note_empty(ax, "No monthly cadence estimates")
        ax.set_xticks([]); ax.set_yticks([])
    fig.supxlabel("Cadence is inferred from observed local and voltage patterns, not proof of the active firmware configuration.\n"
                  "Counts are cleaned normal GPS observations. Missing cells mean no usable estimate, not zero cadence.\n"
                  + _clock_caption(devices), fontsize=8)
    return _save(fig, output / "comparisons" / "cadence.svg")


def write_all_plots(devices, matches_by_device, metrics, output_dir: Path, *,
                    tolerance_seconds: float = 60, gap_seconds: float = 3020,
                    gps_battery_mode: str = "legacy") -> list[Path]:
    """Write one device timeline and six fleet comparisons, using prepared diagnostics."""
    if gps_battery_mode not in ("legacy", "raw"):
        raise ValueError("gps_battery_mode must be 'legacy' or 'raw'")
    devices = _ordered(devices)
    output_dir = Path(output_dir)
    colors = _colors(devices)
    metric_rows = {str(row["device_id"]): row for row in metrics}
    limits = _time_limits(devices, metric_rows)
    signal_limits = (_radio_limits(devices, "rsrp_dbm", (-145, -45)),
                     _radio_limits(devices, "tx_dbm", (-30, 25)))
    with matplotlib.rc_context(_PLOT_RC):
        paths = [_device_plot(device, matches_by_device[str(device.device_id)], output_dir,
                              gap_seconds=gap_seconds, time_limits=limits, signal_limits=signal_limits,
                              gps_battery_mode=gps_battery_mode, color=colors[str(device.device_id)])
                 for device in devices]
        paths.extend([
            _gps_comparison(devices, metric_rows, colors, output_dir, gap_seconds),
            _lte_comparison(devices, metric_rows, colors, output_dir),
            _battery_comparison(devices, colors, output_dir, gps_battery_mode),
            _links_comparison(devices, matches_by_device, metric_rows, colors, output_dir, tolerance_seconds),
            _fleet_status(devices, metric_rows, colors, output_dir),
            _cadence_comparison(devices, colors, output_dir),
        ])
    return paths


_BATTERY_PAIR_SOURCES = (
    ("upload_receipt", "Receipt", "o"),
    ("failed_attempt", "Failed attempt", "x"),
)


def _pair_source_legend(frame):
    return [Line2D([], [], color="#666666", marker=marker, linestyle="none",
                   markerfacecolor="none", markersize=4,
                   label=f"{label} rows (n={int(frame['source_kind'].eq(source).sum()):,})")
            for source, label, marker in _BATTERY_PAIR_SOURCES]


def _pair_dates(ax, times, devices=()):
    valid = times.dropna()
    if valid.empty:
        ax.set_xticks([])
        ax.set_xlabel("No usable calendar timestamps")
        return
    first, last = valid.min(), valid.max()
    padding = max((last - first) * 0.025, pd.Timedelta(hours=1))
    ax.set_xlim(first - padding, last + padding)
    _date_axis(ax)
    ax.set_xlabel(_clock_axis(devices))


def _mv_text(value):
    return "n/a" if value is None or pd.isna(value) else f"{value:.1f} mV"


def _adc_modem_plot(device, pairs, summary, output_dir, *, device_color):
    """Plot every valid voltage pair, retaining source and timing limitations."""
    fig, axes = plt.subplots(2, 2, figsize=(17, 12), layout="constrained")
    voltage_ax, difference_ax, temperature_ax, agreement_ax = axes.flat
    fig.suptitle(
        f"Device {device.device_id} — corrected/calibrated ADC versus modem voltage\n"
        f"{_period_text([device])}\n"
        f"Valid pairs: {summary['pairs']:,}; dated: {summary['timed_pairs']:,}; "
        f"with valid temperature: {summary['temperature_pairs']:,}. All points retained.",
        fontsize=13, color=device_color,
    )
    # battery_pairs owns validity and pairing. This copy adds plot-only time
    # normalisation without changing the helper output or source DeviceData.
    pairs = pairs.copy()
    pairs["time"] = pd.to_datetime(pairs["time"], utc=True, errors="coerce")
    timed = pairs.loc[pairs["time"].notna()].sort_values("time", kind="stable")
    temperatures = pairs.loc[_numeric(pairs, "temp_c").notna()]

    for source, label, marker in _BATTERY_PAIR_SOURCES:
        selected = timed.loc[timed["source_kind"].eq(source)]
        if selected.empty:
            continue
        for column, sensor, color in (("adc_v", "Corrected ADC", _ADC),
                                       ("modem_v", "Modem", _MODEM)):
            voltage_ax.scatter(selected["time"], selected[column], s=13, alpha=0.65,
                               c=color, marker=marker, linewidths=0.55,
                               label=f"{sensor} — {label} (n={len(selected):,})")
        difference_ax.scatter(selected["time"], selected["diff_mv"], s=13, alpha=0.65,
                              c=_GPS, marker=marker, linewidths=0.55,
                              label=f"{label} (n={len(selected):,})")
    _style(voltage_ax, "1. Paired exported sensor values over time", "Voltage (V)")
    if not timed.empty:
        voltage_ax.legend(fontsize=7, ncols=2, loc="upper left", columnspacing=0.8)
    else:
        _note_empty(voltage_ax, "No valid voltage pairs with a calendar timestamp")
    _pair_dates(voltage_ax, timed["time"], [device])

    difference_ax.axhline(0, color="#444444", linestyle="--", linewidth=0.8,
                          label="Zero difference")
    if not timed.empty:
        residual = pd.Series(timed["diff_mv"].to_numpy(), index=pd.DatetimeIndex(timed["time"]))
        median = residual.rolling("7D", min_periods=3, closed="right").median()
        if median.notna().any():
            difference_ax.plot(median.index, median.values, color="#b66a05", linewidth=1.4,
                               label="7-day median (min 3)", zorder=4)
        else:
            difference_ax.text(0.02, 0.03, "No 7-day window contains 3 dated pairs",
                               transform=difference_ax.transAxes, fontsize=7, color="#666666")
    else:
        _note_empty(difference_ax, "No dated voltage pairs")
    _style(difference_ax, "2. ADC minus modem difference over time", "ADC − modem (mV)")
    difference_ax.legend(fontsize=7, loc="upper left", handlelength=1.5)
    _pair_dates(difference_ax, timed["time"], [device])

    age_minutes = _numeric(temperatures, "temp_age_s") / 60
    known_age = age_minutes.ge(0) & age_minutes.notna()
    max_age = float(age_minutes.loc[known_age].max()) if known_age.any() else 1.0
    age_norm = SymLogNorm(linthresh=1.0, linscale=1.0, vmin=0,
                          vmax=max(1.0, max_age), base=10)
    age_artist = None
    for source, _, marker in _BATTERY_PAIR_SOURCES:
        source_mask = temperatures["source_kind"].eq(source)
        known = temperatures.loc[source_mask & known_age]
        unknown = temperatures.loc[source_mask & ~known_age]
        if len(known):
            age_artist = temperature_ax.scatter(
                known["temp_c"], known["diff_mv"], c=age_minutes.loc[known.index],
                norm=age_norm, cmap="viridis", s=17, marker=marker, alpha=0.75,
                linewidths=0.6,
            )
        if len(unknown):
            temperature_ax.scatter(unknown["temp_c"], unknown["diff_mv"], c=_UNKNOWN,
                                   s=17, marker=marker, alpha=0.65, linewidths=0.6)
    temperature_ax.axhline(0, color="#444444", linestyle="--", linewidth=0.8)
    _style(temperature_ax, "3. Difference versus reported BMA temperature", "ADC − modem (mV)")
    missing_temperature = len(pairs) - len(temperatures)
    temperature_ax.set_xlabel(
        "Reported valid BMA temperature (°C)\n"
        f"Pairs without valid temperature excluded from this panel: {missing_temperature:,}",
        fontsize=8,
    )
    if temperatures.empty:
        _note_empty(temperature_ax, "No paired rows with a valid temperature")
    else:
        handles = _pair_source_legend(temperatures)
        handles.append(Patch(facecolor=_UNKNOWN,
                             label=f"Temperature age unknown (n={int((~known_age).sum()):,})"))
        temperature_ax.legend(handles=handles, fontsize=7, loc="upper left")
    if age_artist is not None:
        colorbar = fig.colorbar(age_artist, ax=temperature_ax, pad=0.02, fraction=0.055)
        age_ticks = [value for value in (0, 1, 5, 10, 30, 60, 180, 720, 1440, 10080)
                     if value <= max(1.0, max_age)]
        if max_age > age_ticks[-1] * 1.5:
            age_ticks.append(max_age)
        colorbar.set_ticks(age_ticks)
        colorbar.set_ticklabels([f"{value:g}" for value in age_ticks])
        colorbar.set_label("Reported temperature age (min; nonlinear above 1 min)", fontsize=8)
        colorbar.ax.tick_params(labelsize=7)

    for source, label, marker in _BATTERY_PAIR_SOURCES:
        selected = pairs.loc[pairs["source_kind"].eq(source)]
        if len(selected):
            agreement_ax.scatter(selected["modem_v"], selected["adc_v"], c=_GPS,
                                 s=15, marker=marker, alpha=0.65, linewidths=0.6,
                                 label=f"{label} (n={len(selected):,})")
    _style(agreement_ax, "4. Sensor agreement — all valid voltage pairs", "Corrected/calibrated ADC voltage (V)")
    agreement_ax.set_xlabel("Modem voltage (V)")
    if not pairs.empty:
        sensor_values = np.concatenate([_values(pairs, "adc_v"), _values(pairs, "modem_v")])
        low, high = float(sensor_values.min()), float(sensor_values.max())
        pad = max(0.01, (high - low) * 0.04)
        low, high = low - pad, high + pad
        agreement_ax.plot([low, high], [low, high], linestyle="--", color="#444444",
                          linewidth=0.8, label="1:1 agreement")
        agreement_ax.set_xlim(low, high)
        agreement_ax.set_ylim(low, high)
        agreement_ax.set_aspect("equal", adjustable="box")
        agreement_ax.legend(fontsize=7, loc="lower right")
        agreement_ax.text(
            0.03, 0.97,
            f"Valid pairs: {summary['pairs']:,}\n"
            f"Mean ADC − modem: {_mv_text(summary['mean_diff_mv'])}\n"
            f"Median absolute difference: {_mv_text(summary['median_abs_diff_mv'])}\n"
            f"95th percentile absolute difference: {_mv_text(summary['p95_abs_diff_mv'])}",
            transform=agreement_ax.transAxes, va="top", fontsize=8,
            bbox={"facecolor": "white", "edgecolor": "#dddddd", "alpha": 0.9},
        )
    else:
        _note_empty(agreement_ax, "No valid ADC/modem voltage pairs")

    # The time and temperature views use identical, unclipped residual limits.
    residual_values = _values(pairs, "diff_mv")
    if len(residual_values):
        low, high = min(0.0, float(residual_values.min())), max(0.0, float(residual_values.max()))
        pad = max(5.0, (high - low) * 0.06)
        difference_ax.set_ylim(low - pad, high + pad)
        temperature_ax.set_ylim(low - pad, high + pad)
    fig.supxlabel(
        _clock_caption([device]) + "\n"
        "Same exported row does not imply simultaneous measurements. Cache age and measurement loads affect agreement, not absolute accuracy.\n"
        "ADC correction is already applied. Reported temperature age is context, not sensor separation. No extra correction or pass/fail threshold.",
        fontsize=8,
    )
    return _save(fig, Path(output_dir) / "battery_adc_modem" / f"{device.device_id}.svg")


def write_adc_modem_plots(devices, output_dir: Path) -> list[Path]:
    """Write one four-panel ADC/modem figure per device, without GPS values.

    Voltage pairing and summary rules are shared with ``battery.py``. The
    writer keeps every valid pair; only time-based panels require a timestamp,
    and only the temperature panel requires a valid temperature measurement.
    """
    from .battery import battery_pairs, battery_summary

    paths = []
    devices = _ordered(devices)
    colors = _colors(devices)
    with matplotlib.rc_context(_PLOT_RC):
        for device in devices:
            pairs = battery_pairs(device)
            paths.append(_adc_modem_plot(device, pairs, battery_summary(pairs), Path(output_dir),
                                         device_color=colors[str(device.device_id)]))
    return paths
