"""Descriptive diagnostics checked with small UTC-aligned synthetic frames."""

import json
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

from mini4g_analysis.diagnostics import (
    fleet_event_table, gps_availability, gps_intervals, infer_service_start, normal_gps,
    prepare_diagnostics, uniform_start_timeout_probability,
)


NOW = pd.Timestamp("2026-01-01T12:00:00Z")


def gps(seconds, **changes):
    start = NOW+pd.Timedelta(seconds=seconds)
    row = dict(obs_id=f"gps:{seconds}", time=start+pd.Timedelta(seconds=5), start_time=start,
               ttf_s=5.0, num_sv=5, vbatt_raw=120, voltage_v=4.1,
               source_row=int(seconds)+2, clock_segment=0, clock_record=False,
               clock_anomaly=False, decoded_marker_voltage_v=np.nan)
    row.update(changes)
    return row


def reg(seconds, **changes):
    row = dict(time=NOW+pd.Timedelta(seconds=seconds), outcome="success", tier="HOT", voltage_v=4.1)
    row.update(changes)
    return row


def receipt(seconds):
    return dict(time=NOW+pd.Timedelta(seconds=seconds), upload_seq=1)


def device(identifier="123", observations=(), registrations=(), receipts=(), failures=(), events=()):
    return SimpleNamespace(
        device_id=identifier, gps=pd.DataFrame(observations), registrations=pd.DataFrame(registrations),
        uploads=pd.DataFrame(receipts), failures=pd.DataFrame(failures), events=pd.DataFrame(events),
        quality={}, gaps=pd.DataFrame(), outages=pd.DataFrame(), monthly=pd.DataFrame(),
    )


class IntervalAndServiceTests(unittest.TestCase):
    def test_markers_are_removed_before_spacing_without_masking_next_interval(self):
        data = device(observations=[gps(0), gps(300, clock_record=True),
                                    gps(600, clock_anomaly=True), gps(1200)])
        before = data.gps.copy(deep=True)
        normal = normal_gps(data.gps)
        intervals = gps_intervals(data.gps)
        self.assertEqual(normal["obs_id"].tolist(), ["gps:0", "gps:600", "gps:1200"])
        self.assertTrue(pd.isna(intervals.iloc[0]["interval_s"]))
        self.assertEqual(intervals["interval_s"].dropna().tolist(), [600, 600])
        pd.testing.assert_frame_equal(data.gps, before)

    def test_source_order_and_true_segment_boundaries_are_preserved(self):
        data = device(observations=[gps(0), gps(600), gps(300, clock_segment=1), gps(900, clock_segment=1)])
        result = gps_intervals(data.gps)
        self.assertEqual(result["obs_id"].tolist(), data.gps["obs_id"].tolist())
        self.assertTrue(pd.isna(result.iloc[2]["interval_s"]))
        self.assertEqual(result["interval_s"].dropna().tolist(), [600, 600])
        backwards = gps_intervals(pd.DataFrame([gps(600), gps(300), gps(900)]))
        self.assertTrue(pd.isna(backwards.iloc[1]["interval_s"]))
        self.assertEqual(backwards.iloc[2]["interval_s"], 600)

    def test_canonical_availability_uses_clock_measurement_time_not_marker_ttf(self):
        frame = pd.DataFrame([
            gps(0), gps(100, clock_record=True, start_time=NOW-pd.Timedelta(hours=1), ttf_s=3700), gps(200),
        ])
        result = gps_availability(frame)
        self.assertEqual(result["availability_basis"].tolist(), ["attempt_start", "clock_record_time", "attempt_start"])
        self.assertEqual(result.iloc[1]["availability_time"], NOW+pd.Timedelta(seconds=105))
        self.assertEqual(result["interval_s"].dropna().tolist(), [105, 95])
        self.assertTrue(pd.isna(result.iloc[1]["voltage_v"]))
        self.assertEqual(gps_intervals(frame)["interval_s"].dropna().tolist(), [200])

    def test_common_small_fragment_gap_infers_resumption_day(self):
        devices = [device(str(i), observations=[gps(0), gps(600), gps(9*86400), gps(9*86400+600)]) for i in range(2)]
        devices += [device(str(i), observations=[gps(0), gps(600), gps(1200)]) for i in range(2, 4)]
        start, evidence = infer_service_start(devices)
        self.assertEqual(start, (NOW+pd.Timedelta(days=9)).floor("D"))
        self.assertEqual(evidence["support"], 2)
        self.assertEqual(evidence["support_required"], 2)
        self.assertEqual(evidence["candidates"][0]["fragment_rows"], 2)
        json.dumps(evidence, allow_nan=False)

    def test_one_device_or_large_initial_fragment_is_not_a_fleet_boundary(self):
        candidate = device(observations=[gps(0), gps(9*86400)])
        self.assertIsNone(infer_service_start([candidate])[0])
        fragment = [gps(i*600) for i in range(51)] + [gps(9*86400)]
        start, evidence = infer_service_start([device(observations=fragment)])
        self.assertIsNone(start)
        self.assertEqual(evidence["candidates"], [])

    def test_equally_supported_resumption_days_remain_ambiguous(self):
        devices = [device(str(i), observations=[gps(0), gps(day*86400)])
                   for i, day in enumerate([8, 8, 9, 9])]
        start, evidence = infer_service_start(devices)
        self.assertIsNone(start)
        self.assertIn("ambiguous", evidence["reason"])


