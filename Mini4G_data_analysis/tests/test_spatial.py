"""Analytical spherical geometry and UTC-time position estimation checks."""

import math
import unittest

import numpy as np
import pandas as pd

from mini4g_analysis.spatial import (
    EARTH_RADIUS_M, MAPPED_METHODS, estimate_registration_positions,
    great_circle_distance_m, great_circle_position,
)


NOW = pd.Timestamp("2026-07-01T12:00:00Z")


def position(seconds, latitude=0, longitude=10, source_row=6):
    return dict(time=NOW+pd.Timedelta(seconds=seconds),
                recorded_time=NOW+pd.Timedelta(seconds=seconds+18),
                latitude=latitude, longitude=longitude,
                source_row=source_row, source_rows=[source_row])


def registration(seconds=0, **changes):
    row = dict(time=NOW+pd.Timedelta(seconds=seconds), recorded_time=NOW+pd.Timedelta(seconds=seconds+18),
               source_row=2, tier="HOT", outcome="success")
    row.update(changes)
    return row


class GreatCircleTests(unittest.TestCase):
    def test_equatorial_quarter_and_off_center_fraction(self):
        latitude, longitude = great_circle_position(0, 0, 0, 20, 0.25)
        self.assertAlmostEqual(latitude, 0, places=12)
        self.assertAlmostEqual(longitude, 5, places=10)
        self.assertAlmostEqual(great_circle_position(0, 10, 0, 30, 0.1)[1], 12, places=10)
        self.assertAlmostEqual(great_circle_distance_m(0, 0, 0, 90), math.pi*EARTH_RADIUS_M/2, places=6)

    def test_dateline_takes_shortest_arc_and_continues_direction(self):
        middle = great_circle_position(0, 179, 0, -179, 0.5)
        self.assertAlmostEqual(abs(middle[1]), 180, places=10)
        self.assertAlmostEqual(great_circle_position(0, 179, 0, -179, -1)[1], 177, places=10)
        self.assertAlmostEqual(great_circle_position(0, 179, 0, -179, 2)[1], -177, places=10)

    def test_long_continuation_does_not_reverse_to_shortest_endpoint_path(self):
        latitude, longitude = great_circle_position(0, 10, 0, 20, 20)
        self.assertAlmostEqual(latitude, 0, places=10)
        self.assertAlmostEqual(longitude, -150, places=9)

    def test_pole_and_stationary_geometry_remain_finite(self):
        latitude, longitude = great_circle_position(80, 0, 80, 180, 0.5)
        self.assertAlmostEqual(latitude, 90, places=9)
        self.assertTrue(np.isfinite(longitude) and -180 <= longitude < 180)
        for fraction in (-100, 0.25, 100):
            self.assertEqual(great_circle_position(10, 20, 10, 20, fraction), (10, 20))
        self.assertEqual(great_circle_distance_m(90, 0, 90, 120), 0)

    def test_antipodal_bearing_is_ambiguous_but_endpoints_and_distance_are_defined(self):
        with self.assertRaises(ValueError):
            great_circle_position(0, 0, 0, 180, 0.5)
        with self.assertRaises(ValueError):
            great_circle_position(0, 0, 0, 180, 2)
        self.assertEqual(great_circle_position(0, 0, 0, 180, 0), (0, 0))
        self.assertEqual(great_circle_position(0, 0, 0, 180, 1), (0, -180))
        self.assertAlmostEqual(great_circle_distance_m(0, 0, 0, 180), math.pi*EARTH_RADIUS_M, places=6)

    def test_invalid_coordinates_or_fraction_are_rejected(self):
        for arguments in ((91, 0, 0, 1, 0.5), (0, 181, 0, 1, 0.5), (np.nan, 0, 0, 1, 0.5),
                          (0, 0, 0, 1, np.inf)):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                great_circle_position(*arguments)


