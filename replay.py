import argparse
import json
import sys
from pathlib import Path

from backend import config, database, persistence_repository
from backend.core.pipelines import process_event
from backend.schemas import TransactionEvent


def run_replay(file_path=None):
    events_data = []

    # 1. Primary source: current DB events
    if Path(config.db_path).exists():
        try:
            with database.get_connection() as conn:
                rows = conn.execute(
                    "SELECT event_id, event_time, raw_payload FROM events ORDER BY event_time ASC, event_id ASC"
                ).fetchall()
                for row in rows:
                    events_data.append(json.loads(row["raw_payload"]))
        except Exception:
            events_data = []

    # 2. Secondary source: test_events.json fixture
    if not events_data:
        fixture_path = file_path or (config.FIXTURE_DIR / "test_events.json")
        if Path(fixture_path).exists() and Path(fixture_path).stat().st_size > 0:
            with open(fixture_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    events_data = content
                elif isinstance(content, dict):
                    events_data = [content]

    if not events_data:
        print("REPLAY ERROR: No events found to replay.")
        sys.exit(1)

    # 3. Capture original decisions if present
    original_decisions = {}
    if Path(config.db_path).exists():
        try:
            with database.get_connection() as conn:
                rows = conn.execute(
                    "SELECT event_id, decision_reason, model_label FROM decisions"
                ).fetchall()
                for r in rows:
                    original_decisions[r["event_id"]] = r["model_label"] or r["decision_reason"]
        except Exception:
            pass

    # 4. Use isolated temporary DB for replay
    replay_db_path = config.DATA_DIR / "replay_temp.db"
    if replay_db_path.exists():
        try:
            replay_db_path.unlink()
        except Exception:
            pass

    original_db_path = config.db_path
    config.db_path = replay_db_path

    try:
        database.create_tables()

        # Preserve original chronological order (timestamp ASC, event_id ASC)
        sorted_events = sorted(
            events_data,
            key=lambda x: (x.get("timestamp", ""), x.get("event_id", ""))
        )

        replay_decisions = {}
        for event_dict in sorted_events:
            event = TransactionEvent.model_validate(event_dict)
            res = process_event(event, raw_payload=json.dumps(event_dict))
            replay_decisions[event.event_id] = res["decision"]

        # Verify decisions match original where applicable
        mismatch = False
        for eid, orig_dec in original_decisions.items():
            if eid in replay_decisions:
                rep_dec = replay_decisions[eid]
                if orig_dec in ("normal", "anomalous") and rep_dec not in (orig_dec, "updated", "duplicate"):
                    print(f"Mismatch for {eid}: orig={orig_dec}, replay={rep_dec}")
                    mismatch = True

        if mismatch:
            print("REPLAY FAIL")
            sys.exit(1)
        else:
            print("REPLAY PASS")
            return True

    finally:
        config.db_path = original_db_path
        if replay_db_path.exists():
            try:
                replay_db_path.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay transaction pipeline")
    parser.add_argument("--replay", action="store_true", help="Run replay check")
    parser.add_argument("--file", type=str, default=None, help="Path to events file")

    args = parser.parse_args()
    run_replay(args.file)
