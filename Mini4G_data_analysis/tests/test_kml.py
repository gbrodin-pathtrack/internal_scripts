"""In-memory POS, temporal matching and Google Earth KML checks."""

import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from mini4g_analysis.kml import (
    GPS_ICON_URL, ICON_URL, KML_NS, build_kml, load_positions, match_registrations, registration_category,
)
from mini4g_analysis.spatial import estimate_registration_positions, great_circle_distance_m


NS = {"k": KML_NS}
NOW = pd.Timestamp("2026-07-01T12:00:00Z")


def pos_row(**changes):
    fields = dict(day="1", month="7", year="26", hour="12", minute="0", second="0",
                  sod="43200.125", num_sv="4", lat="51.5", lon="-0.1", height="10",
                  unknown1="0", unknown2="0", unknown3="0", status="uninterpreted")
    fields.update(changes)
    return ",".join(str(value) for value in fields.values())


def positions_from(lines, offset=18):
    text = "\n".join(["POS text header"]*5 + lines) + "\n"
    with patch.object(Path, "open", return_value=io.StringIO(text)):
        return load_positions(Path("in-memory.pos"), clock_offset_seconds=offset)


def position(seconds=0, **changes):
    row = dict(time=NOW+pd.Timedelta(seconds=seconds), recorded_time=NOW+pd.Timedelta(seconds=seconds+18),
               latitude=51.5, longitude=-0.1, source_row=6, source_rows=[6], num_sv=4, status="unknown")
    row.update(changes)
    return row


def registration(seconds=0, **changes):
    row = dict(time=NOW+pd.Timedelta(seconds=seconds), recorded_time=NOW+pd.Timedelta(seconds=seconds+18),
               source_row=2, tier="HOT", outcome="success", duration_s=0.5,
               rsrp_dbm=-110, tx_dbm=20, voltage_v=4.1)
    row.update(changes)
    return row


def kml_document(positions, registrations, **options):
    matches = match_registrations(pd.DataFrame(registrations), positions, tolerance_seconds=options.get("tolerance_seconds"))
    data = build_kml("123", positions, matches, **options)
    return data, ET.fromstring(data).find("k:Document", NS), matches


class PositionLoadingTests(unittest.TestCase):
    def test_fractional_sod_and_clock_offset_preserve_nanoseconds(self):
        positions, quality = positions_from([pos_row(sod="43200.123456789")])
        row = positions.iloc[0]
        self.assertEqual(row["recorded_time"], NOW+pd.Timedelta(nanoseconds=123456789))
        self.assertEqual(row["time"], NOW-pd.Timedelta(seconds=18)+pd.Timedelta(nanoseconds=123456789))
        self.assertEqual(row["source_row"], 6)
        self.assertEqual(quality["positions"], 1)
        self.assertEqual(positions.attrs["clock_offset_seconds"], 18)
        json.dumps(quality, allow_nan=False)

    def test_hms_one_second_difference_and_four_satellite_position_are_retained(self):
        positions, quality = positions_from([pos_row(second="1", sod="43200.125", num_sv="4", status="-1", height="nan")])
        self.assertEqual(len(positions), 1)
        self.assertEqual(quality["hms_sod_display_difference_rows"], 1)
        self.assertEqual(positions.iloc[0]["time"], NOW-pd.Timedelta(seconds=18)+pd.Timedelta(milliseconds=125))
        self.assertEqual(positions.iloc[0]["num_sv"], 4)
        self.assertEqual(positions.iloc[0]["status"], "-1")

    def test_invalid_coordinates_and_zero_zero_sentinel_are_excluded(self):
        positions, quality = positions_from([
            pos_row(lat="91"), pos_row(lon="181"), pos_row(lat="0", lon="0"),
            pos_row(lat="nan"), pos_row(lon="inf"),
            pos_row(sod="43201", lat="0", lon="10"), pos_row(sod="43202", lat="20", lon="0"),
        ])
        self.assertEqual(len(positions), 2)
        self.assertEqual(quality["invalid_coordinate_rows"], 5)
        self.assertEqual(quality["invalid_rows"], 5)

    def test_malformed_rows_are_audited_and_short_header_fails(self):
        positions, quality = positions_from([
            "1,2,3", pos_row(day="31", month="2"), pos_row(sod="86400"), pos_row(year="2026"),
        ])
        self.assertTrue(positions.empty)
        self.assertEqual(quality["invalid_rows"], 4)
        self.assertEqual(quality["audit"][0]["source_row"], 6)
        with patch.object(Path, "open", return_value=io.StringIO("one\ntwo\n")), self.assertRaises(ValueError):
            load_positions("short.pos")

    def test_consistent_duplicates_keep_provenance_conflicting_coordinates_are_excluded(self):
        positions, quality = positions_from([
            pos_row(), pos_row(status="another status"),
            pos_row(sod="43300", lat="52"), pos_row(sod="43300", lat="52.01"),
        ])
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions.iloc[0]["source_rows"], [6, 7])
        self.assertEqual(quality["duplicate_timestamp_rows"], 1)
        self.assertEqual(quality["conflicting_timestamp_groups"], 1)
        self.assertEqual(quality["conflicting_timestamp_rows"], 2)


