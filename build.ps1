param(
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

python tools\build_icon.py

$icon = Join-Path $root "assets\CodexDesktopPet.ico"
$common = @("--noconfirm", "--onefile", "--icon", $icon)
if (-not $NoClean) {
    $common += "--clean"
}

python -m PyInstaller @common --windowed --name CodexDesktopPet main.py
python -m PyInstaller @common --console --name CodexDesktopPetHook hook_main.py

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  $root\dist\CodexDesktopPet.exe"
Write-Host "  $root\dist\CodexDesktopPetHook.exe"
