import csv
import os
import tempfile
import unittest

from ingest.csv.importer import build_run_data
from ingest.csv.laps import infer_laps
from ingest.csv.parser import parse_csv


def _write_csv(rows):
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return path


class TestCsvParsing(unittest.TestCase):
    def test_parse_csv_metadata_header_units(self):
        rows = [
            ["Track", "Thunderhill"],
            ["Track Direction", "CW"],
            ["Racer", "Jane Doe"],
            [],
            ["Time", "Speed"],
            ["s", "km/h"],
            ["0.00", "100.0"],
            ["0.05", "101.0"],
        ]
        path = _write_csv(rows)
        try:
            parsed = parse_csv(path)
        finally:
            os.remove(path)

        self.assertEqual(parsed.metadata["Track"], "Thunderhill")
        self.assertEqual(parsed.metadata["Track Direction"], "CW")
        self.assertEqual(parsed.metadata["Track Identity"], "Thunderhill (CW)")
        self.assertEqual(parsed.header, ["Time", "Speed"])
        self.assertEqual(parsed.units, ["s", "km/h"])
        self.assertEqual(len(parsed.rows), 2)
        self.assertAlmostEqual(parsed.rows[0][0], 0.0)
        self.assertAlmostEqual(parsed.rows[0][1], 100.0)

    def test_build_run_data_converts_units_and_channels(self):
        rows = [
            ["Track", "Laguna Seca"],
            ["Track Direction", "CCW"],
            [],
            ["Time", "Distance on GPS Speed", "GPS Speed", "Latitude", "Longitude", "Accel X"],
            ["s", "km", "km/h", "deg", "deg", "g"],
            ["0.0", "0.0", "72.0", "36.0", "-121.0", "0.1"],
            ["1.0", "0.05", "36.0", "36.0001", "-121.0001", "0.2"],
        ]
        path = _write_csv(rows)
        try:
            parsed = parse_csv(path)
            run_data = build_run_data(parsed)
        finally:
            os.remove(path)

        self.assertEqual(run_data.time_s, [0.0, 1.0])
        self.assertEqual(run_data.distance_m, [0.0, 50.0])
        self.assertAlmostEqual(run_data.speed[0], 20.0, places=3)
        self.assertAlmostEqual(run_data.speed[1], 10.0, places=3)
        self.assertEqual(run_data.lat, [36.0, 36.0001])
        self.assertEqual(run_data.lon, [-121.0, -121.0001])
        self.assertIn("Accel X", run_data.channels)
        self.assertEqual(run_data.channels["Accel X"], [0.1, 0.2])


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
        self.assertEqual(laps[0].lap_index, 1)
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

    def test_infer_laps_from_gps_crossing(self):
        rows = [
            ["Track", "Test"],
            [],
            ["Time", "Latitude", "Longitude"],
            ["s", "deg", "deg"],
            ["0.0", "37.0", "-122.0"],
            ["5.0", "37.0005", "-122.0"],
            ["10.0", "37.0006", "-122.0"],
            ["15.0", "37.0007", "-122.0"],
            ["25.0", "37.0001", "-122.0"],
            ["35.0", "37.0006", "-122.0"],
        ]
        path = _write_csv(rows)
        try:
            parsed = parse_csv(path)
            laps = infer_laps(parsed)
        finally:
            os.remove(path)

        self.assertEqual(len(laps), 1)
        self.assertAlmostEqual(laps[0].start_time_s, 0.0)
        self.assertAlmostEqual(laps[0].end_time_s, 25.0)


if __name__ == "__main__":
    unittest.main()
