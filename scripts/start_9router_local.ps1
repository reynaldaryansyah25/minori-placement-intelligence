# Only changes the listener address; model, provider, and credential files are untouched.
[CmdletBinding()]
param([string]$RouterCli = "$env:APPDATA/npm/node_modules/9router/cli.js")
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $RouterCli -PathType Leaf)) { throw 'Installed 9Router CLI not found.' }
$nodeExecutable = (Get-Command node.exe -ErrorAction Stop).Source
$routerDirectory = Split-Path -Parent (Resolve-Path -LiteralPath $RouterCli).Path
$routerListener = Get-NetTCPConnection -State Listen -LocalPort 20128 -ErrorAction SilentlyContinue
if ($routerListener -and @($routerListener | Where-Object LocalAddress -ne '127.0.0.1').Count -eq 0) {
    Write-Output '9Router already listens on localhost only.'
    return
}
foreach ($routerPid in @($routerListener.OwningProcess | Select-Object -Unique)) {
    if (-not $routerPid) { continue }
    $routerProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$routerPid"
    if ($routerProcess.Name -ne 'node.exe' -or $routerProcess.CommandLine -notmatch '9router[\\/]app[\\/]') {
        throw 'Port 20128 belongs to an unrecognized process; nothing stopped.'
    }
    $routerParent = Get-CimInstance Win32_Process -Filter "ProcessId=$($routerProcess.ParentProcessId)"
    if ($routerParent -and $routerParent.CommandLine -match '9router[\\/]cli.js') {
        Stop-Process -Id $routerParent.ProcessId -ErrorAction Stop
    }
    if (Get-Process -Id $routerPid -ErrorAction SilentlyContinue) { Stop-Process -Id $routerPid -ErrorAction Stop }
}
$routerLogDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'test-results'
New-Item -ItemType Directory -Force -Path $routerLogDirectory | Out-Null
Start-Process -FilePath $nodeExecutable -ArgumentList @("`"$RouterCli`"", '--host', '127.0.0.1', '--port', '20128', '--no-browser', '--skip-update') -WorkingDirectory $routerDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $routerLogDirectory '9router-local-start.log') -RedirectStandardError (Join-Path $routerLogDirectory '9router-local-start-error.log') | Out-Null
Write-Output '9Router started with --host 127.0.0.1. Verify host and Docker connectivity before publishing.'
