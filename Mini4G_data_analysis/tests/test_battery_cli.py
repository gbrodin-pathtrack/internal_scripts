"""Small staged-CLI integration checks over synthetic, temporary Tag exports."""
from __future__ import annotations

import contextlib
import csv
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


class BatteryCliTests(unittest.TestCase):
    @staticmethod
    def write_csv(path, fields, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def snapshot(folder):
        return {path.relative_to(folder).as_posix(): path.read_bytes()
                for path in folder.rglob("*") if path.is_file()}

    def make_data(self, root):
        data = root / "Data"
        tag = data / "Tag123"
        fields = ["upload_seq", "post_ok", "vbatt (V)", "modem_vbatt_mv",
                  "temp (C)", "temp_valid", "temp_time_utc", "temp_to_upload_age_s"]
        self.write_csv(
            tag / "123_uploads.csv", ["upload_time_utc"] + fields,
            [{"upload_time_utc": "2026-07-01T00:00:00Z", "upload_seq": "1",
              "post_ok": "1", "vbatt (V)": "4.100", "modem_vbatt_mv": "4000",
              "temp (C)": "25", "temp_valid": "1",
              "temp_time_utc": "2026-06-30 23:58:00 UTC", "temp_to_upload_age_s": "120"},
             {"upload_time_utc": "2026-07-02T00:00:00Z", "upload_seq": "2",
              "post_ok": "1", "vbatt (V)": "4.050", "modem_vbatt_mv": "0",
              "temp (C)": "22", "temp_valid": "1", "temp_to_upload_age_s": "0"},
             {"upload_time_utc": "2026-07-03T00:00:00Z", "upload_seq": "3",
              "post_ok": "1", "vbatt (V)": "3.950", "modem_vbatt_mv": "4000"}])
        self.write_csv(
            tag / "123_failed_stats.csv", ["attempt_time_utc"] + fields,
            [{"attempt_time_utc": "boot+7s", "upload_seq": "4", "post_ok": "0",
              "vbatt (V)": "3.900", "modem_vbatt_mv": "4000",
              "temp (C)": "20", "temp_valid": "1"}])
        self.write_csv(tag / "123_registrations.csv",
                       ["time", "tier", "outcome", "reg_time", "psm"], [])
        self.write_csv(tag / "notes.csv", ["unrelated"], [{"unrelated": "do not consume"}])
        copied = data / "devices_pos_files" / "ignored.dat"
        copied.parent.mkdir(parents=True)
        copied.write_bytes(b"Unrelated copied DAT, not an analysis source.\r\n")
        return data

    def expected_hashes(self, data):
        return {f"Tag123/123_{name}.csv":
                hashlib.sha256((data / "Tag123" / f"123_{name}.csv").read_bytes()).hexdigest()
                for name in ["uploads", "failed_stats", "registrations"]}

    def test_default_study_period_excludes_june_and_untimed_battery_rows(self):
        with tempfile.TemporaryDirectory(prefix="mini4g-study-period-") as temporary:
            root = Path(temporary)
            data = self.make_data(root)
            uploads = data / "Tag123" / "123_uploads.csv"
            with uploads.open(newline="",encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                fields, rows = reader.fieldnames, list(reader)
            rows.insert(0,{"upload_time_utc":"2026-06-30T12:00:00Z","upload_seq":"99",
                           "post_ok":"1","vbatt (V)":"3.600","modem_vbatt_mv":"3600"})
            self.write_csv(uploads,fields,rows)
            before = self.snapshot(data)
            output = root / "Outputs"
            script = Path(__file__).resolve().parents[1] / "analyse.py"
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["MPLBACKEND"] = "Agg"
            environment["MPLCONFIGDIR"] = str(root / "matplotlib")
            result = subprocess.run([sys.executable,"-B",str(script),"--data",str(data),
                                     "--output",str(output),"--plot-set","adc-modem"],
                                    cwd=script.parent,env=environment,capture_output=True,text=True,timeout=25)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            manifest = json.loads((output / "battery_adc_modem/run.json").read_text())
            self.assertEqual(manifest["settings"]["period"],"study")
            self.assertEqual(manifest["settings"]["effective_start"],"2026-07-01T00:00:00+00:00")
            row, = manifest["metrics"]
            self.assertEqual(row["pairs"],2)
            self.assertAlmostEqual(row["mean_diff_mv"],25)
            self.assertEqual(self.snapshot(data),before)

    def test_adc_only_cli_keeps_incomplete_pairs_and_preserves_existing_results(self):
        with tempfile.TemporaryDirectory(prefix="mini4g-battery-cli-") as temporary:
            root = Path(temporary)
            data = self.make_data(root)
            output = root / "Outputs"
            original_inputs = self.snapshot(data)
            originals = {
                "overview.md": b"Existing main overview\r\n",
                "run.json": b'{"existing":"main manifest"}\r\n',
                "data_quality.json": b'{"existing":"quality"}\r\n',
                "diagnostics.json": b'{"existing":"diagnostics"}\r\n',
                "device_findings.md": b"Existing findings\r\n",
                "devices/123.svg": b"Existing GPS/LTE device plot\r\n",
                "comparisons/gps.svg": b"Existing GPS comparison\r\n",
                "firmware_comparison.md": b"Existing saved firmware review\r\n",
                "review.md": b"Existing unrelated review\r\n",
            }
            for relative, content in originals.items():
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            script = Path(__file__).resolve().parents[1] / "analyse.py"
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["MPLBACKEND"] = "Agg"
            environment["MPLCONFIGDIR"] = str(root / "matplotlib")
            result = subprocess.run(
                [sys.executable, "-B", str(script), "--data", str(data), "--output", str(output),
                 "--device", "123", "--period", "all", "--plot-set", "adc-modem"],
                cwd=script.parent, env=environment, capture_output=True, text=True,
                timeout=25, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            expected_new = {"battery_adc_modem/123.svg", "battery_adc_modem/index.md",
                            "battery_adc_modem/run.json"}
            self.assertEqual(set(self.snapshot(output)), set(originals) | expected_new)
            for relative, content in originals.items():
                with self.subTest(preserved_output=relative):
                    self.assertEqual((output / relative).read_bytes(), content)
            self.assertEqual(self.snapshot(data), original_inputs)
            self.assertFalse(list(output.glob(".analysis-stage-*")))

            child = output / "battery_adc_modem"
            manifest = json.loads((child / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["format_version"], 2)
            self.assertEqual(manifest["analysis"], "adc_modem_agreement")
            self.assertEqual(manifest["settings"]["devices"], ["123"])
            self.assertEqual(manifest["settings"]["device_clock_offset_seconds"], 18)
            self.assertEqual(manifest["plots"], ["battery_adc_modem/123.svg"])
            self.assertEqual(manifest["input_sha256"], self.expected_hashes(data))
            self.assertIn("UTC aligned", manifest["definitions"]["time"])
            summary, = manifest["metrics"]
            for field, expected in {
                "device_id": "123", "pairs": 3, "timed_pairs": 2, "untimed_pairs": 1,
                "temperature_pairs": 2, "temperature_missing": 1,
                "temperature_age_known": 1, "temperature_age_missing": 1,
                "receipt_pairs": 2, "failed_attempt_pairs": 1,
                "above_50mv_count": 2, "above_100mv_count": 0,
            }.items():
                with self.subTest(metric=field):
                    self.assertEqual(summary[field], expected)
            self.assertAlmostEqual(summary["mean_diff_mv"], -50 / 3)
            self.assertEqual(summary["temp_age_median_s"], 120)
            index = (child / "index.md").read_text(encoding="utf-8")
            self.assertIn("](123.svg)", index)
            table_row = next(line for line in index.splitlines() if "](123.svg)" in line)
            self.assertIn("| 3 | 2 | 2 |", table_row)
            self.assertNotIn("n/a", table_row)
            self.assertIn("does not imply simultaneous", index)

            svg = ET.parse(child / "123.svg")
            namespace = "{http://www.w3.org/2000/svg}"
            title = svg.find(namespace + "title")
            description = svg.find(namespace + "desc")
            self.assertIsNotNone(title)
            self.assertIsNotNone(description)
            self.assertEqual(svg.getroot().attrib.get("role"), "img")
            accessible = "\n".join(["".join(title.itertext()), "".join(description.itertext())])
            self.assertTrue(svg.findall(".//" + namespace + "path"))
            for label in [
                "1. Paired exported sensor values over time",
                "2. ADC minus modem difference over time",
                "3. Difference versus reported BMA temperature",
                "4. Sensor agreement", "1:1 agreement",
                "Temperature age unknown (n=1)", "Pairs without valid temperature excluded from this panel: 1",
            ]:
                with self.subTest(svg_label=label):
                    self.assertIn(label, accessible)
            self.assertIn("Valid pairs: 3; dated: 2; with valid temperature: 2", accessible)
            self.assertIn("No 7-day window contains 3 dated pairs", accessible)
            self.assertIn("UTC", accessible)
            self.assertNotIn("unshifted (~18 s basis difference)", accessible)
            self.assertNotIn("clock bases unshifted", accessible)

    def test_default_all_stages_both_plot_groups_and_publishes_grouped_provenance(self):
        with tempfile.TemporaryDirectory(prefix="mini4g-battery-all-cli-") as temporary:
            root = Path(temporary)
            data = self.make_data(root)
            output = root / "Outputs"
            original_inputs = self.snapshot(data)
            main_paths = ["devices/123.svg", "comparisons/gps.svg", "comparisons/lte.svg",
                          "comparisons/battery.svg", "comparisons/gps_lte.svg",
                          "comparisons/fleet_status.svg", "comparisons/cadence.svg"]
            battery_paths = ["battery_adc_modem/123.svg"]
            seen_stages = []

            def sentinels(devices, stage, relative_paths):
                self.assertEqual([device.device_id for device in devices], ["123"])
                stage = Path(stage).resolve()
                self.assertEqual(stage.parent, output.resolve())
                self.assertNotEqual(stage, output.resolve())
                self.assertTrue(stage.name.startswith(".analysis-stage-"))
                self.assertTrue(stage.is_dir())
                seen_stages.append(stage)
                paths = [stage / relative for relative in relative_paths]
                for path in paths:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"<svg>synthetic writer sentinel</svg>\r\n")
                return paths

            def write_main(devices, matches, metrics, stage, **kwargs):
                return sentinels(devices, stage, main_paths)

            def write_battery(devices, stage):
                return sentinels(devices, stage, battery_paths)

            with patch.dict(os.environ, {"MPLCONFIGDIR": str(root / "matplotlib"), "MPLBACKEND": "Agg"}):
                analyse = importlib.import_module("analyse")
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(analyse, "write_all_plots", side_effect=write_main) as main_writer, \
                     patch.object(analyse, "write_adc_modem_plots", side_effect=write_battery) as battery_writer, \
                     contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    status = analyse.main(["--data", str(data), "--output", str(output),
                                           "--device", "123", "--period", "all"])
            self.assertEqual(status, 0, stdout.getvalue() + stderr.getvalue())
            main_writer.assert_called_once()
            battery_writer.assert_called_once()
            self.assertEqual(len(set(seen_stages)), 1)
            self.assertTrue(all(not path.exists() for path in seen_stages))
            manifest = json.loads((output / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["format_version"], 3)
            self.assertEqual(manifest["analysis"], "cleaned_mini4g_service_review")
            self.assertEqual(manifest["settings"]["plot_set"], "all")
            self.assertEqual(manifest["settings"]["device_clock_offset_seconds"], 18)
            self.assertEqual(set(manifest["plots"]), set(main_paths + battery_paths))
            self.assertTrue(all((output / relative).is_file() for relative in manifest["plots"]))
            self.assertEqual(manifest["input_sha256"], self.expected_hashes(data))
            self.assertEqual(manifest["provenance"]["source_count"], 3)
            self.assertTrue(manifest["provenance"]["raw_files_unchanged"])
            self.assertEqual(manifest["provenance"]["input_layout"], "Data/Tag<ID>/<ID>_*")
            grouped, = manifest["metrics"]
            self.assertEqual(grouped["device_id"], "123")
            for group in ["coverage", "gps", "lte", "battery", "data_quality", "restart_evidence"]:
                self.assertIn(group, grouped)
            self.assertNotIn("gps_observations", grouped)
            self.assertEqual(manifest["battery_agreement"][0]["pairs"], 3)
            child = json.loads((output / "battery_adc_modem/run.json").read_text(encoding="utf-8"))
            self.assertEqual(child["plots"], battery_paths)
            quality = json.loads((output / "data_quality.json").read_text(encoding="utf-8"))
            self.assertEqual(quality["devices"][0]["device_id"], "123")
            self.assertIn("gps", quality["devices"][0])
            self.assertIn("stats", quality["devices"][0])
            self.assertEqual(quality["devices"][0]["clock"]["device_offset_seconds"], 18)
            diagnostics = json.loads((output / "diagnostics.json").read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["devices"][0]["device_id"], "123")
            for relative in ["overview.md", "data_quality.md", "device_findings.md"]:
                self.assertTrue((output / relative).is_file())
            overview = (output / "overview.md").read_text(encoding="utf-8")
            self.assertIn("(battery_adc_modem/index.md)", overview)
            battery_index = (output / "battery_adc_modem/index.md").read_text(encoding="utf-8")
            self.assertIn("](123.svg)", battery_index)
            self.assertEqual(self.snapshot(data), original_inputs)


if __name__ == "__main__":
    unittest.main()
