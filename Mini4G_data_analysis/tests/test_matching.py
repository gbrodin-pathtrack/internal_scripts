"""Focused checks for temporal associations; no real datasets or output files."""

from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

from mini4g_analysis.matching import build_event_matches


GPS_COLUMNS = [
    "obs_id", "time", "start_time", "ttf_s", "num_sv", "vbatt_raw",
    "voltage_v", "source_line", "source_row", "clock_segment",
    "clock_anomaly", "duplicate", "cnr_mean", "cnr_peak",
]
ATTEMPT_COLUMNS = [
    "time", "upload_seq", "post_ok", "psm_ok", "voltage_v", "modem_voltage_v",
    "temp_c", "rsrp_dbm", "tx_dbm", "connect_s", "send_s", "ttfb_s", "source_row",
]
REGISTRATION_COLUMNS = [
    "time", "time_text", "outcome", "tier", "duration_s", "rsrp_dbm", "tx_dbm",
    "voltage_v", "psm", "energy", "reg_count", "stats_ts", "source_row",
]
EPOCH = pd.Timestamp("2026-07-01T00:00:00Z")


def observation(seconds=0, **changes):
    time = EPOCH + pd.Timedelta(seconds=seconds)
    row = dict(
        obs_id=f"gps:{seconds}", time=time, start_time=time-pd.Timedelta(seconds=20),
        ttf_s=20.0, num_sv=6, vbatt_raw=100, voltage_v=4.1,
        source_line=6, source_row=2, clock_segment=0,
        clock_anomaly=False, duplicate=False, cnr_mean=35.0, cnr_peak=40.0,
    )
    row.update(changes)
    return row


def attempt(seconds=0, **changes):
    row = dict(
        time=EPOCH+pd.Timedelta(seconds=seconds), upload_seq=1, post_ok=1,
        psm_ok=1, voltage_v=4.1, modem_voltage_v=4.0, temp_c=20,
        rsrp_dbm=-110, tx_dbm=20, connect_s=0, send_s=0.2,
        ttfb_s=0.4, source_row=2,
    )
    row.update(changes)
    return row


def registration(seconds=0, **changes):
    row = dict(
        time=EPOCH+pd.Timedelta(seconds=seconds), time_text="", outcome="success",
        tier="HOT", duration_s=1, rsrp_dbm=-110, tx_dbm=20, voltage_v=4.1,
        psm="yes", energy=4, reg_count=1, stats_ts="receipt|key", source_row=2,
    )
    row.update(changes)
    return row


def device(gps=(), uploads=(), failures=(), registrations=()):
    return SimpleNamespace(
        device_id="123", gps=pd.DataFrame(gps, columns=GPS_COLUMNS),
        satellites=pd.DataFrame(columns=["obs_id", "CNR", "ID", "codePhase"]),
        uploads=pd.DataFrame(uploads, columns=ATTEMPT_COLUMNS),
        failures=pd.DataFrame(failures, columns=ATTEMPT_COLUMNS),
        registrations=pd.DataFrame(registrations, columns=REGISTRATION_COLUMNS),
        issues=[], source_files=[], quality={}, events=pd.DataFrame(),
        gaps=pd.DataFrame(), outages=pd.DataFrame(), monthly=pd.DataFrame(),
    )


