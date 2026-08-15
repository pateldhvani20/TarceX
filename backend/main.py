import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from backend import config, database, persistence_repository
from backend.core.pipelines import process_event
from backend.database import create_tables
from backend.schemas import IngestResponse, TransactionEvent, UserState


def seed_demo_data_if_needed():
    """Seed initial realistic transactions for hackathon demo if database is empty."""
    with database.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if count >= 3:
        return

    demo_events = [
        {
            "event_id": "EV-992A-441",
            "source": "BankA",
            "user_id": "USR-001",
            "timestamp": "2026-08-15T10:00:00Z",
            "amount": 124.50,
            "category": "Retail",
            "merchant": "Acme Corp",
            "description": "Store Purchase",
            "status": "cleared",
            "email": "e.vance@proxy-net.local",
            "phone": "+15550198234"
        },
        {
            "event_id": "EV-881B-772",
            "source": "WalletX",
            "user_id": "USR-842",
            "timestamp": "2026-08-15T10:15:00Z",
            "amount": 9450.00,
            "category": "Wire Transfer",
            "merchant": "Unknown Offshore",
            "description": "High Value International Wire",
            "status": "flagged",
            "email": "usr842@offshore.org",
            "phone": "+15559876543"
        },
        {
            "event_id": "EV-773C-110",
            "source": "BankA",
            "user_id": "USR-044",
            "timestamp": "2026-08-15T10:20:00Z",
            "amount": 12.99,
            "category": "Subscriptions",
            "merchant": "Streaming Svc",
            "description": "Monthly Streaming",
            "status": "cleared",
            "email": "usr044@example.com",
            "phone": "+15551112233"
        },
        {
            "event_id": "EV-664D-551",
            "source": "BankA",
            "user_id": "USR-112",
            "timestamp": "2026-08-15T10:25:00Z",
            "amount": 85.00,
            "category": "Groceries",
            "merchant": "Grocery Local",
            "description": "Weekly Groceries",
            "status": "cleared",
            "email": "usr112@example.com",
            "phone": "+15554445566"
        },
        {
            "event_id": "EV-555E-229",
            "source": "CardProcessor",
            "user_id": "USR-901",
            "timestamp": "2026-08-15T10:30:00Z",
            "amount": 1200.00,
            "category": "Electronics",
            "merchant": "Electronics Hub",
            "description": "Laptop Purchase",
            "status": "cleared",
            "email": "usr901@example.com",
            "phone": "+15557778899"
        },
        {
            "event_id": "EV-331X-001",
            "source": "WalletX",
            "user_id": "USR-001",
            "timestamp": "2026-08-15T10:35:00Z",
            "amount": 5000.00,
            "category": "Crypto",
            "merchant": "Unknown Exchange",
            "description": "Identity Conflict Test Event",
            "status": "pending",
            "email": "conflict.vance@altmail.com",
            "phone": "+15550199999"
        }
    ]

    for evt_dict in demo_events:
        evt = TransactionEvent.model_validate(evt_dict)
        process_event(evt, raw_payload=json.dumps(evt_dict))


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    try:
        seed_demo_data_if_needed()
    except Exception as e:
        print(f"Seed error: {e}")
    yield


app = FastAPI(
    title="TraceX",
    version="1.0.0",
    description=(
        "Real-Time Financial Transaction Anomaly Detection "
        "with Temporal Replay and Identity Resolution"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    frontend_path = Path(__file__).resolve().parent.parent / "frontend" / "overview.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return {
        "service": "TraceX",
        "status": "running",
        "message": "Transaction anomaly detection backend",
    }


@app.get("/health")
def health():
    db_ok = False
    try:
        with database.get_connection() as conn:
            conn.execute("SELECT 1")
            db_ok = True
    except Exception:
        pass

    model_ok = Path(config.model_path).exists()
    audit_ok = Path(config.audit_log_path).parent.exists()

    return {
        "status": "healthy" if db_ok and model_ok else "degraded",
        "backend": "ONLINE",
        "sqlite": "CONNECTED" if db_ok else "DISCONNECTED",
        "model": "LOADED" if model_ok else "MISSING",
        "audit_log": "ACTIVE" if audit_ok else "INACTIVE",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest(request: Request):
    raw_bytes = await request.body()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=422,
            detail="Request body must contain valid JSON.",
        )

    try:
        event = TransactionEvent.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(),
        )

    return process_event(
        event,
        raw_payload=raw_bytes.decode("utf-8"),
    )


