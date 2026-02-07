import unittest

from storage import db


class TestUpsertIdBehavior(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init_schema(self.conn, "storage/schema.sql")

    def tearDown(self):
        self.conn.close()

    def _create_session(self) -> int:
        track_id = db.upsert_track(self.conn, "Test Track", "CW")
        return db.upsert_session(
            self.conn,
            track_id=track_id,
            track_direction="CW",
            start_datetime="2026-02-07T10:00:00Z",
            sample_rate_hz=10.0,
            duration_s=60.0,
            source_file="session.csv",
            source_format="aim_csv",
            raw_metadata={"Track": "Test Track"},
        )

    def _create_run(self) -> int:
        session_id = self._create_session()
        return db.upsert_run(self.conn, session_id=session_id, run_index=1)

    def test_upsert_track_returns_existing_id_on_conflict_update(self):
        first_id = db.upsert_track(self.conn, "Main", "CW", "orig", 1000.0)
        db.upsert_track(self.conn, "Other", "CW", "other", 1200.0)

        returned_id = db.upsert_track(self.conn, "Main", "CW", "updated", 1050.0)

        self.assertEqual(returned_id, first_id)
        row = self.conn.execute(
            "SELECT location_text, length_m FROM tracks WHERE track_id = ?",
            (first_id,),
        ).fetchone()
        self.assertEqual(row["location_text"], "updated")
        self.assertEqual(row["length_m"], 1050.0)

    def test_upsert_run_returns_existing_id_on_conflict_update(self):
        session_id = self._create_session()
        first_id = db.upsert_run(self.conn, session_id=session_id, run_index=1, comment="orig")
        db.upsert_run(self.conn, session_id=session_id, run_index=2, comment="other")

        returned_id = db.upsert_run(
            self.conn,
            session_id=session_id,
            run_index=1,
            comment="updated",
        )

        self.assertEqual(returned_id, first_id)
        row = self.conn.execute(
            "SELECT comment FROM runs WHERE run_id = ?",
            (first_id,),
        ).fetchone()
        self.assertEqual(row["comment"], "updated")

    def test_upsert_lap_returns_existing_id_on_conflict_update(self):
        run_id = self._create_run()
        first_id = db.upsert_lap(self.conn, run_id=run_id, lap_index=1, start_time_s=0.0, end_time_s=10.0, duration_s=10.0)
        db.upsert_lap(self.conn, run_id=run_id, lap_index=2, start_time_s=10.0, end_time_s=20.0, duration_s=10.0)

        returned_id = db.upsert_lap(
            self.conn,
            run_id=run_id,
            lap_index=1,
            start_time_s=0.0,
            end_time_s=11.0,
            duration_s=11.0,
        )

        self.assertEqual(returned_id, first_id)
        row = self.conn.execute(
            "SELECT end_time_s, duration_s FROM laps WHERE lap_id = ?",
            (first_id,),
        ).fetchone()
        self.assertEqual(row["end_time_s"], 11.0)
        self.assertEqual(row["duration_s"], 11.0)

    def test_upsert_channel_returns_existing_id_on_conflict_update(self):
        run_id = self._create_run()
        first_id = db.upsert_channel(
            self.conn,
            run_id=run_id,
            name="GPS Speed",
            unit="km/h",
            source_name="aim",
            norm_unit="km/h",
        )
        db.upsert_channel(
            self.conn,
            run_id=run_id,
            name="RPM",
            unit="rpm",
            source_name="aim",
            norm_unit="rpm",
        )

        returned_id = db.upsert_channel(
            self.conn,
            run_id=run_id,
            name="GPS Speed",
            unit="km/h",
            source_name="aim",
            norm_unit="m/s",
        )

        self.assertEqual(returned_id, first_id)
        row = self.conn.execute(
            "SELECT norm_unit FROM channels WHERE channel_id = ?",
            (first_id,),
        ).fetchone()
        self.assertEqual(row["norm_unit"], "m/s")


if __name__ == "__main__":
    unittest.main()
