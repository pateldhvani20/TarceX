# TraceX

## Real-Time Financial Transaction Anomaly Detection with Temporal Replay and Identity Resolution

TraceX is a local real-time financial transaction intelligence system designed to detect anomalous transactions while handling unreliable, duplicated, conflicting, late-arriving, and identity-inconsistent transaction events.

Instead of directly sending every transaction to an ML model, TraceX first validates, deduplicates, resolves identity conflicts, handles temporal ordering, resolves transaction conflicts, and then performs anomaly detection.

The system produces deterministic, explainable, auditable, and replayable decisions.

---

## 🚀 Project Overview

Traditional anomaly detection:

```text
Transaction
     ↓
ML Model
     ↓
Alert
```

TraceX:

```text
Incoming Event
      ↓
Schema Validation
      ↓
Duplicate Detection
      ↓
Raw Event Persistence
      ↓
Optional Field Normalization
      ↓
Identity Resolution
      ↓
Temporal Ordering
      ↓
Transaction Conflict Resolution
      ↓
Feature Engineering
      ↓
Isolation Forest ML
      ↓
Deterministic Decision
      ↓
SQLite State
      ↓
Audit Log
      ↓
Replay
```

This allows the system to reproduce the same decision when the same event set is replayed.

---

# 🎯 Problem Statement

Financial transaction systems receive events from multiple unreliable sources such as:

- Banks
- Cards
- Digital wallets
- Payment systems
- Other transaction providers

These sources can produce:

- Duplicate events
- Conflicting transaction amounts
- Different transaction categories
- Identity mismatches
- Missing fields
- Late-arriving events
- Out-of-order events
- Replayed events

A simple anomaly detection model cannot reliably handle these inconsistencies.

TraceX provides a deterministic processing layer before anomaly detection so that transaction decisions remain consistent and explainable.

---

# ✨ Key Features

## 1. Real-Time Event Ingestion

Transactions are accepted through a local FastAPI endpoint:

```text
POST /ingest
```

Required fields:

```text
event_id
timestamp
source
user_id
amount
```

Optional fields:

```text
category
description
merchant
status
email
phone
```

---

## 2. Pydantic Validation

Invalid or malformed events are rejected before entering the processing pipeline.

Required fields cannot be missing.

Example:

```json
{
  "event_id": "evt-001",
  "timestamp": "2026-08-15T10:00:00Z",
  "source": "BankA",
  "user_id": "user-001",
  "amount": 9999
}
```

Invalid requests return:

```text
422 Unprocessable Entity
```

Valid requests are accepted with:

```text
202 Accepted
```

---

# 🔁 Event Processing

All events use one shared processing function:

```text
process_event()
```

The same function is used by:

```text
POST /ingest
```

and:

```text
python replay.py --replay
```

This is important because live processing and replay use the same decision logic.

---

# ♻️ Duplicate Detection

TraceX treats `event_id` as the unique event identifier.

### Exact duplicate

If the same `event_id` is submitted with the exact same payload:

```text
Decision:
duplicate
```

The original decision is returned.

The event is not processed again.

### Duplicate conflict

If the same `event_id` is submitted with a different payload:

```text
Decision:
duplicate conflict
```

The original event is retained.

The conflicting payload is not silently used to overwrite the original transaction.

The conflict is recorded for auditability.

---

# 🕐 Temporal Ordering

Transactions are ordered using their own transaction timestamp.

Arrival order is never treated as transaction order.

The ordering strategy is:

```text
event timestamp ASC
event_id ASC
```

The second field provides deterministic ordering when two events have the same timestamp.

This allows TraceX to correctly process late and out-of-order events.

Example:

```text
Event A arrives at 10:05
Transaction time = 10:05

Event B arrives at 10:10
Transaction time = 10:02
```

Although B arrives later, its transaction timestamp places it before A.

---

# 👤 Identity Resolution

TraceX maintains a unified identity state using:

```text
user_id
email
phone
```

Email and phone are optional because they are not part of the original transaction specification but are required to demonstrate identity mismatch handling.

