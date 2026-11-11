"""Bounded integration checks for POS/registration-only KML publication."""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import export_kml


class KmlCliTests(unittest.TestCase):
    def make_data(self, root):
        data = root / "Data"
        tag = data / "Tag123"
        tag.mkdir(parents=True)
        position = tag / "123.pos"
        header = "\n".join(["********", "PathTrack Archival Tracking System Results File",
                             "Created 01.07.26 12:00", "DO NOT MODIFY THIS HEADER", "********"]) + "\n"
        position.write_text(header +
            "30,06,26,23,55,00,86100.000,5,43.000000,-69.500000,10,0,0,0,00\n"
            "01,07,26,10,00,00,36000.250,4,43.123456,-69.654321,12,0,0,0,00\n"
            "01,07,26,10,10,00,36600.000,5,43.234567,-69.765432,14,0,0,0,00\n", encoding="utf-8")
        registration = tag / "123_registrations.csv"
        fields = ["time", "tier", "outcome", "reg_time", "psm", "reg_count"]
        rows = [dict(time="2026-07-01 10:00:10",tier="HOT",outcome="success",reg_time="1 s",psm="yes",reg_count="1"),
                dict(time="2026-07-01 10:10:40",tier="HOT",outcome="timeout",reg_time="20 s",psm="no",reg_count="2"),
                dict(time="2026-07-01 11:00:00",tier="HOT",outcome="timeout",reg_time="20 s",psm="no",reg_count="3"),
                dict(time="boot+1s",tier="COLD",outcome="success",reg_time="2 s",psm="yes",reg_count="4"),
                dict(time="2026-06-30 23:55:00",tier="HOT",outcome="success",reg_time="1 s",psm="yes",reg_count="0")]
        with registration.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows([rows[0],rows[0],*rows[1:]])
        (tag / "123_ublox.dat").write_bytes(b"Unrelated malformed DAT must not be consumed")
        (tag / "123_ublox_GPS_Obs.csv").write_bytes(b"Unrelated malformed GPS CSV")
        return data, position, registration

    @staticmethod
    def snapshot(root):
        return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def test_july_default_estimates_timed_events_and_preserves_existing_outputs(self):
        with tempfile.TemporaryDirectory(prefix="mini4g-kml-cli-") as temporary:
            root = Path(temporary)
            data, position, registration = self.make_data(root)
            original = self.snapshot(data)
            output = root / "Outputs"
            output.mkdir()
            (output / "overview.md").write_bytes(b"Existing report\r\n")
            messages = io.StringIO()
            with contextlib.redirect_stdout(messages):
                status = export_kml.main(["--data",str(data),"--output",str(output)])
            self.assertEqual(status,0,messages.getvalue())
            self.assertEqual(self.snapshot(data),original)
            self.assertEqual((output / "overview.md").read_bytes(),b"Existing report\r\n")
            child = output / "registration_kml"
            self.assertEqual({p.name for p in child.iterdir()},{"123.kml","index.md","run.json"})
            self.assertFalse(list(output.glob(".kml-stage-*")))
            manifest = json.loads((child / "run.json").read_text())
            self.assertEqual(manifest["source_count"],2)
            self.assertTrue(manifest["raw_files_unchanged"])
            self.assertEqual(manifest["settings"]["pos_clock_offset_seconds"],18)
            self.assertEqual(manifest["input_sha256"],{
                p.relative_to(data).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [position,registration]})
            self.assertEqual(manifest["format_version"],2)
            self.assertEqual(manifest["settings"]["start_inclusive"],"2026-07-01T00:00:00+00:00")
            self.assertEqual(manifest["settings"]["position_match_policy"],"time_interpolation_and_endpoint_projection")
            summary, = manifest["devices"]
            self.assertEqual(summary["registrations"],4)
            self.assertEqual(summary["mapped"],3)
            self.assertEqual(summary["unmapped"],1)
            self.assertEqual(summary["outcomes"]["success"],{"mapped":1,"total":2})
            self.assertEqual(summary["outcomes"]["failure"],{"mapped":2,"total":2})
            self.assertEqual(summary["first_position_utc"],"2026-07-01T09:59:42.250000+00:00")
            events = manifest["events"][0]["registrations"]
            first = next(row for row in events if row["outcome"] == "success")
            self.assertEqual(first["time"],"2026-07-01T09:59:52+00:00")
            self.assertEqual(first["recorded_time"],"2026-07-01T10:00:10+00:00")
            self.assertEqual(first["position_offset_s"],-9.75)
            late = next(row for row in events if row["recorded_time"] == "2026-07-01T11:00:00+00:00")
            self.assertEqual(late["position_method"],"projected_after")
            self.assertEqual(late["position_offset_s"],-3000)
            self.assertNotEqual(late["latitude"],43.234567)
            self.assertEqual(late["projection_horizon_s"],3000)
            self.assertEqual(first["position_method"],"interpolated")
            self.assertAlmostEqual(first["time_fraction"],9.75/599.75)
            self.assertEqual(summary["position_method_counts"],{"interpolated":1,"projected_after":2,"untimed":1})
            self.assertEqual(summary["period_selection"]["positions_excluded"],1)
            self.assertEqual(summary["period_selection"]["dated_registrations_excluded"],1)
            self.assertTrue(all(row["time"] is None or row["time"] >= "2026-07-01" for row in events))
            xml = ET.parse(child / "123.kml")
            ns = {"k":"http://www.opengis.net/kml/2.2"}
            self.assertEqual(len(xml.findall(".//k:Point",ns)),5)
            self.assertTrue(xml.findall(".//k:LineString",ns))
            colors = [e.text for e in xml.findall(".//k:IconStyle/k:color",ns)]
            self.assertIn("ff00aa00",colors)
            self.assertIn("ff0000ff",colors)
            self.assertIn("Projected",(child / "index.md").read_text())
            self.assertIn("Purple",(child / "index.md").read_text())

    def test_explicit_end_is_exclusive_and_june_remains_excluded(self):
        with tempfile.TemporaryDirectory(prefix="mini4g-kml-period-") as temporary:
            root = Path(temporary)
            data, _, _ = self.make_data(root)
            output = root / "Outputs"
            with contextlib.redirect_stdout(io.StringIO()):
                status = export_kml.main(["--data",str(data),"--output",str(output),
                                          "--end","2026-07-01T10:10:00Z"])
            self.assertEqual(status,0)
            child = output / "registration_kml"
            manifest = json.loads((child / "run.json").read_text())
            row, = manifest["devices"]
            self.assertEqual(row["mapped"],1)
            self.assertEqual(row["unmapped"],1)
            self.assertEqual(row["dated_registrations"],1)
            self.assertEqual(row["position_method_counts"],{"interpolated":1,"untimed":1})
            self.assertEqual(row["period_selection"]["dated_registrations_excluded"],3)
            self.assertEqual(manifest["settings"]["end_exclusive"],"2026-07-01T10:10:00+00:00")

    def test_utc_pos_option_changes_only_pos_clock_and_labels_both_offsets(self):
        with tempfile.TemporaryDirectory(prefix="mini4g-kml-utc-") as temporary:
            root = Path(temporary)
            data, _, _ = self.make_data(root)
            output = root / "Outputs"
            with contextlib.redirect_stdout(io.StringIO()):
                status = export_kml.main(["--data",str(data),"--output",str(output),"--pos-time-basis","utc"])
            self.assertEqual(status,0)
            child = output / "registration_kml"
            manifest = json.loads((child / "run.json").read_text())
            self.assertEqual(manifest["settings"]["pos_clock_offset_seconds"],0)
            first = next(row for row in manifest["events"][0]["registrations"] if row["outcome"] == "success")
            self.assertEqual(first["time"],"2026-07-01T09:59:52+00:00")
            self.assertEqual(first["position_time"],"2026-07-01T10:00:00.250000+00:00")
            self.assertEqual(first["position_offset_s"],8.25)
            ns = {"k":"http://www.opengis.net/kml/2.2"}
            document = ET.parse(child / "123.kml").find("k:Document",ns)
            description = document.find("k:description",ns).text
            self.assertIn("POS clock seconds subtracted for UTC</th><td>0</td>",description)
            self.assertIn("Registration device clock seconds subtracted for UTC</th><td>18</td>",description)

    def test_source_change_during_export_preserves_previous_kml_and_cleans_stage(self):
        with tempfile.TemporaryDirectory(prefix="mini4g-kml-changing-") as temporary:
            root = Path(temporary)
            data, position, _ = self.make_data(root)
            output = root / "Outputs"
            child = output / "registration_kml"
            child.mkdir(parents=True)
            original = b"Previous complete KML\r\n"
            (child / "123.kml").write_bytes(original)
            build = export_kml.build_kml
            def external_change(*args,**kwargs):
                result = build(*args,**kwargs)
                position.write_bytes(position.read_bytes()+b"\n")
                return result
            messages = io.StringIO()
            with patch.object(export_kml,"build_kml",side_effect=external_change), contextlib.redirect_stderr(messages):
                status = export_kml.main(["--data",str(data),"--output",str(output)])
            self.assertEqual(status,2)
            self.assertIn("changed during export",messages.getvalue())
            self.assertEqual((child / "123.kml").read_bytes(),original)
            self.assertEqual({p.name for p in child.iterdir()},{"123.kml"})
            self.assertFalse(list(output.glob(".kml-stage-*")))


if __name__ == "__main__":
    unittest.main()
