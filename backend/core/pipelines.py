import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from backend import config
from backend.core.model.adapter import predict
from backend.persistence_repository import (
    get_decision,
    get_event,
    get_events_for_user,
    get_user_state,
    insert_decision,
    insert_event,
    upsert_user_state,
)
from backend.schemas import ProcessingDecision, TransactionEvent, UserState


def utc_now():
    return datetime.now(timezone.utc)


def ensure_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_event(event):
    return event.model_copy(
        update={
            "category": event.category or "uncategorized",
            "merchant": event.merchant or "unknown merchant",
            "description": event.description or "",
            "status": event.status or "pending",
        }
    )


def source_rank(source):
    try:
        return config.SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(config.SOURCE_PRIORITY)


def write_audit(
    event_id,
    decision,
    reason,
    resolved_state,
    timestamp,
    model_output,
    source,
):
    path = Path(config.audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "event_id": event_id,
        "decision": decision,
        "reason": reason,
        "resolved_state": resolved_state,
        "timestamp": timestamp,
        "model_output": model_output,
        "source": source,
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                record,
                default=str,
            )
            + "\n"
        )


def raw_payload_to_text(raw_payload):
    if isinstance(raw_payload, str):
        return raw_payload

    return json.dumps(
        raw_payload,
        default=str,
        sort_keys=True,
    )


def raw_payload_data(raw_payload):
    if isinstance(raw_payload, str):
        return json.loads(raw_payload)

    return raw_payload


def build_features(event, history):
    event_time = ensure_utc(event.timestamp)

    cutoff = event_time - timedelta(hours=24)

    recent = []

    for row in history:
        row_time = ensure_utc(
            datetime.fromisoformat(row["event_time"])
        )

        if cutoff <= row_time <= event_time:
            recent.append(row)

    amounts = [
        float(row["amount"])
        for row in history
        if row.get("amount") is not None
    ]

    average_amount = (
        sum(amounts) / len(amounts)
        if amounts
        else float(event.amount)
    )

    # Stable deterministic categorical encoding.
    category_code = (
        sum(ord(c) for c in (event.category or ""))
        % 10
    )

    merchant_code = (
        sum(ord(c) for c in (event.merchant or ""))
        % 20
    )

    return [
        float(event.amount),
        float(len(recent)),
        float(average_amount),
        float(category_code),
        float(merchant_code),
    ]


def calculate_state(
    user_id,
    events,
    email=None,
    phone=None,
):
    ordered = sorted(
        events,
        key=lambda x: (
            x["event_time"],
            x["event_id"],
        ),
    )

    if not ordered:
        return UserState(
            user_id=user_id,
            email=email,
            phone=phone,
        )

    latest_time = ensure_utc(
        datetime.fromisoformat(
            ordered[-1]["event_time"]
        )
    )

    cutoff_24h = latest_time - timedelta(hours=24)
    cutoff_30d = latest_time - timedelta(days=30)

    recent = []
    amounts = []

    for row in ordered:

        event_time = ensure_utc(
            datetime.fromisoformat(
                row["event_time"]
            )
        )

        if event_time >= cutoff_24h:
            recent.append(row)

        if (
            event_time >= cutoff_30d
            and row.get("amount") is not None
        ):
            amounts.append(float(row["amount"]))

    average = (
        sum(amounts) / len(amounts)
        if amounts
        else None
    )

    return UserState(
        user_id=user_id,
        txn_count_24hr=len(recent),
        average_amount_30d=average,
        email=email,
        phone=phone,
        last_event_id=ordered[-1]["event_id"],
        last_updated=utc_now(),
    )


