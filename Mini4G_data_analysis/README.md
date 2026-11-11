# Mini4G data analysis

Reusable offline analysis of GPS observations/satellite measurements, upload
receipts, device-reported POST results and registration events. Original data is
never rewritten. Firmware, backend and position solving are outside this tool.

## Install and run

Use your existing Python environment. The checked environment is Python 3.15.2,
pandas 3.1.1, NumPy 2.5.4 and Matplotlib 3.11.2. No extra test package is required.
If dependencies are needed, install them yourself with:

```powershell
python3 -m pip install -r requirements.txt
```

From this directory:

```powershell
python3 -B analyse.py --data C:\Mini4G_data\Data --output C:\Mini4G_data\Outputs
```

Open `C:\Mini4G_data\Outputs\overview.md` first. It starts with findings, export
status and per-tag verdicts, then links figures, quality decisions and definitions.

## Input layout

Only this layout is supported:

```text
Data/
  Tag188602670/
    188602670_ublox.dat
    188602670_ublox_GPS_Obs.csv
    188602670_ublox_GPS_SVs.csv
    188602670_uploads.csv
    188602670_failed_stats.csv
    188602670_registrations.csv
  Tag2622153757/
    ...same filenames with that numeric ID...
```

Numeric IDs are discovered, not hardcoded. The previous separate `_stats` and
`_ublox` directory layout is not supported. CSVs are the existing decoder/export
outputs. Raw DATs provide byte-level page identity; when absent, weaker semantic
replay handling is explicitly identified in the quality report. GPS decoding is
not rerun or repaired by this analysis. Header-only timestamp hints identify raw
pages missing from the decoded CSV; their overlapping intervals are shown as
parsed-export coverage uncertainty, rather than evidence that GPS stopped.

Unrelated folders such as `devices_pos_files`, position files inside a tag folder,
backups and reference reports are not consumed or hashed by the main analysis.
The separate KML exporter below consumes the supplied POS files explicitly. The manifest identifies
exactly the selected CSV and DAT files. A malformed required header fails clearly
rather than silently producing a healthy partial result.

## Study period and clocks

The default `--period study` begins **1 July 2026 UTC**, following the agreed
field-study period. June is excluded from performance metrics and plots. The KML
exporter uses the same default date, shared in `mini4g_analysis/study.py`.

- `--start` explicitly overrides the default start.
- `--end` is exclusive. A date denotes midnight at its start.
- `--period all` includes the complete supplied history when no explicit start is
  given, including bench data.
- Optional `--period service` retains the older fleet-common bench-break inference
  for reproducing earlier work; it is no longer the default.
- Full-source cleaning audits remain separate from selected-period results.

For July through 17 August inclusive:

```powershell
python3 -B analyse.py --data C:\Mini4G_data\Data --output C:\Mini4G_data\Outputs\august --start 2026-07-01 --end 2026-08-18
```

The device firmware uses GPS-scale time, approximately UTC plus 18 seconds. By
default the loader subtracts 18 seconds from device GPS, failed-attempt,
registration and temperature/stat timestamps, leaving server receipt UTC alone.
Original values remain in `recorded_*` columns and raw input files. Set
`--device-clock-offset-seconds 0` to reproduce unshifted analysis or to analyse an
export whose device clock is already UTC. The chosen basis is recorded in every
run. The main performance analysis does not fit clock drift or calculate
positions. The separate KML exporter estimates registration positions as described
below.

Export status uses the latest selected receipt in the dataset, capped by an
explicit end, not today's wall clock. Last receipt, last GPS and last available
voltage measurement are separate timestamps. No receipt near export does not
establish a dead battery, no attempted uploads or a live device's current state.

## Cleaning and traceability

`data_quality.md` summarises decisions; `data_quality.json` retains source-row,
page-line/hash and canonical-record audit references. Cleaning occurs in memory.

- Byte-identical raw DAT page replays are counted once, retaining the first
  observation/satellite group and its original provenance. Distinct replay groups
  and extra physical page copies are separate counts.
- Whole-payload duplicates with different TTF are identified using observation
  fields plus the complete satellite payload; timestamps alone are insufficient.
- Legacy wrapped clock-record battery candidates are excluded from physical
  voltage. Decoded values are diagnostic only. Ambiguous low-code values are not
  automatically increased by 100 merely because neighbours are higher.
- Identified clock records remain evidence/coverage but are excluded from normal
  GPS acquisition metrics. Their uncertain timing encoding is not silently
  reinterpreted. Replay handling precedes ordering/segment checks; remaining
  backwards ordering is not called a proven reboot.
- Exact failed-stat duplicates are removed. Calendar registration identities are
  consolidated, preserving consistent late enrichment and exposing contradictory
  known values rather than blindly retaining the first. Untimed events use only
  exact duplicate evidence.