The first valid identity information becomes canonical.

If a later transaction provides a conflicting email or phone value, TraceX detects an identity conflict instead of silently replacing the canonical identity.

Example:

```text
Existing:
user_id = user-001
email = alice@example.com

Incoming:
user_id = user-001
email = different@example.com
```

Result:

```text
Identity conflict detected
```

The conflict is preserved for auditability.

---

# ⚔️ Transaction Conflict Resolution

TraceX handles conflicting transactions for the same:

```text
user_id + merchant
```

within the configured conflict window.

Default conflict window:

```text
60 seconds
```

Source priority is deterministic:

```text
BankA
CardY
WalletX
X
```

Therefore:

```text
BankA > CardY > WalletX > X
```

If two sources disagree about a transaction, the higher-priority source determines the resolved state.

The losing transaction is never deleted.

Both events remain available in the event history.

---

# 🧩 Partial Event Handling

Optional fields are normalized using deterministic defaults.

```text
category
→ uncategorized

merchant
→ unknown merchant

description
→ status pending

status
→ pending
```

Required fields are never automatically defaulted.

Required:

```text
event_id
timestamp
user_id
amount
```

---

# 🤖 Machine Learning

TraceX uses a real Scikit-learn Isolation Forest model.

Model:

```text
backend/core/model/anomaly_model.pkl
```

The model is loaded using Joblib.

The model expects exactly five numeric features:

```text
1. amount
2. transaction frequency in previous 24 hours
3. average transaction amount
4. category code
5. merchant code
```

Feature vector:

```text
[
    amount,
    txn_frequency_24h,
    average_amount,
    category_code,
    merchant_code
]
```

The model returns:

```text
normal
```

or:

```text
anomalous
```

along with a numerical anomaly score.

Example:

```text
Input:
[9999, 1, 9999, 5, 10]

Output:
anomalous

Score:
-0.19381479398298185
```

The model is not a stub.

It is a real Scikit-learn Isolation Forest model trained on synthetic transaction data for the hackathon prototype.

---

# 🧠 Decision Logic

Possible processing decisions include:

```text
normal
anomalous
duplicate
duplicate conflict
updated
ignore
rejected
```

Identity conflicts can override the ML decision when required by the processing rules.

Every decision contains an explanation.

Example:

```json
{
  "event_id": "evt-001",
  "status": "accepted",
  "decision": "anomalous",
  "reason": "IsolationForest classification: anomalous."
}
```

---

# 💾 SQLite Persistence

TraceX uses SQLite for local state management.

Database:

```text
data/state.db
```

No cloud database is required.

No external production infrastructure is required.

The system runs completely locally.

---

# 🗄️ Database Structure

The database stores:

## Events

Stores raw transaction events and their normalized information.

Important fields include:

```text
event_id
source
user_id
event_time
received_at
amount
category
description
merchant
status
email
phone
raw_payload
```

## User State

Stores the latest unified state for each user.

Important information includes:

```text
user_id
canonical email
canonical phone
transaction statistics
last event
last updated timestamp
```

## Decisions

Stores processing decisions.

Important information includes:

```text
event_id
decision
decision reason
model label
model score
duplicate flag
late-event flag
configuration
processed timestamp
```

---

# 📝 Audit Trail

Every processing decision is written to:

```text
logs/audit.log
```

The audit log uses JSON Lines format.

Example:

```json
{
  "event_id": "evt-001",
  "decision": "anomalous",
  "reason": "IsolationForest classification: anomalous.",
  "resolved_state": {},
  "timestamp": "2026-08-15T10:00:00Z",
  "model_output": {
    "label": "anomalous",
    "score": -0.1938
  },
  "source": "BankA"
}
```

The audit trail provides:

- Event traceability
- Decision explanation
- Model output
- Source information
- Resolved state
- Processing timestamp

---

# 🔄 Deterministic Replay

TraceX supports complete event replay.

Run:

```bash
python replay.py --replay
```

Replay reads the stored events and processes them through the same:

