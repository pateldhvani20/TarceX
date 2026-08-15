import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend import config, database
from backend.main import app


class TestIngestion(unittest.TestCase):
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

    def test_validation_422_missing_fields(self):
        payload = {
            "event_id": "bad-001",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "BankA"
        }
        response = self.client.post("/ingest", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_normal_ingestion_202(self):
        payload = {
            "event_id": "ingest-001",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "BankA",
            "user_id": "user-01",
            "amount": 50.0,
            "category": "groceries",
            "merchant": "Walmart"
        }
        response = self.client.post("/ingest", json=payload)
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["event_id"], "ingest-001")
        self.assertEqual(data["status"], "accepted")
        self.assertIn(data["decision"], ["normal", "anomalous"])

    def test_partial_optional_fields(self):
        payload = {
            "event_id": "ingest-partial-001",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "WalletX",
            "user_id": "user-02",
            "amount": 25.0
        }
        response = self.client.post("/ingest", json=payload)
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
