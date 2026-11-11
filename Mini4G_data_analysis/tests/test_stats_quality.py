"""Synthetic checks for export cleaning and conservative receipt evidence."""

import json
import unittest

import numpy as np
import pandas as pd

from mini4g_analysis.stats_quality import clean_stats_frames


NOW = pd.Timestamp("2026-07-01T12:00:00Z")
OFFSET = pd.Timedelta(seconds=18)


def upload(**changes):
    row = dict(
        time=NOW, upload_seq=1, post_ok=1, psm_ok=1, voltage_v=4.1,
        modem_voltage_v=4.06, temp_c=25.0, temp_time=NOW+OFFSET-pd.Timedelta(seconds=120),
        temp_age_s=120.0, rsrp_dbm=-110.0, tx_dbm=20.0,
        connect_s=0.0, send_s=0.02, ttfb_s=0.1, http_status=200, os_rc=0,
        source_row=2, data_summary="1 page / UBLOX", record_hash="upload-1",
    )
    row.update(changes)
    return row


def failure(**changes):
    row = upload(time=NOW+OFFSET, post_ok=0, http_status=0, os_rc=-11,
                 record_hash="failure-1")
    row.pop("data_summary")
    row.update(changes)
    return row


def registration(**changes):
    row = dict(
        time=NOW+OFFSET, time_text="2026-07-01 12:00:18", reg_count=1,
        tier="HOT", outcome="success", duration_s=0.73, psm="yes",
        rsrp_dbm=-110.0, tx_dbm=20.0, voltage_v=4.1, energy=5.0,
        stats_ts="", source_row=2, record_hash="reg-1",
    )
    row.update(changes)
    return row


def clean(uploads=(), failures=(), registrations=(), **options):
    return clean_stats_frames("123", pd.DataFrame(uploads), pd.DataFrame(failures),
                              pd.DataFrame(registrations), **options)


