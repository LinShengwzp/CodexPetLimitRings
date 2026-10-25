#requires -version 5.1
# Persistent read-only Windows UI Automation watcher for the Codex Mini image.
# ASCII-only file deliberately supports Windows PowerShell 5.1 without a BOM.
# It prints newline-delimited JSON containing only HWND, bbox, and status.
param(
    [Parameter(Mandatory = $true)][long]$HostHwnd,
    [ValidateRange(150, 5000)][int]$IntervalMs = 300
)
$ErrorActionPreference = "Stop"
try {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    Add-Type -AssemblyName WindowsBase
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class CodexPetDpi {
    [DllImport("user32.dll", SetLastError=true)]
    public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr value);
}
"@
    [void][CodexPetDpi]::SetThreadDpiAwarenessContext([IntPtr](-4))
} catch {
    # If DPI context setup fails, the Python parent will prefer other sources.
}

# Windows PowerShell 5.1 stdout defaults to a legacy console encoding. JSON
# values are all ASCII numbers/status codes so a mismatch cannot leak strings.
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$imageType = [System.Windows.Automation.ControlType]::Image
$name = "GPT" + [char]0x5A18 + " " + [char]0x865A + [char]0x62DF + [char]0x5BA0 + [char]0x7269
$byName = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, $name)
$byType = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty, $imageType)
$exact = [System.Windows.Automation.AndCondition]::new($byName, $byType)
$handle = [IntPtr]$HostHwnd
$cached = $null

function Get-Bounds($element) {
    if ($null -eq $element) { return $null }
    try {
        $info = $element.Current
        $rect = $info.BoundingRectangle
        $class = [string]$info.ClassName
        $n = [string]$info.Name
        if ($info.IsOffscreen -or $rect.IsEmpty -or
            $rect.Width -lt 40 -or $rect.Width -gt 800 -or
            $rect.Height -lt 40 -or $rect.Height -gt 800) { return $null }
        if ($info.ControlType -ne $imageType) { return $null }
        if ($n -ne $name -and -not $class.StartsWith("codex-avatar-button")) { return $null }
        return [ordered]@{
            status = "ok"
            hwnd = $HostHwnd
            left = [int][Math]::Round($rect.Left)
            top = [int][Math]::Round($rect.Top)
            right = [int][Math]::Round($rect.Right)
            bottom = [int][Math]::Round($rect.Bottom)
            source = "uia-image"
        }
    } catch {
        return $null
    }
}

while ($true) {
    try {
        # A cached image element normally supports cheap BoundingRectangle
        # reads. Re-discover only if it has gone stale or is hidden.
        $result = Get-Bounds $cached
        if ($null -eq $result) {
            $root = [System.Windows.Automation.AutomationElement]::FromHandle($handle)
            if ($null -ne $root) {
                $cached = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $exact)
                $result = Get-Bounds $cached
                if ($null -eq $result) {
                    # Localization might change the Name but keep the class.
                    $images = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $byType)
                    for ($i = 0; $i -lt $images.Count; $i++) {
                        $candidate = Get-Bounds $images.Item($i)
                        if ($null -ne $candidate) {
                            $cached = $images.Item($i)
                            $result = $candidate
                            break
                        }
                    }
                }
            }
        }
        if ($null -eq $result) {
            # Chromium may lazily activate UIA only after a point query.
            # When the cursor happens to be over the pet, FromPoint is the
            # exact mechanism already validated in Find-PetUIA.ps1.
            try {
                $cursor = [System.Windows.Forms.Cursor]::Position
                $point = [System.Windows.Point]::new([double]$cursor.X, [double]$cursor.Y)
                $hit = [System.Windows.Automation.AutomationElement]::FromPoint($point)
                $result = Get-Bounds $hit
                if ($null -ne $result) { $cached = $hit }
            } catch { }
        }
        if ($null -eq $result) {
            [Console]::Out.WriteLine('{"status":"not_found"}')
        } else {
            [Console]::Out.WriteLine(($result | ConvertTo-Json -Compress -Depth 3))
        }
    } catch {
        $cached = $null
        [Console]::Out.WriteLine('{"status":"unavailable"}')
    }
    [Console]::Out.Flush()
    Start-Sleep -Milliseconds $IntervalMs
}