class AnalyticBaselineTests(unittest.TestCase):
    def test_clipped_union_counts_overlapping_windows_once(self):
        timeouts = [NOW+pd.Timedelta(seconds=value) for value in (20, 25, 80)]
        value = uniform_start_timeout_probability(timeouts, 10, NOW, NOW+pd.Timedelta(seconds=100))
        self.assertAlmostEqual(value, 0.25)

    def test_edge_clipping_and_unsupported_domains(self):
        self.assertAlmostEqual(uniform_start_timeout_probability([NOW+pd.Timedelta(seconds=5)], 10,
                                                                 NOW, NOW+pd.Timedelta(seconds=100)), 0.05)
        self.assertEqual(uniform_start_timeout_probability([], 10, NOW, NOW+pd.Timedelta(seconds=100)), 0)
        self.assertIsNone(uniform_start_timeout_probability([], 10, NOW, NOW))
        with self.assertRaises(ValueError):
            uniform_start_timeout_probability([], -1, NOW, NOW+pd.Timedelta(seconds=100))

    def test_expected_hits_and_observed_hits_share_eligible_population(self):
        data = device(observations=[gps(value) for value in (0, 10, 20, 30, 50, 60)],
                      registrations=[reg(0), reg(25, outcome="timeout"), reg(60)], receipts=[receipt(60)])
        prepare_diagnostics([data], gap_seconds=5)
        result = data.quality["diagnostics"]
        self.assertEqual(result["gap_timeout_eligible"], 5)
        self.assertEqual(result["gap_timeout_hits"], 1)
        self.assertAlmostEqual(result["gap_timeout_expected_hits"], 1.3)
        self.assertEqual(result["observed_gap_timeout_percent"], 20)
        self.assertAlmostEqual(result["expected_gap_timeout_percent"], 26)
        self.assertEqual(int(data.gaps["timeout_baseline_eligible"].sum()), 5)

    def test_missing_registration_span_is_unavailable_not_zero_baseline(self):
        data = device(observations=[gps(0), gps(4000)])
        prepare_diagnostics([data])
        result = data.quality["diagnostics"]
        self.assertEqual(result["gap_timeout_eligible"], 0)
        self.assertIsNone(result["gap_timeout_expected_hits"])
        self.assertIsNone(result["expected_gap_timeout_percent"])

    def test_clock_time_endpoint_counts_as_availability_for_baseline_coverage(self):
        data = device(observations=[gps(value) for value in (0, 600, 1200, 1800, 2400, 3000)]
                      + [gps(7000, clock_record=True, voltage_v=np.nan)],
                      registrations=[reg(-100), reg(4000, outcome="timeout"), reg(8000)])
        prepare_diagnostics([data])
        result = data.quality["diagnostics"]
        self.assertEqual(result["gap_timeout_eligible"], 1)
        self.assertEqual(result["gap_timeout_hits"], 1)
        self.assertEqual(data.gaps.iloc[-1]["end_basis"], "clock_record_time")


