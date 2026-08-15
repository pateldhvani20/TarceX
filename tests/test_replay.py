import tempfile
import unittest
from pathlib import Path
from backend import config, database
from replay import run_replay


class TestReplay(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.original_db = config.db_path
        config.db_path = Path(self.temp_db.name)
        database.create_tables()

    def tearDown(self):
        config.db_path = self.original_db
        try:
            Path(self.temp_db.name).unlink()
        except Exception:
            pass

    def test_replay_with_fixture(self):
        fixture_path = config.FIXTURE_DIR / "test_events.json"
        res = run_replay(str(fixture_path))
        self.assertTrue(res)


if __name__ == "__main__":
    unittest.main()
