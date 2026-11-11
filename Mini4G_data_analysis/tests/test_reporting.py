"""Pure-report contracts using synthetic prepared summaries only."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import re
import unittest

import pandas as pd

from mini4g_analysis.reporting import (
    battery_index_markdown, clock_axis_label, clock_description, data_quality_markdown,
    device_findings_markdown, overview_markdown,
)


def tag(value, *, offset=18):
    return SimpleNamespace(device_id=str(value), quality={"clock": {"device_offset_seconds": offset}},
                           gps=pd.DataFrame(), satellites=pd.DataFrame(), uploads=pd.DataFrame(),
                           failures=pd.DataFrame(), registrations=pd.DataFrame(), events=pd.DataFrame(),
                           gaps=pd.DataFrame(), outages=pd.DataFrame(), monthly=pd.DataFrame(), issues=[])


CONFIG = {"service_start": "2026-06-24T00:00:00Z", "effective_start": "2026-06-24T00:00:00Z",
          "effective_end": None, "export_reference": "2026-11-10T08:39:12Z",
          "period_selection": {"reason": "study service boundary assumption"},
          "gps_window_seconds": 60, "gap_seconds": 3020, "receipt_window_seconds": 120,
          "future_stats_lead_seconds": 0}


class ReportingTests(unittest.TestCase):
    def test_clock_policy_distinguishes_corrected_raw_and_missing(self):
        self.assertIn("18 s corrected", clock_description([tag(3)]))
        self.assertIn("UTC aligned", clock_axis_label([tag(3)]))
        self.assertIn("uncorrected", clock_description([tag(3, offset=0)]))
        unknown = tag(3); unknown.quality = {}
        self.assertIn("not provided", clock_description([unknown]))
        self.assertNotIn("UTC aligned", clock_axis_label([unknown]))

    def test_missing_values_are_readable_and_numeric_order_is_shared(self):
        devices = [tag(20), tag(3)]
        summaries = [{"device_id": "20"}, {"device_id": "3", "last_adc_v": float("nan")}]
        reports = [overview_markdown(devices, summaries, CONFIG, [], pd.DataFrame()),
                   data_quality_markdown(devices, CONFIG),
                   device_findings_markdown(devices, summaries, pd.DataFrame()),
                   battery_index_markdown(devices, summaries)]
        for report in reports:
            self.assertLess(report.index("Tag 3"), report.index("Tag 20"))
            self.assertIsNone(re.search(r"\b(?:nan|NaT|None|inf)\b", report))
            self.assertNotIn("n/a s", report)
        self.assertIn("open end", reports[0])

    def test_snapshot_voltage_date_is_distinct_from_last_receipt(self):
        summary = {"device_id": "3", "last_receipt": "2026-11-10T08:39:12Z",
                   "last_gps": "2026-11-09T22:55:00Z", "receipt_silence_days": 0,
                   "last_adc_v": 3.633, "last_modem_v": 3.793,
                   "last_voltage_time": "2026-11-06T21:24:00Z"}
        report = overview_markdown([tag(3)], [summary], CONFIG, [], pd.DataFrame())
        self.assertIn("2026-11-10 08:39", report)
        self.assertIn("2026-11-06 21:24", report)
        self.assertIn("3.633 / 3.793", report)
        self.assertIn("3.5 d", report)
        self.assertIn("not the current date or a live service", report)

    def test_quality_exact_and_additional_semantic_removals_are_separate(self):
        device = tag(3)
        device.quality["stats"] = {"raw_uploads": 8, "raw_failures": 6, "exact_failed_duplicates": 2,
            "raw_registrations": 10, "exact_registration_duplicates": 2,
            "semantic_registration_removed": 1, "registration_conflicts": 0,
            "rejected_receipt_stats": 3}
        report = data_quality_markdown([device], CONFIG)
        self.assertIn("| Tag 3 | 8 | 0 | 6 | 4 | 0 | 10 | 7 | 0 |", report)
        self.assertIn("additional semantic merges", report)
        self.assertIn("Unknown-to-known enrichment is not classified", report)
        self.assertIn("clock TIME points may bound availability intervals at their recorded measurement time", report)

    def test_rendering_has_no_file_io_and_does_not_modify_prepared_data(self):
        device = tag(3)
        device.gaps = pd.DataFrame([{"start": "2026-08-01T00:00:00Z", "end": "2026-08-01T02:00:00Z",
            "duration_s": 7200.0, "absolute_long": True, "timeout_count": 1, "failure_count": 0,
            "receipt_count": 1, "voltage_before_v": 4.1, "voltage_after_v": 4.0, "gap_class": "timeout"}])
        before = device.gaps.copy(deep=True)
        quality_before = deepcopy(device.quality)
        summary = {"device_id": "3", "gap_timeout_eligible": 2, "gap_timeout_hits": 1,
                   "gap_timeout_expected_hits": 0.2}
        with patch("builtins.open", side_effect=AssertionError("Report renderer performed file I/O")):
            overview = overview_markdown([device], [summary], CONFIG, [], pd.DataFrame())
            findings = device_findings_markdown([device], [summary], pd.DataFrame())
            data_quality_markdown([device], CONFIG)
            battery_index_markdown([device], {"3": {"pairs": 0}})
        pd.testing.assert_frame_equal(before, device.gaps)
        self.assertEqual(quality_before, device.quality)
        self.assertIn("2026-08-01 02:00", findings)
        self.assertIn("monthly-uniform expectation is 0.2", overview)
        self.assertIn("not a firmware or network verdict", overview)

    def test_unparsed_dat_pages_expose_counts_and_physical_lines(self):
        devices = [tag(2622153757), tag(311057696)]
        for device, line in zip(devices, (53, 449)):
            device.quality["gps"] = {"page_identity_available": True, "unparsed_dat_page_count": 1,
                                      "unparsed_dat_pages": [{"line": line, "data_type": 144,
                                                               "declared_length": 392, "header_length": 3}]}
        report = data_quality_markdown(devices, CONFIG)
        self.assertIn("Physical DAT line(s)", report)
        self.assertIn("| Tag 2622153757 | 1 | 53 |", report)
        self.assertIn("| Tag 311057696 | 1 | 449 |", report)
        self.assertIn("does not classify the payload or infer a cause", report)
        self.assertNotIn("corrupt", report.lower())
        findings = device_findings_markdown(devices, [], pd.DataFrame())
        self.assertIn("physical DAT line(s) 53", findings)
        self.assertIn("physical DAT line(s) 449", findings)

    def test_positional_battery_summaries_keep_the_original_tag_identity(self):
        devices = [tag(20), tag(3)]
        summaries = [{"pairs": 20, "timed_pairs": 19, "mean_diff_mv": 20},
                     {"pairs": 3, "timed_pairs": 2, "mean_diff_mv": 3}]
        report = battery_index_markdown(devices, summaries)
        self.assertIn("| [Tag 3](3.svg) | 3 | 2 |", report)
        self.assertIn("| [Tag 20](20.svg) | 20 | 19 |", report)
        self.assertLess(report.index("Tag 3"), report.index("Tag 20"))
        with self.assertRaisesRegex(ValueError, "positional summary"):
            battery_index_markdown(devices, [{"pairs": 3}])

    def test_parser_affected_interval_is_separate_from_supported_gap(self):
        device = tag(3)
        device.gaps = pd.DataFrame([
            {"start": "2026-08-01T00:00:00Z", "end": "2026-08-06T00:00:00Z",
             "duration_s": 432000, "absolute_long": True, "unparsed_page_overlap": True,
             "unparsed_source_lines": [53], "gap_class": "unparsed_source"},
            {"start": "2026-08-07T00:00:00Z", "end": "2026-08-07T01:00:00Z",
             "duration_s": 3600, "absolute_long": True, "unparsed_page_overlap": False,
             "gap_class": "timeout", "timeout_count": 1},
        ])
        report = device_findings_markdown([device], [], pd.DataFrame())
        self.assertIn("Largest observed interval in parsed GPS availability", report)
        self.assertIn("Parsed source page omitted", report)
        self.assertIn("physical DAT line(s) 53", report)
        self.assertIn("Largest source-covered absolute-long GPS interval candidate: 2026-08-07", report)
        self.assertIn("excluded from device-gap counts and the timeout baseline", report)

    def test_findings_show_gps_effort_coverage_and_qualified_mechanism_link(self):
        summary = {"device_id": "3", "gps_observations": 10, "gps_5plus_count": 8,
                   "gps_satellite_count_known": 10, "gps_success_ttf_median_s": 4.5,
                   "on_time_per_5plus_s": 6.25, "on_time_known_attempts": 9,
                   "on_time_coverage_percent": 90, "on_time_qualifying_denominator": 8,
                   "gap_timeout_eligible": 2, "gap_timeout_hits": 1,
                   "gap_timeout_expected_hits": 0.2}
        report = device_findings_markdown([tag(3)], [summary], pd.DataFrame())
        self.assertIn("5+ satellite proxy 8/10 (80.0%)", report)
        self.assertIn("qualifying-observation TTF median 4.50 s", report)
        self.assertIn("on-time per qualifying observation: 6.25 s", report)
        self.assertIn("known TTF/satellite attempts 9/10 (90.0% availability)", report)
        self.assertIn("qualifying known denominator 8", report)
        self.assertIn("(firmware_comparison.md)", report)
        self.assertIn("not proof for each gap or for current BinaryHost firmware", report)


if __name__ == "__main__":
    unittest.main()
