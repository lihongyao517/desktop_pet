$ErrorActionPreference = "Stop"
$installDir = Join-Path $env:LOCALAPPDATA "CodexTrafficLight"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Codex Traffic Light.lnk"
$startupFile = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\CodexTrafficLight.vbs"
$hookExe = Join-Path $installDir "CodexTrafficLightHook.exe"
$hookScript = Join-Path $installDir "hook_main.py"

if (Test-Path -LiteralPath $hookExe) {
    & $hookExe --uninstall-hooks | Out-Host
} elseif (Test-Path -LiteralPath $hookScript) {
    python $hookScript --uninstall-hooks | Out-Host
}

Get-Process -Name "CodexTrafficLight" -ErrorAction SilentlyContinue | Stop-Process -Force
if (Test-Path -LiteralPath $desktopShortcut) {
    Remove-Item -LiteralPath $desktopShortcut -Force
}
if (Test-Path -LiteralPath $startupFile) {
    Remove-Item -LiteralPath $startupFile -Force
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

Write-Host "Codex Traffic Light uninstalled." -ForegroundColor Green

