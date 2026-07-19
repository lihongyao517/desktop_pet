param(
    [switch]$StartWithWindows,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installDir = Join-Path $env:LOCALAPPDATA "CodexTrafficLight"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Codex Traffic Light.lnk"
$distUi = Join-Path $sourceRoot "dist\CodexTrafficLight.exe"
$distHook = Join-Path $sourceRoot "dist\CodexTrafficLightHook.exe"

New-Item -ItemType Directory -Path $installDir -Force | Out-Null

$mode = "source"
if ((Test-Path -LiteralPath $distUi) -and (Test-Path -LiteralPath $distHook)) {
    Copy-Item -LiteralPath $distUi -Destination (Join-Path $installDir "CodexTrafficLight.exe") -Force
    Copy-Item -LiteralPath $distHook -Destination (Join-Path $installDir "CodexTrafficLightHook.exe") -Force
    $uiTarget = Join-Path $installDir "CodexTrafficLight.exe"
    $hookTarget = Join-Path $installDir "CodexTrafficLightHook.exe"
    $uiArguments = ""
    $mode = "exe"
} else {
    $python = (Get-Command python -ErrorAction Stop).Source
    $pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
    if (-not (Test-Path -LiteralPath $pythonw)) {
        $pythonw = $python
    }
    Copy-Item -LiteralPath (Join-Path $sourceRoot "codex_traffic_light") -Destination $installDir -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $sourceRoot "main.py") -Destination $installDir -Force
    Copy-Item -LiteralPath (Join-Path $sourceRoot "hook_main.py") -Destination $installDir -Force
    $uiTarget = $pythonw
    $uiArguments = '"' + (Join-Path $installDir "main.py") + '"'
    $hookTarget = $python
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $uiTarget
$shortcut.Arguments = $uiArguments
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $uiTarget
$shortcut.Description = "Codex task status traffic light"
$shortcut.Save()

if ($mode -eq "exe") {
    & $hookTarget --install-hooks | Out-Host
} else {
    & $hookTarget (Join-Path $installDir "hook_main.py") --install-hooks | Out-Host
}

if ($StartWithWindows) {
    Push-Location -LiteralPath $installDir
    try {
        if ($mode -eq "exe") {
            $startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
            New-Item -ItemType Directory -Path $startupDir -Force | Out-Null
            $startupFile = Join-Path $startupDir "CodexTrafficLight.vbs"
            $escaped = ('"' + $uiTarget + '"').Replace('"', '""')
            @(
                'Set shell = CreateObject("WScript.Shell")'
                "shell.Run `"$escaped`", 0, False"
            ) | Set-Content -LiteralPath $startupFile -Encoding UTF8
        } else {
            & $hookTarget -c "from codex_traffic_light.startup import set_start_with_windows; set_start_with_windows(True)"
        }
    } finally {
        Pop-Location
    }
}

if (-not $NoLaunch) {
    if ($mode -eq "exe") {
        Start-Process -FilePath $uiTarget -WorkingDirectory $installDir
    } else {
        Start-Process -FilePath $uiTarget -ArgumentList $uiArguments -WorkingDirectory $installDir
    }
}

Write-Host ""
Write-Host "Codex Traffic Light installed." -ForegroundColor Green
Write-Host "Desktop shortcut: $shortcutPath"
Write-Host "Install folder:   $installDir"
Write-Host "Open /hooks in Codex once and trust 'Codex Traffic Light status bridge'." -ForegroundColor Yellow

