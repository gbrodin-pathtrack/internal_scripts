"""Checks for metric populations, missing values and GPS interval handling."""

import json
import unittest

import numpy as np
import pandas as pd

from mini4g_analysis.matching import build_event_matches
from mini4g_analysis.metrics import device_metrics, gps_intervals
from test_matching import EPOCH, attempt, device, observation, registration


class DeviceMetricTests(unittest.TestCase):
    def test_outcome_denominators_do_not_depend_on_battery_or_missing_psm(self):
        data = device(
            gps=[observation(0, num_sv=5, ttf_s=10),
                 observation(600, num_sv=4, ttf_s=20, source_row=3),
                 observation(1200, num_sv=6, ttf_s=30, source_row=4)],
            uploads=[attempt(voltage_v=np.nan, modem_voltage_v=np.nan),
                     attempt(600, post_ok=np.nan, psm_ok=np.nan, voltage_v=4, modem_voltage_v=0, source_row=3),
                     attempt(1200, post_ok=0, psm_ok=0, voltage_v=4.1, modem_voltage_v=4, source_row=4)],
            failures=[attempt(post_ok=0, psm_ok=np.nan, voltage_v=np.nan, source_row=2),
                      attempt(post_ok=1, psm_ok=1, voltage_v=4.2, modem_voltage_v=4.1, source_row=3)],
            registrations=[registration(outcome="success", duration_s=10, psm="yes"),
                           registration(outcome="timeout", duration_s=30, psm="no", source_row=3),
                           registration(outcome="unknown", duration_s=np.nan, psm="unknown", source_row=4)],
        )
        summary = device_metrics(data, build_event_matches(data))
        self.assertEqual(summary["gps_5plus_count"], 2)
        self.assertAlmostEqual(summary["gps_5plus_percent"], 200/3)
        self.assertEqual(summary["on_time_per_5plus_s"], 30)
        self.assertEqual(summary["ttf_mean_s"], 20)
        self.assertEqual(summary["upload_known_outcomes"], 4)
        self.assertEqual(summary["upload_successes"], 2)
        self.assertEqual(summary["upload_failures"], 2)
        self.assertEqual(summary["upload_success_percent"], 50)
        self.assertEqual(summary["upload_stats_missing"], 1)
        self.assertEqual(summary["psm_known"], 3)
        self.assertAlmostEqual(summary["psm_yes_percent"], 200/3)
        self.assertEqual(summary["registration_attempts"], 3)
        self.assertEqual(summary["registration_known_outcomes"], 2)
        self.assertEqual(summary["registration_success_percent"], 50)
        self.assertEqual(summary["registration_duration_median_s"], 20)
        self.assertEqual(summary["registration_success_duration_median_s"], 10)
        self.assertEqual(summary["registration_timeout_duration_median_s"], 30)
        self.assertEqual(summary["registration_psm_known"], 2)
        self.assertEqual(summary["battery_pairs"], 2)
        self.assertAlmostEqual(summary["battery_diff_mean_v"], 0.1)
        json.dumps(summary, allow_nan=False)

    def test_constant_interval_trim_is_defined(self):
        gps = [observation(second, source_row=index+2) for index, second in enumerate((0, 600, 1200))]
        data = device(gps=gps)
        summary = device_metrics(data, build_event_matches(data))
        self.assertEqual(summary["gps_interval_trimmed_mean_s"], 600)
        self.assertEqual(summary["gps_longest_gap_s"], 600)
        self.assertEqual(summary["gps_gap_count"], 0)

    def test_intervals_preserve_source_order_and_do_not_cross_resets(self):
        data = device(gps=[
            observation(0), observation(600, source_row=3),
            observation(300, source_row=4, clock_segment=1, clock_anomaly=True),
            observation(900, source_row=5, clock_segment=1),
            observation(1500, source_row=6, clock_segment=1),
        ])
        result = gps_intervals(data.gps)
        self.assertEqual(result["obs_id"].tolist(), data.gps["obs_id"].tolist())
        self.assertTrue(pd.isna(result.iloc[0]["interval_s"]))
        self.assertEqual(result.iloc[1]["interval_s"], 600)
        self.assertTrue(pd.isna(result.iloc[2]["interval_s"]))
        self.assertEqual(result.iloc[3]["interval_s"], 600)
        self.assertEqual(result.iloc[4]["interval_s"], 600)

    def test_long_gap_is_not_clipped_and_boundary_is_strict(self):
        data = device(gps=[observation(0), observation(3020, source_row=3),
                           observation(7021, source_row=4)])
        summary = device_metrics(data, build_event_matches(data))
        self.assertEqual(summary["gps_gap_count"], 1)
        self.assertEqual(summary["gps_longest_gap_s"], 4001)

    def test_missing_ttf_reports_available_case_on_time_and_coverage(self):
        data = device(gps=[observation(ttf_s=np.nan), observation(600, source_row=3)])
        summary = device_metrics(data, build_event_matches(data))
        self.assertEqual(summary["on_time_per_5plus_s"], 20)
        self.assertEqual(summary["on_time_known_attempts"], 1)
        self.assertEqual(summary["on_time_coverage_percent"], 50)
        self.assertEqual(summary["ttf_known_count"], 1)
        self.assertTrue(any("TTF" in issue for issue in summary["issues"]))
        json.dumps(summary, allow_nan=False)

    def test_peak_cnr_is_not_replaced_by_observation_mean(self):
        data = device(gps=[observation(cnr_mean=30, cnr_peak=45)])
        summary = device_metrics(data, build_event_matches(data))
        self.assertEqual(summary["cnr_mean"], 30)
        self.assertEqual(summary["cnr_peak"], 45)

    def test_empty_data_is_json_safe_and_has_no_invented_rates(self):
        data = device()
        summary = device_metrics(data, build_event_matches(data))
        self.assertEqual(summary["gps_observations"], 0)
        self.assertEqual(summary["timed_events"], 0)
        self.assertIsNone(summary["gps_5plus_percent"])
        self.assertIsNone(summary["upload_success_percent"])
        self.assertIsNone(summary["registration_success_percent"])
        self.assertIsNone(summary["gps_match_percent"])
        json.dumps(summary, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