def process_event(
    event: TransactionEvent,
    raw_payload=None,
    received_at=None,
):
    """
    SINGLE shared processing function.

    Both /ingest and replay.py must use this function.
    """

    received_at = received_at or utc_now()

    if raw_payload is None:
        raw_payload = event.model_dump_json()

    raw_payload = raw_payload_to_text(raw_payload)

    # =========================================================
    # 1. DUPLICATE CHECK
    # =========================================================

    existing = get_event(event.event_id)

    if existing:

        original = get_decision(event.event_id)

        try:
            is_same = (
                raw_payload_data(raw_payload)
                == raw_payload_data(existing["raw_payload"])
            )
        except Exception:
            is_same = (raw_payload.strip() == existing["raw_payload"].strip())

        if is_same:
            decision = "duplicate"
            reason = (
                "Exact duplicate event_id; "
                "original decision returned."
            )
        else:
            decision = "duplicate conflict"
            reason = (
                "Same event_id received with different "
                "payload; original retained."
            )

        write_audit(
            event_id=event.event_id,
            decision=decision,
            reason=reason,
            resolved_state=None,
            timestamp=utc_now().isoformat(),
            model_output={
                "label": (
                    original.get("model_label")
                    if original
                    else None
                ),
                "score": (
                    original.get("model_score")
                    if original
                    else None
                ),
            },
            source=event.source,
        )

        return {
            "event_id": event.event_id,
            "status": "accepted",
            "decision": decision,
            "reason": reason,
        }

    # =========================================================
    # 2. DEFAULT OPTIONAL FIELDS
    # =========================================================

    event = normalize_event(event)

    # =========================================================
    # 3. RAW EVENT PERSISTENCE
    # =========================================================

    insert_event(
        event,
        raw_payload,
        received_at,
    )

    # =========================================================
    # 4. TEMPORAL HISTORY
    # =========================================================

    history = get_events_for_user(
        event.user_id
    )

    previous = [
        row
        for row in history
        if row["event_id"] != event.event_id
    ]

    current_time = ensure_utc(event.timestamp)

    is_late = any(
        current_time
        < ensure_utc(
            datetime.fromisoformat(
                row["event_time"]
            )
        )
        for row in previous
    )

    # =========================================================
    # 5. IDENTITY RESOLUTION
    # =========================================================

    state = get_user_state(event.user_id)

    canonical_email = (
        state.email
        if state and state.email
        else event.email
    )

    canonical_phone = (
        state.phone
        if state and state.phone
        else event.phone
    )

    identity_conflict = False
    identity_reasons = []

    if (
        state
        and event.email
        and state.email
        and event.email != state.email
    ):
        identity_conflict = True
        identity_reasons.append(
            "email mismatch"
        )

    if (
        state
        and event.phone
        and state.phone
        and event.phone != state.phone
    ):
        identity_conflict = True
        identity_reasons.append(
            "phone mismatch"
        )

    # =========================================================
    # 6. TRANSACTION CONFLICT
    # =========================================================

    conflicts = []

    for old in previous:

        if old["merchant"] != event.merchant:
            continue

        old_time = ensure_utc(
            datetime.fromisoformat(
                old["event_time"]
            )
        )

        difference = abs(
            (
                current_time - old_time
            ).total_seconds()
        )

        if difference > config.CONFLICT_WINDOW_SECONDS:
            continue

        changed = []

        if old["amount"] != event.amount:
            changed.append("amount")

        if old["category"] != event.category:
            changed.append("category")

        if old["description"] != event.description:
            changed.append("description")

        if changed:
            old_rank = source_rank(old["source"])
            new_rank = source_rank(event.source)

            winner = (
                event.source
                if new_rank < old_rank
                else old["source"]
            )

            conflicts.append(
                {
                    "event_id": old["event_id"],
                    "fields": changed,
                    "winner_source": winner,
                }
            )

    # =========================================================
    # 7. ML
    # =========================================================

    features = build_features(
        event,
        previous,
    )

    model_label, model_score = predict(
        features
    )

    # =========================================================
    # 8. FINAL DECISION
    # =========================================================

    if identity_conflict:

        decision = "updated"

        reason = (
            "Identity conflict: "
            + ", ".join(identity_reasons)
            + ". Canonical identity retained."
        )

    elif conflicts:

        decision = "updated"

        reason = (
            "Transaction conflict resolved using "
            "configured source priority. "
            "Both transaction records retained."
        )

    else:

        decision = model_label

        reason = (
            f"IsolationForest classification: "
            f"{model_label}."
        )

    # =========================================================
    # 9. STATE
    # =========================================================

    all_events = get_events_for_user(
        event.user_id
    )

    state = calculate_state(
        event.user_id,
        all_events,
        canonical_email,
        canonical_phone,
    )

    upsert_user_state(state)

    # =========================================================
    # 10. DECISION
    # =========================================================

    decision_record = ProcessingDecision(
        event_id=event.event_id,
        decision_reason=reason,
        model_label=model_label,
        model_score=model_score,
        is_duplicate=False,
        is_late=is_late,
        config_json=json.dumps(
            {
                "source_priority":
                    config.SOURCE_PRIORITY,
                "conflict_window_seconds":
                    config.CONFLICT_WINDOW_SECONDS,
            },
            sort_keys=True,
        ),
        processed_at=utc_now(),
    )

    insert_decision(
        decision_record
    )

    # =========================================================
    # 11. AUDIT
    # =========================================================

    write_audit(
        event_id=event.event_id,
        decision=decision,
        reason=reason,
        resolved_state=state.model_dump(
            mode="json"
        ),
        timestamp=event.timestamp.isoformat(),
        model_output={
            "label": model_label,
            "score": model_score,
            "features": features,
        },
        source=event.source,
    )

    return {
        "event_id": event.event_id,
        "status": "accepted",
        "decision": decision,
        "reason": reason,
    }
