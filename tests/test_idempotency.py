import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend import config, database
from backend.main import app


class TestIdempotency(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.original_db = config.db_path
        config.db_path = Path(self.temp_db.name)
        database.create_tables()
        self.client = TestClient(app)

    def tearDown(self):
        config.db_path = self.original_db
        try:
            Path(self.temp_db.name).unlink()
        except Exception:
            pass

    def test_duplicate_exact_payload(self):
        payload = {
            "event_id": "dup-001",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "BankA",
            "user_id": "user-dup",
            "amount": 100.0
        }
        res1 = self.client.post("/ingest", json=payload)
        self.assertEqual(res1.status_code, 202)

        res2 = self.client.post("/ingest", json=payload)
        self.assertEqual(res2.status_code, 202)
        self.assertEqual(res2.json()["decision"], "duplicate")

    def test_duplicate_conflict_payload(self):
        payload1 = {
            "event_id": "dup-002",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "BankA",
            "user_id": "user-dup",
            "amount": 100.0
        }
        payload2 = {
            "event_id": "dup-002",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "BankA",
            "user_id": "user-dup",
            "amount": 500.0
        }
        res1 = self.client.post("/ingest", json=payload1)
        self.assertEqual(res1.status_code, 202)

        res2 = self.client.post("/ingest", json=payload2)
        self.assertEqual(res2.status_code, 202)
        self.assertEqual(res2.json()["decision"], "duplicate conflict")


if __name__ == "__main__":
    unittest.main()
