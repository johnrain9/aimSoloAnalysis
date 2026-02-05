import unittest

from analytics.deltas import LapWindow
from analytics.segment_metrics import compute_segment_metrics
from analytics.segments import Segment
from domain.run_data import RunData


class TestSegmentMetrics(unittest.TestCase):
    def _run_data(
        self,
        *,
        time_s,
        distance_m,
        speed_mps,
        channels=None,
    ):
        size = len(time_s)
        return RunData(
            time_s=time_s,
            distance_m=distance_m,
            lat=[None] * size,
            lon=[None] * size,
            speed=speed_mps,
            channels=channels or {},
            metadata={},
        )

    def _segment(self, start_m, apex_m, end_m):
        return Segment(
            start_idx=0,
            apex_idx=0,
            end_idx=0,
            start_m=start_m,
            apex_m=apex_m,
            end_m=end_m,
            sign=1,
            kappa_peak=0.01,
            confidence=1.0,
            label="T1",
        )

    def test_lean_proxy_good(self):
        time_s = [0, 1, 2, 3, 4, 5]
        distance_m = [0, 20, 40, 60, 80, 100]
        speed_mps = [20, 20, 20, 20, 20, 20]
        channels = {
            "Lateral Accel": [0.7] * 6,
            "GPS Radius": [60] * 6,
            "RollRate": [50] * 6,
            "GPS Accuracy": [1.0] * 6,
            "GPS SpdAccuracy": [0.5] * 6,
        }
        run_data = self._run_data(
            time_s=time_s,
            distance_m=distance_m,
            speed_mps=speed_mps,
            channels=channels,
        )
        segment = self._segment(0.0, 60.0, 100.0)
        metrics = compute_segment_metrics(run_data, LapWindow(0.0, 5.0), [segment])
        data = metrics["T1"]
        self.assertEqual("good", data.get("lean_quality"))
        lean = data.get("lean_proxy_deg")
        self.assertIsNotNone(lean)
        self.assertAlmostEqual(34.6, lean, delta=0.7)

    def test_lean_proxy_bad_low_speed(self):
        time_s = [0, 1, 2, 3]
        distance_m = [0, 5, 10, 15]
        speed_mps = [5, 5, 5, 5]
        channels = {"Lateral Accel": [0.7] * 4, "GPS Radius": [60] * 4}
        run_data = self._run_data(
            time_s=time_s,
            distance_m=distance_m,
            speed_mps=speed_mps,
            channels=channels,
        )
        segment = self._segment(0.0, 10.0, 15.0)
        metrics = compute_segment_metrics(run_data, LapWindow(0.0, 3.0), [segment])
        data = metrics["T1"]
        self.assertEqual("bad", data.get("lean_quality"))
        self.assertIsNone(data.get("lean_proxy_deg"))

    def test_entry_decel_metrics(self):
        time_s = [0, 1, 2, 3, 4]
        distance_m = [0, 20, 40, 60, 80]
        speed_mps = [30, 28, 26, 24, 22]
        run_data = self._run_data(
            time_s=time_s,
            distance_m=distance_m,
            speed_mps=speed_mps,
        )
        segment = self._segment(0.0, 60.0, 80.0)
        metrics = compute_segment_metrics(run_data, LapWindow(0.0, 4.0), [segment])
        data = metrics["T1"]
        self.assertAlmostEqual(25.0, data.get("decel_dist_m"), delta=0.2)
        self.assertGreater(data.get("decel_time_s"), 0.0)
        self.assertLess(data.get("decel_avg_g"), 0.0)
        self.assertGreater(data.get("decel_g_per_10m"), 0.0)


if __name__ == "__main__":
    unittest.main()
