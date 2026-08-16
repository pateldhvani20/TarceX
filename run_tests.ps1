# Run TraceX unit tests from the project root (TarceX).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m unittest discover -s tests -p "test_*.py" -v