class StatsQualityTests(unittest.TestCase):
    def test_reused_sequence_future_stats_are_masked_receipt_is_retained(self):
        later = NOW+pd.Timedelta(days=7)
        captured_temperature = later+OFFSET-pd.Timedelta(seconds=120)
        result, _, _, events, quality = clean(uploads=[
            upload(temp_time=captured_temperature, record_hash="wrong-boot"),
            upload(time=NOW+pd.Timedelta(minutes=1), upload_seq=2, source_row=3, record_hash="middle"),
            upload(time=later, temp_time=captured_temperature, source_row=4, record_hash="later-boot"),
        ])
        self.assertEqual(len(result), 3)
        self.assertTrue(result.iloc[0]["stats_rejected"])
        self.assertFalse(result.iloc[0]["stats_valid"])
        self.assertTrue(pd.isna(result.iloc[0]["post_ok"]))
        self.assertTrue(pd.isna(result.iloc[0]["voltage_v"]))
        self.assertTrue(pd.isna(result.iloc[0]["temp_time"]))
        self.assertEqual(result.iloc[0]["time"], NOW)
        self.assertEqual(result.iloc[0]["upload_seq"], 1)
        self.assertEqual(result.iloc[0]["source_row"], 2)
        self.assertEqual(result.iloc[0]["data_summary"], "1 page / UBLOX")
        self.assertEqual(result.iloc[0]["record_hash"], "wrong-boot")
        self.assertTrue(result.iloc[2]["stats_valid"])
        self.assertEqual(quality["rejected_receipt_stats"], 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events.iloc[0]["kind"], "counter_restart")
        self.assertEqual(events.iloc[0]["confidence"], "counter_only")
        self.assertEqual(result["counter_epoch"].tolist(), [0, 0, 1])
        rejected = [item for item in quality["audit"] if item["action"] == "receipt_stats_rejected"][0]
        self.assertEqual(rejected["source_row"], 2)
        self.assertIsNotNone(rejected["temperature_time_recorded"])

    def test_inferred_stats_time_and_inclusive_future_boundary(self):
        result, _, _, _, quality = clean(uploads=[
            upload(temp_time=NOW+OFFSET+pd.Timedelta(seconds=500), temp_age_s=200),
            upload(time=NOW, temp_time=NOW+OFFSET+pd.Timedelta(seconds=600), temp_age_s=0,
                   source_row=3, record_hash="boundary", upload_seq=2),
        ])
        self.assertEqual(quality["rejected_receipt_stats"], 1)
        self.assertEqual(result.iloc[0]["rejection_reason"], "inferred_stats_after_receipt")
        self.assertFalse(result.iloc[1]["stats_rejected"])
        self.assertEqual(result.iloc[1]["stats_time"], NOW+OFFSET+pd.Timedelta(seconds=600))

    def test_negative_or_unknown_age_is_not_used_to_infer_stats_time(self):
        result, _, _, _, quality = clean(uploads=[
            upload(temp_time=NOW+OFFSET+pd.Timedelta(seconds=590), temp_age_s=-20),
            upload(temp_age_s=np.nan, source_row=3, record_hash="unknown-age", upload_seq=2),
        ])
        self.assertTrue(result["stats_time"].isna().all())
        self.assertTrue(result["temp_age_s"].isna().all())
        self.assertEqual(quality["rejected_receipt_stats"], 0)
        self.assertEqual(result.iloc[0]["temp_time"], NOW+OFFSET+pd.Timedelta(seconds=590))

    def test_exact_failed_duplicates_use_raw_hash_and_preserve_first(self):
        _, failures, _, _, quality = clean(failures=[failure(), failure(source_row=3)])
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures.iloc[0]["source_row"], 2)
        self.assertEqual(failures.iloc[0]["post_ok"], 0)
        self.assertEqual(quality["exact_failed_duplicates"], 1)
        self.assertEqual(quality["failed_unmatched"], 1)

    def test_exact_duplicate_fallback_excludes_metadata_and_handles_missing(self):
        first = failure(voltage_v=np.nan)
        first.pop("record_hash")
        second = dict(first, source_row=99)
        _, failures, _, _, quality = clean(failures=[first, second])
        self.assertEqual(len(failures), 1)
        self.assertEqual(quality["exact_failed_duplicates"], 1)

    def test_registration_late_enrichment_is_merged(self):
        _, _, registrations, _, quality = clean(registrations=[
            registration(psm="unknown", rsrp_dbm=np.nan),
            registration(psm="yes", rsrp_dbm=-110, stats_ts="later|capture", source_row=3, record_hash="reg-2"),
        ])
        self.assertEqual(len(registrations), 1)
        row = registrations.iloc[0]
        self.assertEqual(row["psm"], "yes")
        self.assertEqual(row["rsrp_dbm"], -110)
        self.assertEqual(row["stats_ts"], "later|capture")
        self.assertEqual(row["merged_source_rows"], [2, 3])
        self.assertEqual(quality["exact_registration_duplicates"], 0)
        self.assertEqual(quality["semantic_registration_removed"], 1)
        self.assertEqual(quality["registration_conflicts"], 0)

    def test_known_registration_conflicts_are_unknown_not_first_wins(self):
        _, _, registrations, _, quality = clean(registrations=[
            registration(psm="yes", voltage_v=4.1),
            registration(psm="no", voltage_v=4.0, source_row=3, record_hash="reg-2"),
        ])
        row = registrations.iloc[0]
        self.assertEqual(row["psm"], "unknown")
        self.assertTrue(pd.isna(row["voltage_v"]))
        self.assertEqual(row["energy"], 5)
        self.assertEqual(set(row["conflict_fields"]), {"psm", "voltage_v"})
        self.assertEqual(quality["registration_conflicts"], 1)
        self.assertEqual(quality["semantic_registration_removed"], 1)
        json.dumps(quality, allow_nan=False)

    def test_untimed_boot_rows_receive_exact_only_deduplication(self):
        _, _, registrations, _, quality = clean(registrations=[
            registration(time=pd.NaT, time_text="boot+12s", record_hash="boot-a"),
            registration(time=pd.NaT, time_text="boot+12s", record_hash="boot-b", source_row=3),
            registration(time=pd.NaT, time_text="boot+12s", record_hash="boot-a", source_row=4),
        ])
        self.assertEqual(len(registrations), 2)
        self.assertTrue(registrations["time"].isna().all())
        self.assertEqual(quality["exact_registration_duplicates"], 1)
        self.assertEqual(quality["semantic_registration_removed"], 0)

    def test_failure_receipt_evidence_uses_offset_and_preserves_transport_result(self):
        _, failures, _, _, quality = clean(
            uploads=[upload()], failures=[failure()], receipt_window_seconds=0,
        )
        row = failures.iloc[0]
        self.assertEqual(row["receipt_match_status"], "received")
        self.assertEqual(row["time"], NOW+OFFSET)
        self.assertEqual(row["matched_receipt_time"], NOW)
        self.assertEqual(row["matched_receipt_source_row"], 2)
        self.assertEqual(row["post_ok"], 0)
        self.assertEqual(quality["failed_received"], 1)

    def test_ambiguous_and_missing_receipts_are_not_called_undelivered(self):
        _, failures, _, _, quality = clean(
            uploads=[upload(upload_seq=3), upload(time=NOW+pd.Timedelta(seconds=60), upload_seq=3,
                                                 source_row=3, record_hash="second-receipt")],
            failures=[failure(upload_seq=3), failure(upload_seq=9, source_row=3, record_hash="missing"),
                      failure(time=pd.NaT, source_row=4, record_hash="untimed")],
        )
        self.assertEqual(failures["receipt_match_status"].tolist(), ["ambiguous", "no_matching_receipt", "no_matching_receipt"])
        self.assertEqual(failures["receipt_candidate_count"].tolist(), [2, 0, 0])
        self.assertTrue(failures["matched_receipt_time"].isna().all())
        self.assertEqual(quality["failed_ambiguous"], 1)
        self.assertEqual(quality["failed_unmatched"], 2)
        self.assertEqual(quality["failed_untimed"], 1)

    def test_repeated_receipt_stats_are_counted_once_per_counter_epoch_only(self):
        result, _, _, events, quality = clean(uploads=[
            upload(),
            upload(time=NOW+pd.Timedelta(seconds=10), source_row=3, record_hash="repeat"),
            upload(time=NOW+pd.Timedelta(seconds=20), upload_seq=2, source_row=4, record_hash="higher"),
            upload(time=NOW+pd.Timedelta(seconds=30), source_row=5, record_hash="new-counter-epoch"),
        ])
        self.assertEqual(len(result), 4)
        self.assertEqual(result["stats_counted"].tolist(), [True, False, True, True])
        self.assertEqual(quality["receipt_stats_deduplicated"], 1)
        self.assertEqual(len(events), 1)
        self.assertTrue(result["stats_valid"].all())

    def test_distinct_raw_stats_hashes_are_not_collapsed_after_normalization(self):
        result, _, _, _, quality = clean(uploads=[
            upload(stats_hash="raw-stats-a"),
            upload(time=NOW+pd.Timedelta(seconds=10), source_row=3,
                   record_hash="another-receipt", stats_hash="raw-stats-b"),
        ])
        self.assertTrue(result["stats_counted"].all())
        self.assertEqual(quality["receipt_stats_deduplicated"], 0)

    def test_unavailable_zero_sequence_does_not_split_a_rising_counter(self):
        result, failures, _, events, quality = clean(
            uploads=[
                upload(upload_seq=10),
                upload(time=NOW+pd.Timedelta(seconds=10), upload_seq=0, source_row=3, record_hash="unknown-seq"),
                upload(time=NOW+pd.Timedelta(seconds=20), upload_seq=11, source_row=4, record_hash="rising-seq"),
            ],
            failures=[failure(upload_seq=0)],
        )
        self.assertTrue(events.empty)
        self.assertEqual(result["counter_epoch"].tolist(), [0, 0, 0])
        self.assertEqual(quality["counter_restarts"], 0)
        self.assertEqual(failures.iloc[0]["receipt_match_status"], "no_matching_receipt")

    def test_non_one_positive_decrease_is_regression_not_restart(self):
        result, _, _, events, quality = clean(uploads=[
            upload(upload_seq=10),
            upload(time=NOW+pd.Timedelta(seconds=10), upload_seq=8, source_row=3, record_hash="regression"),
        ])
        self.assertEqual(events.iloc[0]["kind"], "sequence_regression")
        self.assertEqual(events.iloc[0]["confidence"], "sequence_only")
        self.assertEqual(quality["counter_restarts"], 0)
        self.assertEqual(quality["sequence_regressions"], 1)
        self.assertEqual(result["counter_epoch"].tolist(), [0, 1])

    def test_empty_frames_and_quality_are_json_safe(self):
        uploads, failures, registrations, events, quality = clean()
        self.assertTrue(uploads.empty and failures.empty and registrations.empty and events.empty)
        self.assertEqual(quality["raw_uploads"], 0)
        self.assertEqual(quality["failed_received"], 0)
        self.assertEqual(quality["rejected_receipt_stats"], 0)
        json.dumps(quality, allow_nan=False)

    def test_inputs_are_unchanged(self):
        inputs = [pd.DataFrame([upload()]), pd.DataFrame([failure()]), pd.DataFrame([registration()])]
        snapshots = [frame.copy(deep=True) for frame in inputs]
        clean_stats_frames("123", *inputs)
        for original, snapshot in zip(inputs, snapshots):
            pd.testing.assert_frame_equal(original, snapshot)

    def test_invalid_options_fail_before_cleaning(self):
        for options in ({"future_lead_seconds": -1}, {"receipt_window_seconds": np.inf},
                        {"device_clock_offset_seconds": np.nan}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                clean(**options)


if __name__ == "__main__":
    unittest.main()
