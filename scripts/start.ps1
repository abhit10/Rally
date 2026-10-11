$ErrorActionPreference = 'Stop'
$racketRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $racketRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { throw 'Create the Python 3.12 virtual environment first. See README.md.' }
if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) { throw 'Build the dashboard first with npm run build in frontend.' }
& .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
