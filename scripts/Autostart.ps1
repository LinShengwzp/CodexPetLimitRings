#requires -version 5.1
# Opt-in autostart of a hidden Python/Tk watcher at Windows user sign-in.
# Only the per-user Startup shortcut is affected. No admin privileges.
[CmdletBinding()]
param(
    [ValidateSet('Install', 'Remove', 'Status')]
    [string]$Mode = 'Status'
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$main = Join-Path $repo 'main.py'
$startup = [Environment]::GetFolderPath('Startup')
if (-not $startup) { throw 'Unable to locate the per-user Startup folder.' }
$shortcutPath = Join-Path $startup 'Codex Pet Limit Rings.lnk'
$wsh = New-Object -ComObject WScript.Shell

function Test-OurShortcut($shortcut) {
    if ($null -eq $shortcut) { return $false }
    $arguments = [string]$shortcut.Arguments
    return ($arguments -match '(?i)codexpetlimitrings.*main\.py' -or
        [string]::Equals($arguments.Trim('"'), $main, [StringComparison]::OrdinalIgnoreCase))
}

if ($Mode -eq 'Status') {
    if (Test-Path -LiteralPath $shortcutPath) {
        $lnk = $wsh.CreateShortcut($shortcutPath)
        Write-Host 'Autostart: installed'
        Write-Host "Shortcut: $shortcutPath"
        Write-Host "Executable: $($lnk.TargetPath)"
        Write-Host "Arguments: $($lnk.Arguments)"
    } else {
        Write-Host 'Autostart: not installed'
    }
    exit 0
}

if ($Mode -eq 'Remove') {
    if (-not (Test-Path -LiteralPath $shortcutPath)) {
        Write-Host 'Autostart already removed.'
        exit 0
    }
    $lnk = $wsh.CreateShortcut($shortcutPath)
    if (-not (Test-OurShortcut $lnk)) {
        throw "Refusing to delete an unrecognized shortcut: $shortcutPath"
    }
    Remove-Item -LiteralPath $shortcutPath
    Write-Host 'Removed user autostart shortcut. Running ring process is unaffected.'
    exit 0
}

if (-not (Test-Path -LiteralPath $main)) {
    throw "Cannot find application entrypoint: $main"
}
if (Test-Path -LiteralPath $shortcutPath) {
    $lnk = $wsh.CreateShortcut($shortcutPath)
    if (-not (Test-OurShortcut $lnk)) {
        throw "Refusing to overwrite an unrelated Startup shortcut: $shortcutPath"
    }
}

$candidates = @(
    (Join-Path $repo '.venv\Scripts\pythonw.exe'),
    (Join-Path $env:USERPROFILE 'anaconda3\pythonw.exe')
)
if ($env:VIRTUAL_ENV) { $candidates = @((Join-Path $env:VIRTUAL_ENV 'Scripts\pythonw.exe')) + $candidates }
if ($env:CONDA_PREFIX) { $candidates = @((Join-Path $env:CONDA_PREFIX 'pythonw.exe')) + $candidates }
$fromPath = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($fromPath) { $candidates += $fromPath.Source }
$pythonw = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $pythonw) { throw 'pythonw.exe not found. Install Python with tkinter and retry.' }

$link = $wsh.CreateShortcut($shortcutPath)
$link.TargetPath = $pythonw
$link.Arguments = '"' + $main + '"'
$link.WorkingDirectory = $repo
$link.Description = 'Show rings only while the native Codex Mini pet is visible'
$link.Save()

Write-Host "Installed user autostart: $shortcutPath"
Write-Host "Python: $pythonw"
Write-Host 'No system-wide startup setting or Codex installation was changed.'
Write-Host 'After next sign-in, the watcher stays hidden until Codex Mini appears.'
