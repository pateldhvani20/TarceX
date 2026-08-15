import unittest
from datetime import datetime, timezone
from backend.core.model.adapter import predict
from backend.core.pipelines import build_features
from backend.schemas import TransactionEvent


class TestDeterminism(unittest.TestCase):
    def test_feature_determinism(self):
        event = TransactionEvent(
            event_id="det-001",
            timestamp=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
            source="BankA",
            user_id="user-det",
            amount=9999.0,
            category="shopping",
            merchant="Amazon"
        )
        features1 = build_features(event, [])
        features2 = build_features(event, [])
        self.assertEqual(features1, features2)
        self.assertEqual(len(features1), 5)

    def test_prediction_determinism(self):
        features = [9999.0, 1.0, 9999.0, 5.0, 10.0]
        res1 = predict(features)
        res2 = predict(features)
        self.assertEqual(res1, res2)


if __name__ == "__main__":
    unittest.main()
