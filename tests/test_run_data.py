import unittest

from domain.run_data import RunData


class TestRunDataValidation(unittest.TestCase):
    def test_validate_lengths_passes(self):
        data = RunData(
            time_s=[0.0, 1.0],
            distance_m=[0.0, 10.0],
            lat=[36.0, 36.1],
            lon=[-121.0, -121.1],
            speed=[20.0, 21.0],
            channels={"Accel X": [0.1, 0.2]},
        )
        data.validate_lengths()

    def test_validate_lengths_fails_on_series(self):
        data = RunData(
            time_s=[0.0, 1.0],
            distance_m=[0.0],
            lat=None,
            lon=None,
            speed=None,
            channels={},
        )
        with self.assertRaises(ValueError):
            data.validate_lengths()

    def test_validate_lengths_fails_on_channel(self):
        data = RunData(
            time_s=[0.0, 1.0, 2.0],
            distance_m=None,
            lat=None,
            lon=None,
            speed=None,
            channels={"Throttle": [0.1, 0.2]},
        )
        with self.assertRaises(ValueError):
            data.validate_lengths()


if __name__ == "__main__":
    unittest.main()