- Receipt rows are retained even if their attached stats are rejected. Grossly
  future temperature/stat times, after clock alignment, invalidate the joined
  telemetry rather than turning that receipt into a failure.
- Known POST outcomes and confirmed receipt evidence are different measurements.
  A failed result with a unique same-sequence nearby receipt is labelled received;
  no matching receipt is not proof of non-delivery or packet-level response loss.
- Counter decreases to one, other sequence regressions and clock-record markers
  are separate evidence, never automatically reported as physical MCU reboots.

Queue/server replays originate outside the analysis, but counting them as new
measurements is an analysis issue. This tool does not change server idempotency.

## Generated results

For nine tags the full run creates **24 SVG figures**:

- Nine `devices/<id>.svg` timelines: GPS intervals/gap spans, communication events,
  valid battery readings and LTE radio measurements on aligned axes. Evidence
  markers are labelled conservatively and gap spans are shared across panels.
- `comparisons/gps.svg`: acquisition quality/timeout and success-only timing,
  signal measurements and service-period gap rates/durations.
- `comparisons/lte.svg`: outcome rates with counts, successful registration
  duration, POST/receipt evidence and monthly timing/outcome context.
- `comparisons/battery.svg`: fixed-scale battery small multiples with the reported
  3.6 V policy line, excluding known marker voltages.
- `comparisons/gps_lte.svg`: descriptive gap/timeout/voltage and receipt-outage
  evidence, not proof of causal firmware or network faults.
- `comparisons/fleet_status.svg`: coverage, exported silence and shared events.
- `comparisons/cadence.svg`: measured monthly GPS cadence by tag.
- Nine `battery_adc_modem/<id>.svg` details: paired corrected ADC/modem over time,
  signed difference with a trailing seven-day median, difference versus BMA
  temperature coloured by reported temperature age, and equal-scale agreement.

Reports include `overview.md`, revised `device_findings.md`, `data_quality.md`,
`data_quality.json`, `diagnostics.json`, structured `run.json`, and the ADC group's
index/manifest. Definitions, counts, coverage and source hashes are explicit.
Diagnostics JSON saves flagged intervals/outages and monthly/fleet evidence, not
copies of all raw observations. `--event-details` adds association JSON Lines.

Font outlines make SVG labels independent of installed viewer fonts. Dense data
layers may be rasterised within SVG to keep files smaller; calculations use the
complete valid populations. Numeric tag ordering and tag colours are shared.

To regenerate only the ADC/modem group:

```powershell
python3 -B analyse.py --data C:\Mini4G_data\Data --output C:\Mini4G_data\Outputs --plot-set adc-modem
```

That mode uses the same cleaning/period/clock rules but preserves the main reports,
GPS/LTE plots and saved reviews. All runs stage generated files under Outputs,
verify selected input hashes again, then publish only their analysis artifacts.
The saved firmware comparison is never overwritten. Use different output folders
when retaining separate runs. No unrelated output files are deleted.

## Metrics and settings

- `--min-satellites 5`: qualifying observations / known normal satellite-count
  observations. This is an acquisition proxy, not solved-position success.
- `--gps-timeout-seconds 20`: normal attempts at/above the configured reported
  timeout / attempts with known TTF. Qualifying-only TTF is reported separately.
- GPS on-time proxy: sum of TTF on normal attempts with known TTF/satellite count
  divided by qualifying observations in the same population. Partial coverage is
  shown, rather than making every result unavailable after one unknown row.
- `--gap-seconds 3020`: the comparable historical absolute long-gap threshold,
  strictly greater than 3020 seconds. Availability uses normal attempt starts and
  clock TIME measurement times. Parser-affected intervals remain in the audit but
  are excluded from supported gap counts/causes and the timeout baseline. Rates
  use the recorded GPS span.
- Relative cadence diagnostics supplement that threshold using supported neighboring
  normal cadence and jitter allowance. The interval being assessed is excluded
  from inference; sustained local cadence takes precedence over voltage/history
  fallback. They do not prove the active
  device configuration or a particular count of missed configured slots.
- Gap classes describe evidence (timeout, low reading, counter/clock marker,
  incomplete registration span, unexplained), with explicit priority and all
  overlapping context flags retained. Low ADC values are not ground-truth cells.
- The analytic baseline conditions on each gap duration and start-month within
  recorded GPS/registration outer-span overlap, assuming uniform possible start
  times. It does not control voltage or missing logs, prove continuous logging,
  produce p-values, or establish causation. Unsupported windows remain unknown.
- `--receipt-gap-hours 24`: describe gaps in exported receipts and count GPS
  observations inside them; this does not imply uninterrupted GPS collection.
- `--receipt-window-seconds 300`: failed-result/receipt evidence window.
- `--future-stats-lead-seconds 600`: maximum future joined-stats lead after clock
  alignment; rejected payloads remain traceable and the receipt stays counted.
