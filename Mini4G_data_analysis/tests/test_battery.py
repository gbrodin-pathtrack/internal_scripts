"""Focused battery-pair checks using in-memory records only."""

import json
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

from mini4g_analysis.battery import PAIR_COLUMNS, battery_pairs, battery_summary


TIME = pd.Timestamp("2026-07-01T12:00:00Z")


def row(**changes):
    result = {
        "time": TIME, "voltage_v": 4.1, "modem_voltage_v": 4.0,
        "temp_c": 25.0, "temp_time": TIME-pd.Timedelta(seconds=180),
        "temp_age_s": 180.0, "source_row": 2, "post_ok": 1,
    }
    result.update(changes)
    return result


def device(uploads=(), failures=()):
    return SimpleNamespace(uploads=pd.DataFrame(uploads), failures=pd.DataFrame(failures))


class BatteryPairTests(unittest.TestCase):
    def test_difference_sign_units_and_exact_threshold_boundaries(self):
        pairs = battery_pairs(device(uploads=[row(), row(voltage_v=4.0, modem_voltage_v=4.05, source_row=3)]))
        self.assertEqual(pairs["diff_mv"].tolist(), [100.0, -50.0])
        summary = battery_summary(pairs)
        self.assertEqual(summary["mean_diff_mv"], 25.0)
        self.assertEqual(summary["median_diff_mv"], 25.0)
        self.assertEqual(summary["median_abs_diff_mv"], 75.0)
        self.assertEqual(summary["above_50mv_count"], 1)
        self.assertEqual(summary["above_100mv_count"], 0)

    def test_invalid_voltage_pairs_are_excluded_without_using_temperature(self):
        pairs = battery_pairs(device(uploads=[
            row(voltage_v=0), row(modem_voltage_v=0),
            row(voltage_v=np.nan), row(modem_voltage_v=np.nan),
            row(voltage_v=np.inf), row(modem_voltage_v=-np.inf),
            row(voltage_v=6.01), row(modem_voltage_v=6.01),
            row(voltage_v=-1), row(modem_voltage_v=-1),
            row(voltage_v=6.0, modem_voltage_v=6.0, temp_c=np.nan),
        ]))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs.iloc[0]["adc_v"], 6.0)
        self.assertTrue(pd.isna(pairs.iloc[0]["temp_c"]))

    def test_missing_time_temperature_and_invalid_age_keep_voltage_pairs(self):
        pairs = battery_pairs(device(uploads=[
            row(time=pd.NaT, temp_c=np.nan, temp_time=pd.NaT, temp_age_s=-1),
            row(time=pd.NaT, temp_c=np.inf, temp_time=pd.NaT, temp_age_s=np.inf, source_row=3),
        ]))
        self.assertEqual(len(pairs), 2)
        self.assertTrue(pairs["time"].isna().all())
        self.assertTrue(pairs["temp_c"].isna().all())
        self.assertTrue(pairs["temp_time"].isna().all())
        self.assertTrue(pairs["temp_age_s"].isna().all())
        summary = battery_summary(pairs)
        self.assertEqual(summary["timed_pairs"], 0)
        self.assertEqual(summary["temperature_pairs"], 0)
        self.assertEqual(summary["temperature_age_known"], 0)
        self.assertIsNone(summary["temp_age_median_s"])
        self.assertEqual(summary["mean_diff_mv"], 100.0)

    def test_reported_age_is_preserved_and_never_recomputed_from_clocks(self):
        pairs = battery_pairs(device(uploads=[
            row(temp_time=TIME-pd.Timedelta(hours=1), temp_age_s=42),
            row(temp_c=np.nan, temp_age_s=99, source_row=3),
            row(temp_c=20, temp_age_s=np.nan, source_row=4),
        ]))
        self.assertEqual(pairs.iloc[0]["temp_age_s"], 42)
        self.assertEqual(pairs.iloc[1]["temp_age_s"], 99)
        summary = battery_summary(pairs)
        self.assertEqual(summary["temperature_pairs"], 2)
        self.assertEqual(summary["temperature_age_known"], 1)
        self.assertEqual(summary["temperature_age_missing"], 1)
        self.assertEqual(summary["reported_age_pairs"], 2)
        self.assertEqual(summary["temp_age_median_s"], 42)

    def test_same_timestamp_rows_and_both_sources_remain_distinct(self):
        pairs = battery_pairs(device(
            uploads=[row(), row(source_row=3)],
            failures=[row(post_ok=0)],
        ))
        self.assertEqual(len(pairs), 3)
        self.assertEqual(pairs["source_kind"].tolist(), ["upload_receipt", "upload_receipt", "failed_attempt"])
        self.assertEqual(pairs["source_row"].tolist(), [2, 3, 2])
        self.assertEqual(pairs["post_ok"].tolist(), [1, 1, 0])
        summary = battery_summary(pairs)
        self.assertEqual(summary["receipt_pairs"], 2)
        self.assertEqual(summary["failed_attempt_pairs"], 1)

    def test_inputs_are_not_mutated(self):
        data = device(uploads=[row()], failures=[row(post_ok=0)])
        before_uploads = data.uploads.copy(deep=True)
        before_failures = data.failures.copy(deep=True)
        pairs = battery_pairs(data)
        battery_summary(pairs)
        pd.testing.assert_frame_equal(data.uploads, before_uploads)
        pd.testing.assert_frame_equal(data.failures, before_failures)

    def test_empty_output_and_summary_are_json_safe(self):
        pairs = battery_pairs(device())
        self.assertEqual(pairs.columns.tolist(), PAIR_COLUMNS)
        self.assertTrue(pairs.empty)
        summary = battery_summary(pairs)
        self.assertEqual(summary["pairs"], 0)
        self.assertEqual(summary["timed_pairs"], 0)
        self.assertEqual(summary["above_50mv_count"], 0)
        self.assertEqual(summary["above_100mv_count"], 0)
        for name in ("mean_diff_mv", "median_diff_mv", "median_abs_diff_mv", "p95_abs_diff_mv", "temp_age_median_s"):
            self.assertIsNone(summary[name])
        json.dumps(summary, allow_nan=False)
        json.dumps(battery_summary(pd.DataFrame()), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
