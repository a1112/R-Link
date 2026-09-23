param([string]$DesktopPath)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not $DesktopPath) {
    $candidates = @(
        (Join-Path $projectRoot '.repository-consolidation-local/bin/R-Link.exe'),
        (Join-Path $projectRoot 'apps/r-link-web/src-tauri/target/release/rlink-tauri.exe'),
        (Join-Path $projectRoot 'apps/r-link-web/src-tauri/target/debug/rlink-tauri.exe')
    )
    $DesktopPath = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $DesktopPath -or -not (Test-Path -LiteralPath $DesktopPath -PathType Leaf)) {
    throw 'Build the desktop app first, or pass -DesktopPath with its executable path.'
}
$DesktopPath = (Resolve-Path -LiteralPath $DesktopPath).Path
function Test-RLinkService {
    try {
        $identity = Invoke-RestMethod 'http://127.0.0.1:8210/' -TimeoutSec 2
        $health = Invoke-RestMethod 'http://127.0.0.1:8210/health' -TimeoutSec 2
        return $identity.name -eq 'R-Link-Server' -and $health.status -eq 'healthy'
    } catch { return $false }
}
if (-not (Test-RLinkService)) {
    if (Get-NetTCPConnection -State Listen -LocalPort 8210 -ErrorAction SilentlyContinue) {
        throw 'Port 8210 is occupied by an unrecognized or unhealthy service. No process was stopped.'
    }
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install server dependencies in .venv first.' }
    $logDirectory = Join-Path $projectRoot 'logs'
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $oldHost = $env:R_LINK_HOST
    $oldDev = $env:DEV
    try {
        $env:R_LINK_HOST = '127.0.0.1'
        $env:DEV = 'false'
        $serverProcess = Start-Process -FilePath $pythonPath -ArgumentList 'main.py' -WorkingDirectory (Join-Path $projectRoot 'R-Link-Server') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory "server-$stamp.log") -RedirectStandardError (Join-Path $logDirectory "server-$stamp-error.log")
    } finally {
        $env:R_LINK_HOST = $oldHost
        $env:DEV = $oldDev
    }
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if ($serverProcess.HasExited) { throw "Server exited. See $logDirectory/server-$stamp-error.log" }
        if (Test-RLinkService) { $ready = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Server is not ready. See $logDirectory/server-$stamp-error.log" }
    Write-Output "R-Link server started (PID $($serverProcess.Id)); logs: $logDirectory"
} else {
    Write-Output 'Reusing the healthy R-Link server at http://127.0.0.1:8210.'
}
# Hidden suppresses the debug executable's console; Tauri shows its own main window.
Start-Process -FilePath $DesktopPath -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
Write-Output 'R-Link desktop launched. Closing the window keeps it in the tray; use the tray menu to exit. The server runs independently.'
