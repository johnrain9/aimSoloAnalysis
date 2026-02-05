import csv
import os
import tempfile
import unittest

from ingest.csv.laps import infer_laps
from ingest.csv.parser import parse_csv


def _write_csv(rows):
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return path


class TestLapInference(unittest.TestCase):
    def test_infer_laps_from_beacons(self):
        rows = [
            ["Track", "Test"],
            [],
            ["Time", "Beacon Markers"],
            ["s", ""],
            ["0.0", "1"],
            ["10.0", "1"],
            ["20.0", "2"],
            ["30.0", "2"],
            ["40.0", "3"],
        ]
        path = _write_csv(rows)
        try:
            parsed = parse_csv(path)
            laps = infer_laps(parsed)
        finally:
            os.remove(path)

        self.assertEqual(len(laps), 2)
        self.assertAlmostEqual(laps[0].start_time_s, 0.0)
        self.assertAlmostEqual(laps[0].end_time_s, 20.0)

    def test_infer_laps_from_distance_resets(self):
        rows = [
            ["Track", "Test"],
            [],
            ["Time", "Distance on GPS Speed"],
            ["s", "m"],
            ["0.0", "0"],
            ["5.0", "10"],
            ["10.0", "20"],
            ["15.0", "5"],
            ["20.0", "15"],
            ["25.0", "25"],
            ["30.0", "4"],
        ]
        path = _write_csv(rows)
        try:
            parsed = parse_csv(path)
            laps = infer_laps(parsed)
        finally:
            os.remove(path)

        self.assertEqual(len(laps), 1)
        self.assertAlmostEqual(laps[0].start_time_s, 15.0)
        self.assertAlmostEqual(laps[0].end_time_s, 30.0)

    def test_infer_laps_empty_without_signals(self):
        rows = [
            ["Track", "Test"],
            [],
            ["Time", "Speed"],
            ["s", "km/h"],
            ["0.0", "10.0"],
            ["5.0", "11.0"],
        ]
        path = _write_csv(rows)
        try:
            parsed = parse_csv(path)
            laps = infer_laps(parsed)
        finally:
            os.remove(path)

        self.assertEqual(laps, [])


if __name__ == "__main__":
    unittest.main()
