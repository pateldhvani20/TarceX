import json
from datetime import datetime

from backend.database import get_connection
from backend.schemas import (
    ProcessingDecision,
    TransactionEvent,
    UserState,
)


def insert_event(
    event: TransactionEvent,
    raw_payload: str,
    received_at,
) -> bool:

    # Handle both datetime and string types for received_at
    if isinstance(received_at, str):
        received_at_iso = received_at
    else:
        received_at_iso = received_at.isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO events (
                event_id,
                source,
                user_id,
                event_time,
                received_at,
                amount,
                category,
                description,
                merchant,
                status,
                email,
                phone,
                raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.source,
                event.user_id,
                event.timestamp.isoformat(),
                received_at_iso,
                event.amount,
                event.category,
                event.description,
                event.merchant,
                event.status,
                event.email,
                event.phone,
                raw_payload,
            ),
        )

        return cursor.rowcount == 1


def get_event(event_id: str):

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM events
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()

        return dict(row) if row else None


def get_events_for_user(user_id: str) -> list[dict]:

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM events
            WHERE user_id = ?
            ORDER BY event_time ASC, event_id ASC
            """,
            (user_id,),
        ).fetchall()

        return [dict(row) for row in rows]


def upsert_user_state(state: UserState) -> None:

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_state (
                user_id,
                txn_count_24hr,
                average_amount_30d,
                email,
                phone,
                last_event_id,
                last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                txn_count_24hr = excluded.txn_count_24hr,
                average_amount_30d = excluded.average_amount_30d,
                email = excluded.email,
                phone = excluded.phone,
                last_event_id = excluded.last_event_id,
                last_updated = excluded.last_updated
            """,
            (
                state.user_id,
                state.txn_count_24hr,
                state.average_amount_30d,
                state.email,
                state.phone,
                state.last_event_id,
                (
                    state.last_updated.isoformat()
                    if state.last_updated
                    else None
                ),
            ),
        )


def get_user_state(user_id: str):

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM user_state
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if not row:
            return None

        data = dict(row)

        return UserState(
            user_id=data["user_id"],
            txn_count_24hr=data["txn_count_24hr"],
            average_amount_30d=data["average_amount_30d"],
            email=data["email"],
            phone=data["phone"],
            last_event_id=data["last_event_id"],
            last_updated=(
                datetime.fromisoformat(
                    data["last_updated"]
                )
                if data["last_updated"]
                else None
            ),
        )


def insert_decision(
    decision: ProcessingDecision,
) -> None:

    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO decisions (
                event_id,
                decision_reason,
                model_label,
                model_score,
                is_duplicate,
                is_late,
                config_json,
                processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.event_id,
                decision.decision_reason,
                decision.model_label,
                decision.model_score,
                int(decision.is_duplicate),
                int(decision.is_late),
                decision.config_json,
                decision.processed_at.isoformat(),
            ),
        )


def get_decision(event_id: str):

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM decisions
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()

        return dict(row) if row else None


def get_all_events() -> list[dict]:
    """Get all events from the database."""

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM events
            ORDER BY event_time ASC, event_id ASC
            """
        ).fetchall()

        return [dict(row) for row in rows]


def get_all_decisions() -> list[dict]:
    """Get all decisions from the database."""

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM decisions
            ORDER BY processed_at ASC, event_id ASC
            """
        ).fetchall()

        return [dict(row) for row in rows]