class RegistrationPositionTests(unittest.TestCase):
    def test_quarter_time_interpolation_and_complete_anchor_provenance(self):
        points = pd.DataFrame([position(0, longitude=10), position(100, longitude=30, source_row=7)])
        events = pd.DataFrame([registration(25)])
        result = estimate_registration_positions(events, points)
        row = result.iloc[0]
        self.assertEqual(row["position_method"], "interpolated")
        self.assertEqual(row["match_status"], "interpolated")
        self.assertAlmostEqual(row["longitude"], 15, places=10)
        self.assertEqual(row["anchor_start_time"], NOW)
        self.assertEqual(row["anchor_end_time"], NOW+pd.Timedelta(seconds=100))
        self.assertEqual(row["anchor_start_recorded_time"], NOW+pd.Timedelta(seconds=18))
        self.assertEqual(row["anchor_start_source_rows"], [6])
        self.assertEqual(row["anchor_end_source_rows"], [7])
        self.assertEqual(row["anchor_span_s"], 100)
        self.assertEqual(row["time_fraction"], 0.25)
        self.assertEqual(row["seconds_from_anchor_start"], 25)
        self.assertEqual(row["seconds_to_anchor_end"], 75)
        self.assertEqual(row["projection_horizon_s"], 0)
        self.assertEqual(row["position_time"], NOW)
        self.assertEqual(row["position_offset_s"], -25)
        self.assertEqual(row["time"], events.iloc[0]["time"])
        self.assertAlmostEqual(row["segment_speed_m_s"], row["segment_distance_m"]/100)

    def test_before_and_after_use_first_and_last_leg_velocities(self):
        points = pd.DataFrame([position(0, longitude=10), position(100, longitude=20, source_row=7),
                               position(300, longitude=50, source_row=8)])
        result = estimate_registration_positions(pd.DataFrame([registration(-50), registration(500)]), points)
        before, after = result.iloc[0], result.iloc[1]
        self.assertEqual(before["position_method"], "projected_before")
        self.assertAlmostEqual(before["longitude"], 5, places=9)
        self.assertEqual(before["time_fraction"], -0.5)
        self.assertEqual(before["projection_horizon_s"], 50)
        self.assertEqual(before["seconds_from_anchor_start"], -50)
        self.assertEqual(after["position_method"], "projected_after")
        self.assertAlmostEqual(after["longitude"], 80, places=9)
        self.assertEqual(after["anchor_start_source_rows"], [7])
        self.assertEqual(after["anchor_end_source_rows"], [8])
        self.assertEqual(after["time_fraction"], 2)
        self.assertEqual(after["projection_horizon_s"], 200)
        self.assertEqual(after["seconds_to_anchor_end"], -200)

    def test_stationary_two_point_leg_has_zero_speed_for_projection_and_interpolation(self):
        points = pd.DataFrame([position(0, latitude=10, longitude=20),
                               position(60, latitude=10, longitude=20, source_row=7)])
        result = estimate_registration_positions(pd.DataFrame([registration(-60), registration(30), registration(180)]), points)
        self.assertEqual(result["position_method"].tolist(), ["projected_before", "interpolated", "projected_after"])
        self.assertTrue(result["latitude"].eq(10).all() and result["longitude"].eq(20).all())
        self.assertTrue(result["segment_distance_m"].eq(0).all())
        self.assertTrue(result["segment_speed_m_s"].eq(0).all())

    def test_exact_single_point_maps_without_inventing_speed_other_times_insufficient(self):
        points = pd.DataFrame([position(0, longitude=180)])
        result = estimate_registration_positions(pd.DataFrame([registration(0), registration(86400)]), points)
        self.assertEqual(result.iloc[0]["position_method"], "exact")
        self.assertEqual(result.iloc[0]["longitude"], 180)
        self.assertEqual(result.iloc[0]["anchor_span_s"], 0)
        self.assertTrue(pd.isna(result.iloc[0]["segment_speed_m_s"]))
        self.assertEqual(result.iloc[1]["position_method"], "insufficient_positions")
        self.assertTrue(pd.isna(result.iloc[1]["latitude"]))
        self.assertEqual(result.iloc[1]["position_offset_s"], -86400)

    def test_dateline_interpolation_does_not_cross_greenwich(self):
        points = pd.DataFrame([position(0, longitude=179), position(100, longitude=-179, source_row=7)])
        result = estimate_registration_positions(pd.DataFrame([registration(50)]), points)
        self.assertAlmostEqual(abs(result.iloc[0]["longitude"]), 180, places=10)

    def test_antipodal_estimates_are_unmapped_but_exact_endpoint_stays_valid(self):
        points = pd.DataFrame([position(0, longitude=0), position(100, longitude=180, source_row=7)])
        result = estimate_registration_positions(pd.DataFrame([registration(0), registration(50), registration(200)]), points)
        self.assertEqual(result["position_method"].tolist(), ["exact", "ambiguous_geometry", "ambiguous_geometry"])
        self.assertTrue(result.loc[1:, "latitude"].isna().all())
        self.assertAlmostEqual(result.iloc[1]["segment_distance_m"], math.pi*EARTH_RADIUS_M, places=6)

    def test_missing_clock_empty_positions_and_conflicting_timestamp(self):
        events = pd.DataFrame([registration(), registration(time=pd.NaT)])
        result = estimate_registration_positions(events, pd.DataFrame())
        self.assertEqual(result["position_method"].tolist(), ["no_positions", "untimed"])
        conflicts = pd.DataFrame([position(0, longitude=10), position(0, longitude=11, source_row=7)])
        ambiguous = estimate_registration_positions(pd.DataFrame([registration()]), conflicts)
        self.assertEqual(ambiguous.iloc[0]["position_method"], "ambiguous_geometry")
        self.assertTrue(pd.isna(ambiguous.iloc[0]["longitude"]))

    def test_inputs_are_unchanged_and_mapped_methods_are_explicit(self):
        points = pd.DataFrame([position(0), position(100, longitude=20, source_row=7)])
        events = pd.DataFrame([registration(25), registration(200, outcome="timeout")])
        before_points, before_events = points.copy(deep=True), events.copy(deep=True)
        result = estimate_registration_positions(events, points)
        pd.testing.assert_frame_equal(points, before_points)
        pd.testing.assert_frame_equal(events, before_events)
        self.assertEqual(set(MAPPED_METHODS), {"exact", "interpolated", "projected_before", "projected_after"})
        self.assertEqual(result["outcome"].tolist(), events["outcome"].tolist())
        self.assertTrue(result["position_method"].isin(MAPPED_METHODS).all())
        self.assertTrue(estimate_registration_positions(pd.DataFrame(), points).empty)


if __name__ == "__main__":
    unittest.main()