```text
process_event()
```

function used during live ingestion.

The replay verifies that decisions remain deterministic.

Successful output:

```text
REPLAY PASS
```

This demonstrates:

```text
Same Events
     +
Same Configuration
     +
Same Processing Logic
     =
Same Decisions
```

---

# 🧪 Testing

TraceX uses Python's built-in `unittest` framework.

Pytest is not required.

Run all tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected result:

```text
Ran 15 tests

OK
```

The test suite covers:

- Backend startup
- Persistence
- Event ingestion
- Schema validation
- Duplicate events
- Duplicate conflicts
- Late events
- Out-of-order events
- Transaction conflicts
- Identity mismatch
- Partial data
- Idempotency
- Determinism
- Replay

---

# 📁 Project Structure

```text
TraceX/
│
├── backend/
│   │
│   ├── core/
│   │   │
│   │   ├── model/
│   │   │   ├── __pycache__/
│   │   │   ├── adapter.py
│   │   │   ├── anomaly_model.pkl
│   │   │   └── train_model.py
│   │   │
│   │   └── pipelines.py
│   │
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── persistence_repository.py
│   └── schemas.py
│
├── data/
│   └── state.db
│
├── docs/
│   └── architecture.md
│
├── fixtures/
│   └── test_events.json
│
├── logs/
│   └── audit.log
│
├── scripts/
│   ├── inspect_model.py
│   └── load_fixture.py
│
├── tests/
│   ├── __init__.py
│   ├── test_backend.py
│   ├── test_determinism.py
│   ├── test_edge_cases.py
│   ├── test_idempotency.py
│   ├── test_ingestion.py
│   ├── test_persistence.py
│   └── test_replay.py
│
├── replay.py
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core backend |
| FastAPI | REST API |
| Pydantic | Input validation |
| SQLite | Local persistence |
| Scikit-learn | Machine learning |
| Isolation Forest | Anomaly detection |
| Joblib | ML model loading |
| JSON | Event and audit format |
| unittest | Automated tests |
| Stitch | UI design |
| HTML/CSS/JavaScript/Frontend framework | UI integration |

No TensorFlow is used.

No PyTorch is used.

No Kafka is used.

No Kubernetes is used.

No cloud infrastructure is required.

No production banking API is required.

---

# ⚙️ Installation

## 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
```

Move into the project:

```bash
cd TraceX
```

---

# 🐍 2. Create Virtual Environment

### Windows

```powershell
python -m venv .venv
```

Activate:

```powershell
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
```

Activate:

```bash
source .venv/bin/activate
```

---

# 📦 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If dependencies are not installed yet:

```bash
pip install fastapi uvicorn pydantic scikit-learn joblib
```

---

# ▶️ Running the Backend

From the project root:

```text
TraceX/
```

run:

```bash
python -m uvicorn backend.main:app --reload
```

The backend will start at:

```text
http://127.0.0.1:8000
```

Expected output:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

---

# 🌐 API Documentation

FastAPI automatically provides Swagger documentation.

Open:

```text
http://127.0.0.1:8000/docs
```

This allows you to test:

```text
POST /ingest
```

without requiring an external API client.

---

# 📊 Dashboard

The TraceX dashboard is available locally at:

```text
http://127.0.0.1:8000/dashboard
```

Statistics endpoint:

```text
http://127.0.0.1:8000/stats
```

The dashboard provides a visual representation of:

- Transaction activity
- Anomalies
- Normal transactions
- Duplicate events
- Identity conflicts
- Late events
- Processing decisions
- System statistics

If the Stitch frontend is being run separately, use the frontend URL provided by the frontend development server.

---

# 📡 API Example

Example PowerShell request:

```powershell
$body = @{
    event_id = "demo-001"
    timestamp = "2026-08-15T10:00:00Z"
    source = "BankA"
    user_id = "user-001"
    amount = 9999
    category = "shopping"
    description = "Laptop purchase"
    merchant = "Amazon"
    status = "confirmed"
    email = "user@example.com"
    phone = "9999999999"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/ingest `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

