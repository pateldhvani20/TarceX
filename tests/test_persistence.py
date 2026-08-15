import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from backend import config, database, persistence_repository
from backend.schemas import ProcessingDecision, TransactionEvent, UserState


class TestPersistence(unittest.TestCase):
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

    def test_insert_and_get_event(self):
        event = TransactionEvent(
            event_id="p-001",
            timestamp=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
            source="BankA",
            user_id="user-p",
            amount=100.0,
            category="food"
        )
        now = datetime.now(timezone.utc)
        inserted = persistence_repository.insert_event(event, event.model_dump_json(), now)
        self.assertTrue(inserted)

        fetched = persistence_repository.get_event("p-001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["event_id"], "p-001")

    def test_user_state_and_decision(self):
        state = UserState(
            user_id="user-p",
            txn_count_24hr=1,
            average_amount_30d=100.0,
            email="test@example.com",
            phone="+123456"
        )
        persistence_repository.upsert_user_state(state)
        fetched_state = persistence_repository.get_user_state("user-p")
        self.assertIsNotNone(fetched_state)
        self.assertEqual(fetched_state.email, "test@example.com")

        event = TransactionEvent(
            event_id="p-001",
            timestamp=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
            source="BankA",
            user_id="user-p",
            amount=100.0
        )
        persistence_repository.insert_event(event, event.model_dump_json(), datetime.now(timezone.utc))

        decision = ProcessingDecision(
            event_id="p-001",
            decision_reason="normal",
            model_label="normal",
            model_score=0.5,
            processed_at=datetime.now(timezone.utc)
        )
        persistence_repository.insert_decision(decision)
        fetched_decision = persistence_repository.get_decision("p-001")
        self.assertIsNotNone(fetched_decision)
        self.assertEqual(fetched_decision["model_label"], "normal")


if __name__ == "__main__":
    unittest.main()