class ContextAndOutageTests(unittest.TestCase):
    def pattern(self, **options):
        observations = [gps(value) for value in (0, 600, 1200, 1800, 2400, 3000, 4800, 5400, 6000, 6600, 7200, 7800)]
        return device(observations=observations, registrations=[reg(-100), reg(3900, outcome="timeout"), reg(8000)], **options)

    def test_relative_cadence_gap_is_found_below_absolute_threshold(self):
        data = self.pattern()
        prepare_diagnostics([data])
        gap = data.gaps.loc[data.gaps["duration_s"].eq(1800)].iloc[0]
        self.assertEqual(gap["expected_interval_s"], 600)
        self.assertEqual(gap["cadence_multiple"], 3)
        self.assertTrue(gap["cadence_gap"])
        self.assertFalse(gap["absolute_long"])
        self.assertEqual(gap["gap_class"], "timeout")
        self.assertTrue(gap["registration_coverage"])

    def test_context_priority_keeps_all_flags_and_does_not_double_shift_utc(self):
        data = self.pattern(receipts=[receipt(3005)], failures=[dict(time=NOW+pd.Timedelta(seconds=4000), post_ok=0)],
                            events=[dict(time=NOW+pd.Timedelta(seconds=4300), kind="counter_restart",
                                         confidence="counter_only", source_row=2)])
        data.gps.loc[data.gps["obs_id"].eq("gps:3000"), "voltage_v"] = 3.63
        marker = pd.DataFrame([gps(4500, clock_record=True, decoded_marker_voltage_v=3.61)])
        data.gps = pd.concat([data.gps.iloc[:6], marker, data.gps.iloc[6:]], ignore_index=True)
        original = data.gps.copy(deep=True)
        prepare_diagnostics([data])
        gap = data.gaps.loc[data.gaps["end_basis"].eq("clock_record_time")].iloc[0]
        self.assertEqual(gap["duration_s"], 1505)
        self.assertEqual(gap["gap_class"], "restart_or_clock")
        self.assertEqual(gap["timeout_count"], 1)
        self.assertEqual(gap["failure_count"], 1)
        self.assertEqual(gap["receipt_count"], 1)
        self.assertEqual(gap["restart_count"], 1)
        self.assertEqual(gap["clock_marker_count"], 1)
        self.assertTrue(gap["low_voltage_boundary"])
        self.assertEqual(gap["boundary_voltage_v"], 3.63)
        self.assertTrue(pd.isna(gap["voltage_after_v"]))
        pd.testing.assert_frame_equal(data.gps, original)

    def test_local_sustained_tier_overrides_historical_voltage_mode_but_isolated_double_remains(self):
        durations = [600]*25 + [1200]*8 + [600]*25 + [1200] + [600]*8
        starts = np.cumsum([0]+durations).tolist()
        data = device(observations=[gps(value) for value in starts],
                      registrations=[reg(-100), reg(starts[-1]+100)], receipts=[receipt(starts[-1])])
        prepare_diagnostics([data])
        sustained = data.gaps.iloc[25:33]
        self.assertTrue(sustained["duration_s"].eq(1200).all())
        self.assertTrue(sustained["expected_interval_s"].eq(1200).all())
        self.assertFalse(sustained["cadence_gap"].any())
        isolated = data.gaps.iloc[58]
        self.assertEqual(isolated["duration_s"], 1200)
        self.assertEqual(isolated["expected_interval_s"], 600)
        self.assertTrue(isolated["cadence_gap"])

    def test_unparsed_page_hints_exclude_gap_causes_and_baseline_without_repair(self):
        data = device(observations=[gps(value) for value in (0, 600, 1200, 1800, 2400, 3000, 7200, 7800, 8400, 9000)],
                      registrations=[reg(-100), reg(5000, outcome="timeout"), reg(10000)],
                      receipts=[receipt(3005)])
        data.quality["gps"] = {"unparsed_dat_pages": [{
            "line": 449, "first_time_utc": (NOW+pd.Timedelta(seconds=3600)).isoformat(),
            "last_time_utc": (NOW+pd.Timedelta(seconds=6600)).isoformat(),
        }]}
        original = data.gps.copy(deep=True)
        prepare_diagnostics([data])
        gap = data.gaps.loc[data.gaps["duration_s"].eq(4200)].iloc[0]
        self.assertEqual(gap["gap_class"], "unparsed_source")
        self.assertTrue(gap["absolute_long"] and gap["cadence_gap"])
        self.assertTrue(gap["unparsed_page_overlap"])
        self.assertEqual(gap["unparsed_page_count"], 1)
        self.assertEqual(gap["unparsed_source_lines"], [449])
        self.assertEqual(gap["timeout_count"], 1)
        result = data.quality["diagnostics"]
        self.assertEqual(result["absolute_gap_count"], 0)
        self.assertEqual(result["parsed_absolute_gap_count"], 1)
        self.assertEqual(result["parser_affected_gap_count"], 1)
        self.assertAlmostEqual(result["parser_affected_gap_hours"], 4200/3600)
        self.assertEqual(result["parser_affected_source_lines"], [449])
        self.assertEqual(result["gap_timeout_eligible"], 0)
        self.assertIsNone(result["gap_timeout_expected_hits"])
        self.assertTrue(fleet_event_table([data])["gap_device_count"].eq(0).all())
        pd.testing.assert_frame_equal(data.gps, original)

    def test_timeout_and_low_and_outside_span_classes(self):
        data = self.pattern()
        data.gps.loc[data.gps["obs_id"].eq("gps:3000"), "voltage_v"] = 3.63
        prepare_diagnostics([data])
        gap = data.gaps.loc[data.gaps["duration_s"].eq(1800)].iloc[0]
        self.assertEqual(gap["gap_class"], "timeout_and_low")
        self.assertTrue(data.gaps.loc[data.gaps["duration_s"].eq(600), "gap_class"].eq("regular").all())
        other = self.pattern()
        other.registrations = pd.DataFrame([reg(0), reg(2000)])
        prepare_diagnostics([other])
        gap = other.gaps.loc[other.gaps["duration_s"].eq(1800)].iloc[0]
        self.assertEqual(gap["gap_class"], "outside_reg_span")

    def test_receipt_outages_include_internal_and_trailing_gps_counts(self):
        data = device(observations=[gps(hour*3600) for hour in (0, 12, 36, 72)],
                      receipts=[receipt(0), receipt(48*3600)])
        reference = NOW+pd.Timedelta(hours=96)
        returned = prepare_diagnostics([data], export_reference=reference)
        self.assertEqual(returned, reference)
        self.assertEqual(data.outages["kind"].tolist(), ["internal", "trailing"])
        self.assertEqual(data.outages["gps_count"].tolist(), [3, 1])
        self.assertEqual(data.outages["ongoing_at_export"].tolist(), [False, True])

    def test_leading_and_no_receipt_outages_remain_descriptive(self):
        data = device(observations=[gps(0), gps(12*3600)], receipts=[receipt(30*3600)])
        prepare_diagnostics([data], export_reference=NOW+pd.Timedelta(hours=48))
        self.assertEqual(data.outages["kind"].tolist(), ["leading"])
        no_receipts = device(observations=[gps(0), gps(12*3600)])
        prepare_diagnostics([no_receipts], export_reference=NOW+pd.Timedelta(hours=48))
        self.assertEqual(no_receipts.outages.iloc[0]["kind"], "no_receipts")
        self.assertTrue(no_receipts.outages.iloc[0]["ongoing_at_export"])

    def test_reference_prefers_latest_receipt_and_never_uses_live_clock(self):
        first = device("1", observations=[gps(9000)], receipts=[receipt(100)])
        second = device("2", observations=[gps(10000)], receipts=[receipt(200)])
        self.assertEqual(prepare_diagnostics([first, second]), NOW+pd.Timedelta(seconds=200))
        gps_only = device(observations=[gps(0), gps(600)])
        self.assertEqual(prepare_diagnostics([gps_only]), NOW+pd.Timedelta(seconds=605))
        self.assertIsNone(prepare_diagnostics([]))

    def test_monthly_counts_and_minimum_median_samples(self):
        data = device(observations=[gps(value) for value in (0, 600, 1200, 1800)],
                      registrations=[reg(100, voltage_v=4.0), reg(200, outcome="timeout", voltage_v=4.15),
                                     reg(300, outcome="timeout", tier="COLD"), reg(400, time=pd.NaT)],
                      receipts=[receipt(1800)])
        prepare_diagnostics([data])
        month = data.monthly.iloc[0]
        self.assertEqual(month["reg_attempts"], 3)
        self.assertEqual(month["hot_attempts"], 2)
        self.assertEqual(month["hot_timeouts"], 1)
        self.assertEqual(month["cold_attempts"], 1)
        self.assertEqual(month["hot_good_v_attempts"], 2)
        self.assertEqual(month["hot_good_v_timeouts"], 1)
        self.assertEqual(month["reg_successes"], month["successes"])
        self.assertEqual(month["reg_timeouts"], month["timeouts"])
        self.assertEqual(month["median_cadence_s"], 600)
        short = device(observations=[gps(0), gps(600), gps(1200)])
        prepare_diagnostics([short])
        self.assertTrue(pd.isna(short.monthly.iloc[0]["median_cadence_s"]))

    def test_fleet_counts_distinct_devices_and_prepared_utc_days(self):
        first = device("1", observations=[gps(0), gps(48*3600)],
                       registrations=[reg(10, outcome="timeout"), reg(20, outcome="timeout")],
                       receipts=[receipt(30)],
                       events=[dict(time=NOW+pd.Timedelta(seconds=40), kind="counter_restart", confidence="counter_only")])
        second = device("2", observations=[gps(0), gps(600)], registrations=[reg(10, outcome="timeout")],
                        events=[dict(time=NOW+pd.Timedelta(seconds=40), kind="sequence_regression", confidence="sequence_only")])
        prepare_diagnostics([first, second], export_reference=NOW+pd.Timedelta(days=3))
        fleet = fleet_event_table([first, second])
        day = fleet.loc[fleet["date"].eq(NOW.floor("D"))].iloc[0]
        self.assertEqual(day["timeout_device_count"], 2)
        self.assertEqual(day["registration_device_count"], 2)
        self.assertEqual(day["gps_device_count"], 2)
        self.assertEqual(day["receipt_device_count"], 1)
        self.assertEqual(day["counter_restart_device_count"], 1)
        self.assertTrue(fleet["gap_device_count"].ge(1).any())

    def test_empty_diagnostics_are_safe(self):
        data = device()
        self.assertIsNone(prepare_diagnostics([data]))
        self.assertTrue(data.gaps.empty and data.outages.empty and data.monthly.empty)
        self.assertTrue(fleet_event_table([data]).empty)
        json.dumps(data.quality, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