class EventMatchingTests(unittest.TestCase):
    def test_one_minute_boundary_preserves_subsecond_precision(self):
        data = device(
            gps=[observation(60)],
            registrations=[registration(0), registration(-0.000001, source_row=3)],
        )
        rows = build_event_matches(data, 60).set_index("event_id")
        exact = rows.loc["123:registration:2"]
        outside = rows.loc["123:registration:3"]
        self.assertTrue(exact["within_window"])
        self.assertEqual(exact["offset_s"], 60.0)
        self.assertFalse(outside["within_window"])
        self.assertAlmostEqual(outside["offset_s"], 60.000001, places=8)
        self.assertEqual(outside["match_status"], "outside_window")

    def test_nearest_tie_prefers_previous_and_retains_bracket(self):
        rows = build_event_matches(device(
            gps=[observation(0), observation(120, source_row=3)],
            registrations=[registration(60)],
        ))
        row = rows.iloc[0]
        self.assertEqual(row["gps_time"], EPOCH)
        self.assertEqual(row["offset_s"], -60)
        self.assertEqual(row["previous_gps_time"], EPOCH)
        self.assertEqual(row["next_gps_time"], EPOCH+pd.Timedelta(seconds=120))
        self.assertEqual(row["bracket_gap_s"], 120)

    def test_receipts_and_untimed_registration_keep_their_clock_basis(self):
        rows = build_event_matches(device(
            gps=[observation(30)], uploads=[attempt(30)],
            failures=[attempt(15, post_ok=0)],
            registrations=[registration(time=pd.NaT, time_text="boot+45s")],
        ))
        receipt = rows[rows["event_type"] == "upload_receipt"].iloc[0]
        failed = rows[rows["event_type"] == "upload_failure"].iloc[0]
        untimed = rows[rows["event_type"] == "registration"].iloc[0]
        self.assertEqual(len(rows), 3)
        self.assertEqual(receipt["clock_basis"], "server_receipt")
        self.assertEqual(receipt["event_outcome"], "received")
        self.assertEqual(failed["clock_basis"], "device")
        self.assertEqual(failed["event_outcome"], "failure")
        self.assertTrue(failed["gps_overlap"])
        self.assertEqual(untimed["match_status"], "untimed")
        self.assertFalse(untimed["within_window"])

    def test_outside_window_still_reports_nearest_observation(self):
        rows = build_event_matches(device(
            gps=[observation(0)], registrations=[registration(3600)],
        ))
        row = rows.iloc[0]
        self.assertEqual(row["match_status"], "outside_window")
        self.assertEqual(row["gps_obs_id"], "gps:0")
        self.assertEqual(row["offset_s"], -3600)

    def test_acquisition_overlap_is_independent_of_nearest_observation(self):
        rows = build_event_matches(device(
            gps=[observation(0), observation(30, start_time=EPOCH-pd.Timedelta(seconds=10),
                                           ttf_s=40, source_row=3)],
            registrations=[registration(5)],
        ))
        row = rows.iloc[0]
        self.assertEqual(row["gps_time"], EPOCH)
        self.assertEqual(row["offset_s"], -5)
        self.assertTrue(row["within_window"])
        self.assertTrue(row["gps_overlap"])

    def test_missing_gps_and_empty_events(self):
        rows = build_event_matches(device(registrations=[registration()]))
        self.assertEqual(rows.iloc[0]["match_status"], "no_gps")
        self.assertTrue(pd.isna(rows.iloc[0]["gps_time"]))
        self.assertTrue(build_event_matches(device()).empty)

    def test_overlapping_clock_segments_are_ambiguous(self):
        rows = build_event_matches(device(
            gps=[observation(0), observation(120, source_row=3),
                 observation(0, obs_id="reset:0", clock_segment=1, source_row=4),
                 observation(180, obs_id="reset:180", clock_segment=1, source_row=5)],
            registrations=[registration(60)],
        ))
        self.assertEqual(rows.iloc[0]["match_status"], "clock_ambiguous")
        self.assertFalse(rows.iloc[0]["within_window"])
        self.assertIsNone(rows.iloc[0]["gps_obs_id"])

    def test_flagged_clock_row_is_excluded_without_dropping_events(self):
        rows = build_event_matches(device(
            gps=[observation(clock_anomaly=True)],
            registrations=[registration(), registration(1, source_row=3)],
        ))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows["match_status"].eq("no_gps").all())

    def test_one_observation_can_support_multiple_events(self):
        rows = build_event_matches(device(
            gps=[observation()], registrations=[registration(), registration(5, source_row=3)],
        ))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows["within_window"].all())
        self.assertEqual(rows["gps_obs_id"].nunique(), 1)

    def test_invalid_tolerance_is_rejected(self):
        for tolerance in (-1, np.nan, np.inf):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                build_event_matches(device(), tolerance)


if __name__ == "__main__":
    unittest.main()
