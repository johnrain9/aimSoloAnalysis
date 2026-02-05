import csv
import os
import tempfile
import unittest

from ingest.csv.parser import parse_csv


def _write_csv(rows):
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return path


class TestCsvParser(unittest.TestCase):
    def test_parse_metadata_header_units_and_rows(self):
        rows = [
            ["Track", "Thunderhill"],
            ["Track Direction", "Clockwise"],
            ["Driver", "Jane Doe"],
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

    def test_parse_blank_units_row(self):
        rows = [
            ["Track", "Test"],
            [],
            ["Time", "Speed"],
            [],
            ["0.0", "10.0"],
        ]
        path = _write_csv(rows)
        try:
            parsed = parse_csv(path)
        finally:
            os.remove(path)

        self.assertEqual(parsed.units, ["", ""])
        self.assertEqual(parsed.rows[0], [0.0, 10.0])


if __name__ == "__main__":
    unittest.main()
