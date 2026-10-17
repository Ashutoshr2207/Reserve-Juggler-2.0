param(
    [int]$Port = 8000,
    [switch]$Foreground
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv-win\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    $projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Create a Windows environment and install requirements-dev.txt first. See HANDOVER.md.'
}
if ($Foreground) {
    & $projectPython server.py --port $Port
    exit $LASTEXITCODE
}

$applicationUrl = "http://127.0.0.1:$Port"
function Test-ApplicationHealth {
    try {
        $health = Invoke-RestMethod -Uri "$applicationUrl/api/health" -TimeoutSec 2
        return $health.status -eq 'ok' -and $health.mode -eq 'simulation'
    } catch {
        return $false
    }
}

if (Test-ApplicationHealth) {
    Write-Output "Reserve Juggler is already running: $applicationUrl"
    return
}

$runtimePath = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
$serverPath = Join-Path $PSScriptRoot 'server.py'
$serverProcess = Start-Process -FilePath $projectPython `
    -ArgumentList @('"' + $serverPath + '"', '--port', $Port) `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtimePath 'server.stdout.log') `
    -RedirectStandardError (Join-Path $runtimePath 'server.stderr.log')

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if (Test-ApplicationHealth) {
        $serverProcess.Id | Set-Content -LiteralPath (Join-Path $runtimePath 'server.pid')
        Write-Output "Reserve Juggler is running: $applicationUrl (PID $($serverProcess.Id))"
        Write-Output 'The server runs in the background. Logs are in .runtime.'
        return
    }
    if ($serverProcess.HasExited) {
        throw 'Server startup failed. See .runtime/server.stderr.log.'
    }
    Start-Sleep -Milliseconds 500
}
throw 'Server did not become ready in time. See .runtime/server.stderr.log.'
