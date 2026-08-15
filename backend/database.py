import sqlite3
from pathlib import Path

from backend import config


def get_connection() -> sqlite3.Connection:
    """
    Open a SQLite connection using config.db_path.

    SQLite is the only persistence backend used by TraceX.
    """

    db_path = Path(config.db_path)

    # Make sure the database directory exists.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(db_path))

    # Allows:
    # row["event_id"]
    # row["user_id"]
    # etc.
    connection.row_factory = sqlite3.Row

    # Required for the foreign key from decisions -> events.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_tables() -> None:
    """
    Create the three TraceX persistence tables if they do not exist.

    Tables:
        1. events
        2. user_state
        3. decisions

    No business logic is performed here.
    """

    with get_connection() as connection:

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,

                source TEXT NOT NULL,
                user_id TEXT NOT NULL,

                event_time TEXT NOT NULL,
                received_at TEXT NOT NULL,

                amount REAL,
                category TEXT,
                description TEXT,
                merchant TEXT,
                status TEXT,

                email TEXT,
                phone TEXT,

                raw_payload TEXT NOT NULL
            );


            CREATE INDEX IF NOT EXISTS idx_events_user_id
            ON events(user_id);


            CREATE INDEX IF NOT EXISTS idx_events_event_time
            ON events(event_time);


            CREATE TABLE IF NOT EXISTS user_state (
                user_id TEXT PRIMARY KEY,

                txn_count_24hr INTEGER NOT NULL DEFAULT 0,
                average_amount_30d REAL,

                email TEXT,
                phone TEXT,

                last_event_id TEXT,
                last_updated TEXT
            );


            CREATE TABLE IF NOT EXISTS decisions (
                event_id TEXT PRIMARY KEY,

                decision_reason TEXT NOT NULL,

                model_label TEXT,
                model_score REAL,

                is_duplicate INTEGER NOT NULL DEFAULT 0,
                is_late INTEGER NOT NULL DEFAULT 0,

                config_json TEXT,

                processed_at TEXT NOT NULL,

                FOREIGN KEY(event_id)
                    REFERENCES events(event_id)
                    ON DELETE CASCADE
            );
            """
        )