@app.get("/stats")
def get_stats():
    with database.get_connection() as conn:
        events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        decisions_rows = conn.execute("SELECT * FROM decisions").fetchall()

    decisions = [dict(r) for r in decisions_rows]
    normal_cnt = sum(1 for d in decisions if d.get("model_label") == "normal")
    anomalous_cnt = sum(1 for d in decisions if d.get("model_label") == "anomalous")
    duplicate_cnt = sum(1 for d in decisions if d.get("is_duplicate"))
    late_cnt = sum(1 for d in decisions if d.get("is_late"))
    identity_conflicts_cnt = sum(1 for d in decisions if "Identity conflict" in (d.get("decision_reason") or ""))

    latest = decisions[-1]["decision_reason"] if decisions else "No transactions processed yet"
    return {
        "total_events": events,
        "normal_count": normal_cnt,
        "anomalous_count": anomalous_cnt,
        "duplicate_count": duplicate_cnt,
        "identity_conflicts_count": identity_conflicts_cnt,
        "late_count": late_cnt,
        "latest_decision": latest
    }


@app.get("/transactions")
def get_transactions():
    with database.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT e.event_id, e.source, e.user_id, e.event_time, e.received_at,
                   e.amount, e.category, e.description, e.merchant, e.status,
                   e.email, e.phone,
                   d.decision_reason, d.model_label, d.model_score, d.is_duplicate, d.is_late, d.processed_at
            FROM events e
            LEFT JOIN decisions d ON e.event_id = d.event_id
            ORDER BY e.event_time DESC, e.event_id DESC
            """
        ).fetchall()

    result = []
    for r in rows:
        item = dict(r)
        # determine decision string
        if item.get("decision_reason") and "Identity conflict" in item["decision_reason"]:
            item["decision"] = "updated"
        elif item.get("decision_reason") and "Transaction conflict" in item["decision_reason"]:
            item["decision"] = "updated"
        elif item.get("is_duplicate"):
            item["decision"] = "duplicate"
        elif item.get("model_label"):
            item["decision"] = item["model_label"]
        else:
            item["decision"] = "normal"
        result.append(item)
    return result


@app.get("/transactions/{event_id}")
def get_transaction_detail(event_id: str):
    evt = persistence_repository.get_event(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail="Transaction not found")
    dec = persistence_repository.get_decision(event_id)
    usr = persistence_repository.get_user_state(evt["user_id"])
    return {
        "event": evt,
        "decision": dec,
        "user_state": usr.model_dump() if usr else None
    }


@app.post("/replay")
@app.get("/replay")
def trigger_replay():
    import replay
    start_time = time.time()
    try:
        success = replay.run_replay()
        exec_ms = int((time.time() - start_time) * 1000)
    except Exception as e:
        return {
            "status": "FAIL",
            "message": str(e),
            "determinism": False
        }

    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT event_id, event_time, user_id, amount, merchant FROM events ORDER BY event_time ASC"
        ).fetchall()
        events_list = [dict(r) for r in rows]

    return {
        "status": "PASS" if success else "FAIL",
        "determinism": True if success else False,
        "message": "REPLAY VERIFIED" if success else "REPLAY FAILED",
        "execution_time_ms": exec_ms,
        "events_count": len(events_list),
        "events": events_list
    }


@app.get("/identities")
def get_identities():
    with database.get_connection() as conn:
        user_rows = conn.execute("SELECT * FROM user_state").fetchall()
        users = [dict(r) for r in user_rows]

    result = []
    for u in users:
        user_id = u["user_id"]
        with database.get_connection() as conn:
            user_events = conn.execute(
                "SELECT * FROM events WHERE user_id = ? ORDER BY event_time DESC", (user_id,)
            ).fetchall()
        evts = [dict(e) for e in user_events]
        
        # Calculate risk score
        risk_score = 15
        if len(evts) > 5:
            risk_score += 20
        for e in evts:
            if (e.get("amount") or 0) > 5000:
                risk_score += 40
        risk_score = min(risk_score, 98)

        result.append({
            "user_id": user_id,
            "email": u.get("email") or (evts[0].get("email") if evts else "N/A"),
            "phone": u.get("phone") or (evts[0].get("phone") if evts else "N/A"),
            "txn_count_24hr": u.get("txn_count_24hr", len(evts)),
            "average_amount_30d": u.get("average_amount_30d"),
            "last_event_id": u.get("last_event_id"),
            "risk_score": risk_score,
            "events_count": len(evts),
            "events": evts
        })
    return result


@app.get("/audit")
def get_audit():
    audit_path = Path(config.audit_log_path)
    records = []
    if audit_path.exists():
        with open(audit_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
    return records[::-1]  # Return newest first


@app.post("/seed")
def force_seed():
    seed_demo_data_if_needed()
    return {"status": "seeded"}


# Serve static frontend files
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    app.mount("/static", StaticFiles(directory=str(frontend_dir), html=True), name="static")