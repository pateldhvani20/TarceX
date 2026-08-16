# TraceX — Real-Time Financial Transaction Anomaly Detection

TraceX is a real-time transaction intelligence and anomaly-detection platform. It processes transaction events through a deterministic backend pipeline, detects anomalous transactions using IsolationForest, resolves identity and transaction conflicts, maintains an audit trail, supports deterministic temporal replay, and exposes the results through a connected web dashboard.

## Features

- Real-time transaction ingestion through `POST /ingest`
- Duplicate and idempotent event handling
- Duplicate payload conflict detection
- SQLite transaction persistence
- Temporal ordering of events
- Identity resolution using user ID, email and phone
- Identity mismatch detection
- Transaction/source conflict resolution
- Configurable source priority
- IsolationForest anomaly detection
- Five-feature ML pipeline alignment
- Decision and reason generation
- JSON-line audit logging
- Deterministic replay
- FastAPI REST API
- Swagger/OpenAPI documentation
- Connected TraceX dashboard
- Backend health and statistics monitoring
- Automated backend test suite

## ML Model

The trained IsolationForest model expects exactly five numerical features:

```text
[amount, txn_frequency_24h, average_amount, category_code, merchant_code]
```

The model returns an anomaly classification:

```text
normal
anomalous
```

The trained model is located at:

```text
backend/core/model/anomaly_model.pkl
```

## Source Priority

Transaction conflicts are resolved using the configured source priority:

```text
BankA > CardY > WalletX > X
```

Conflicting transaction records are retained while the configured priority determines the effective resolution.

## Architecture

```text
Transaction Event
       |
       v
POST /ingest
       |
       v
Schema Validation
       |
       v
Duplicate / Idempotency Check
       |
       v
Raw Event Persistence
       |
       v
Temporal Ordering
       |
       +-----------------------+
       |                       |
       v                       v
Identity Resolution     Transaction Conflict
       |                 Resolution
       +-----------+-----------+
                   |
                   v
          IsolationForest Model
                   |
                   v
            Decision + Reason
                   |
             +-----+-----+
             |           |
             v           v
          SQLite      Audit Log
             |
             v
          REST API
             |
             v
        TraceX Dashboard
```

## Project Structure

```text
TarceX/
│
├── backend/
│   ├── core/
│   │   ├── model/
│   │   │   ├── adapter.py
│   │   │   ├── anomaly_model.pkl
│   │   │   └── train_model.py
│   │   └── pipelines.py
│   │
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── schemas.py
│   ├── persistence_repository.py
│   └── backend_persistence_repository.py
│
├── data/
│   └── state.db
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
│   ├── test_backend.py
│   ├── test_determinism.py
│   ├── test_edge_cases.py
│   ├── test_identity.py
│   ├── test_ingestion.py
│   └── test_replay.py
│
├── replay.py
├── README.md
└── requirements.txt
```

## Requirements

Recommended:

- Python 3.11+
- Node.js 18+ for the frontend
- npm

Python dependencies are listed in `requirements.txt`.

## Installation

### 1. Open the project root

PowerShell:

```powershell
cd D:\TraceX_hackathon\TarceX
```

**Important:** Run backend commands from the project root. Do not `cd backend` before starting Uvicorn.

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the Python commands without activating the environment, or use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 4. Install Python dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Running the Backend

From the project root:

```powershell
cd D:\TraceX_hackathon\TarceX
python -m uvicorn backend.main:app --reload
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

Keep this terminal running.

### Backend URLs

API:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

Dashboard backend route, if enabled:

```text
http://127.0.0.1:8000/dashboard
```

## Running the Frontend

Open a **second terminal**.

Go to the frontend directory:

```powershell
cd <your-frontend-folder>
```

Install frontend dependencies if needed:

```powershell
npm install
```

Start the development server:

```powershell
npm run dev
```

Open the Vite URL printed by the terminal, for example:

```text
http://127.0.0.1:5174
```

The TraceX UI should show:

```text
Backend Online
127.0.0.1:8000
```

when the FastAPI backend is running.

## Quick Start — Two Terminals

### Terminal 1 — Backend

```powershell
cd D:\TraceX_hackathon\TarceX
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload
```

### Terminal 2 — Frontend

```powershell
cd <your-frontend-folder>
npm install
npm run dev
```

Then open the frontend URL shown by Vite.

## API Endpoints

```text
GET  /
GET  /health
POST /ingest
GET  /stats
GET  /transactions
GET  /dashboard
```

## Test Backend Health

With the backend running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Test Backend Statistics

```powershell
Invoke-RestMethod http://127.0.0.1:8000/stats
```

## Test `/ingest`

You can test `/ingest` from Swagger:

```text
http://127.0.0.1:8000/docs
```

Open:

```text
POST /ingest
```

Click:

```text
Try it out
```

Paste:

```json
{
  "event_id": "final-demo-001",
  "timestamp": "2026-08-16T10:00:00Z",
  "source": "BankA",
  "user_id": "user-demo",
  "amount": 9999,
  "category": "shopping",
  "description": "Laptop purchase",
  "merchant": "Amazon",
  "status": "confirmed",
  "email": "demo@example.com",
  "phone": "9999999999"
}
```

Click:

```text
Execute
```

The response should contain the accepted event and the pipeline decision.

You can also test from PowerShell:

```powershell
$body = @{
    event_id = "final-demo-001"
    timestamp = "2026-08-16T10:00:00Z"
    source = "BankA"
    user_id = "user-demo"
    amount = 9999
    category = "shopping"
    description = "Laptop purchase"
    merchant = "Amazon"
    status = "confirmed"
    email = "demo@example.com"
    phone = "9999999999"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/ingest" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

## Backend Tests

Run all tests from the project root:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected:

```text
Ran 15 tests
OK
```

## Deterministic Replay

Run:

```powershell
python replay.py --replay
```

Expected:

```text
REPLAY PASS
```

Replay processes events through the same pipeline and checks deterministic behavior.

## Model Test

Run:

```powershell
python -c "from backend.core.model.adapter import predict; print(predict([9999,1,9999,5,10]))"
```

Expected form:

```text
('anomalous', <score>)
```

## Pipeline Import Test

Run:

```powershell
python -c "from backend.core.pipelines import process_event; print('PIPELINE OK')"
```

Expected:

```text
PIPELINE OK
```

## Audit Log

View the latest audit entries:

```powershell
Get-Content .\logsudit.log -Tail 10
```

## Useful Verification Commands

Check Python version:

```powershell
python --version
```

Check installed dependencies:

```powershell
pip list
```

Check whether the backend port is being used:

```powershell
netstat -ano | findstr :8000
```

Check frontend port:

```powershell
netstat -ano | findstr :5174
```

## Dashboard Pages

The connected TraceX UI contains:

### Overview
- Total events
- Decisions
- Anomalies
- Identity conflicts
- Transaction activity
- Decision distribution
- Live decision feed
- Signal snapshot

### Transactions
Displays persisted transaction records:

- Event
- User
- Source
- Amount
- Merchant
- Decision
- Time

### Anomaly Detection
Allows transaction submission and displays the actual backend decision.

### Identity Resolution
Displays identity signals and detected conflicts.

### Temporal Replay
Displays events chronologically with their decision and reason.

### Audit Trail
Displays persisted decisions and explanations.

### System Health
Displays:

- Backend status
- `/health`
- `/stats`
- `/transactions`
- `/ingest`
- API base URL

## Recommended Hackathon Demo

Use this sequence:

```text
1. Start backend
2. Start frontend
3. Open Overview
4. Show live statistics
5. Open Anomaly Detection
6. Submit a high-value transaction
7. Show anomalous/normal decision from backend
8. Open Transactions
9. Open Identity Resolution
10. Open Temporal Replay
11. Open Audit Trail
12. Open System Health
13. Show backend tests
14. Run replay and show REPLAY PASS
```

## Final Backend Verification

Run these commands before submission:

```powershell
cd D:\TraceX_hackathon\TarceX

python -m unittest discover -s tests -p "test_*.py" -v

python replay.py --replay

python -c "from backend.core.model.adapter import predict; print(predict([9999,1,9999,5,10]))"

python -c "from backend.core.pipelines import process_event; print('PIPELINE OK')"
```

Then start the server:

```powershell
python -m uvicorn backend.main:app --reload
```

In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/stats
```

## Final Checklist

- [x] FastAPI backend
- [x] IsolationForest anomaly detection
- [x] Five-feature model alignment
- [x] Transaction ingestion
- [x] Duplicate/idempotency handling
- [x] Identity resolution
- [x] Identity mismatch detection
- [x] Source-priority conflict resolution
- [x] Temporal ordering
- [x] Deterministic replay
- [x] SQLite persistence
- [x] Audit log
- [x] REST APIs
- [x] Automated tests
- [x] Connected frontend
- [x] Overview
- [x] Transactions
- [x] Anomaly Detection
- [x] Identity Resolution
- [x] Temporal Replay
- [x] Audit Trail
- [x] System Health

## Demo Scope

TraceX is a hackathon/demo system. It uses synthetic transaction data and does not require real banking credentials, real customer accounts, or production financial-system integrations.