class PositionMatchingTests(unittest.TestCase):
    def test_inclusive_window_tie_chooses_earlier_position(self):
        positions = pd.DataFrame([position(0), position(120, source_row=7, source_rows=[7])])
        matches = match_registrations(pd.DataFrame([registration(60)]), positions, tolerance_seconds=60)
        row = matches.iloc[0]
        self.assertEqual(row["match_status"], "within_window")
        self.assertEqual(row["position_time"], NOW)
        self.assertEqual(row["position_offset_s"], -60)
        self.assertEqual(row["position_source_rows"], [6])

    def test_outside_window_has_offset_but_no_mapped_coordinates(self):
        positions = pd.DataFrame([position(0)])
        matches = match_registrations(pd.DataFrame([registration(60.000000001), registration(time=pd.NaT)]), positions, tolerance_seconds=60)
        self.assertEqual(matches.iloc[0]["match_status"], "outside_window")
        self.assertAlmostEqual(matches.iloc[0]["position_offset_s"], -60.000000001, places=9)
        self.assertTrue(pd.isna(matches.iloc[0]["latitude"]))
        self.assertEqual(matches.iloc[1]["match_status"], "untimed")
        self.assertEqual(len(matches), 2)

    def test_default_no_cutoff_maps_distant_events_before_and_after_track(self):
        positions = pd.DataFrame([position(0), position(120, source_row=7, source_rows=[7])])
        matches = match_registrations(pd.DataFrame([
            registration(-12*86400), registration(120+12*86400), registration(60), registration(time=pd.NaT),
        ]), positions)
        self.assertEqual(matches["match_status"].tolist(), ["nearest", "nearest", "nearest", "untimed"])
        self.assertEqual(matches["position_offset_s"].iloc[:3].tolist(), [12*86400, -12*86400, -60])
        self.assertEqual(matches["position_source_row"].iloc[:3].tolist(), [6, 7, 6])
        self.assertTrue(matches["latitude"].iloc[:3].notna().all())

    def test_empty_positions_preserve_registrations_and_inputs(self):
        registrations = pd.DataFrame([registration(), registration(1, outcome="timeout")])
        before = registrations.copy(deep=True)
        matches = match_registrations(registrations, pd.DataFrame())
        self.assertEqual(len(matches), 2)
        self.assertTrue(matches["match_status"].eq("no_positions").all())
        pd.testing.assert_frame_equal(registrations, before)
        with self.assertRaises(ValueError):
            match_registrations(registrations, pd.DataFrame(), tolerance_seconds=-1)


