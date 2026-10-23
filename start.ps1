<#
.SYNOPSIS
  Starts PlaceIQ from this machine's Python virtualenvs and opens
  http://localhost:8080 (the fallback to "docker compose up").

.DESCRIPTION
  Postgres still runs in Docker (published on 127.0.0.1:5432 only, via
  docker-compose.dev.yml); the ML service and the app (API + built UI) run
  from .venv-ml and .venv-backend. The ML service listens on 127.0.0.1 only.
  Stop everything with .\stop.ps1.

  First run: generates a JWT secret into the git-ignored .env, builds the UI
  if frontend\dist is missing, applies the schema and loads the synthetic
  data if the database is empty.

.PARAMETER NoBrowser
  Don't open the browser at the end.
#>
param([switch]$NoBrowser)

# Native tools (docker, npm) write progress to stderr; with "Stop", Windows
# PowerShell 5.1 would treat that as a failure. Exit codes are checked instead.
$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
$Run = Join-Path $Root ".run"
$Url = "http://localhost:8080"
$Health = "http://127.0.0.1:8080/api/health"

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) {
    Write-Host ""
    Write-Host "PlaceIQ did not start: $msg" -ForegroundColor Red
    exit 1
}
function Test-Up($u) {
    try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $u).StatusCode -eq 200 } catch { $false }
}

Set-Location $Root
New-Item -ItemType Directory -Force $Run | Out-Null

# --- 1. Docker (Postgres runs in it) -------------------------------------------
Step "Checking Docker"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker is not installed. Install Docker Desktop (free for personal and education use) from https://www.docker.com/products/docker-desktop/ and run this again."
}
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "Docker Desktop is not running. Start it, wait until it shows 'Engine running', then run .\start.ps1 again."
}

# --- 2. Already running? Port free? -----------------------------------------------
if (Test-Up $Health) {
    Write-Host "PlaceIQ is already running at $Url" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $Url }
    exit 0
}
if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) {
    Fail "port 8080 is used by another program. If it is the Docker version of PlaceIQ, stop it with 'docker compose down' first."
}

# --- 3. Virtualenvs ---------------------------------------------------------------
$Py = @{
    db      = Join-Path $Root ".venv-db\Scripts\python.exe"
    backend = Join-Path $Root ".venv-backend\Scripts\python.exe"
    ml      = Join-Path $Root ".venv-ml\Scripts\python.exe"
}
foreach ($k in $Py.Keys) {
    if (-not (Test-Path $Py[$k])) {
        Fail "the virtualenv .venv-$k is missing. Create it as described in README.md (Setup without Docker), or use 'docker compose up -d --build' instead."
    }
}

# --- 4. JWT secret in the git-ignored .env (generated, never printed) -------------
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) { Copy-Item (Join-Path $Root ".env.example") $EnvFile }
$lines = @(Get-Content $EnvFile)
$secretLine = $lines | Where-Object { $_ -match '^JWT_SECRET_KEY=' } | Select-Object -First 1
if (-not $secretLine -or $secretLine -match '^JWT_SECRET_KEY=(replace_with_a_long_random_secret)?\s*$') {
    Step "Generating a JWT secret into .env (git-ignored)"
    $secret = & $Py.backend -c "import secrets; print(secrets.token_urlsafe(64))"
    $lines = @($lines | Where-Object { $_ -notmatch '^JWT_SECRET_KEY=' }) + "JWT_SECRET_KEY=$secret"
    Set-Content -Path $EnvFile -Value $lines -Encoding ascii
    Remove-Variable secret
}

# --- 5. Database ------------------------------------------------------------------
Step "Starting the database container"
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "could not start the database container ('docker compose ... up -d db' failed)." }
$deadline = (Get-Date).AddSeconds(90)
while ((docker inspect -f "{{.State.Health.Status}}" placement_db 2>$null) -ne "healthy") {
    if ((Get-Date) -gt $deadline) { Fail "the database container did not become healthy within 90 seconds." }
    Start-Sleep -Seconds 2
}
& $Py.db (Join-Path $Root "docker\init_db.py")
if ($LASTEXITCODE -ne 0) { Fail "preparing the database failed (see the messages above)." }

# --- 6. Built UI ------------------------------------------------------------------
# Built when missing, and rebuilt when any frontend source is newer than the
# build: serving a stale build after a UI change would show old code (or, as
# happened once, call an API address that no longer exists).
$distIndex = Join-Path $Root "frontend\dist\index.html"
$needBuild = -not (Test-Path $distIndex)
if (-not $needBuild) {
    $builtAt = (Get-Item $distIndex).LastWriteTime
    $sources = @(Get-ChildItem (Join-Path $Root "frontend\src"), (Join-Path $Root "frontend\public") -Recurse -File -ErrorAction SilentlyContinue) +
               @(Get-Item (Join-Path $Root "frontend\index.html"), (Join-Path $Root "frontend\package.json"),
                          (Join-Path $Root "frontend\vite.config.js"), (Join-Path $Root "frontend\.env") -ErrorAction SilentlyContinue)
    $needBuild = [bool]($sources | Where-Object { $_.LastWriteTime -gt $builtAt } | Select-Object -First 1)
}
if ($needBuild) {
    Step "Building the UI (first run, or the UI changed since the last build)"
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Fail "frontend\dist is missing and Node.js is not installed to build it. Install Node.js LTS from https://nodejs.org/ or use 'docker compose up -d --build'."
    }
    Push-Location (Join-Path $Root "frontend")
    npm ci --no-audit --no-fund 2>&1 | Out-Null
    npm run build 2>&1 | Out-Null
    $built = $LASTEXITCODE -eq 0
    Pop-Location
    if (-not $built) { Fail "the UI build failed. Run 'npm run build' in frontend\ to see why." }
}

# --- 7. ML service and app ---------------------------------------------------------
function Start-PlaceIQProcess($name, $python, $script, $dir) {
    $p = Start-Process -FilePath $python -ArgumentList $script -WorkingDirectory $dir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $Run "$name.log") -RedirectStandardError (Join-Path $Run "$name.err.log")
    Set-Content -Path (Join-Path $Run "$name.pid") -Value $p.Id
    return $p
}
Step "Starting the ML service (127.0.0.1:6000, internal)"
$ml = Start-PlaceIQProcess "ml" $Py.ml "app.py" (Join-Path $Root "ml-service")
Step "Starting the app on $Url"
$app = Start-PlaceIQProcess "app" $Py.backend "serve.py" (Join-Path $Root "backend")

$deadline = (Get-Date).AddSeconds(60)
while (-not (Test-Up $Health)) {
    if ($app.HasExited -or (Get-Date) -gt $deadline) {
        Write-Host (Get-Content (Join-Path $Run "app.err.log") -Tail 15 -ErrorAction SilentlyContinue | Out-String)
        Fail "the app did not answer on $Health (log above, full logs in .run\). Stop leftovers with .\stop.ps1."
    }
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "PlaceIQ is running at $Url" -ForegroundColor Green
Write-Host "Stop it with .\stop.ps1   (logs: .run\)"
if (-not $NoBrowser) { Start-Process $Url }