- `--gps-window-seconds 60`: inclusive nearby-GPS coverage for future location
  linkage. It is an appendix coverage measure, not association strength above
  chance. A clock/replay ambiguity is not silently counted as a positive match.
- `--gps-battery legacy`: assumed raw * 0.005263 + 3.5 V for normal legacy GPS
  voltage. `raw` omits that conversion. Stats ADC is already temperature-corrected
  and offset-calibrated; no correction or recalibration model is applied again.
- ADC-minus-modem differences describe paired exported records, not independent
  accuracy or necessarily simultaneous/load-matched measurements. Reported
  temperature age is not their sampling-time separation. Zero modem values are
  unavailable, while zero connect duration can be legitimate connection reuse.
- Energy indicators are not converted into charge, energy or remaining life.

## Google Earth registration maps

The exporter uses each supplied solved `<id>.pos` file and
`<id>_registrations.csv` in `Data/Tag<id>`. It does not decode raw GPS data or rerun
the main performance analysis.

```powershell
python3 -B export_kml.py --data C:\Mini4G_data\Data --output C:\Mini4G_data\Outputs
```

Both commands default to 1 July 2026 UTC. `--start` and exclusive `--end` select another
period. GPS positions and dated registrations outside that period are excluded;
clockless registrations remain in the audit and have no map location.

Open `C:\Mini4G_data\Outputs\registration_kml\index.md`, then a device KML in
Google Earth. Toggle the folders to show:

- Blue dots for actual supplied GPS positions, with clickable timestamps.
- Purple lines connecting consecutive GPS positions, including long gaps.
- Green registration markers for reported success and red for timeout/failure.
  Other/unknown outcomes are grey.
- Positioning-method subfolders separating exact-time coordinates, interpolated
  estimates and before/after-track projections.

Between GPS points, the registration fraction is elapsed time divided by the
anchor interval. The estimate moves at constant angular speed along the shortest
great-circle arc. For example, an event one-quarter of the time between two GPS
points is placed one-quarter along that arc. Exact timestamp matches use the
observed coordinate. Before or after coverage, the first or last two positions
define the same speed/direction projection. There is no time cutoff. Long gaps
and projections over days are labelled estimates; they do not establish the
actual route or subsequent movement.

Click a registration for both anchor timestamps and source rows, time from/to
each anchor, interval length, fraction, nearest-point time difference and outcome.
Projections additionally show their horizon and assumed segment speed. Method
names are visible in the Places sidebar and popup. Dense map labels are hidden.
All points are visible together without a time-slider filter.

Purple lines end at the last actual GPS point. Arc vertices added for drawing are
not measured points and are not blue. `--track-gap-seconds` optionally splits the
displayed purple line at long holes; it does not alter registration estimation.
A stationary anchor pair produces a stationary estimate; positions are never
artificially scattered to avoid overlap. Missing or insufficient anchors and
ambiguous antipodal geometry remain unlocated in the audit.

The user confirmed POS timestamps use GPS time. Both POS and registration clocks
subtract 18 seconds once for UTC by default. `--pos-time-basis utc` handles future
already-UTC position exports; `--device-clock-offset-seconds` configures the device
offset. Fractional seconds-of-day are preserved. Unconfirmed extra POS quality
fields are not interpreted; valid four-satellite positions remain eligible.
Zero/zero, nonfinite, out-of-range and conflicting same-time coordinates are
excluded. Heights are not used; geometry is clamped to the ground.

Only selected POS and registration files are read and hashed (18 files for nine
tags). Registration cleaning reuses the main analysis rules. Source cleaning
counts and date exclusions are recorded separately. KMLs, an index and a JSON
audit are staged, verified and published under `registration_kml`. Original data,
firmware and saved firmware reviews stay unchanged. Google Earth may fetch marker
artwork from Google's public KML icon service. No new dependencies are needed.

## Code and verification

`loaders.py` selects sources and normalises clocks. `gps_quality.py` and
`stats_quality.py` own cleaning/audits; `diagnostics.py` owns service/cadence/gap,
outage and fleet evidence; `metrics.py` owns metric populations; `matching.py`
owns temporal coverage; `battery.py` owns voltage agreement; `spatial.py` owns
time-based registration estimates; `kml.py` renders maps; `plots.py` and
`reporting.py` present these shared results. All repository text uses CRLF.

```powershell
python3 -B -m unittest discover -s tests -v
```

Synthetic checks cover replay pages with changed line numbers, payload duplicates,
markers, enrichment/conflicts, reused sequence/future stats, partial observations,
UTC offsets, analytic interval unions, service inference, staged CLI publication,
ignored copied inputs, July date selection, great-circle interpolation/projection
and source immutability. Tests do not access firmware,
backend, live AWS or hardware.
