<#
.SYNOPSIS
  Stops what start.ps1 started: the app, the ML service and the database
  container. Data is kept (it lives in a Docker volume).

.PARAMETER KeepDb
  Leave the database container running.
#>
param([switch]$KeepDb)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
$Run = Join-Path $Root ".run"
Set-Location $Root

foreach ($name in "app", "ml") {
    $pidFile = Join-Path $Run "$name.pid"
    if (Test-Path $pidFile) {
        $id = (Get-Content $pidFile | Select-Object -First 1).Trim()
        # /T kills the whole tree: a venv's python.exe is a launcher whose
        # child is the real server, and that child holds the port.
        taskkill /PID $id /T /F 2>&1 | Out-Null
        Remove-Item $pidFile
        Write-Host "Stopped $name (process tree $id)"
    }
}

if (-not $KeepDb) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            docker compose -f docker-compose.yml -f docker-compose.dev.yml stop db 2>&1 | Out-Null
            Write-Host "Stopped the database container (data kept)"
        } else {
            Write-Host "Docker is not running, so the database container is already stopped."
        }
    }
}
Write-Host "PlaceIQ stopped."
