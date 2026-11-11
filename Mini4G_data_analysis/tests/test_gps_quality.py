"""Synthetic GPS-quality regressions; no production datasets or output files."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from mini4g_analysis.gps_quality import GPS_COLUMNS, clean_gps_frames


OBS = ["line", "datetime", "date", "time", "numSV", "vbatt", "TTF", "startDatetime", "source_row"]
SV = OBS + ["ID", "CNR", "codePhase"]


class GpsQualityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mini4g-gps-quality-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    @staticmethod
    def observation(line=6, source_row=2, when="2026-07-01 12:00:00",
                    start=None, ttf="1", battery="100", satellites="1"):
        if start is None:
            try:
                start = str(datetime.fromisoformat(when) - timedelta(seconds=float(ttf)))
            except ValueError:
                start = when
        return dict(zip(OBS, [str(line), when, when.split(" ")[0], when.split(" ")[-1],
                             str(satellites), str(battery), str(ttf), start, str(source_row)]))

    @staticmethod
    def satellite(observation, source_row=2, cnr="40", phase="100"):
        return {**observation, "source_row": str(source_row), "ID": "3",
                "CNR": str(cnr), "codePhase": str(phase)}

    def dat(self, salts, kind=0x90):
        path = self.root / "input.dat"
        pages = [bytes([kind, salt]) + bytes(510) for salt in salts]
        content = "\r\n".join(["header"] * 5 + [" ".join(map(str, page)) for page in pages])
        path.write_bytes((content + "\r\n").encode())
        return path, pages

    def clean(self, observations, satellites=(), dat=None, mode="legacy"):
        obs = pd.DataFrame(observations, columns=OBS).astype(str)
        sv = pd.DataFrame(satellites, columns=SV).astype(str)
        before_obs, before_sv = obs.copy(deep=True), sv.copy(deep=True)
        result = clean_gps_frames("123", obs, sv, dat, mode)
        assert_frame_equal(obs, before_obs)
        assert_frame_equal(sv, before_sv)
        json.dumps(result[2], allow_nan=False)
        return result

    def test_dat_replays_remove_whole_copies_and_preserve_valid_ttf_and_order(self):
        first = self.observation()
        later = self.observation(7, 3, "2026-07-01 12:10:00")
        copy1 = {**first, "line": "8", "source_row": "4"}
        copy2 = {**first, "line": "9", "source_row": "5"}
        observations = [first, later, copy1, copy2]
        satellites = [self.satellite(row, i + 2, phase="200" if i == 1 else "100")
                      for i, row in enumerate(observations)]
        path, pages = self.dat([1, 2, 1, 1])
        before_dat = path.read_bytes()
        gps, sats, quality = self.clean(observations, satellites, path)
        self.assertEqual(path.read_bytes(), before_dat)
        self.assertEqual(gps["obs_id"].tolist(), ["123:gps:2", "123:gps:3"])
        self.assertEqual(gps["ttf_s"].tolist(), [1, 1])
        self.assertEqual(gps["clock_segment"].tolist(), [0, 0])
        self.assertFalse(gps["clock_anomaly"].any())
        self.assertEqual(len(sats), 2)
        self.assertEqual(quality["replay_page_groups"], 1)
        self.assertEqual(quality["extra_page_copies"], 2)
        self.assertEqual(quality["replayed_obs"], 2)
        self.assertEqual(quality["replayed_sv"], 2)
        self.assertEqual(quality["remaining_backwards"], 0)
        audit = [row for row in quality["audit"] if row["reason"] == "dat_page_replay"]
        self.assertEqual(len(audit), 2)
        self.assertEqual(audit[0]["source_rows"], [4])
        self.assertEqual(audit[0]["retained_source_rows"], [2])
        self.assertEqual(audit[0]["page_sha256"], hashlib.sha256(pages[0]).hexdigest())

    def test_missing_dat_uses_labelled_semantic_fallback_and_removes_attached_svs(self):
        first = self.observation()
        copied = {**first, "line": "20", "source_row": "3"}
        gps, sats, quality = self.clean(
            [first, copied], [self.satellite(first), self.satellite(copied, 3)])
        self.assertEqual(len(gps), 1)
        self.assertEqual(len(sats), 1)
        self.assertFalse(quality["page_identity_available"])
        self.assertEqual(quality["extra_page_copies"], 0)
        self.assertEqual(quality["semantic_duplicate_obs"], 1)
        self.assertEqual(quality["semantic_duplicate_sv"], 1)
        self.assertTrue(any("weaker" in issue for issue in quality["issues"]))

    def test_payload_ttf_duplicate_marks_contextual_clock_record_without_reinterpreting_ttf(self):
        first = self.observation(battery="10")
        copied = self.observation(7, 3, ttf="2", battery="10")
        path, _ = self.dat([1, 2])
        gps, sats, quality = self.clean(
            [first, copied], [self.satellite(first), self.satellite(copied, 3)], path)
        self.assertEqual(len(gps), 1)
        self.assertEqual(len(sats), 1)
        self.assertEqual(quality["payload_duplicate_obs"], 1)
        self.assertEqual(quality["payload_duplicate_sv"], 1)
        self.assertEqual(quality["raw_contextual_markers"], 2)
        self.assertEqual(quality["contextual_markers"], 1)
        self.assertEqual(gps.iloc[0]["marker_kind"], "contextual_unwrapped_clock_candidate")
        self.assertTrue(gps.iloc[0]["clock_record"])
        self.assertTrue(pd.isna(gps.iloc[0]["voltage_v"]))
        self.assertAlmostEqual(gps.iloc[0]["decoded_marker_voltage_v"], 4.07893)
        self.assertEqual(gps.iloc[0]["raw_ttf_s"], 1)
        self.assertEqual(gps.iloc[0]["ttf_s"], 1)
        self.assertEqual(quality["remaining_backwards"], 0)
        self.assertTrue(sats.iloc[0]["clock_record"])

    def test_full_parent_and_payload_fields_prevent_timestamp_only_join_and_multiplication(self):
        first = self.observation(ttf="2")
        other = self.observation(7, 3, ttf="1")
        duplicate_csv = {**first, "source_row": "4"}
        gps, sats, quality = self.clean(
            [first, other, duplicate_csv],
            [self.satellite(first, 2, cnr="30", phase="100"),
             self.satellite(first, 3, cnr="30", phase="100"),
             self.satellite(other, 4, cnr="40", phase="200")])
        self.assertEqual(len(gps), 2)
        self.assertEqual(len(sats), 2)
        self.assertEqual(gps["cnr_mean"].tolist(), [30, 40])
        self.assertEqual(sats["obs_id"].tolist(), ["123:gps:2", "123:gps:3"])
        self.assertEqual(quality["identical_csv_obs"], 1)
        self.assertEqual(quality["identical_csv_sv"], 1)
        self.assertEqual(quality["payload_duplicate_obs"], 0)

    def test_incomplete_satellite_payload_does_not_prove_a_duplicate(self):
        first = self.observation(ttf="2", satellites="2")
        other = self.observation(7, 3, ttf="1", satellites="2")
        gps, sats, quality = self.clean(
            [first, other], [self.satellite(first), self.satellite(other, 3)])
        self.assertEqual(len(gps), 2)
        self.assertEqual(len(sats), 2)
        self.assertEqual(quality["payload_duplicate_obs"], 0)

    def test_wrapped_candidates_zero_valid_and_255_ambiguous_without_dat(self):
        codes = [0, 20, 100, 152, 153, 156, 175, 196, 254, 255]
        observations = [self.observation(i + 6, i + 2, f"2026-07-01 12:{i:02d}:00",
                                         battery=str(code)) for i, code in enumerate(codes)]
        gps, _, quality = self.clean(observations)
        by_code = gps.set_index("vbatt_raw")
        self.assertEqual(by_code.loc[0, "voltage_v"], 3.5)
        self.assertAlmostEqual(by_code.loc[100, "voltage_v"], 4.0263)
        self.assertTrue(pd.isna(by_code.loc[153, "voltage_v"]))
        self.assertFalse(by_code.loc[153, "clock_record"])
        self.assertEqual(quality["wrapped_markers"], 4)
        self.assertEqual(quality["raw_wrapped_markers"], 4)
        for code in [156, 175, 196, 254]:
            with self.subTest(code=code):
                self.assertTrue(by_code.loc[code, "clock_record"])
                self.assertTrue(pd.isna(by_code.loc[code, "voltage_v"]))
                self.assertAlmostEqual(by_code.loc[code, "decoded_marker_voltage_v"],
                                       (code - 156) * 0.005263 + 3.5)
        self.assertEqual(by_code.loc[255, "marker_kind"], "unavailable_255")
        self.assertFalse(by_code.loc[255, "clock_record"])
        self.assertTrue(pd.isna(by_code.loc[255, "voltage_v"]))
        raw_gps, _, _ = self.clean(observations, mode="raw")
        self.assertTrue(raw_gps["voltage_v"].isna().all())

    def test_raw_255_requires_stronger_legacy_page_evidence(self):
        path, _ = self.dat([1])
        gps, _, quality = self.clean([self.observation(battery="255")], dat=path)
        self.assertTrue(gps.iloc[0]["clock_record"])
        self.assertEqual(gps.iloc[0]["marker_kind"], "legacy_wrapped_255_candidate")
        self.assertEqual(quality["wrapped_markers"], 1)
        self.assertTrue(pd.isna(gps.iloc[0]["voltage_v"]))

    def test_marker_start_cannot_partition_normal_clock_ordering(self):
        observations = [
            self.observation(6, 2, "2026-07-01 12:00:00"),
            self.observation(7, 3, "2026-07-01 12:00:10",
                             start="2026-07-01 11:00:00", ttf="3610", battery="176"),
            self.observation(8, 4, "2026-07-01 12:10:00"),
            self.observation(9, 5, "2026-07-01 11:30:00")]
        gps, _, quality = self.clean(observations)
        self.assertEqual(gps["clock_segment"].tolist(), [0, 0, 0, 1])
        self.assertEqual(gps["clock_anomaly"].tolist(), [False, False, False, True])
        self.assertEqual(quality["remaining_backwards"], 1)
        self.assertTrue(gps.iloc[1]["clock_record"])
        self.assertEqual(gps.iloc[1]["raw_ttf_s"], 3610)
        self.assertEqual(gps.iloc[1]["recorded_start_time"].isoformat(),
                         "2026-07-01T11:00:00+00:00")
        normal = gps.loc[~gps["clock_record"]]
        self.assertEqual((normal.iloc[1]["start_time"] - normal.iloc[0]["start_time"]).total_seconds(), 600)

    def test_iso_calendar_times_and_utc_suffix_do_not_guess_day_month_order(self):
        observations = [
            self.observation(6, 2, "2026-07-01", start="2026-07-01", ttf="0"),
            self.observation(7, 3, "2026-07-01 12:00:00 UTC",
                             start="2026-07-01 11:59:59 UTC"),
            self.observation(8, 4, "01/07/2026 12:10:00", start="01/07/2026 12:09:59")]
        gps, _, quality = self.clean(observations)
        self.assertEqual(gps.iloc[0]["time"].isoformat(), "2026-07-01T00:00:00+00:00")
        self.assertEqual(gps.iloc[1]["time"].isoformat(), "2026-07-01T12:00:00+00:00")
        self.assertTrue(pd.isna(gps.iloc[2]["time"]))
        self.assertTrue(gps.iloc[2]["clock_anomaly"])
        self.assertEqual(gps.iloc[2]["ttf_s"], 1)
        self.assertEqual(quality["invalid_time_rows"], 1)
        self.assertTrue(any(row["reason"] == "invalid_calendar_time" for row in quality["audit"]))

    def test_remaining_ordering_and_invalid_times_keep_known_ttf(self):
        observations = [
            self.observation(6, 2, "2026-07-01 12:10:00"),
            self.observation(7, 3, "2026-07-01 12:00:00", ttf="2"),
            self.observation(8, 4, "invalid", ttf="3")]
        gps, _, quality = self.clean(observations)
        self.assertEqual(gps["ttf_s"].tolist(), [1, 2, 3])
        self.assertEqual(gps["clock_segment"].tolist(), [0, 1, 1])
        self.assertEqual(gps["clock_anomaly"].tolist(), [False, True, True])
        self.assertEqual(quality["remaining_backwards"], 1)
        self.assertEqual(quality["invalid_time_rows"], 1)
        self.assertTrue(any(row["reason"] == "backward_ordering" for row in quality["audit"]))

    def test_nonempty_legacy_pages_without_parsed_observations_are_audited_only(self):
        pages = []
        for kind, length, salt in [(0x90, 12, 1), (0x90, 12, 2),
                                   (0x90, 3, 3), (0x92, 12, 4)]:
            page = bytearray(512)
            page[0], page[1], page[2], page[3] = kind, length, 0, salt
            pages.append(bytes(page))
        path = self.root / "coverage.dat"
        path.write_bytes(("\r\n".join(["header"] * 5 + [" ".join(map(str, page))
                         for page in pages]) + "\r\n").encode())
        before = path.read_bytes()
        gps, _, quality = self.clean([self.observation()], dat=path)
        self.assertEqual(len(gps), 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(quality["unparsed_dat_page_count"], 1)
        entry, = quality["unparsed_dat_pages"]
        self.assertEqual(entry["line"], 7)
        self.assertEqual(entry["declared_length"], 12)
        self.assertEqual(entry["header_length"], 3)
        self.assertEqual(entry["page_sha256"], hashlib.sha256(pages[1]).hexdigest())
        audit, = [row for row in quality["audit"]
                  if row["reason"] == "dat_page_without_parsed_observation"]
        self.assertEqual(audit["line"], 7)
        self.assertIsNone(audit["source_row"])
        self.assertTrue(any("raw pages are preserved" in issue for issue in quality["issues"]))
        self.assertFalse(any("corrupt" in issue.lower() for issue in quality["issues"]))

    def test_unparsed_page_time_hints_skip_zero_time_and_keep_partial_payload_header(self):
        zero_time_record = bytes(5) + bytes([0, 100, 1])
        first = bytes([26, 123, 5, 163, 0]) + bytes([1, 100, 1]) + bytes(5)
        partial = bytes([26, 123, 5, 171, 64]) + bytes([2, 100, 1]) + bytes(4)
        body = zero_time_record + first + partial
        page = bytearray(512)
        page[0] = 0x90
        declared = len(body) + 3
        page[1:3] = declared.to_bytes(2, "little")
        page[3:declared] = body
        path = self.root / "time-hints.dat"
        path.write_bytes(("\r\n".join(["header"] * 5 + [" ".join(map(str, page))]) + "\r\n").encode())
        before = path.read_bytes()
        gps, sats, quality = self.clean([], dat=path)
        self.assertTrue(gps.empty)
        self.assertTrue(sats.empty)
        self.assertEqual(path.read_bytes(), before)
        entry, = quality["unparsed_dat_pages"]
        self.assertEqual(entry["recorded_first_time"], "2026-06-15T05:24:20+00:00")
        self.assertEqual(entry["recorded_last_time"], "2026-06-15T05:24:21.500000+00:00")
        self.assertEqual(entry["valid_time_headers"], 2)
        self.assertEqual(entry["invalid_time_headers"], 1)
        self.assertEqual(entry["complete_record_count"], 2)
        self.assertEqual(entry["complete_valid_time_records"], 1)
        self.assertTrue(entry["partial_record_payload"])
        self.assertEqual(entry["header_walk_stop"], "partial_record_payload")
        self.assertEqual(len(entry["recorded_time_headers"]), 2)
        self.assertIn("not decoded GPS measurements", entry["time_hint_basis"])
        audit, = [row for row in quality["audit"]
                  if row["reason"] == "dat_page_without_parsed_observation"]
        self.assertEqual(audit["recorded_first_time"], entry["recorded_first_time"])

    def test_unparsed_time_hint_walk_stops_when_declared_length_exceeds_page(self):
        page = bytearray(512)
        page[:3] = bytes([0x90, 0, 4])
        page[3:11] = bytes([26, 123, 5, 163, 0, 0, 100, 1])
        path = self.root / "invalid-length.dat"
        path.write_bytes(("\r\n".join(["header"] * 5 + [" ".join(map(str, page))]) + "\r\n").encode())
        gps, _, quality = self.clean([], dat=path)
        self.assertTrue(gps.empty)
        entry, = quality["unparsed_dat_pages"]
        self.assertEqual(entry["header_walk_stop"], "invalid_declared_length")
        self.assertEqual(entry["valid_time_headers"], 0)
        self.assertIsNone(entry["recorded_first_time"])
        self.assertEqual(entry["complete_record_count"], 0)

    def test_empty_inputs_and_malformed_dat_are_explicit(self):
        gps, sats, quality = self.clean([])
        self.assertEqual(list(gps.columns), GPS_COLUMNS)
        self.assertTrue(gps.empty)
        self.assertTrue(sats.empty)
        self.assertEqual(quality["retained_gps_rows"], 0)
        path = self.root / "bad.dat"
        path.write_bytes(b"header\r\n1 2 3\r\n")
        with self.assertRaisesRegex(ValueError, "expected 512 DAT bytes"):
            self.clean([self.observation()], dat=path)


if __name__ == "__main__":
    unittest.main()
