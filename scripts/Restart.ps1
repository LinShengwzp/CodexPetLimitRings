#requires -version 5.1
# Spawn a fresh rings instance only after the requesting instance has exited.
# Invoked by its own right-click menu; never terminates a process.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateRange(1, 2147483647)][int]$WaitPid,
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [Parameter(Mandatory = $true)][string]$MainPath
)
$ErrorActionPreference = 'Stop'
$logDir = Join-Path $env:LOCALAPPDATA 'CodexPetLimitRings'
$logFile = Join-Path $logDir 'restart-last-error.txt'
try {
    # Avoid an immediate single-instance mutex collision. Do not kill the
    # running application; Tk will exit normally after starting this helper.
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while ([DateTime]::UtcNow -lt $deadline) {
        $old = Get-Process -Id $WaitPid -ErrorAction SilentlyContinue
        if ($null -eq $old) { break }
        Start-Sleep -Milliseconds 150
    }
    if ($null -ne (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue)) {
        throw "Old rings process $WaitPid did not exit within 20 seconds."
    }
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw "Python executable not found: $PythonPath"
    }
    if (-not (Test-Path -LiteralPath $MainPath -PathType Leaf)) {
        throw "main.py not found: $MainPath"
    }
    $work = Split-Path -Parent $MainPath
    Start-Process -FilePath $PythonPath -ArgumentList ('"' + $MainPath + '"') -WorkingDirectory $work | Out-Null
    if (Test-Path -LiteralPath $logFile) {
        Remove-Item -LiteralPath $logFile -Force -ErrorAction SilentlyContinue
    }
} catch {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    [string]$_ | Set-Content -LiteralPath $logFile -Encoding UTF8
    exit 1
}
