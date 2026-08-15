from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
FIXTURE_DIR = BASE_DIR / "fixtures"
MODEL_DIR = BASE_DIR / "backend" / "core" / "model"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

db_path = DATA_DIR / "state.db"
audit_log_path = LOG_DIR / "audit.log"
model_path = MODEL_DIR / "anomaly_model.pkl"

SOURCE_PRIORITY = [
    "BankA",
    "CardY",
    "WalletX",
    "X",
]

CONFLICT_WINDOW_SECONDS = 60