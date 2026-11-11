"""Read-only loader checks using temporary, synthetic exports."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from mini4g_analysis.loaders import discover_sources, load_devices, load_registration_export, selected_input_files


GPS_FIELDS = ["line", "datetime", "date", "time", "numSV", "vbatt", "TTF", "startDatetime"]
SAT_FIELDS = GPS_FIELDS + ["ID", "CNR", "codePhase"]
STAT_FIELDS = ["upload_seq", "post_ok", "psm_ok", "vbatt (V)", "modem_vbatt_mv",
               "temp (C)", "temp_valid", "temp_time_utc", "temp_to_upload_age_s",
               "rsrp (dBm)", "tx_power (dBm)",
               "connect (ms)", "send (ms)", "ttfb (ms)", "http_status", "os_rc"]
REG_FIELDS = ["time", "tier", "outcome", "reg_time", "rsrp", "tx_power", "vbatt",
              "psm", "energy", "reg_count", "stats_ts"]


class LoaderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mini4g-loader-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_csv(self, relative, fields, rows):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def stats(self, *, folder="Tag123", prefix="123_", uploads=(), failures=(), registrations=()):
        self.write_csv(f"{folder}/{prefix}uploads.csv", ["upload_time_utc"] + STAT_FIELDS, uploads)
        self.write_csv(f"{folder}/{prefix}failed_stats.csv", ["attempt_time_utc"] + STAT_FIELDS, failures)
        self.write_csv(f"{folder}/{prefix}registrations.csv", REG_FIELDS, registrations)

    def gps(self, observations, satellites=(), *, folder="Tag123", prefix="123_ublox"):
        self.write_csv(f"{folder}/{prefix}_GPS_Obs.csv", GPS_FIELDS, observations)
        self.write_csv(f"{folder}/{prefix}_GPS_SVs.csv", SAT_FIELDS, satellites)

    @staticmethod
    def observation(line, when, start, *, battery="100", ttf="1", satellites="1"):
        return {"line": str(line), "datetime": when, "date": when.split(" ")[0],
                "time": when.split(" ")[-1], "numSV": satellites, "vbatt": battery,
                "TTF": ttf, "startDatetime": start}

    @staticmethod
    def satellite(observation, cnr):
        return {**observation, "ID": "3", "CNR": str(cnr), "codePhase": "100"}

    def test_communications_units_missing_values_and_boot_times(self):
        self.stats(
            folder="Tag123",
            uploads=[
                {"upload_time_utc": "2026-07-01T12:00:00.125000+00:00",
                 "upload_seq": "7", "post_ok": "1", "psm_ok": "1",
                 "vbatt (V)": "4.100", "modem_vbatt_mv": "0",
                 "connect (ms)": "0", "send (ms)": "0", "ttfb (ms)": "0"},
                {"upload_time_utc": "2026-07-01T12:01:00Z",
                 "upload_seq": "8", "post_ok": "", "psm_ok": ""}],
            failures=[
                {"attempt_time_utc": "2026-07-01 12:00:05 UTC", "upload_seq": "9",
                 "post_ok": "0", "vbatt (V)": "4.100", "modem_vbatt_mv": "4050",
                 "connect (ms)": "0", "send (ms)": "0", "ttfb (ms)": "0"}],
            registrations=[
                {"time": "2026-07-01 12:00:02", "tier": "HOT", "outcome": "SUCCESS",
                 "reg_time": "1.08 s", "rsrp": "-101 dBm", "tx_power": "19 dBm",
                 "vbatt": "4.043 V", "psm": "yes", "energy": "7",
                 "reg_count": "3", "stats_ts": "opaque-receipt-key"},
                {"time": "boot+7s", "tier": "COLD", "outcome": "timeout",
                 "reg_time": "-", "rsrp": "-", "vbatt": "0 V", "psm": ""}])
        device, = load_devices(self.root, device_clock_offset_seconds=0)
        self.assertEqual(device.device_id, "123")
        self.assertEqual(device.uploads.iloc[0]["time"].microsecond, 125000)
        self.assertEqual(device.failures.iloc[0]["time"].isoformat(), "2026-07-01T12:00:05+00:00")
        self.assertTrue(math.isnan(device.uploads.iloc[0]["modem_voltage_v"]))
        self.assertAlmostEqual(device.failures.iloc[0]["modem_voltage_v"], 4.05)
        self.assertEqual(device.failures.iloc[0]["connect_s"], 0)
        self.assertTrue(math.isnan(device.failures.iloc[0]["ttfb_s"]))
        self.assertTrue(math.isnan(device.failures.iloc[0]["send_s"]))
        self.assertEqual(device.uploads.iloc[0]["ttfb_s"], 0)
        self.assertTrue(math.isnan(device.uploads.iloc[1]["post_ok"]))
        self.assertTrue(math.isnan(device.uploads.iloc[1]["voltage_v"]))
        registration = device.registrations.iloc[0]
        self.assertAlmostEqual(registration["duration_s"], 1.08)
        self.assertEqual(registration["rsrp_dbm"], -101)
        self.assertEqual(registration["tx_dbm"], 19)
        self.assertAlmostEqual(registration["voltage_v"], 4.043)
        self.assertEqual(registration["outcome"], "success")
        self.assertEqual(registration["stats_ts"], "opaque-receipt-key")
        untimed = device.registrations.iloc[1]
        self.assertEqual(untimed["time_text"], "boot+7s")
        self.assertNotEqual(untimed["time"], untimed["time"])
        self.assertEqual(untimed["psm"], "unknown")
        self.assertTrue(math.isnan(untimed["duration_s"]))
        self.assertTrue(math.isnan(untimed["voltage_v"]))
        self.assertEqual(untimed["source_row"], 3)
        self.assertEqual(device.quality["selected_counts"]["registrations"], 2)

    def test_temperature_context_is_preserved_without_inferred_age(self):
        self.stats(uploads=[
            {"upload_time_utc": "2026-07-01T12:00:00Z", "upload_seq": "1", "post_ok": "1",
             "temp (C)": "33", "temp_valid": "1", "temp_time_utc": "2026-07-01 11:57:00 UTC",
             "temp_to_upload_age_s": "180"},
            {"upload_time_utc": "2026-07-01T12:01:00Z", "upload_seq": "2", "post_ok": "0",
             "temp (C)": "99", "temp_valid": "0", "temp_time_utc": "bad timestamp",
             "temp_to_upload_age_s": "-1"},
            {"upload_time_utc": "2026-07-01T12:02:00Z", "upload_seq": "3", "post_ok": "1",
             "temp (C)": "22", "temp_valid": "1", "temp_time_utc": "2026-07-01 12:00:00 UTC"}])
        device, = load_devices(self.root, device_clock_offset_seconds=0)
        first, invalid, no_age = [row for _, row in device.uploads.iterrows()]
        self.assertEqual(first["temp_c"], 33)
        self.assertEqual(first["temp_time"].isoformat(), "2026-07-01T11:57:00+00:00")
        self.assertEqual(first["temp_age_s"], 180)
        self.assertTrue(math.isnan(invalid["temp_c"]))
        self.assertTrue(math.isnan(invalid["temp_age_s"]))
        self.assertNotEqual(invalid["temp_time"], invalid["temp_time"])
        self.assertEqual(no_age["temp_c"], 22)
        self.assertTrue(math.isnan(no_age["temp_age_s"]))

    def test_gps_legacy_voltage_and_remaining_ordering_preserve_ttf_and_raw_codes(self):
        observations = [
            self.observation(1, "2026-07-01 12:00:00", "2026-07-01 11:59:59", battery="0"),
            self.observation(2, "2026-07-01 12:01:00", "2026-07-01 12:00:59", battery="255"),
            self.observation(3, "2026-07-01 11:00:00", "2026-07-01 10:59:59", battery="200"),
            self.observation(4, "2026-07-01 11:01:00", "2026-07-01 11:00:59", battery="100")]
        self.gps(observations)
        device, = load_devices(self.root, device_clock_offset_seconds=0)
        gps = device.gps
        self.assertEqual(gps["source_line"].tolist(), [1, 2, 3, 4])
        self.assertEqual(gps["source_row"].tolist(), [2, 3, 4, 5])
        self.assertEqual(gps["clock_segment"].tolist(), [0, 0, 0, 1])
        self.assertEqual(gps["clock_anomaly"].tolist(), [False, False, False, True])
        self.assertEqual(gps.iloc[0]["vbatt_raw"], 0)
        self.assertEqual(gps.iloc[0]["voltage_v"], 3.5)
        self.assertEqual(gps.iloc[1]["vbatt_raw"], 255)
        self.assertFalse(gps.iloc[1]["clock_record"])
        self.assertTrue(math.isnan(gps.iloc[1]["voltage_v"]))
        self.assertEqual(gps.iloc[2]["vbatt_raw"], 200)
        self.assertTrue(math.isnan(gps.iloc[2]["voltage_v"]))
        self.assertEqual(gps.iloc[2]["ttf_s"], 1)
        self.assertTrue(gps.iloc[2]["clock_record"])
        self.assertAlmostEqual(gps.iloc[3]["voltage_v"], 4.0263)
        self.assertEqual(gps.iloc[3]["ttf_s"], 1)
        self.assertEqual(device.quality["gps"]["remaining_backwards"], 1)
        self.assertEqual(device.quality["gps"]["wrapped_markers"], 1)
        self.assertTrue(any(row["reason"] == "backward_ordering"
                            for row in device.quality["gps"]["audit"]))

    def test_satellite_parent_matching_does_not_multiply_duplicate_observations(self):
        first = self.observation(1, "2026-07-01 12:00:00", "2026-07-01 11:59:59")
        other = self.observation(2, "2026-07-01 12:00:00", "2026-07-01 11:59:58", ttf="2")
        unmatched = {**other, "line": "99"}
        self.gps([first, other, dict(first)], [
            self.satellite(first, 30), self.satellite(other, 40), self.satellite(unmatched, 50)])
        device, = load_devices(self.root, device_clock_offset_seconds=0)
        self.assertEqual(len(device.gps), 2)
        self.assertEqual(len(device.satellites), 3)
        self.assertFalse(device.gps["duplicate"].any())
        self.assertEqual(device.gps["cnr_mean"].tolist(), [30, 40])
        self.assertEqual(device.gps["obs_id"].tolist(), ["123:gps:2", "123:gps:3"])
        self.assertEqual(device.satellites.iloc[1]["obs_id"], device.gps.iloc[1]["obs_id"])
        self.assertEqual(device.satellites["obs_id"].isna().sum(), 1)
        self.assertEqual(device.quality["gps"]["identical_csv_obs"], 1)
        self.assertEqual(device.quality["gps"]["unmatched_sv"], 1)
        removed, = [row for row in device.quality["gps"]["audit"]
                    if row["reason"] == "identical_csv_observation"]
        self.assertEqual(removed["source_row"], 4)
        self.assertEqual(removed["retained_source_row"], 2)

    def test_date_filter_is_start_inclusive_end_exclusive_and_accounts_for_untimed_rows(self):
        beginning = "2026-07-01 12:00:00"
        ending = "2026-07-01 12:01:00"
        observations = [
            self.observation(1, beginning, "2026-07-01 11:59:59"),
            self.observation(2, ending, "2026-07-01 12:00:59"),
            self.observation(3, "boot+3s", "boot+2s")]
        self.gps(observations, [self.satellite(row, 35) for row in observations])
        self.stats(
            uploads=[{"upload_time_utc": when, "upload_seq": str(index), "post_ok": "1"}
                     for index, when in enumerate([beginning, ending, "boot+3s"])],
            registrations=[
                {"time": when, "tier": "HOT", "outcome": "success", "reg_time": "1 s", "psm": "yes"}
                for when in ["2026-07-01 11:59:59", beginning,
                             "2026-07-01 12:00:59", ending, "boot+3s"]])
        device, = load_devices(
            self.root, device_clock_offset_seconds=0, start=datetime(2026, 7, 1, 12, 0),
            end=datetime(2026, 7, 1, 12, 1))
        self.assertEqual(len(device.gps), 1)
        self.assertEqual(len(device.uploads), 1)
        self.assertEqual(len(device.registrations), 2)
        self.assertEqual(len(device.satellites), 1)
        self.assertEqual(device.satellites.iloc[0]["obs_id"], device.gps.iloc[0]["obs_id"])
        for kind in ["gps", "uploads", "registrations"]:
            with self.subTest(kind=kind):
                self.assertEqual(device.quality["period_excluded"][kind]["untimed"], 1)
        self.assertEqual(device.quality["gps"]["raw_gps_rows"], 3)
        self.assertEqual(device.gps.iloc[0]["time"].isoformat(), "2026-07-01T12:00:00+00:00")
        offset = timezone(timedelta(hours=1))
        aware, = load_devices(
            self.root, device_clock_offset_seconds=0, start=datetime(2026, 7, 1, 13, 0, tzinfo=offset),
            end=datetime(2026, 7, 1, 13, 1, tzinfo=offset))
        self.assertEqual(aware.gps["obs_id"].tolist(), device.gps["obs_id"].tolist())
        self.assertEqual(aware.quality["selected_counts"], device.quality["selected_counts"])

    def test_tag_layout_replays_and_selected_inputs_preserve_raw_files(self):
        first = self.observation(6, "2026-07-01 12:00:00", "2026-07-01 11:59:59")
        other = self.observation(7, "2026-07-01 12:10:00", "2026-07-01 12:09:59")
        replay = {**first, "line": "8"}
        self.gps([first, other, replay], [self.satellite(row, 35)
                 for row in [first, other, replay]], folder="Tag123")
        self.stats(folder="Tag123", prefix="123_", uploads=[
            {"upload_time_utc": "2026-07-01T12:00:18Z", "upload_seq": "1", "post_ok": "1"}])
        pages = [bytes([0x90, salt]) + bytes(510) for salt in [1, 2, 1]]
        dat = self.root / "Tag123/123_ublox.dat"
        dat.write_bytes(("\r\n".join(["header"] * 5 + [" ".join(map(str, page))
                        for page in pages]) + "\r\n").encode())
        self.stats(folder="Tag456", prefix="456_")
        self.write_csv("Tag123/notes.csv", ["unrelated"], [{"unrelated": "keep"}])
        self.write_csv("devices_pos_files/Tag999/999_ublox_GPS_Obs.csv", ["unrelated"], [])
        self.write_csv("unrelated/123_uploads.csv", ["unrelated"], [])
        self.write_csv("unrelated.csv", ["unrelated"], [])
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        sources = discover_sources(self.root, device_ids=["123"])
        expected = {self.root / "Tag123" / name for name in [
            "123_ublox.dat", "123_ublox_GPS_Obs.csv", "123_ublox_GPS_SVs.csv",
            "123_uploads.csv", "123_failed_stats.csv", "123_registrations.csv"]}
        self.assertEqual(set(selected_input_files(sources)), expected)
        device, = load_devices(self.root, sources=sources, device_clock_offset_seconds=0)
        self.assertEqual(device.device_id, "123")
        self.assertEqual(set(device.source_files), expected)
        self.assertEqual(device.gps["obs_id"].tolist(), ["123:gps:2", "123:gps:3"])
        self.assertEqual(device.gps["clock_segment"].tolist(), [0, 0])
        self.assertEqual(device.gps["ttf_s"].tolist(), [1, 1])
        self.assertEqual(device.satellites["obs_id"].tolist(), ["123:gps:2", "123:gps:3"])
        self.assertEqual(device.quality["gps"]["extra_page_copies"], 1)
        self.assertEqual(device.quality["gps"]["replayed_obs"], 1)
        self.assertEqual(device.quality["gps"]["replayed_sv"], 1)
        self.assertEqual(device.quality["gps"]["remaining_backwards"], 0)
        self.assertEqual({path.relative_to(self.root): path.read_bytes()
                          for path in self.root.rglob("*") if path.is_file()}, before)

    def test_default_offset_aligns_device_fields_but_preserves_receipt_and_recorded_times(self):
        observation = self.observation(6, "2026-07-01 12:00:18", "2026-07-01 12:00:17")
        self.gps([observation], [self.satellite(observation, 35)])
        self.stats(
            uploads=[{"upload_time_utc": "2026-07-01T12:00:05Z", "upload_seq": "1", "post_ok": "1",
                      "vbatt (V)": "4.100", "modem_vbatt_mv": "4000", "temp (C)": "25",
                      "temp_valid": "1", "temp_time_utc": "2026-07-01 12:00:10 UTC",
                      "temp_to_upload_age_s": "8"}],
            failures=[{"attempt_time_utc": "2026-07-01 12:01:18 UTC", "upload_seq": "2", "post_ok": "0",
                       "temp (C)": "25", "temp_valid": "1", "temp_time_utc": "2026-07-01 12:01:10 UTC",
                       "temp_to_upload_age_s": "8"}],
            registrations=[{"time": "2026-07-01 12:00:18", "tier": "HOT", "outcome": "success",
                            "reg_time": "1 s", "reg_count": "1", "psm": "yes"}])
        device, = load_devices(self.root)
        gps = device.gps.iloc[0]
        self.assertEqual(gps["time"].isoformat(), "2026-07-01T12:00:00+00:00")
        self.assertEqual(gps["start_time"].isoformat(), "2026-07-01T11:59:59+00:00")
        self.assertEqual(gps["recorded_time"].isoformat(), "2026-07-01T12:00:18+00:00")
        self.assertEqual(gps["recorded_start_time"].isoformat(), "2026-07-01T12:00:17+00:00")
        receipt = device.uploads.iloc[0]
        self.assertEqual(receipt["time"].isoformat(), "2026-07-01T12:00:05+00:00")
        self.assertEqual(receipt["recorded_time"], receipt["time"])
        self.assertEqual(receipt["temp_time"].isoformat(), "2026-07-01T11:59:52+00:00")
        self.assertEqual(receipt["recorded_temp_time"].isoformat(), "2026-07-01T12:00:10+00:00")
        self.assertEqual(receipt["stats_time"].isoformat(), "2026-07-01T12:00:00+00:00")
        self.assertEqual(receipt["recorded_stats_time"].isoformat(), "2026-07-01T12:00:18+00:00")
        failure = device.failures.iloc[0]
        self.assertEqual(failure["time"].isoformat(), "2026-07-01T12:01:00+00:00")
        self.assertEqual(failure["recorded_time"].isoformat(), "2026-07-01T12:01:18+00:00")
        self.assertEqual(failure["temp_time"].isoformat(), "2026-07-01T12:00:52+00:00")
        self.assertEqual(failure["recorded_temp_time"].isoformat(), "2026-07-01T12:01:10+00:00")
        registration = device.registrations.iloc[0]
        self.assertEqual(registration["time"].isoformat(), "2026-07-01T12:00:00+00:00")
        self.assertEqual(registration["recorded_time"].isoformat(), "2026-07-01T12:00:18+00:00")
        self.assertEqual(device.quality["clock"]["device_offset_seconds"], 18)

    def test_old_split_trees_are_not_accepted_and_malformed_tag_headers_fail(self):
        self.stats(folder="123_stats", prefix="")
        self.gps([self.observation(6, "2026-07-01 12:00:00", "2026-07-01 11:59:59")],
                 folder="123_ublox")
        with self.assertRaises(ValueError):
            load_devices(self.root, device_clock_offset_seconds=0)
        self.write_csv("headers/Tag456/456_uploads.csv",
                       ["upload_time_utc", "upload_seq"],
                       [{"upload_time_utc": "2026-07-01T12:00:00Z", "upload_seq": "1"}])
        with self.assertRaisesRegex(ValueError, "missing required columns: post_ok"):
            load_devices(self.root / "headers", device_clock_offset_seconds=0)

    def test_registration_only_export_reuses_cleaning_and_reads_no_other_source(self):
        original = {"time": "2026-07-01 12:00:18", "tier": "HOT", "outcome": "success",
                    "reg_time": "1.08 s", "reg_count": "5", "psm": "", "rsrp": "-", "stats_ts": ""}
        enriched = {**original, "psm": "yes", "rsrp": "-101 dBm", "stats_ts": "captured-link"}
        boot = {"time": "boot+7s", "tier": "COLD", "outcome": "timeout", "reg_time": "-", "psm": ""}
        self.write_csv("single-registration.csv", REG_FIELDS, [original, dict(original), enriched, boot])
        source = self.root / "single-registration.csv"
        self.write_csv("123_uploads.csv", ["must_not_read"], [{"must_not_read": "untouched"}])
        self.write_csv("123_ublox_GPS_Obs.csv", ["must_not_read"], [])
        (self.root / "123_ublox.dat").write_bytes(b"must not read or parse")
        before = {path.name: path.read_bytes() for path in self.root.iterdir() if path.is_file()}
        read_csv = pd.read_csv
        read_paths = []

        def only_registration(path, *args, **kwargs):
            self.assertEqual(Path(path).resolve(), source.resolve())
            read_paths.append(Path(path).resolve())
            return read_csv(path, *args, **kwargs)

        with patch("mini4g_analysis.loaders.pd.read_csv", side_effect=only_registration), \
             patch("mini4g_analysis.loaders.discover_sources", side_effect=AssertionError("Unexpected source discovery")), \
             patch("mini4g_analysis.loaders._read_stats", side_effect=AssertionError("Unexpected stats read")):
            registrations, quality = load_registration_export(source, device_id="123")
        self.assertEqual(read_paths, [source.resolve()])
        self.assertEqual(len(registrations), 2)
        registration = registrations.iloc[0]
        self.assertEqual(registration["time"].isoformat(), "2026-07-01T12:00:00+00:00")
        self.assertEqual(registration["recorded_time"].isoformat(), "2026-07-01T12:00:18+00:00")
        self.assertEqual(registration["psm"], "yes")
        self.assertEqual(registration["rsrp_dbm"], -101)
        self.assertEqual(registration["merged_source_rows"], [2, 4])
        self.assertEqual(registration["stats_ts_values"], ["captured-link"])
        self.assertEqual(len(registration["merged_record_hashes"]), 2)
        self.assertTrue(pd.isna(registrations.iloc[1]["time"]))
        self.assertTrue(pd.isna(registrations.iloc[1]["recorded_time"]))
        self.assertEqual(quality["stats"]["raw_registrations"], 4)
        self.assertEqual(quality["stats"]["exact_registration_duplicates"], 1)
        self.assertEqual(quality["stats"]["semantic_registration_removed"], 1)
        self.assertEqual(quality["stats"]["registration_conflicts"], 0)
        self.assertEqual(quality["stats"]["raw_uploads"], 0)
        self.assertEqual(quality["stats"]["raw_failures"], 0)
        self.assertEqual(quality["clock"]["device_offset_seconds"], 18)
        self.assertEqual(quality["source_file"], str(source.resolve()))
        exact, = [row for row in quality["stats"]["audit"] if row["action"] == "exact_duplicate_removed"]
        self.assertEqual(exact["source_row"], 3)
        self.assertEqual(exact["kept_source_row"], 2)
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir() if path.is_file()}, before)

    def test_registration_only_export_requires_a_valid_csv_and_finite_offset(self):
        with self.assertRaisesRegex(ValueError, "Registration export does not exist"):
            load_registration_export(self.root / "missing.csv", device_id="123")
        self.write_csv("wrong-header.csv", ["time", "tier"], [])
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            load_registration_export(self.root / "wrong-header.csv", device_id="123")
        broken = self.root / "broken.csv"
        broken.write_bytes(b'time,tier,outcome,reg_time,psm\r\n"unterminated\r\n')
        with self.assertRaisesRegex(ValueError, "Cannot read registration export"):
            load_registration_export(broken, device_id="123")
        with self.assertRaisesRegex(ValueError, "Device clock offset must be finite"):
            load_registration_export(broken, device_id="123", device_clock_offset_seconds=float("nan"))

    def test_header_only_registration_export_and_explicit_zero_offset(self):
        self.write_csv("empty-registrations.csv", REG_FIELDS, [])
        frame, quality = load_registration_export(self.root / "empty-registrations.csv", device_id="123",
                                                   device_clock_offset_seconds=0)
        self.assertTrue(frame.empty)
        self.assertIn("recorded_time", frame)
        self.assertEqual(quality["stats"]["raw_registrations"], 0)
        self.assertEqual(quality["clock"]["device_offset_seconds"], 0)
        self.write_csv("uncorrected.csv", REG_FIELDS, [{"time": "2026-07-01 12:00:18", "tier": "HOT",
                                                       "outcome": "success", "reg_time": "1 s", "psm": "yes"}])
        frame, _ = load_registration_export(self.root / "uncorrected.csv", device_id="123",
                                             device_clock_offset_seconds=0)
        self.assertEqual(frame.iloc[0]["time"], frame.iloc[0]["recorded_time"])


if __name__ == "__main__":
    unittest.main()
