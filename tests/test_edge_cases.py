import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend import config, database, persistence_repository
from backend.main import app


class TestEdgeCases(unittest.TestCase):
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

    def test_late_event(self):
        # Event 1 at 10:00
        p1 = {
            "event_id": "late-001",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "BankA",
            "user_id": "user-late",
            "amount": 50.0
        }
        self.client.post("/ingest", json=p1)

        # Event 2 arriving with timestamp 09:30 (late event)
        p2 = {
            "event_id": "late-002",
            "timestamp": "2026-08-15T09:30:00Z",
            "source": "BankA",
            "user_id": "user-late",
            "amount": 30.0
        }
        res2 = self.client.post("/ingest", json=p2)
        self.assertEqual(res2.status_code, 202)

        # Verify decision stored with is_late = True
        dec = persistence_repository.get_decision("late-002")
        self.assertIsNotNone(dec)
        self.assertEqual(dec["is_late"], 1)

    def test_transaction_conflict(self):
        # Transaction 1 at 10:00:00 with CardY
        p1 = {
            "event_id": "txc-001",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "CardY",
            "user_id": "user-txc",
            "amount": 100.0,
            "merchant": "Amazon"
        }
        self.client.post("/ingest", json=p1)

        # Transaction 2 within 60 seconds with higher priority source (BankA)
        p2 = {
            "event_id": "txc-002",
            "timestamp": "2026-08-15T10:00:30Z",
            "source": "BankA",
            "user_id": "user-txc",
            "amount": 150.0,  # conflicting amount
            "merchant": "Amazon"
        }
        res2 = self.client.post("/ingest", json=p2)
        self.assertEqual(res2.status_code, 202)
        self.assertEqual(res2.json()["decision"], "updated")

    def test_identity_mismatch(self):
        # Event 1 sets canonical email
        p1 = {
            "event_id": "id-001",
            "timestamp": "2026-08-15T10:00:00Z",
            "source": "BankA",
            "user_id": "user-idm",
            "amount": 50.0,
            "email": "canonical@example.com"
        }
        self.client.post("/ingest", json=p1)

        # Event 2 with conflicting email
        p2 = {
            "event_id": "id-002",
            "timestamp": "2026-08-15T10:05:00Z",
            "source": "BankA",
            "user_id": "user-idm",
            "amount": 60.0,
            "email": "conflicting@example.com"
        }
        res2 = self.client.post("/ingest", json=p2)
        self.assertEqual(res2.status_code, 202)
        self.assertEqual(res2.json()["decision"], "updated")

        # Canonical email retained in user_state
        state = persistence_repository.get_user_state("user-idm")
        self.assertEqual(state.email, "canonical@example.com")


if __name__ == "__main__":
    unittest.main()