class KmlExportTests(unittest.TestCase):
    def test_coordinates_styles_hidden_labels_and_no_time_filter_primitives(self):
        positions = pd.DataFrame([position()])
        data, document, matches = kml_document(positions, [registration(), registration(outcome="timeout", source_row=3),
                                                         registration(outcome="unfamiliar", source_row=4)])
        self.assertEqual(matches["match_status"].tolist(), ["nearest"]*3)
        colors = {style.attrib["id"]: style.findtext("k:IconStyle/k:color", namespaces=NS)
                  for style in document.findall("k:Style", NS)}
        self.assertEqual(colors["registration_success"], "ff00aa00")
        self.assertEqual(colors["registration_failure"], "ff0000ff")
        self.assertEqual(colors["registration_other"], "ff888888")
        self.assertEqual(colors["observed_gps"], "ffff0000")
        for style in document.findall("k:Style", NS):
            self.assertEqual(style.findtext("k:LabelStyle/k:scale", namespaces=NS), "0")
            if style.find("k:IconStyle", NS) is not None:
                self.assertEqual(style.findtext("k:IconStyle/k:Icon/k:href", namespaces=NS),
                                 GPS_ICON_URL if style.attrib["id"] == "observed_gps" else ICON_URL)
        success = next(folder for folder in document.findall("k:Folder", NS)
                       if folder.findtext("k:name", namespaces=NS).startswith("Successful registrations"))
        marker = success.find("k:Placemark", NS)
        self.assertEqual(marker.findtext("k:Point/k:coordinates", namespaces=NS), "-0.1000000000,51.5000000000,0")
        self.assertEqual(marker.findtext("k:Point/k:altitudeMode", namespaces=NS), "clampToGround")
        self.assertIsNone(document.find(".//k:TimeStamp", NS))
        self.assertIsNone(document.find(".//k:TimeSpan", NS))
        self.assertGreater(data.count(b"\r\n"), 0)
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))

    def test_track_splits_at_long_holes_without_new_coordinates(self):
        positions = pd.DataFrame([position(seconds, source_row=index+6, latitude=51.5+index/100)
                                  for index, seconds in enumerate((0, 60, 7200, 7260))])
        _, document, _ = kml_document(positions, [], track_gap_seconds=3600)
        lines = document.findall(".//k:LineString", NS)
        self.assertEqual(len(lines), 2)
        self.assertEqual([len(line.findtext("k:coordinates", namespaces=NS).split()) for line in lines], [2, 2])
        self.assertTrue(all(line.findtext("k:altitudeMode", namespaces=NS) == "clampToGround" for line in lines))
        track_style = next(style for style in document.findall("k:Style", NS) if style.attrib["id"] == "position_track")
        self.assertEqual(track_style.findtext("k:LineStyle/k:color", namespaces=NS), "ff800080")

    def test_popup_escaping_provenance_and_feature_element_order(self):
        positions = pd.DataFrame([position()])
        matches = match_registrations(pd.DataFrame([registration(tier="<HOT>&", merged_source_rows=[2, 8])]), positions)
        data = build_kml("123<&", positions, matches)
        document = ET.fromstring(data).find("k:Document", NS)
        self.assertEqual(document.findtext("k:name", namespaces=NS), "Device 123<& registrations and GPS positions")
        folder = next(folder for folder in document.findall("k:Folder", NS)
                      if folder.findtext("k:name", namespaces=NS).startswith("Successful registrations"))
        placemark = folder.find("k:Placemark", NS)
        description = placemark.findtext("k:description", namespaces=NS)
        self.assertIn("&lt;HOT&gt;&amp;", description)
        self.assertNotIn("<HOT>", description)
        fields = {item.attrib["name"]: item.findtext("k:value", namespaces=NS)
                  for item in placemark.findall("k:ExtendedData/k:Data", NS)}
        self.assertEqual(fields["registration_source_rows"], "2, 8")
        self.assertEqual(fields["position_source_rows"], "6")
        self.assertTrue(fields["registration_utc"].endswith("Z"))
        self.assertFalse(fields["registration_recorded_clock"].endswith("Z"))
        child_names = [child.tag.rsplit("}", 1)[-1] for child in document]
        self.assertLess(child_names.index("description"), child_names.index("Style"))
        self.assertEqual([child.tag.rsplit("}", 1)[-1] for child in placemark],
                         ["name", "description", "styleUrl", "ExtendedData", "Point"])

    def test_unbounded_popup_explains_signed_distant_gap_and_direction(self):
        positions = pd.DataFrame([position(0)])
        data, document, _ = kml_document(positions, [registration(12*86400)])
        marker = document.find("k:Folder[k:name='Successful registrations (1 mapped / 1 records)']/k:Placemark", NS)
        fields = {item.attrib["name"]: item.findtext("k:value", namespaces=NS)
                  for item in marker.findall("k:ExtendedData/k:Data", NS)}
        self.assertEqual(fields["position_offset_seconds"], "-1036800")
        self.assertEqual(fields["absolute_time_gap"], "12 days")
        self.assertEqual(fields["position_time_direction"], "before registration")
        description = marker.findtext("k:description", namespaces=NS)
        self.assertIn("no time cutoff", description)
        self.assertNotIn("within 60 seconds", data.decode())
        for seconds, expected in ((30, "30 seconds"), (90, "1.5 minutes"), (7200, "2 hours")):
            _, small_document, _ = kml_document(positions, [registration(-seconds)])
            point = next(folder for folder in small_document.findall("k:Folder", NS)
                         if folder.findtext("k:name", namespaces=NS).startswith("Successful registrations")).find("k:Placemark", NS)
            values = {item.attrib["name"]: item.findtext("k:value", namespaces=NS)
                      for item in point.findall("k:ExtendedData/k:Data", NS)}
            self.assertEqual(values["absolute_time_gap"], expected)
            self.assertEqual(values["position_time_direction"], "after registration")

    def test_explicit_builder_window_does_not_map_unbounded_distant_match(self):
        positions = pd.DataFrame([position(0)])
        matches = match_registrations(pd.DataFrame([registration(1000)]), positions)
        document = ET.fromstring(build_kml("123", positions, matches, tolerance_seconds=60)).find("k:Document", NS)
        self.assertTrue(all(folder.find("k:Placemark", NS) is None for folder in document.findall("k:Folder", NS)[1:]))

    def test_unmatched_rows_are_not_mapped_and_unknown_outcomes_stay_neutral(self):
        positions = pd.DataFrame([position()])
        _, document, _ = kml_document(positions, [registration(1000, outcome="timeout"),
                                                registration(time=pd.NaT, outcome="success")], tolerance_seconds=60)
        outcome_folders = document.findall("k:Folder", NS)[1:]
        self.assertTrue(all(folder.find("k:Placemark", NS) is None for folder in outcome_folders))
        self.assertEqual(registration_category(" Success "), "success")
        self.assertEqual(registration_category("TIMEOUT"), "failure")
        self.assertEqual(registration_category("failed"), "failure")
        self.assertEqual(registration_category("shutdown"), "other")
        self.assertEqual(registration_category(None), "other")

    def test_actual_gps_points_are_blue_and_default_purple_track_crosses_time_gaps(self):
        positions = pd.DataFrame([position(0), position(7200, latitude=51.51, source_row=7, source_rows=[7])])
        _, document, _ = kml_document(positions, [])
        observed = next(folder for folder in document.findall(".//k:Folder", NS)
                        if folder.findtext("k:name", namespaces=NS).startswith("Actual GPS positions"))
        self.assertEqual(len(observed.findall("k:Placemark", NS)), 2)
        self.assertTrue(all(marker.findtext("k:styleUrl", namespaces=NS) == "#observed_gps"
                            for marker in observed.findall("k:Placemark", NS)))
        self.assertEqual(len(document.findall(".//k:LineString", NS)), 1)
        gps_style = document.find("k:Style[@id='observed_gps']", NS)
        self.assertEqual(gps_style.findtext("k:IconStyle/k:color", namespaces=NS), "ffff0000")
        self.assertEqual(gps_style.findtext("k:IconStyle/k:scale", namespaces=NS), "0.35")
        self.assertEqual(gps_style.findtext("k:IconStyle/k:Icon/k:href", namespaces=NS), GPS_ICON_URL)
        self.assertIn("Original POS rows", observed.findtext("k:Placemark/k:description", namespaces=NS))
        self.assertIsNone(document.find(".//k:TimeStamp", NS))

    def test_estimates_keep_outcome_colours_and_popup_anchor_provenance(self):
        positions = pd.DataFrame([position(0, latitude=0, longitude=-1),
                                  position(600, latitude=0, longitude=1, source_row=7, source_rows=[7])])
        registrations = pd.DataFrame([registration(0), registration(300, outcome="timeout", source_row=3),
                                      registration(-300, source_row=4), registration(900, outcome="timeout", source_row=5)])
        estimates = estimate_registration_positions(registrations, positions)
        before_positions, before_estimates = positions.copy(deep=True), estimates.copy(deep=True)
        document = ET.fromstring(build_kml("123", positions, estimates)).find("k:Document", NS)
        markers = {}
        for marker in document.findall(".//k:Placemark", NS):
            fields = {item.attrib["name"]: item.findtext("k:value", namespaces=NS)
                      for item in marker.findall("k:ExtendedData/k:Data", NS)}
            if "position_method" in fields:
                markers[fields["position_method"]] = (marker, fields)
        self.assertEqual(set(markers), {"exact", "interpolated", "projected_before", "projected_after"})
        self.assertEqual(markers["interpolated"][0].findtext("k:Point/k:coordinates", namespaces=NS),
                         "0.0000000000,0.0000000000,0")
        for method in ("exact", "projected_before"):
            self.assertEqual(markers[method][0].findtext("k:styleUrl", namespaces=NS), "#registration_success")
        for method in ("interpolated", "projected_after"):
            self.assertEqual(markers[method][0].findtext("k:styleUrl", namespaces=NS), "#registration_failure")
        marker, fields = markers["projected_after"]
        self.assertIn("Projected after track", marker.findtext("k:name", namespaces=NS))
        self.assertEqual(fields["anchor_start_utc"], NOW.isoformat().replace("+00:00", "Z"))
        self.assertEqual(fields["anchor_end_utc"], (NOW+pd.Timedelta(seconds=600)).isoformat().replace("+00:00", "Z"))
        self.assertEqual(fields["anchor_start_source_rows"], "6")
        self.assertEqual(fields["anchor_end_source_rows"], "7")
        self.assertEqual(fields["anchor_span_s"], "600")
        self.assertEqual(fields["time_fraction"], "1.5")
        self.assertEqual(fields["seconds_from_anchor_start"], "+900")
        self.assertEqual(fields["seconds_to_anchor_end"], "-300")
        self.assertEqual(fields["projection_horizon_s"], "300")
        self.assertEqual(fields["registration_location_measured"], "false")
        self.assertGreater(float(fields["segment_speed_m_s"]), 0)
        self.assertIn("not measured", marker.findtext("k:description", namespaces=NS))
        self.assertIn("Earlier anchor GPS UTC", marker.findtext("k:description", namespaces=NS))
        pd.testing.assert_frame_equal(positions, before_positions)
        pd.testing.assert_frame_equal(estimates, before_estimates)

    def test_long_track_uses_same_great_circle_without_fabricated_blue_points_or_projection_lines(self):
        positions = pd.DataFrame([position(0, latitude=0, longitude=-1),
                                  position(600, latitude=0, longitude=1, source_row=7, source_rows=[7])])
        estimates = estimate_registration_positions(pd.DataFrame([registration(-300), registration(900)]), positions)
        document = ET.fromstring(build_kml("123", positions, estimates)).find("k:Document", NS)
        lines = document.findall(".//k:LineString", NS)
        self.assertEqual(len(lines), 1)
        coordinates = [tuple(map(float, value.split(",")[:2]))
                       for value in lines[0].findtext("k:coordinates", namespaces=NS).split()]
        self.assertGreater(len(coordinates), len(positions))
        self.assertEqual(coordinates[0], (-1, 0))
        self.assertEqual(coordinates[-1], (1, 0))
        self.assertTrue(all(-1 <= longitude <= 1 for longitude, _ in coordinates))
        for first, last in zip(coordinates, coordinates[1:]):
            self.assertLessEqual(great_circle_distance_m(first[1], first[0], last[1], last[0]), 25000.1)
        observed = next(folder for folder in document.findall(".//k:Folder", NS)
                        if folder.findtext("k:name", namespaces=NS).startswith("Actual GPS positions"))
        self.assertEqual(len(observed.findall("k:Placemark", NS)), 2)
        track_style = document.find("k:Style[@id='position_track']", NS)
        self.assertEqual(track_style.findtext("k:LineStyle/k:color", namespaces=NS), "ff800080")

    def test_elapsed_seconds_keep_decimal_precision_and_estimate_popup_escapes_values(self):
        positions = pd.DataFrame([position(0), position(60, latitude=51.6, source_row=7)])
        estimates = estimate_registration_positions(pd.DataFrame([registration(30, tier="<HOT>&")]), positions)
        estimates.loc[0, "anchor_span_s"] = 1049104.34
        estimates.loc[0, "projection_horizon_s"] = 1049104.123456
        document = ET.fromstring(build_kml("123", positions, estimates)).find("k:Document", NS)
        marker = next(marker for marker in document.findall(".//k:Placemark", NS)
                      if marker.findtext("k:styleUrl", namespaces=NS) == "#registration_success")
        fields = {item.attrib["name"]: item.findtext("k:value", namespaces=NS)
                  for item in marker.findall("k:ExtendedData/k:Data", NS)}
        self.assertEqual(fields["anchor_span_s"], "1049104.34")
        self.assertEqual(fields["projection_horizon_s"], "1049104.123456")
        self.assertIn("&lt;HOT&gt;&amp;", marker.findtext("k:description", namespaces=NS))
        self.assertNotIn("<HOT>", marker.findtext("k:description", namespaces=NS))

    def test_antipodal_leg_keeps_blue_observations_but_does_not_choose_an_arbitrary_track_arc(self):
        positions = pd.DataFrame([position(0, latitude=10, longitude=0),
                                  position(600, latitude=-10, longitude=180, source_row=7, source_rows=[7])])
        estimates = estimate_registration_positions(pd.DataFrame([registration(300)]), positions)
        document = ET.fromstring(build_kml("123", positions, estimates)).find("k:Document", NS)
        self.assertEqual(estimates.iloc[0]["match_status"], "ambiguous_geometry")
        self.assertFalse(document.findall(".//k:LineString", NS))
        self.assertIn("Ambiguous antipodal legs left unjoined: 1", document.findtext("k:description", namespaces=NS))
        self.assertEqual(len(document.findall(".//k:Point", NS)), 2)


if __name__ == "__main__":
    unittest.main()
