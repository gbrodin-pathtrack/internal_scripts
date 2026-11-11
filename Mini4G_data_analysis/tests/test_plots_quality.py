"""Rendering contracts that do not read or modify any study dataset."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mini4g_analysis import plots
from mini4g_analysis.loaders import DeviceData
from mini4g_analysis.matching import MATCH_COLUMNS


class PlotQualityTests(unittest.TestCase):
    def test_device_order_is_numeric_and_palette_is_consistent(self):
        devices = [SimpleNamespace(device_id=value) for value in ("100", "20", "3")]
        self.assertEqual([device.device_id for device in plots._ordered(devices)], ["3", "20", "100"])
        self.assertEqual(plots._colors(devices), plots._colors(list(reversed(devices))))
        self.assertEqual(len(set(plots._colors(devices).values())), len(devices))

    def test_svg_keeps_accessible_labels_and_embeds_dense_data(self):
        with TemporaryDirectory() as directory, matplotlib.rc_context(plots._PLOT_RC):
            fig, ax = plt.subplots()
            fig.suptitle("Synthetic recorded evidence")
            ax.set_title("Dense measurements", loc="left")
            ax.set_xlabel("Recorded time")
            ax.set_ylabel("Reported voltage (V)")
            ax.plot(np.linspace(0, 10, 1500), np.sin(np.linspace(0, 10, 1500)))
            path = plots._save(fig, Path(directory) / "synthetic.svg")
            root = ET.parse(path).getroot()
            namespace = {"svg": "http://www.w3.org/2000/svg"}
            self.assertEqual(root.get("role"), "img")
            self.assertIn("Synthetic recorded evidence", root.find("svg:title", namespace).text)
            description = root.find("svg:desc", namespace).text
            self.assertIn("Dense measurements", description)
            self.assertIn("Reported voltage (V)", description)
            self.assertTrue(root.findall(".//svg:image", namespace))
            self.assertFalse(list(Path(directory).glob("*.png")))
            self.assertNotIn("dc:date", path.read_text(encoding="utf-8"))

    def test_empty_device_still_has_all_named_figures(self):
        device = DeviceData("3")
        matches = pd.DataFrame(columns=MATCH_COLUMNS)
        empty_intervals = device.gps.assign(interval_s=pd.Series(dtype=float))
        # Exercise plotting independently of the diagnostics/calculation module.
        with TemporaryDirectory() as directory, patch.object(plots, "_intervals", return_value=empty_intervals):
            paths = plots.write_all_plots([device], {"3": matches}, [{"device_id": "3"}], Path(directory))
            adc_paths = plots.write_adc_modem_plots([device], Path(directory))
            self.assertEqual(len(paths), 7)
            self.assertEqual(len(adc_paths), 1)
            self.assertEqual({path.name for path in paths},
                             {"3.svg", "gps.svg", "lte.svg", "battery.svg", "gps_lte.svg",
                              "fleet_status.svg", "cadence.svg"})
            self.assertTrue(all(path.is_file() for path in paths + adc_paths))
            self.assertFalse(list(Path(directory).rglob("*.png")))

    def test_clock_record_still_contributes_to_availability_extent(self):
        device = DeviceData("3")
        device.gps = pd.DataFrame({"time": pd.to_datetime(["2026-08-01", "2026-08-02"], utc=True),
                                   "clock_record": [False, True], "clock_anomaly": [False, False]})
        self.assertEqual(max(plots._all_times([device])), pd.Timestamp("2026-08-02", tz="UTC"))

    def test_parser_hatching_does_not_spread_to_missing_flag_values(self):
        device = DeviceData("3")
        device.gaps = pd.DataFrame([
            {"start": "2026-08-01", "end": "2026-08-02", "cadence_gap": True,
             "gap_class": "unparsed_source", "unparsed_page_overlap": True},
            {"start": "2026-08-03", "end": "2026-08-04", "cadence_gap": True,
             "gap_class": "timeout"},
        ])
        fig, ax = plt.subplots()
        plots._shade_context([ax], device, None)
        self.assertEqual([patch.get_hatch() for patch in ax.patches], ["////", None])
        plt.close(fig)

    def test_low_rate_count_labels_anchor_above_the_bar(self):
        fig, ax = plt.subplots()
        for rate in (0, 0.1, 1, 20):
            text = plots._rate_label(ax, 0, rate, "100/10000")
            self.assertEqual(text.get_verticalalignment(), "bottom")
            self.assertGreater(text.get_position()[1], rate)
            self.assertGreaterEqual(text.get_position()[1], 2)
        high = plots._rate_label(ax, 1, 95, "9500/10000")
        self.assertEqual(high.get_verticalalignment(), "top")
        self.assertLessEqual(high.get_position()[1], 95)
        plt.close(fig)

    def test_cadence_cells_do_not_expose_clock_precision_noise(self):
        self.assertEqual(plots._cadence_cell(9.99997, 1250), "10 min\nn=1,250")
        self.assertEqual(plots._cadence_cell(49.9996, 100), "50 min\nn=100")
        self.assertEqual(plots._cadence_cell(22.34, 5), "22.3 min\nn=5")
        self.assertEqual(plots._cadence_cell(float("nan"), 0), "n/a")


if __name__ == "__main__":
    unittest.main()
