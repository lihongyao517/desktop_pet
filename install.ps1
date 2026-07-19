param(
    [switch]$StartWithWindows,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installDir = Join-Path $env:LOCALAPPDATA "CodexDesktopPet"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Codex Desktop Pet.lnk"
$legacyShortcutPath = Join-Path $desktop "Codex Traffic Light.lnk"
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$legacyStartupFile = Join-Path $startupDir "CodexTrafficLight.vbs"
$migrateStartup = Test-Path -LiteralPath $legacyStartupFile
$distUi = Join-Path $sourceRoot "dist\CodexDesktopPet.exe"
$distHook = Join-Path $sourceRoot "dist\CodexDesktopPetHook.exe"
$installedUi = Join-Path $installDir "CodexDesktopPet.exe"
$sourceIcon = Join-Path $sourceRoot "assets\CodexDesktopPet.ico"
$installedIcon = Join-Path $installDir "CodexDesktopPet.ico"

$running = @(
    Get-Process -Name "CodexDesktopPet" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $installedUi }
)
if ($running.Count) {
    $running | Stop-Process -Force -ErrorAction SilentlyContinue
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 150
        $remaining = @(
            Get-Process -Name "CodexDesktopPet" -ErrorAction SilentlyContinue |
                Where-Object { $_.Path -eq $installedUi }
        )
    } while ($remaining.Count -and [DateTime]::UtcNow -lt $deadline)
    if ($remaining.Count) {
        throw "Unable to stop the running Codex Desktop Pet before update."
    }
}

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
if (Test-Path -LiteralPath $sourceIcon) {
    Copy-Item -LiteralPath $sourceIcon -Destination $installedIcon -Force
}

$mode = "source"
if ((Test-Path -LiteralPath $distUi) -and (Test-Path -LiteralPath $distHook)) {
    Copy-Item -LiteralPath $distUi -Destination $installedUi -Force
    Copy-Item -LiteralPath $distHook -Destination (Join-Path $installDir "CodexDesktopPetHook.exe") -Force
    $uiTarget = $installedUi
    $hookTarget = Join-Path $installDir "CodexDesktopPetHook.exe"
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
if (Test-Path -LiteralPath $installedIcon) {
    $shortcut.IconLocation = "$installedIcon,0"
} else {
    $shortcut.IconLocation = "$uiTarget,0"
}
$shortcut.Description = "Codex stick-figure desktop pet"
$shortcut.Save()
if (Test-Path -LiteralPath $legacyShortcutPath) {
    Remove-Item -LiteralPath $legacyShortcutPath -Force
}

if ($mode -eq "exe") {
    & $hookTarget --install-hooks | Out-Host
} else {
    & $hookTarget (Join-Path $installDir "hook_main.py") --install-hooks | Out-Host
}

if ($StartWithWindows -or $migrateStartup) {
    Push-Location -LiteralPath $installDir
    try {
        if ($mode -eq "exe") {
            New-Item -ItemType Directory -Path $startupDir -Force | Out-Null
            $startupFile = Join-Path $startupDir "CodexDesktopPet.vbs"
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
if (Test-Path -LiteralPath $legacyStartupFile) {
    Remove-Item -LiteralPath $legacyStartupFile -Force
}

if (-not $NoLaunch) {
    if ($mode -eq "exe") {
        Start-Process -FilePath $uiTarget -WorkingDirectory $installDir
    } else {
        Start-Process -FilePath $uiTarget -ArgumentList $uiArguments -WorkingDirectory $installDir
    }
}

Write-Host ""
Write-Host "Codex Desktop Pet installed." -ForegroundColor Green
Write-Host "Desktop shortcut: $shortcutPath"
Write-Host "Install folder:   $installDir"
Write-Host "Open /hooks in Codex once and trust 'Codex Desktop Pet status bridge'." -ForegroundColor Yellow
