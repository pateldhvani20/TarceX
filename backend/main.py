import json
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.database import create_tables
from backend.schemas import TransactionEvent
from backend.core.pipelines import process_event


app = FastAPI(
    title="TraceX",
    description=(
        "Real-Time Financial Transaction Anomaly Detection "
        "with Temporal Replay and Identity Resolution"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup() -> None:
    """Initialize the local SQLite database."""
    create_tables()


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "TraceX",
        "status": "running",
        "message": "Transaction anomaly detection backend",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "TraceX",
    }


# ============================================================
# INGEST
# ============================================================

@app.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest(
    event: TransactionEvent,
    request: Request,
) -> dict[str, Any]:
    """
    Receive and process a financial transaction event.

    FastAPI/Pydantic validates the JSON body before this function
    is called. Invalid or missing required fields automatically
    result in HTTP 422.
    """

    # Preserve the original JSON payload for audit/idempotency.
    raw_payload = json.dumps(
        event.model_dump(mode="json"),
        sort_keys=True,
    )

    # Record when the API received the event.
    received_at = datetime.now(timezone.utc).isoformat()

    # Use the single shared processing pipeline.
    result = process_event(
        event=event,
        raw_payload=raw_payload,
        received_at=received_at,
    )

    return result


# ============================================================
# STATS
# ============================================================

@app.get("/stats")
def stats() -> dict[str, Any]:
    """
    Lightweight statistics endpoint.

    Uses the existing SQLite database directly so the endpoint
    remains independent of the frontend.
    """

    try:
        from backend.persistence_repository import (
            get_all_events,
            get_all_decisions,
        )

        events = get_all_events()
        decisions = get_all_decisions()

        normal = 0
        anomalous = 0
        duplicate = 0
        identity_conflict = 0
        updated = 0

        for decision in decisions:
            value = str(decision.get("model_label") or "").lower()
            reason = str(decision.get("decision_reason") or "").lower()

            if value == "normal":
                normal += 1
            elif value == "anomalous":
                anomalous += 1

            if "duplicate" in reason:
                duplicate += 1

            if "identity" in reason:
                identity_conflict += 1

            if "conflict" in reason:
                updated += 1

        return {
            "total_events": len(events),
            "total_decisions": len(decisions),
            "normal": normal,
            "anomalous": anomalous,
            "duplicate": duplicate,
            "identity_conflict": identity_conflict,
            "updated": updated,
        }

    except Exception as exc:
        return {
            "total_events": 0,
            "total_decisions": 0,
            "normal": 0,
            "anomalous": 0,
            "duplicate": 0,
            "identity_conflict": 0,
            "updated": 0,
            "error": str(exc),
        }


# ============================================================
# TRANSACTIONS
# ============================================================

@app.get("/transactions")
def transactions() -> dict[str, Any]:
    """
    Return persisted events with their processing decisions.

    This is a read-only projection over the existing repository
    functions so the frontend can display real pipeline output.
    """

    from backend.persistence_repository import (
        get_all_decisions,
        get_all_events,
    )

    decisions = {
        decision["event_id"]: decision
        for decision in get_all_decisions()
    }

    records = []

    for event in get_all_events():
        decision = decisions.get(event["event_id"], {})

        records.append(
            {
                "event_id": event["event_id"],
                "source": event["source"],
                "user_id": event["user_id"],
                "timestamp": event["event_time"],
                "received_at": event["received_at"],
                "amount": event["amount"],
                "category": event["category"],
                "description": event["description"],
                "merchant": event["merchant"],
                "status": event["status"],
                "email": event["email"],
                "phone": event["phone"],
                "decision": decision.get("model_label"),
                "decision_reason": decision.get("decision_reason"),
                "model_score": decision.get("model_score"),
                "is_duplicate": bool(decision.get("is_duplicate", 0)),
                "is_late": bool(decision.get("is_late", 0)),
                "processed_at": decision.get("processed_at"),
            }
        )

    return {
        "count": len(records),
        "transactions": records,
    }


# ============================================================
# SIMPLE DASHBOARD
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    """
    Lightweight backend dashboard.

    The main Stitch frontend can later replace this.
    """

    return """
<!DOCTYPE html>
<html>
<head>
    <title>TraceX Dashboard</title>
    <meta charset="UTF-8">

    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f7f7f7;
            margin: 0;
            padding: 40px;
        }

        h1 {
            color: #222;
        }

        .grid {
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }

        .card {
            background: white;
            padding: 25px;
            border-radius: 14px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }

        .number {
            font-size: 32px;
            font-weight: bold;
            margin-top: 10px;
        }

        .label {
            color: #666;
        }

        .links {
            margin-top: 30px;
        }

        a {
            margin-right: 20px;
        }
    </style>
</head>

<body>

<h1>TraceX</h1>

<p>
Real-Time Financial Transaction Anomaly Detection
with Temporal Replay and Identity Resolution
</p>

<div class="grid">

    <div class="card">
        <div class="label">Total Events</div>
        <div class="number" id="events">-</div>
    </div>

    <div class="card">
        <div class="label">Total Decisions</div>
        <div class="number" id="decisions">-</div>
    </div>

    <div class="card">
        <div class="label">Normal</div>
        <div class="number" id="normal">-</div>
    </div>

    <div class="card">
        <div class="label">Anomalous</div>
        <div class="number" id="anomalous">-</div>
    </div>

    <div class="card">
        <div class="label">Duplicates</div>
        <div class="number" id="duplicate">-</div>
    </div>

    <div class="card">
        <div class="label">Identity Conflicts</div>
        <div class="number" id="identity">-</div>
    </div>

</div>

<div class="links">

    <a href="/docs" target="_blank">
        API Documentation
    </a>

    <a href="/health" target="_blank">
        Health
    </a>

    <a href="/stats" target="_blank">
        Stats JSON
    </a>

</div>

<script>

async function loadStats() {

    try {

        const response = await fetch("/stats");
        const data = await response.json();

        document.getElementById("events").innerText =
            data.total_events ?? 0;

        document.getElementById("decisions").innerText =
            data.total_decisions ?? 0;

        document.getElementById("normal").innerText =
            data.normal ?? 0;

        document.getElementById("anomalous").innerText =
            data.anomalous ?? 0;

        document.getElementById("duplicate").innerText =
            data.duplicate ?? 0;

        document.getElementById("identity").innerText =
            data.identity_conflict ?? 0;

    } catch (error) {

        console.error(error);

    }
}

loadStats();

setInterval(loadStats, 3000);

</script>

</body>
</html>
"""
