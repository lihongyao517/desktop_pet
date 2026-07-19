param(
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$common = @("--noconfirm", "--onefile")
if (-not $NoClean) {
    $common += "--clean"
}

python -m PyInstaller @common --windowed --name CodexTrafficLight main.py
python -m PyInstaller @common --console --name CodexTrafficLightHook hook_main.py

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  $root\dist\CodexTrafficLight.exe"
Write-Host "  $root\dist\CodexTrafficLightHook.exe"