Example response:

```text
event_id    status    decision    reason
---------   -------   ----------  -------------------------------
demo-001    accepted  anomalous   IsolationForest classification
```

---

# 🧪 Testing an Anomaly

You can send a high-value transaction:

```json
{
  "event_id": "demo-anomaly-001",
  "timestamp": "2026-08-15T10:00:00Z",
  "source": "BankA",
  "user_id": "user-001",
  "amount": 99999,
  "category": "luxury",
  "description": "Large transaction",
  "merchant": "Unknown Merchant",
  "status": "confirmed"
}
```

The Isolation Forest model evaluates the transaction using the five engineered features.

The final decision is returned through the API.

---

# 🔁 Testing Duplicate Handling

Submit the same event twice.

First request:

```text
decision = normal
```

or:

```text
decision = anomalous
```

Second identical request:

```text
decision = duplicate
```

The original decision is returned without reprocessing the transaction.

---

# ⚔️ Testing Identity Conflict

First event:

```json
{
  "event_id": "identity-001",
  "timestamp": "2026-08-15T10:00:00Z",
  "source": "BankA",
  "user_id": "user-001",
  "amount": 500,
  "email": "user@example.com"
}
```

Later event:

```json
{
  "event_id": "identity-002",
  "timestamp": "2026-08-15T10:01:00Z",
  "source": "CardY",
  "user_id": "user-001",
  "amount": 700,
  "email": "different@example.com"
}
```

TraceX detects the identity mismatch and records it in the decision/audit trail.

---

# 🕐 Testing Late Events

Submit an event with an earlier transaction timestamp after a newer event has already arrived.

Example:

```text
Event A:
transaction time = 10:05

Event B:
transaction time = 10:02
arrival time = 10:10
```

TraceX uses:

```text
transaction timestamp
```

rather than:

```text
arrival timestamp
```

for temporal ordering.

---

# 🔥 Hackathon Demo Flow

The recommended demonstration sequence is:

### 1. Start TraceX

```bash
python -m uvicorn backend.main:app --reload
```

### 2. Open the dashboard

```text
http://127.0.0.1:8000/dashboard
```

### 3. Open Swagger

```text
http://127.0.0.1:8000/docs
```

### 4. Submit a normal transaction

Show:

```text
Transaction
    ↓
ML
    ↓
normal
```

### 5. Submit an anomalous transaction

Show:

```text
Transaction
    ↓
Isolation Forest
    ↓
anomalous
```

### 6. Submit the same event again

Show:

```text
duplicate
```

### 7. Submit the same ID with different data

Show:

```text
duplicate conflict
```

### 8. Demonstrate identity mismatch

Show:

```text
Identity Conflict
```

### 9. Demonstrate late event

Show:

```text
Temporal Ordering
```

### 10. Open audit log

```text
logs/audit.log
```

Show the JSON decision record.

### 11. Run replay

```bash
python replay.py --replay
```

Show:

```text
REPLAY PASS
```

This demonstrates that the system is deterministic and replayable.

---

# ⚡ Determinism

TraceX follows:

```text
Same Input
+
Same Configuration
+
Same Processing Logic
=
Same Output
```

This is one of the core properties of the system.

---

# 🔐 Auditability

Each event can be traced through:

```text
Raw Event
    ↓
Validation
    ↓
Identity Resolution
    ↓
Conflict Resolution
    ↓
ML Output
    ↓
Final Decision
    ↓
Persisted State
    ↓
Audit Record
```

This allows developers and judges to understand why a transaction received a particular decision.

---

# 📈 Performance

The MVP is designed for local processing.

Normal events are processed synchronously through:

```text
FastAPI
→ Pipeline
→ SQLite
→ ML
→ Audit
```

No distributed infrastructure is required.

---

# 🔧 Configuration

Configuration is stored in:

```text
backend/config.py
```

Important settings include:

