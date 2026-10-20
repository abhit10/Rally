param([string]$AllowedOrigin = 'http://localhost:5173')
$ErrorActionPreference = 'Stop'
$demoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $demoRoot
$demoData = Join-Path $demoRoot 'data/demo'
New-Item -ItemType Directory -Force -Path $demoData | Out-Null
$keyPath = Join-Path $demoData 'access-key.txt'
if (-not (Test-Path -LiteralPath $keyPath)) {
    & .venv/Scripts/python.exe -c "import secrets,pathlib;pathlib.Path('data/demo/access-key.txt').write_text(secrets.token_urlsafe(32))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not create demo key.' }
}
$env:RALLY_DEMO_KEY = (Get-Content -Raw -LiteralPath $keyPath).Trim()
$env:RALLY_ALLOWED_ORIGINS = $AllowedOrigin.TrimEnd('/')
$env:RACKET_DATA = $demoData
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $demoData 'sessions.db').Replace('\','/')
$env:RACKET_WEIGHTS = Join-Path $demoRoot 'weights'
$env:QUEUE_MODE = 'local'
$env:SPORTS_CV_ENABLED = 'false'
& .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001 --no-access-log
exit $LASTEXITCODE
