$ErrorActionPreference = "Stop"
$installDir = Join-Path $env:LOCALAPPDATA "CodexDesktopPet"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Codex Desktop Pet.lnk"
$legacyDesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Codex Traffic Light.lnk"
$startupFile = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\CodexDesktopPet.vbs"
$legacyStartupFile = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\CodexTrafficLight.vbs"
$hookExe = Join-Path $installDir "CodexDesktopPetHook.exe"
$hookScript = Join-Path $installDir "hook_main.py"

if (Test-Path -LiteralPath $hookExe) {
    & $hookExe --uninstall-hooks | Out-Host
} elseif (Test-Path -LiteralPath $hookScript) {
    python $hookScript --uninstall-hooks | Out-Host
}

Get-Process -Name "CodexDesktopPet" -ErrorAction SilentlyContinue | Stop-Process -Force
foreach ($shortcut in ($desktopShortcut, $legacyDesktopShortcut)) {
    if (Test-Path -LiteralPath $shortcut) {
        Remove-Item -LiteralPath $shortcut -Force
    }
}
foreach ($startup in ($startupFile, $legacyStartupFile)) {
    if (Test-Path -LiteralPath $startup) {
        Remove-Item -LiteralPath $startup -Force
    }
}
if (Test-Path -LiteralPath $installDir) {
    $resolved = (Resolve-Path -LiteralPath $installDir).Path
    $localRoot = (Resolve-Path -LiteralPath $env:LOCALAPPDATA).Path
    if ($resolved.StartsWith($localRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    } else {
        throw "Refusing to remove path outside LOCALAPPDATA: $resolved"
    }
}

Write-Host "Codex Desktop Pet uninstalled." -ForegroundColor Green