```python
SOURCE_PRIORITY = [
    "BankA",
    "CardY",
    "WalletX",
    "X"
]

CONFLICT_WINDOW_SECONDS = 60
```

Paths:

```text
Database:
data/state.db

Audit:
logs/audit.log

Model:
backend/core/model/anomaly_model.pkl
```

---

# 🧠 Why TraceX Is Different

Most anomaly detection systems focus primarily on the ML model.

TraceX focuses on the reliability of the data going into the model.

The system answers:

> "Can we trust the transaction before deciding whether it is anomalous?"

TraceX therefore combines:

```text
Data Reliability
+
Identity Resolution
+
Temporal Reasoning
+
Conflict Resolution
+
Machine Learning
+
Auditability
+
Deterministic Replay
```

This makes TraceX more suitable for environments where transaction data can be incomplete, duplicated, contradictory, or delayed.

---

# 🏆 Hackathon Value Proposition

TraceX provides a complete local prototype for deterministic financial anomaly detection.

Its main differentiators are:

### Deterministic

The same event history produces the same result.

### Explainable

Every decision contains a reason.

### Replayable

Historical events can be replayed.

### Identity-Aware

Identity mismatches are detected.

### Conflict-Aware

Conflicting transaction records are resolved deterministically.

### Temporal-Aware

Late and out-of-order events are handled according to their actual transaction timestamps.

### Local

The complete MVP runs without cloud infrastructure.

---

# 📋 Requirements Compliance

| Requirement | Status |
|---|---|
| Python | ✅ |
| FastAPI | ✅ |
| Pydantic | ✅ |
| Scikit-learn | ✅ |
| Isolation Forest | ✅ |
| SQLite | ✅ |
| POST /ingest | ✅ |
| Event validation | ✅ |
| Duplicate handling | ✅ |
| Duplicate conflict handling | ✅ |
| Late events | ✅ |
| Out-of-order events | ✅ |
| Transaction conflicts | ✅ |
| Identity resolution | ✅ |
| Identity mismatch detection | ✅ |
| Partial data handling | ✅ |
| Audit logging | ✅ |
| Deterministic decisions | ✅ |
| Replay | ✅ |
| Automated tests | ✅ |
| Local execution | ✅ |
| External cloud infrastructure | ❌ |
| Kafka | ❌ |
| Kubernetes | ❌ |
| TensorFlow | ❌ |
| PyTorch | ❌ |

---

# 📊 Current Project Status

```text
Backend                         ✅ Complete
FastAPI                         ✅ Complete
Pydantic Validation             ✅ Complete
SQLite Persistence              ✅ Complete
ML Model                        ✅ Complete
Feature Engineering             ✅ Complete
Anomaly Detection               ✅ Complete
Duplicate Detection             ✅ Complete
Duplicate Conflict Detection    ✅ Complete
Temporal Ordering               ✅ Complete
Identity Resolution              ✅ Complete
Transaction Conflict Resolution  ✅ Complete
Partial Data Handling            ✅ Complete
Audit Logging                    ✅ Complete
Replay                           ✅ Complete
Automated Tests                  ✅ Complete
Dashboard                        ✅ Complete
Swagger API                      ✅ Complete
Stitch UI Design                 ✅ Complete
UI/API Integration               🔄 Final Integration
```

---

# 🚀 Quick Start

For the fastest demo:

```bash
python -m uvicorn backend.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/dashboard
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Run replay:

```bash
python replay.py --replay
```

Expected replay result:

```text
REPLAY PASS
```

---

# 👥 Project

**Project:** TraceX

**Title:** Real-Time Financial Transaction Anomaly Detection with Temporal Replay and Identity Resolution

**Type:** Hackathon Prototype

**Execution:** Local

**Backend:** Python + FastAPI

**Database:** SQLite

**Machine Learning:** Scikit-learn Isolation Forest

**UI:** Stitch-generated frontend

---

# 📄 License

This project is developed as a hackathon prototype.

The transaction data used for demonstration is synthetic and should not be treated as real financial data.

No real banking credentials, financial accounts, or production financial-system integrations are required.