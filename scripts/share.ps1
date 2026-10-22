<#
.SYNOPSIS
  Shares PlaceIQ on a temporary public https link (Cloudflare quick tunnel,
  free, no account), with private passwords instead of the demo ones.

.DESCRIPTION
  1. Checks Docker.
  2. Creates .env.public (git-ignored) with a random JWT secret and random
     admin and student passwords the first time. Open that file to see the
     passwords; they are never printed.
  3. Starts the Docker stack in PUBLIC_MODE: strong secrets required, demo
     passwords replaced, login rate limit on.
  4. Starts `cloudflared tunnel --url http://localhost:8080` and prints the
     public https://....trycloudflare.com address.

  The link lasts until you stop it, and a new address is made each time.
  Stop with:  .\scripts\share.ps1 -Stop
  (ends the tunnel, restores the demo passwords for local use, stops the stack)

.PARAMETER Stop
  Stop sharing.
.PARAMETER Yes
  Don't ask before downloading cloudflared.
#>
param([switch]$Stop, [switch]$Yes)

$ErrorActionPreference = "Continue"
$Root = Split-Path $PSScriptRoot -Parent
$Run = Join-Path $Root ".run"
$EnvPublic = Join-Path $Root ".env.public"
$Tools = Join-Path $Root "tools"
$Health = "http://127.0.0.1:8080/api/health"
$CloudflaredUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host ""; Write-Host "Sharing did not start: $msg" -ForegroundColor Red; exit 1 }
function Test-Up { try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $Health).StatusCode -eq 200 } catch { $false } }

Set-Location $Root
New-Item -ItemType Directory -Force $Run | Out-Null
$compose = @("compose", "--env-file", $EnvPublic)

if ($Stop) {
    $pidFile = Join-Path $Run "cloudflared.pid"
    if (Test-Path $pidFile) {
        taskkill /PID (Get-Content $pidFile) /T /F 2>&1 | Out-Null
        Remove-Item $pidFile
        Write-Host "Stopped the tunnel. The public link no longer works."
    }
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        if (Test-Up) {
            docker exec placeiq_app python /app/docker/set_passwords.py --demo
        }
        docker @compose down 2>&1 | Out-Null
        Write-Host "Stopped PlaceIQ. Next local start uses the demo passwords again."
    }
    exit 0
}

# --- 1. Docker --------------------------------------------------------------------
Step "Checking Docker"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail "Docker is not installed. Install Docker Desktop (free for personal and education use) and run this again." }
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Docker Desktop is not running. Start it, wait until it shows 'Engine running', then run this again." }

# --- 2. Private secrets (generated once, never printed) ---------------------------
if (-not (Test-Path $EnvPublic)) {
    Step "Creating .env.public with a random JWT secret and passwords (git-ignored)"
    Add-Type -AssemblyName System.Security
    function New-Secret($bytes) {
        $b = New-Object byte[] $bytes
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
        # URL-safe text, no characters that need quoting in an env file
        return ([Convert]::ToBase64String($b)).Replace("+", "-").Replace("/", "_").TrimEnd("=")
    }
    @(
        "# Secrets for the PUBLIC instance (scripts/share.ps1). Git-ignored: never commit it.",
        "# Log in on the public link with these. Delete this file to get new ones.",
        "PUBLIC_MODE=1",
        "JWT_SECRET_KEY=$(New-Secret 48)",
        "ADMIN_PASSWORD=$(New-Secret 12)",
        "STUDENT_PASSWORD=$(New-Secret 12)"
    ) | Set-Content -Path $EnvPublic -Encoding ascii
}

# --- 3. Stack in public mode --------------------------------------------------------
if ((Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) -and
    -not (docker ps --filter "name=placeiq_app" --format "{{.Names}}")) {
    Fail "port 8080 is used by another program (perhaps start.ps1; stop it with .\stop.ps1)."
}
Step "Starting PlaceIQ in public mode"
docker @compose up -d --build 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "docker compose could not start the stack." }
$deadline = (Get-Date).AddMinutes(15)
while (-not (Test-Up)) {
    if ((Get-Date) -gt $deadline) { Fail "PlaceIQ did not become ready (docker logs placeiq_app)." }
    Start-Sleep -Seconds 3
}

# --- 4. cloudflared ---------------------------------------------------------------------
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) { $cloudflared = Join-Path $Tools "cloudflared.exe" }
if (-not (Test-Path $cloudflared)) {
    Write-Host ""
    Write-Host "cloudflared (Cloudflare's free tunnel client, no account needed) is not installed."
    Write-Host "It will be downloaded from Cloudflare's official GitHub release page:"
    Write-Host "  $CloudflaredUrl"
    Write-Host "into $Tools (git-ignored)."
    if (-not $Yes) {
        $answer = Read-Host "Download it now? [y/N]"
        if ($answer -notmatch '^(y|yes)$') { Fail "cloudflared is needed for the public link. Install it yourself (winget install Cloudflare.cloudflared) or answer y." }
    }
    New-Item -ItemType Directory -Force $Tools | Out-Null
    # curl.exe (built into Windows 10+) rather than Invoke-WebRequest, which
    # in Windows PowerShell 5.1 once stopped early and left a truncated .exe.
    curl.exe -fL --retry 3 --progress-bar -o $cloudflared $CloudflaredUrl
}
# A broken or partial download can't run: check before relying on it.
& $cloudflared --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Remove-Item $cloudflared -ErrorAction SilentlyContinue
    Fail "cloudflared did not run (incomplete download?). It was deleted; run this script again."
}

Step "Opening the tunnel"
$log = Join-Path $Run "cloudflared.log"
Remove-Item $log -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $cloudflared -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://localhost:8080" `
    -WindowStyle Hidden -PassThru -RedirectStandardError $log -RedirectStandardOutput (Join-Path $Run "cloudflared.out.log")
Set-Content -Path (Join-Path $Run "cloudflared.pid") -Value $p.Id

$url = $null
$deadline = (Get-Date).AddSeconds(60)
while (-not $url -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
    # The link is https://<random-words>.trycloudflare.com. The log also
    # mentions https://api.trycloudflare.com, Cloudflare's API, which is not it.
    $m = Select-String -Path $log -Pattern "https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value }
    if (Select-String -Path $log -Pattern "failed to request quick Tunnel" -Quiet -ErrorAction SilentlyContinue) { break }
}
if (-not $url) {
    taskkill /PID $p.Id /T /F 2>&1 | Out-Null
    Remove-Item (Join-Path $Run "cloudflared.pid") -ErrorAction SilentlyContinue
    Fail "Cloudflare did not create a tunnel (see .run\cloudflared.log; often a network or firewall block on api.trycloudflare.com). Try again in a minute. PlaceIQ is still running locally; stop it with .\scripts\share.ps1 -Stop."
}

Set-Content -Path (Join-Path $Run "share-url.txt") -Value $url
Write-Host ""
Write-Host "PlaceIQ is public at:  $url" -ForegroundColor Green
Write-Host "Log in with the passwords in .env.public (demo passwords are disabled)."
Write-Host "Anyone with the link can reach the login page. Stop sharing with:  .\scripts\share.ps1 -Stop"
