# Always start TraceX FastAPI from the project root (TarceX),
# never from the backend/ subdirectory.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
